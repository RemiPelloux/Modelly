/*
 * modelly._native.fastrng: random.Random's hot draws in C, on CPython's own
 * Mersenne Twister state.
 *
 * The type extends _random.Random and reads and advances the same state the
 * standard library uses (the RandomObject layout in mtdraws.h), so random(),
 * getrandbits(), seed() and getstate() from the base class and the methods
 * here consume one stream, exactly as random.Random does. Python checks the
 * layout and the stream against the standard library at import and falls
 * back to the pure-Python FastRandom on any mismatch.
 *
 * Everything outside the fast paths (big ranges, non-int arguments, sequences
 * that are not lists or tuples) is delegated to the standard library's own
 * Python implementation, which draws from the same state.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdlib.h>

#include "ftcompat.h" /* critical sections before 3.13, DECLARE_NO_GIL */
#include "mtdraws.h"  /* RandomObject, below32, sample_indices */

/* The standard library's methods, used outside the fast paths. Set once at import,
 * before any instance exists (a free-threaded build refuses a second call). */
static PyObject *py_randint = NULL;   /* random.Random.randint   */
static PyObject *py_choice = NULL;    /* random.Random.choice    */
static PyObject *py_shuffle = NULL;   /* random.Random.shuffle   */
static PyObject *py_randbelow = NULL; /* random.Random._randbelow_with_getrandbits */
static PyObject *py_sample = NULL;    /* random.Random.sample    */
#define FALLBACK_COUNT 5

/*
 * Free-threaded builds: every draw holds the generator's critical section, as
 * _random.Random's own methods do, so the two never interleave on one state;
 * a list being read is locked with it (Py_BEGIN_CRITICAL_SECTION2).
 */

static PyObject *
call_fallback(PyObject *func, PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    PyObject *stack[4];
    stack[0] = self;
    for (Py_ssize_t i = 0; i < nargs && i < 3; i++)
        stack[i + 1] = args[i];
    return PyObject_Vectorcall(func, stack, nargs + 1, NULL);
}

/* below32 under the generator's lock. */
static uint32_t
locked_below(PyObject *self, uint32_t n)
{
    uint32_t r;
    Py_BEGIN_CRITICAL_SECTION(self);
    r = below32((RandomObject *)self, n);
    Py_END_CRITICAL_SECTION();
    return r;
}

static PyObject *
fast_randbelow(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs == 1 && PyLong_CheckExact(args[0])) {
        int overflow;
        long long n = PyLong_AsLongLongAndOverflow(args[0], &overflow);
        if (!overflow && n > 0 && n < WORD_RANGE)
            return PyLong_FromUnsignedLong(locked_below(self, (uint32_t)n));
    }
    return call_fallback(py_randbelow, self, args, nargs);
}

static PyObject *
fast_randint(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs == 2 && PyLong_CheckExact(args[0]) && PyLong_CheckExact(args[1])) {
        int oa, ob;
        long long a = PyLong_AsLongLongAndOverflow(args[0], &oa);
        long long b = PyLong_AsLongLongAndOverflow(args[1], &ob);
        if (!oa && !ob && b >= a && a > -INT_BOUND && b < INT_BOUND) {
            long long n = b - a + 1;
            if (n < WORD_RANGE)
                return PyLong_FromLongLong(a + (long long)locked_below(self, (uint32_t)n));
        }
    }
    return call_fallback(py_randint, self, args, nargs);
}

/* One item of a non-empty list or tuple, NULL (no error) when the fast path does not apply. */
static PyObject *
choose(PyObject *self, PyObject *seq)
{
    PyObject *item = NULL;
    Py_BEGIN_CRITICAL_SECTION2(self, seq);
    Py_ssize_t n = PySequence_Fast_GET_SIZE(seq);
    if (n > 0 && n < WORD_RANGE)
        item = Py_NewRef(PySequence_Fast_ITEMS(seq)[below32((RandomObject *)self, (uint32_t)n)]);
    Py_END_CRITICAL_SECTION2();
    return item;
}

static PyObject *
fast_choice(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs == 1 && (PyList_CheckExact(args[0]) || PyTuple_CheckExact(args[0]))) {
        PyObject *item = choose(self, args[0]);
        if (item != NULL)
            return item;
    }
    return call_fallback(py_choice, self, args, nargs);
}

static PyObject *
fast_shuffle(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs != 1 || !PyList_CheckExact(args[0]) || PyList_GET_SIZE(args[0]) >= WORD_RANGE)
        return call_fallback(py_shuffle, self, args, nargs);
    PyObject *list = args[0];
    Py_BEGIN_CRITICAL_SECTION2(self, list);
    /* No Python code runs in this loop, so the list cannot change. */
    PyObject **items = ((PyListObject *)list)->ob_item;
    for (Py_ssize_t i = PyList_GET_SIZE(list) - 1; i > 0; i--) {
        uint32_t j = below32((RandomObject *)self, (uint32_t)(i + 1));
        PyObject *tmp = items[i];
        items[i] = items[j];
        items[j] = tmp;
    }
    Py_END_CRITICAL_SECTION2();
    Py_RETURN_NONE;
}

/* sample(pop, k) for a list or tuple: a list, NULL with an error, or NULL without one
 * when the fast path does not apply. */
