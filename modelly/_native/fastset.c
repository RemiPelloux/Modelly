/*
 * modelly._native.fastset: the loops behind AgentSet.select, agg and get, in C.
 *
 * Each function ports one Python loop of modelly/_native/sets.py, which stays
 * the fallback; same objects visited in the same order, same calls, same
 * exceptions, so a model gives the same results with or without this module.
 *
 * - live_agents: AgentSet.to_list, the live referents of a dict of weakrefs
 * - make_refs:   AgentSet._make_refs, dict.fromkeys of one weakref per agent
 * - keep_type:   select's ``[a for a in agents if isinstance(a, agent_type)]``
 * - keep_if:     select's ``[a for a in agents if filter_func(a)]``
 * - attr_values: get / agg's ``list(map(operator.attrgetter(name), agents))``
 *
 * Every loop walks a list it owns or a reference it holds to each item
 * (item_or_end), so it is safe on a free-threaded build too.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "ftcompat.h"

static PyObject *str_dot = NULL; /* "." */

typedef int (*keep_test)(PyObject *item, PyObject *with);

/* Append to ``out`` each item of ``items`` for which test(item, with) is true. */
static PyObject *
keep_where(PyObject *items, PyObject *with, keep_test test)
{
    PyObject *out = PyList_New(0), *item;
    for (Py_ssize_t i = 0; out != NULL && (item = item_or_end(items, i)) != NULL; i++) {
        int keep = test(item, with);
        if (keep > 0 && PyList_Append(out, item) < 0)
            keep = -1;
        Py_DECREF(item);
        if (keep < 0)
            Py_CLEAR(out);
    }
    return out;
}

static int
is_instance(PyObject *item, PyObject *cls)
{
    return PyObject_IsInstance(item, cls);
}

static int
call_is_true(PyObject *item, PyObject *func)
{
    PyObject *result = PyObject_CallOneArg(func, item);
    if (result == NULL)
        return -1;
    int truth = PyObject_IsTrue(result);
    Py_DECREF(result);
    return truth;
}

static int
check_list(PyObject *const *argv, Py_ssize_t nargs, const char *usage)
{
    if (nargs == 2 && PyList_Check(argv[0]))
        return 0;
    PyErr_SetString(PyExc_TypeError, usage);
    return -1;
}

/* keep_type(agents: list, agent_type) -> list: the agents that are instances of agent_type. */
static PyObject *
keep_type(PyObject *Py_UNUSED(module), PyObject *const *argv, Py_ssize_t nargs)
{
    if (check_list(argv, nargs, "keep_type(agents: list, agent_type)") < 0)
        return NULL;
    return keep_where(argv[0], argv[1], is_instance);
}

/* keep_if(agents: list, filter_func) -> list: the agents for which filter_func is truthy. */
static PyObject *
keep_if(PyObject *Py_UNUSED(module), PyObject *const *argv, Py_ssize_t nargs)
{
    if (check_list(argv, nargs, "keep_if(agents: list, filter_func)") < 0)
        return NULL;
    return keep_where(argv[0], argv[1], call_is_true);
}

/* ``obj.a.b.c`` for parts ("a", "b", "c"), as operator.attrgetter("a.b.c") reads it. */
static PyObject *
dotted_get(PyObject *obj, PyObject *parts)
{
    PyObject *value = Py_NewRef(obj);
    for (Py_ssize_t i = 0; value != NULL && i < PyList_GET_SIZE(parts); i++)
        Py_SETREF(value, PyObject_GetAttr(value, PyList_GET_ITEM(parts, i)));
    return value;
}

/* attr_values(agents: list, name: str) -> list: ``list(map(operator.attrgetter(name), agents))``. */
static PyObject *
attr_values(PyObject *Py_UNUSED(module), PyObject *const *argv, Py_ssize_t nargs)
{
    if (check_list(argv, nargs, "attr_values(agents: list, name: str)") < 0)
        return NULL;
    if (!PyUnicode_Check(argv[1])) {
        PyErr_SetString(PyExc_TypeError, "attribute name must be a string");
        return NULL;
    }
    PyObject *agents = argv[0], *parts = PyUnicode_Split(argv[1], str_dot, -1);
    PyObject *out = parts == NULL ? NULL : PyList_New(0), *agent;
    for (Py_ssize_t i = 0; out != NULL && (agent = item_or_end(agents, i)) != NULL; i++) {
        PyObject *value = dotted_get(agent, parts);
        Py_DECREF(agent);
        if (value == NULL || PyList_Append(out, value) < 0)
            Py_CLEAR(out);
        Py_XDECREF(value);
    }
    Py_XDECREF(parts);
    return out;
}

