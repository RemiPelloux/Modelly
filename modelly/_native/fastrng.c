/*
 * modelly._native.fastrng: random.Random's hot draws in C, on CPython's own
 * Mersenne Twister state.
 *
 * The type extends _random.Random and reads and advances the same state the
 * standard library uses (the RandomObject layout below), so random(),
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
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define MT_N 624
#define MT_M 397
#define MATRIX_A 0x9908b0dfU
#define UPPER_MASK 0x80000000U
#define LOWER_MASK 0x7fffffffU

/* CPython's Modules/_randommodule.c RandomObject, unchanged since 3.2. */
typedef struct {
    PyObject_HEAD
    int index;
    uint32_t state[MT_N];
} RandomObject;

static PyObject *py_randint = NULL;   /* random.Random.randint   */
static PyObject *py_choice = NULL;    /* random.Random.choice    */
static PyObject *py_shuffle = NULL;   /* random.Random.shuffle   */
static PyObject *py_randbelow = NULL; /* random.Random._randbelow_with_getrandbits */
static PyObject *py_sample = NULL;    /* random.Random.sample    */

#define SMALL_SET_SIZE 21        /* random.sample: small set minus empty list */
#define SAMPLE_SET_THRESHOLD 5   /* above this k the set size grows */

static inline uint32_t
genrand_uint32(RandomObject *self)
{
    uint32_t y;
    static const uint32_t mag01[2] = {0x0U, MATRIX_A};
    uint32_t *mt = self->state;
    if (self->index >= MT_N) {
        int kk;
        for (kk = 0; kk < MT_N - MT_M; kk++) {
            y = (mt[kk] & UPPER_MASK) | (mt[kk + 1] & LOWER_MASK);
            mt[kk] = mt[kk + MT_M] ^ (y >> 1) ^ mag01[y & 0x1U];
        }
        for (; kk < MT_N - 1; kk++) {
            y = (mt[kk] & UPPER_MASK) | (mt[kk + 1] & LOWER_MASK);
            mt[kk] = mt[kk + (MT_M - MT_N)] ^ (y >> 1) ^ mag01[y & 0x1U];
        }
        y = (mt[MT_N - 1] & UPPER_MASK) | (mt[0] & LOWER_MASK);
        mt[MT_N - 1] = mt[MT_M - 1] ^ (y >> 1) ^ mag01[y & 0x1U];
        self->index = 0;
    }
    y = mt[self->index++];
    y ^= (y >> 11);
    y ^= (y << 7) & 0x9d2c5680U;
    y ^= (y << 15) & 0xefc60000U;
    y ^= (y >> 18);
    return y;
}

/* _randbelow_with_getrandbits for 0 < n < 2**32: k = n.bit_length(),
 * then getrandbits(k) until below n; getrandbits(k <= 32) is the top k bits
 * of one word. */
static inline uint32_t
below32(RandomObject *self, uint32_t n)
{
    int k = 32 - __builtin_clz(n);
    uint32_t r = genrand_uint32(self) >> (32 - k);
    while (r >= n)
        r = genrand_uint32(self) >> (32 - k);
    return r;
}

static PyObject *
call_fallback(PyObject *func, PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    PyObject *stack[4];
    stack[0] = self;
    for (Py_ssize_t i = 0; i < nargs && i < 3; i++)
        stack[i + 1] = args[i];
    return PyObject_Vectorcall(func, stack, nargs + 1, NULL);
}

static PyObject *
fast_randbelow(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs == 1 && PyLong_CheckExact(args[0])) {
        int overflow;
        long long n = PyLong_AsLongLongAndOverflow(args[0], &overflow);
        if (!overflow && n > 0 && n < 4294967296LL)
            return PyLong_FromUnsignedLong(below32((RandomObject *)self, (uint32_t)n));
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
        if (!oa && !ob && b >= a && a > -(1LL << 62) && b < (1LL << 62)) {
            long long n = b - a + 1;
            if (n < 4294967296LL)
                return PyLong_FromLongLong(a + (long long)below32((RandomObject *)self, (uint32_t)n));
        }
    }
    return call_fallback(py_randint, self, args, nargs);
}

static PyObject *
fast_choice(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs == 1) {
        PyObject *seq = args[0];
        Py_ssize_t n;
        PyObject **items;
        if (PyList_CheckExact(seq)) {
            n = PyList_GET_SIZE(seq);
            items = ((PyListObject *)seq)->ob_item;
        }
        else if (PyTuple_CheckExact(seq)) {
            n = PyTuple_GET_SIZE(seq);
            items = ((PyTupleObject *)seq)->ob_item;
        }
        else {
            return call_fallback(py_choice, self, args, nargs);
        }
        if (n > 0 && n < 4294967296LL) {
            PyObject *item = items[below32((RandomObject *)self, (uint32_t)n)];
            return Py_NewRef(item);
        }
    }
    return call_fallback(py_choice, self, args, nargs);
}

static PyObject *
fast_shuffle(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs == 1 && PyList_CheckExact(args[0])) {
        PyListObject *list = (PyListObject *)args[0];
        Py_ssize_t n = PyList_GET_SIZE(list);
        if (n < 4294967296LL) {
            /* No Python code runs in this loop, so the list cannot change. */
            PyObject **items = list->ob_item;
            for (Py_ssize_t i = n - 1; i > 0; i--) {
                uint32_t j = below32((RandomObject *)self, (uint32_t)(i + 1));
                PyObject *tmp = items[i];
                items[i] = items[j];
                items[j] = tmp;
            }
            Py_RETURN_NONE;
        }
    }
    return call_fallback(py_shuffle, self, args, nargs);
}