static PyObject *
sample_fast(PyObject *self, PyObject *pop, long long k)
{
    PyObject *result = NULL;
    Py_BEGIN_CRITICAL_SECTION2(self, pop);
    Py_ssize_t n = PySequence_Fast_GET_SIZE(pop);
    if (n < WORD_RANGE && (k < 0 || k > n))
        PyErr_SetString(PyExc_ValueError, "Sample larger than population or is negative");
    else if (n < WORD_RANGE)
        result = sample_indices((RandomObject *)self, PySequence_Fast_ITEMS(pop), n, (Py_ssize_t)k);
    Py_END_CRITICAL_SECTION2();
    return result;
}

/* The stdlib sample with the original arguments (counts= or a keyword k=). */
static PyObject *
sample_fallback(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    Py_ssize_t total = nargs + (kwnames ? PyTuple_GET_SIZE(kwnames) : 0);
    PyObject **full = PyMem_Malloc((size_t)(total + 1) * sizeof(PyObject *));
    if (full == NULL)
        return PyErr_NoMemory();
    full[0] = self;
    memcpy(full + 1, args, (size_t)total * sizeof(PyObject *));
    PyObject *res = PyObject_Vectorcall(py_sample, full, (size_t)nargs + 1, kwnames);
    PyMem_Free(full);
    return res;
}

static PyObject *
fast_sample(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    if (kwnames == NULL && nargs == 2 && PyLong_CheckExact(args[1])
        && (PyList_CheckExact(args[0]) || PyTuple_CheckExact(args[0]))) {
        int overflow;
        long long k = PyLong_AsLongLongAndOverflow(args[1], &overflow);
        if (!overflow) {
            PyObject *result = sample_fast(self, args[0], k);
            if (result != NULL || PyErr_Occurred())
                return result;
        }
    }
    return sample_fallback(self, args, nargs, kwnames);
}

static PyObject *
set_fallbacks(PyObject *Py_UNUSED(module), PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs != FALLBACK_COUNT) {
        PyErr_SetString(PyExc_TypeError, "set_fallbacks(randint, choice, shuffle, randbelow, sample)");
        return NULL;
    }
#ifdef Py_GIL_DISABLED
    if (py_randint != NULL) { /* another thread may be calling through them */
        PyErr_SetString(PyExc_RuntimeError, "set_fallbacks runs once on a free-threaded build");
        return NULL;
    }
#endif
    PyObject **slots[] = {&py_randint, &py_choice, &py_shuffle, &py_randbelow, &py_sample};
    for (int i = 0; i < FALLBACK_COUNT; i++)
        Py_XSETREF(*slots[i], Py_NewRef(args[i]));
    Py_RETURN_NONE;
}

static PyMethodDef core_methods[] = {
    {"randint", (PyCFunction)(void (*)(void))fast_randint, METH_FASTCALL,
     "Random integer in [a, b], same stream as random.Random.randint."},
    {"choice", (PyCFunction)(void (*)(void))fast_choice, METH_FASTCALL,
     "Random element, same stream as random.Random.choice."},
    {"shuffle", (PyCFunction)(void (*)(void))fast_shuffle, METH_FASTCALL,
     "Shuffle in place, same stream as random.Random.shuffle."},
    {"_randbelow", (PyCFunction)(void (*)(void))fast_randbelow, METH_FASTCALL,
     "Random int in [0, n), same stream as random.Random._randbelow."},
    {"sample", (PyCFunction)(void (*)(void))fast_sample, METH_FASTCALL | METH_KEYWORDS,
     "k unique elements, same stream as random.Random.sample."},
    {NULL, NULL, 0, NULL},
};

static PyMethodDef module_methods[] = {
    {"set_fallbacks", (PyCFunction)(void (*)(void))set_fallbacks, METH_FASTCALL,
     "Register the standard library methods used outside the fast paths."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT, "fastrng",
    "random.Random's hot draws in C on CPython's own Mersenne Twister state.",
    -1, module_methods, NULL, NULL, NULL, NULL,
};

/* _random.Random, checked to have the RandomObject layout this module reads. */
static PyObject *
random_base(void)
{
    PyObject *random_mod = PyImport_ImportModule("_random");
    if (random_mod == NULL)
        return NULL;
    PyObject *base = PyObject_GetAttrString(random_mod, "Random");
    Py_DECREF(random_mod);
    if (base == NULL)
        return NULL;
    if (!PyType_Check(base) || ((PyTypeObject *)base)->tp_basicsize != (Py_ssize_t)sizeof(RandomObject)) {
        Py_DECREF(base);
        PyErr_SetString(PyExc_ImportError, "_random.Random layout differs from the one fastrng was built for");
        return NULL;
    }
    return base;
}

/* The Core type: _random.Random plus the fast methods. */
static PyObject *
core_type(void)
{
    PyObject *base = random_base();
    if (base == NULL)
        return NULL;
    PyType_Slot slots[] = {
        {Py_tp_methods, core_methods},
        {Py_tp_doc, "random.Random's hot draws in C; subclass together with random.Random."},
        {0, NULL},
    };
    PyType_Spec spec = {
        "modelly._native.fastrng.Core", (int)sizeof(RandomObject), 0,
        Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, slots,
    };
    PyObject *core = PyType_FromSpecWithBases(&spec, base);
    Py_DECREF(base);
    return core;
}

PyMODINIT_FUNC
PyInit_fastrng(void)
{
    PyObject *core = core_type();
    PyObject *module = core == NULL ? NULL : PyModule_Create(&module_def);
    if (module != NULL && (PyModule_AddObjectRef(module, "Core", core) < 0
                           || DECLARE_NO_GIL(module) < 0))
        Py_CLEAR(module);
    Py_XDECREF(core);
    return module;
}
