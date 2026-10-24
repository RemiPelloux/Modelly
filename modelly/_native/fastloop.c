/*
 * modelly._native.fastloop: the framework's per-agent and per-cell loops in C.
 *
 * Each function here is a line-for-line port of a Python loop that stays in
 * the source as the fallback (see modelly/_native/__init__.py); they visit the
 * same objects in the same order and make the same calls, so a model gives the
 * same results with or without this module.
 *
 * - call_each:  AgentSet.do / shuffle_do's "for agent in order: if alive: call"
 * - neighborhood: Cell._bfs_neighborhood's breadth-first walk
 *
 * Free-threaded builds: items are read as new references (item_or_end), and a
 * cell's connections dict is walked inside its critical section.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "ftcompat.h"

static PyObject *str_connections = NULL; /* "connections" */
static PyObject *str_agents = NULL;      /* "_agents"     */

/* One call's arguments: ``vec[1:]`` holds args' items, slot 0 is the agent's. */
typedef struct {
    PyObject *method, *args, *kwargs; /* kwargs NULL when there are none */
    PyObject **vec;
    Py_ssize_t extra;
    int by_name;
} call_t;

/* ``method(agent, *args, **kwargs)`` with keyword arguments. */
static PyObject *
call_with_kwargs(call_t *call, PyObject *agent)
{
    PyObject *full = PyTuple_New(call->extra + 1), *result = NULL;
    if (full != NULL) {
        PyTuple_SET_ITEM(full, 0, Py_NewRef(agent));
        for (Py_ssize_t j = 0; j < call->extra; j++)
            PyTuple_SET_ITEM(full, j + 1, Py_NewRef(call->vec[j + 1]));
        result = PyObject_Call(call->method, full, call->kwargs);
        Py_DECREF(full);
    }
    return result;
}

/* ``getattr(agent, method)(*args, **kwargs)`` or ``method(agent, *args, **kwargs)``. */
static PyObject *
call_agent(call_t *call, PyObject *agent)
{
    if (call->by_name) {
        PyObject *bound = PyObject_GetAttr(agent, call->method), *result = NULL;
        if (bound != NULL) {
            result = call->kwargs == NULL
                         ? PyObject_Vectorcall(bound, call->vec + 1, call->extra, NULL)
                         : PyObject_Call(bound, call->args, call->kwargs);
            Py_DECREF(bound);
        }
        return result;
    }
    if (call->kwargs != NULL)
        return call_with_kwargs(call, agent);
    call->vec[0] = agent;
    return PyObject_Vectorcall(call->method, call->vec, call->extra + 1, NULL);
}

/* Call on each agent of ``order`` still in ``members``; -1 at the first error. */
static int
call_members(call_t *call, PyObject *order, PyObject *members)
{
    PyObject *agent;
    for (Py_ssize_t i = 0; (agent = item_or_end(order, i)) != NULL; i++) {
        int alive = PyDict_Contains(members, agent);
        PyObject *result = alive > 0 ? call_agent(call, agent) : NULL;
        Py_DECREF(agent);
        if (alive < 0 || (alive > 0 && result == NULL))
            return -1;
        Py_XDECREF(result);
    }
    return 0;
}

/*
 * call_each(order, members, method, args, kwargs) -> None
 *
 * For each agent of the list ``order`` that is still a key of the dict
 * ``members``: call ``getattr(agent, method)(*args, **kwargs)`` when method is
 * a str, else ``method(agent, *args, **kwargs)``. The membership test runs
 * before every call, so an agent removed by an earlier call is skipped.
 */
static PyObject *
call_each(PyObject *Py_UNUSED(module), PyObject *const *argv, Py_ssize_t nargs)
{
    if (nargs != 5 || !PyList_CheckExact(argv[0]) || !PyDict_Check(argv[1])
        || !PyTuple_CheckExact(argv[3])) {
        PyErr_SetString(PyExc_TypeError,
                        "call_each(order: list, members: dict, method, args: tuple, kwargs: dict|None)");
        return NULL;
    }
    call_t call = {argv[2], argv[3], argv[4] == Py_None ? NULL : argv[4], NULL,
                   PyTuple_GET_SIZE(argv[3]), PyUnicode_Check(argv[2])};
    call.vec = PyMem_New(PyObject *, call.extra + 1); /* reused for every call */
    if (call.vec == NULL)
        return PyErr_NoMemory();
    for (Py_ssize_t j = 0; j < call.extra; j++)
        call.vec[j + 1] = PyTuple_GET_ITEM(call.args, j);
    int rc = call_members(&call, argv[0], argv[1]);
    PyMem_Free(call.vec);
    if (rc < 0)
        return NULL;
    Py_RETURN_NONE;
}