/* random.Random.sample for a list or tuple and an int k, both code paths
 * reproduced draw for draw: a pool copy when n <= setsize, otherwise
 * rejection against the indices already selected. */
static PyObject *
sample_indices(RandomObject *self, PyObject **items, Py_ssize_t n, Py_ssize_t k)
{
    Py_ssize_t setsize = SMALL_SET_SIZE;
    if (k > SAMPLE_SET_THRESHOLD)
        /* 4 ** ceil(math.log(k * 3, 4)), with math.log's own double arithmetic */
        setsize += (Py_ssize_t)1 << (2 * (int)ceil(log((double)(k * 3)) / log(4.0)));
    PyObject *result = PyList_New(k);
    if (result == NULL)
        return NULL;
    PyObject **out = ((PyListObject *)result)->ob_item;
    if (n <= setsize) {
        PyObject **pool = PyMem_Malloc((size_t)(n > 0 ? n : 1) * sizeof(PyObject *));
        if (pool == NULL) {
            Py_DECREF(result);
            return PyErr_NoMemory();
        }
        memcpy(pool, items, (size_t)n * sizeof(PyObject *));
        for (Py_ssize_t i = 0; i < k; i++) {
            uint32_t j = below32(self, (uint32_t)(n - i));
            out[i] = Py_NewRef(pool[j]);
            pool[j] = pool[n - i - 1];
        }
        PyMem_Free(pool);
        return result;
    }
    unsigned char *seen = PyMem_Calloc((size_t)(n / 8 + 1), 1);
    if (seen == NULL) {
        Py_DECREF(result);
        return PyErr_NoMemory();
    }
    for (Py_ssize_t i = 0; i < k; i++) {
        uint32_t j = below32(self, (uint32_t)n);
        while (seen[j >> 3] & (1u << (j & 7)))
            j = below32(self, (uint32_t)n);
        seen[j >> 3] |= (unsigned char)(1u << (j & 7));
        out[i] = Py_NewRef(items[j]);
    }
    PyMem_Free(seen);
    return result;
}

static PyObject *
fast_sample(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    if (kwnames == NULL && nargs == 2 && PyLong_CheckExact(args[1])) {
        PyObject *pop = args[0];
        Py_ssize_t n = -1;
        PyObject **items = NULL;
        if (PyList_CheckExact(pop)) {
            n = PyList_GET_SIZE(pop);
            items = ((PyListObject *)pop)->ob_item;
        }
        else if (PyTuple_CheckExact(pop)) {
            n = PyTuple_GET_SIZE(pop);
            items = ((PyTupleObject *)pop)->ob_item;
        }
        int overflow;
        long long k = PyLong_AsLongLongAndOverflow(args[1], &overflow);
        if (n >= 0 && !overflow && n < 4294967296LL) {
            if (k < 0 || k > n) {
                PyErr_SetString(PyExc_ValueError, "Sample larger than population or is negative");
                return NULL;
            }
            return sample_indices((RandomObject *)self, items, n, (Py_ssize_t)k);
        }
    }
    PyObject *stack[3] = {self, nargs > 0 ? args[0] : NULL, nargs > 1 ? args[1] : NULL};
    Py_ssize_t total = nargs + (kwnames ? PyTuple_GET_SIZE(kwnames) : 0);
    if (total > 2) {
        /* rare: counts= or keyword k=; rebuild the call for the stdlib method */
        PyObject **full = PyMem_Malloc((size_t)(total + 1) * sizeof(PyObject *));
        if (full == NULL)
            return PyErr_NoMemory();
        full[0] = self;
        memcpy(full + 1, args, (size_t)total * sizeof(PyObject *));
        PyObject *res = PyObject_Vectorcall(py_sample, full, (size_t)nargs + 1, kwnames);
        PyMem_Free(full);
        return res;
    }
    if (kwnames != NULL) {
        PyObject *full[3] = {self, NULL, NULL};
        memcpy(full + 1, args, (size_t)total * sizeof(PyObject *));
        return PyObject_Vectorcall(py_sample, full, (size_t)nargs + 1, kwnames);
    }
    return PyObject_Vectorcall(py_sample, stack, (size_t)nargs + 1, NULL);
}

static PyObject *
set_fallbacks(PyObject *Py_UNUSED(module), PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs != 5) {
        PyErr_SetString(PyExc_TypeError, "set_fallbacks(randint, choice, shuffle, randbelow, sample)");
        return NULL;
    }
    Py_XSETREF(py_randint, Py_NewRef(args[0]));
    Py_XSETREF(py_choice, Py_NewRef(args[1]));
    Py_XSETREF(py_shuffle, Py_NewRef(args[2]));
    Py_XSETREF(py_randbelow, Py_NewRef(args[3]));
    Py_XSETREF(py_sample, Py_NewRef(args[4]));
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

PyMODINIT_FUNC
PyInit_fastrng(void)
{
#ifdef Py_GIL_DISABLED
    /* The state is read and written without the base type's critical section. */
    PyErr_SetString(PyExc_ImportError, "fastrng is not built for free-threaded CPython");
    return NULL;
#endif
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
    if (core == NULL)
        return NULL;
    PyObject *module = PyModule_Create(&module_def);
    if (module == NULL) {
        Py_DECREF(core);
        return NULL;
    }
    if (PyModule_AddObject(module, "Core", core) < 0) {
        Py_DECREF(core);
        Py_DECREF(module);
        return NULL;
    }
    return module;
}
