/*
 * modelly._native: one call per agent, ``getattr(agent, method)(*args, **kwargs)``
 * or ``method(agent, *args, **kwargs)``, as fastloop.c's loops make it.
 *
 * The argument vector is built once per loop: a spare slot (so callees may use
 * PY_VECTORCALL_ARGUMENTS_OFFSET), the agent, ``args``, then the keyword values,
 * with their names in one tuple. A method name is called through
 * PyObject_VectorcallMethod, which finds the method as getattr would without
 * building a bound method; the interpreter calls ``obj.name()`` the same way.
 *
 * Included by fastloop.c after <Python.h> and ftcompat.h.
 */
#ifndef MODELLY_AGENTCALL_H
#define MODELLY_AGENTCALL_H

#define SPARE_SLOTS 2 /* vec[0] for PY_VECTORCALL_ARGUMENTS_OFFSET, vec[1] the agent */

typedef struct {
    PyObject *method;   /* a str (a method name) or a callable; borrowed */
    PyObject *kwnames;  /* the keyword names, NULL when there are none; owned */
    PyObject **vec;     /* spare slot, agent, args (borrowed), keyword values (owned) */
    Py_ssize_t nargs;   /* positional arguments, the agent included */
    Py_ssize_t nkw;
    int by_name;
} call_t;

/* Take the keyword names and values of ``kwargs`` (a dict) into ``call``; -1 on error. */
static int
take_kwargs(call_t *call, PyObject *kwargs)
{
    PyObject *items = PyDict_Items(kwargs); /* one consistent snapshot, new references */
    if (items == NULL)
        return -1;
    call->nkw = PyList_GET_SIZE(items);
    call->kwnames = PyTuple_New(call->nkw);
    PyObject **values = PyMem_New(PyObject *, SPARE_SLOTS + call->nargs - 1 + call->nkw);
    if (call->kwnames == NULL || values == NULL) { /* call_release drops the names */
        if (values == NULL && !PyErr_Occurred())
            PyErr_NoMemory();
        PyMem_Free(values);
        Py_DECREF(items);
        call->nkw = 0;
        return -1;
    }
    call->vec = values;
    for (Py_ssize_t j = 0; j < call->nkw; j++) {
        PyObject *pair = PyList_GET_ITEM(items, j); /* ``items`` is ours alone */
        PyTuple_SET_ITEM(call->kwnames, j, Py_NewRef(PyTuple_GET_ITEM(pair, 0)));
        call->vec[SPARE_SLOTS + call->nargs - 1 + j] = Py_NewRef(PyTuple_GET_ITEM(pair, 1));
    }
    Py_DECREF(items);
    return 0;
}

/* Set up ``call`` for ``method`` with ``args`` (a tuple) and ``kwargs`` (a dict or NULL);
 * -1 on error. call_release() must follow either way. */
static int
call_init(call_t *call, PyObject *method, PyObject *args, PyObject *kwargs)
{
    *call = (call_t){method, NULL, NULL, PyTuple_GET_SIZE(args) + 1, 0, PyUnicode_Check(method)};
    if (kwargs != NULL && PyDict_Size(kwargs) > 0 && take_kwargs(call, kwargs) < 0)
        return -1;
    if (call->vec == NULL && (call->vec = PyMem_New(PyObject *, SPARE_SLOTS + call->nargs - 1)) == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    call->vec[0] = NULL;
    for (Py_ssize_t j = 0; j < call->nargs - 1; j++)
        call->vec[SPARE_SLOTS + j] = PyTuple_GET_ITEM(args, j); /* the caller keeps ``args`` */
    return 0;
}

static void
call_release(call_t *call)
{
    for (Py_ssize_t j = 0; call->vec != NULL && j < call->nkw; j++)
        Py_DECREF(call->vec[SPARE_SLOTS + call->nargs - 1 + j]);
    PyMem_Free(call->vec);
    Py_XDECREF(call->kwnames);
}

/* ``getattr(agent, method)(*args, **kwargs)`` or ``method(agent, *args, **kwargs)``. */
static inline PyObject *
call_agent(call_t *call, PyObject *agent)
{
    call->vec[1] = agent;
    size_t nargsf = (size_t)call->nargs | PY_VECTORCALL_ARGUMENTS_OFFSET;
    if (call->by_name)
        return PyObject_VectorcallMethod(call->method, call->vec + 1, nargsf, call->kwnames);
    return PyObject_Vectorcall(call->method, call->vec + 1, nargsf, call->kwnames);
}

#endif /* MODELLY_AGENTCALL_H */