/* reached[cell] = cell._agents; append cell to frontier. -1 on error. */
static int
reach(PyObject *reached, PyObject *frontier, PyObject *cell)
{
    PyObject *agents = PyObject_GetAttr(cell, str_agents);
    if (agents == NULL)
        return -1;
    int rc = PyDict_SetItem(reached, cell, agents);
    Py_DECREF(agents);
    if (rc < 0)
        return -1;
    return PyList_Append(frontier, cell);
}

/* Reach every neighbor of the dict ``links`` not yet in ``reached``; -1 on error. */
static int
visit(PyObject *reached, PyObject *links, PyObject *next)
{
    int rc = 0;
    Py_ssize_t pos = 0;
    PyObject *key, *neighbor;
    Py_BEGIN_CRITICAL_SECTION(links);
    while (rc == 0 && PyDict_Next(links, &pos, &key, &neighbor)) {
        Py_INCREF(neighbor); /* reach() may run Python code (a property ``_agents``) */
        int seen = PyDict_Contains(reached, neighbor);
        rc = seen < 0 || (!seen && reach(reached, next, neighbor) < 0) ? -1 : 0;
        Py_DECREF(neighbor);
    }
    Py_END_CRITICAL_SECTION();
    return rc;
}

/* Visit the connections of every cell in ``layer``; new cells go to ``next``. */
static int
expand(PyObject *reached, PyObject *layer, PyObject *next)
{
    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(layer); i++) { /* ``layer`` is ours alone */
        PyObject *links = PyObject_GetAttr(PyList_GET_ITEM(layer, i), str_connections);
        if (links == NULL)
            return -1;
        int rc = PyDict_Check(links) ? visit(reached, links, next) : -1;
        if (!PyDict_Check(links))
            PyErr_SetString(PyExc_TypeError, "cell.connections must be a dict");
        Py_DECREF(links);
        if (rc < 0)
            return -1;
    }
    return 0;
}

/*
 * neighborhood(cell, radius) -> dict
 *
 * Every cell within ``radius`` hops of ``cell`` (itself excluded), mapped to
 * its ``_agents`` list, in breadth-first discovery order.
 */
static PyObject *
neighborhood(PyObject *Py_UNUSED(module), PyObject *const *argv, Py_ssize_t nargs)
{
    if (nargs != 2) {
        PyErr_SetString(PyExc_TypeError, "neighborhood(cell, radius)");
        return NULL;
    }
    PyObject *start = argv[0];
    Py_ssize_t radius = PyNumber_AsSsize_t(argv[1], PyExc_OverflowError); /* __index__, like range() */
    if (radius == -1 && PyErr_Occurred())
        return NULL;
    PyObject *reached = PyDict_New();
    PyObject *layer = PyList_New(0);
    PyObject *own = PyObject_GetAttr(start, str_agents);
    if (reached == NULL || layer == NULL || own == NULL
        || PyDict_SetItem(reached, start, own) < 0)
        goto fail;
    Py_CLEAR(own);

    PyObject *seed = PyList_New(1);
    if (seed == NULL)
        goto fail;
    PyList_SET_ITEM(seed, 0, Py_NewRef(start));
    int rc = expand(reached, seed, layer);
    Py_DECREF(seed);
    if (rc < 0)
        goto fail;

    for (Py_ssize_t hop = 1; hop < radius && PyList_GET_SIZE(layer) > 0; hop++) {
        PyObject *next = PyList_New(0);
        if (next == NULL || expand(reached, layer, next) < 0) {
            Py_XDECREF(next);
            goto fail;
        }
        Py_SETREF(layer, next);
    }
    Py_DECREF(layer);
    if (PyDict_DelItem(reached, start) < 0) {
        Py_DECREF(reached);
        return NULL;
    }
    return reached;

fail:
    Py_XDECREF(own);
    Py_XDECREF(layer);
    Py_XDECREF(reached);
    return NULL;
}

static PyMethodDef module_methods[] = {
    {"call_each", (PyCFunction)(void (*)(void))call_each, METH_FASTCALL,
     "Call method on each agent of order that is still in members."},
    {"neighborhood", (PyCFunction)(void (*)(void))neighborhood, METH_FASTCALL,
     "Cells within radius hops of cell, mapped to their agent lists, BFS order."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT, "fastloop",
    "The framework's per-agent and per-cell loops in C.",
    -1, module_methods, NULL, NULL, NULL, NULL,
};

PyMODINIT_FUNC
PyInit_fastloop(void)
{
    str_connections = PyUnicode_InternFromString("connections");
    str_agents = PyUnicode_InternFromString("_agents");
    if (str_connections == NULL || str_agents == NULL)
        return NULL;
    PyObject *module = PyModule_Create(&module_def);
    if (module != NULL && DECLARE_NO_GIL(module) < 0)
        Py_CLEAR(module);
    return module;
}
