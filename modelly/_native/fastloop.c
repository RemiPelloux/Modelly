/*
 * modelly._native.fastloop: the framework's per-agent and per-cell loops in C.
 *
 * Each function here does what a Python loop of modelly/_native/loops.py does,
 * which stays the fallback; they visit the same objects in the same order and
 * make the same calls, so a model gives the same results with or without this
 * module.
 *
 * - call_each / map_each: _HardKeyAgentSet.do / shuffle_do / map's
 *   "for agent in order: if agent in members: call"
 * - call_each_weak / map_each_weak: AgentSet.do / shuffle_do / map's
 *   "for r in order: if (agent := r()) is not None and r in refs: call"
 * - neighborhood: Cell._bfs_neighborhood's breadth-first walk
 *
 * Free-threaded builds: items are read as new references (item_or_end), and a
 * cell's connections dict is walked inside its critical section.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "ftcompat.h"
#include "agentcall.h" /* call_t, call_init, call_agent, call_release */

static PyObject *str_connections = NULL; /* "connections" */
static PyObject *str_agents = NULL;      /* "_agents"     */

/* ``r()``: 1 and a new reference when it gives an object, 0 when None (dead), -1 on error. */
static int
deref(PyObject *ref, PyObject **agent)
{
    if (PyWeakref_CheckRef(ref))
        return PyWeakref_GetRef(ref, agent);
    *agent = PyObject_CallNoArgs(ref); /* not a weakref: call it, as the twin does */
    if (*agent == NULL)
        return -1;
    if (*agent != Py_None)
        return 1;
    Py_CLEAR(*agent);
    return 0;
}

/* The agent to call for ``item`` of the order, as a new reference in ``agent``: 1 to
 * call it, 0 to skip it, -1 on error. Strong: ``item in members``. Weak: ``item`` is a
 * ref, ``(agent := item()) is not None and item in members``. */
static int
member(PyObject *item, PyObject *members, int weak, PyObject **agent)
{
    *agent = NULL;
    int alive = weak ? deref(item, agent) : 1;
    if (alive > 0)
        alive = PyDict_Contains(members, item);
    if (alive > 0 && !weak)
        *agent = Py_NewRef(item);
    if (alive <= 0)
        Py_CLEAR(*agent);
    return alive;
}

/* Call on each member of ``order``, appending the results to ``results`` unless NULL. */
static int
each_member(call_t *call, PyObject *order, PyObject *members, int weak, PyObject *results)
{
    PyObject *item, *agent;
    for (Py_ssize_t i = 0; (item = item_or_end(order, i)) != NULL; i++) {
        int alive = member(item, members, weak, &agent);
        Py_DECREF(item);
        PyObject *result = alive > 0 ? call_agent(call, agent) : NULL;
        Py_XDECREF(agent);
        if (alive < 0 || (alive > 0 && result == NULL))
            return -1;
        int rc = result != NULL && results != NULL ? PyList_Append(results, result) : 0;
        Py_XDECREF(result);
        if (rc < 0)
            return -1;
    }
    return 0;
}

/* The shared body of the four loops: check the arguments, call, return None or the list. */
static PyObject *
run_loop(PyObject *const *argv, Py_ssize_t nargs, int weak, int collect, const char *usage)
{
    if (nargs != 5 || !PyList_CheckExact(argv[0]) || !PyDict_Check(argv[1])
        || !PyTuple_CheckExact(argv[3]) || (argv[4] != Py_None && !PyDict_Check(argv[4]))) {
        PyErr_SetString(PyExc_TypeError, usage);
        return NULL;
    }
    PyObject *results = NULL;
    if (collect && (results = PyList_New(0)) == NULL)
        return NULL;
    call_t call;
    int rc = call_init(&call, argv[2], argv[3], argv[4] == Py_None ? NULL : argv[4]);
    if (rc == 0)
        rc = each_member(&call, argv[0], argv[1], weak, results);
    call_release(&call);
    if (rc < 0) {
        Py_XDECREF(results);
        return NULL;
    }
    return collect ? results : Py_NewRef(Py_None);
}

#define LOOP(name, weak, collect, usage)                                                  \
    static PyObject *name(PyObject *Py_UNUSED(module), PyObject *const *argv, Py_ssize_t n) \
    {                                                                                     \
        return run_loop(argv, n, weak, collect, #name usage);                             \
    }

/*
 * call_each(order, members, method, args, kwargs) -> None
 *
 * For each agent of the list ``order`` that is still a key of the dict
 * ``members``: call ``getattr(agent, method)(*args, **kwargs)`` when method is
 * a str, else ``method(agent, *args, **kwargs)``. The membership test runs
 * before every call, so an agent removed by an earlier call is skipped.
 * map_each returns the results as a list; the _weak versions take a list of
 * weakrefs and their dict and dereference each ref just before its test.
 */
LOOP(call_each, 0, 0, "(order: list, members: dict, method, args: tuple, kwargs: dict|None)")
LOOP(map_each, 0, 1, "(order: list, members: dict, method, args: tuple, kwargs: dict|None)")
LOOP(call_each_weak, 1, 0, "(order: list, refs: dict, method, args: tuple, kwargs: dict|None)")
LOOP(map_each_weak, 1, 1, "(order: list, refs: dict, method, args: tuple, kwargs: dict|None)")


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

#ifdef Py_GIL_DISABLED
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
#else /* with the GIL: 1.2.0's loop, borrowed references, as fast as before */
/* Visit the connections of every cell in ``layer``; new cells go to ``next``. */
static int
expand(PyObject *reached, PyObject *layer, PyObject *next)
{
    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(layer); i++) {
        PyObject *links = PyObject_GetAttr(PyList_GET_ITEM(layer, i), str_connections);
        if (links == NULL)
            return -1;
        if (!PyDict_Check(links)) {
            Py_DECREF(links);
            PyErr_SetString(PyExc_TypeError, "cell.connections must be a dict");
            return -1;
        }
        Py_ssize_t pos = 0;
        PyObject *key, *neighbor;
        while (PyDict_Next(links, &pos, &key, &neighbor)) {
            int seen = PyDict_Contains(reached, neighbor);
            if (seen < 0 || (!seen && reach(reached, next, neighbor) < 0)) {
                Py_DECREF(links);
                return -1;
            }
        }
        Py_DECREF(links);
    }
    return 0;
}
#endif

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
    {"map_each", (PyCFunction)(void (*)(void))map_each, METH_FASTCALL,
     "call_each, returning the results as a list."},
    {"call_each_weak", (PyCFunction)(void (*)(void))call_each_weak, METH_FASTCALL,
     "Call method on the referent of each weakref of order that is alive and still in refs."},
    {"map_each_weak", (PyCFunction)(void (*)(void))map_each_weak, METH_FASTCALL,
     "call_each_weak, returning the results as a list."},
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