/* r() for one key of the snapshot: a new reference, Py_None when dead, NULL on error. */
static PyObject *
deref(PyObject *ref)
{
    PyObject *target;
    if (PyWeakref_CheckRef(ref)) {
        if (PyWeakref_GetRef(ref, &target) < 0)
            return NULL;
        return target != NULL ? target : Py_NewRef(Py_None);
    }
    return PyObject_CallNoArgs(ref); /* not a weakref: call it, as the twin does */
}

/* live_agents(refs: dict) -> list: ``[a for r in list(refs) if (a := r()) is not None]``. */
static PyObject *
live_agents(PyObject *Py_UNUSED(module), PyObject *refs)
{
    if (!PyDict_Check(refs)) {
        PyErr_SetString(PyExc_TypeError, "live_agents(refs: dict)");
        return NULL;
    }
    PyObject *keys = PyDict_Keys(refs);
    PyObject *out = keys == NULL ? NULL : PyList_New(0);
    for (Py_ssize_t i = 0; out != NULL && i < PyList_GET_SIZE(keys); i++) {
        PyObject *agent = deref(PyList_GET_ITEM(keys, i)); /* ``keys`` is ours alone */
        if (agent == NULL || (agent != Py_None && PyList_Append(out, agent) < 0))
            Py_CLEAR(out);
        Py_XDECREF(agent);
    }
    Py_XDECREF(keys);
    return out;
}

/* Add ``ref(agent, callback)`` as a key of ``refs`` (value None); -1 on error. */
static int
add_ref(PyObject *refs, PyObject *agent, PyObject *callback)
{
    PyObject *ref = PyWeakref_NewRef(agent, callback);
    if (ref == NULL)
        return -1;
    int rc = PyDict_SetItem(refs, ref, Py_None); /* a repeated agent keeps its first ref */
    Py_DECREF(ref);
    return rc;
}

/* make_refs(agents: iterable, callback) -> dict: ``dict.fromkeys([ref(a, callback) for a in agents])``. */
static PyObject *
make_refs(PyObject *Py_UNUSED(module), PyObject *const *argv, Py_ssize_t nargs)
{
    if (nargs != 2) {
        PyErr_SetString(PyExc_TypeError, "make_refs(agents, callback)");
        return NULL;
    }
    PyObject *iter = PyObject_GetIter(argv[0]);
    PyObject *refs = iter == NULL ? NULL : PyDict_New();
    PyObject *agent;
    while (refs != NULL && (agent = PyIter_Next(iter)) != NULL) {
        if (add_ref(refs, agent, argv[1]) < 0)
            Py_CLEAR(refs);
        Py_DECREF(agent);
    }
    Py_XDECREF(iter);
    if (refs != NULL && PyErr_Occurred())
        Py_CLEAR(refs);
    return refs;
}

static PyMethodDef module_methods[] = {
    {"keep_type", (PyCFunction)(void (*)(void))keep_type, METH_FASTCALL,
     "The agents of a list that are instances of agent_type, in order."},
    {"keep_if", (PyCFunction)(void (*)(void))keep_if, METH_FASTCALL,
     "The agents of a list for which filter_func is truthy, in order."},
    {"attr_values", (PyCFunction)(void (*)(void))attr_values, METH_FASTCALL,
     "getattr(agent, name) for each agent of a list, in order."},
    {"live_agents", (PyCFunction)(void (*)(void))live_agents, METH_O,
     "The live referents of the weakref keys of a dict, in order."},
    {"make_refs", (PyCFunction)(void (*)(void))make_refs, METH_FASTCALL,
     "A dict keyed on one weakref (with callback) per agent, in order."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT, "fastset",
    "The loops behind AgentSet.select, agg and get, in C.",
    -1, module_methods, NULL, NULL, NULL, NULL,
};

PyMODINIT_FUNC
PyInit_fastset(void)
{
    str_dot = PyUnicode_InternFromString(".");
    if (str_dot == NULL)
        return NULL;
    PyObject *module = PyModule_Create(&module_def);
    if (module != NULL && DECLARE_NO_GIL(module) < 0)
        Py_CLEAR(module);
    return module;
}
