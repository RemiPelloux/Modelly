/*
 * modelly._native: fastrng.c's random.Random.sample and choices, on CPython's own
 * Mersenne Twister state (mtdraws.h). The population (a list or tuple) and k are
 * accepted as ``f(population, k)`` or ``f(population, k=k)``; any other call goes to
 * the standard library's method, which draws from the same state.
 *
 * Included by fastrng.c after its fallback slots (py_sample).
 */
#ifndef MODELLY_RNGSAMPLE_H
#define MODELLY_RNGSAMPLE_H

/* Set at import: random.Random.choices, _random.Random.random (what choices draws with
 * unless a subclass overrides it) and the interned names "k" and "random". */
static PyObject *py_choices = NULL, *base_random = NULL, *str_k = NULL, *str_random = NULL;
#define STACK_ARGS 8 /* a fallback call with fewer arguments passes them from the stack */

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

/* ``func(self, *args, **kwargs)`` with the original vectorcall arguments. */
static PyObject *
call_fallback_kw(PyObject *func, PyObject *self, PyObject *const *args, Py_ssize_t nargs,
                 PyObject *kwnames)
{
    Py_ssize_t total = nargs + (kwnames ? PyTuple_GET_SIZE(kwnames) : 0);
    PyObject *small[STACK_ARGS];
    PyObject **full = total < STACK_ARGS ? small
                                         : PyMem_Malloc((size_t)(total + 1) * sizeof(PyObject *));
    if (full == NULL)
        return PyErr_NoMemory();
    full[0] = self;
    memcpy(full + 1, args, (size_t)total * sizeof(PyObject *));
    PyObject *res = PyObject_Vectorcall(func, full, (size_t)nargs + 1, kwnames);
    if (full != small)
        PyMem_Free(full);
    return res;
}

/* The ``k`` of a call ``f(population, k)`` or ``f(population, k=k)`` with a list or tuple
 * population, as a C number: 1 when it is an int in range, 0 when the fast path does not apply. */
static int
k_argument(PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames, long long *k)
{
    Py_ssize_t nkw = kwnames ? PyTuple_GET_SIZE(kwnames) : 0;
    if (nargs < 1 || nargs + nkw != 2 || !(PyList_CheckExact(args[0]) || PyTuple_CheckExact(args[0])))
        return 0;
    if (nkw == 1) {
        PyObject *name = PyTuple_GET_ITEM(kwnames, 0); /* a str, as vectorcall guarantees */
        if (name != str_k && PyUnicode_Compare(name, str_k) != 0)
            return 0;
    }
    if (!PyLong_CheckExact(args[1]))
        return 0;
    int overflow;
    *k = PyLong_AsLongLongAndOverflow(args[1], &overflow);
    return !overflow;
}

static PyObject *
fast_sample(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    long long k;
    if (k_argument(args, nargs, kwnames, &k)) {
        PyObject *result = sample_fast(self, args[0], k);
        if (result != NULL || PyErr_Occurred())
            return result;
    }
    return call_fallback_kw(py_sample, self, args, nargs, kwnames);
}

/* choices(pop, k=k) for a list or tuple: a list, NULL with an error, or NULL without one
 * when the fast path does not apply (an empty population). */
static PyObject *
choices_fast(PyObject *self, PyObject *pop, long long k)
{
    if (k > PY_SSIZE_T_MAX)
        return NULL;
    PyObject *result = PyList_New(k > 0 ? (Py_ssize_t)k : 0);
    if (result == NULL)
        return NULL;
    int rc;
    Py_BEGIN_CRITICAL_SECTION2(self, pop);
    Py_ssize_t n = PySequence_Fast_GET_SIZE(pop);
    rc = n == 0 ? 1
                : choices_uniform((RandomObject *)self, PySequence_Fast_ITEMS(pop), n,
                                  PyList_GET_SIZE(result), ((PyListObject *)result)->ob_item);
    Py_END_CRITICAL_SECTION2();
    if (rc < 0) /* as the standard library's ``population[n]`` */
        PyErr_Format(PyExc_IndexError, "%s index out of range", PyList_Check(pop) ? "list" : "tuple");
    if (rc != 0)
        Py_CLEAR(result); /* the unset items are NULL, which list dealloc skips */
    return result;
}

/* Whether ``type(self).random`` is _random.Random.random, which choices_fast draws as. */
static int
draws_base_random(PyObject *self)
{
    PyObject *method = PyObject_GetAttr((PyObject *)Py_TYPE(self), str_random);
    Py_XDECREF(method); /* compared by address only */
    if (method == NULL)
        PyErr_Clear();
    return method != NULL && method == base_random;
}

static PyObject *
fast_choices(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    long long k = 1;
    int plain = nargs == 1 && kwnames == NULL
                && (PyList_CheckExact(args[0]) || PyTuple_CheckExact(args[0]));
    if ((plain || k_argument(args, nargs, kwnames, &k)) && nargs == 1 && draws_base_random(self)) {
        PyObject *result = choices_fast(self, args[0], k);
        if (result != NULL || PyErr_Occurred())
            return result;
    }
    return call_fallback_kw(py_choices, self, args, nargs, kwnames);
}

/* What fast_choices needs: random.Random.choices, ``base.random`` (``base`` is
 * _random.Random) and two names. -1 on error. */
static int
choices_init(PyObject *base)
{
    PyObject *random_mod = PyImport_ImportModule("random");
    PyObject *cls = random_mod == NULL ? NULL : PyObject_GetAttrString(random_mod, "Random");
    py_choices = cls == NULL ? NULL : PyObject_GetAttrString(cls, "choices");
    base_random = base == NULL ? NULL : PyObject_GetAttrString(base, "random");
    str_k = PyUnicode_InternFromString("k");
    str_random = PyUnicode_InternFromString("random");
    Py_XDECREF(random_mod);
    Py_XDECREF(cls);
    return py_choices && base_random && str_k && str_random ? 0 : -1;
}

#endif /* MODELLY_RNGSAMPLE_H */
