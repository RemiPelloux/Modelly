/*
 * modelly._native.fastcell: moving an agent between cells, in C.
 *
 * set_cell ports py_set_cell (modelly/_native/cells.py), HasCell.cell's setter.
 * When a cell's type resolves add_agent / remove_agent to Cell's own (handed
 * over by bind()), their bodies run inline, ported line by line from
 * modelly/space/cells/cell.py; any other method (an override, a patch) is
 * called. Same calls, same order, same exceptions; ``empty`` is written through
 * the attribute protocol, so a property-layer-backed ``empty`` still works.
 * The type check is cached per type and revalidated on its version tag (CPython
 * bumps it when the type or a base changes); ``_agents`` and ``capacity`` are
 * then read at their slot offsets, as the interpreter's specialised loads do.
 * Public C API only (PyUnstable_ is its unstable tier): see typelookup.h.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "typelookup.h" /* mro_lookup, slot_offset */

#define LIST_REMOVE_MISSING "list.remove(x): x not in list" /* list.remove's own */

/* Interned attribute names, set at import (str_cell_slot is "_modelly_cell"). */
static PyObject *str_agents, *str_capacity, *str_coordinate, *str_empty, *str_append,
    *str_remove, *str_add_agent, *str_remove_agent, *str_cell_slot;

/* Set by bind(): Cell.add_agent, Cell.remove_agent and their exceptions. */
static PyObject *ref_add, *ref_remove, *exc_full, *exc_missing;

/* What one cell type resolves; valid while ``type`` keeps ``version``. */
typedef struct {
    PyTypeObject *type; /* compared by address only, together with version */
    unsigned int version;
    int inline_add, inline_remove;
    Py_ssize_t agents_at, capacity_at; /* slot offsets, 0: use getattr */
} layout_t;

static layout_t cached = {NULL, 0, 0, 0, 0, 0};

/* Fill ``out`` for ``type``. Inline only for dict-less, generically accessed types. */
static void
learn(PyTypeObject *type, layout_t *out)
{
    int plain = type->tp_dictoffset == 0 && !(type->tp_flags & Py_TPFLAGS_MANAGED_DICT)
                && type->tp_getattro == PyObject_GenericGetAttr;
    out->type = type;
    out->version = PyUnstable_Type_AssignVersionTag(type) ? type->tp_version_tag : 0;
    out->inline_add = plain && ref_add != NULL && mro_lookup(type, str_add_agent) == ref_add;
    out->inline_remove = plain && ref_remove != NULL
                         && mro_lookup(type, str_remove_agent) == ref_remove;
    out->agents_at = plain ? slot_offset(type, str_agents) : 0;
    out->capacity_at = plain ? slot_offset(type, str_capacity) : 0;
}

/* The layout of ``cell``'s type, relearned when the type or its version changed. */
static const layout_t *
layout_of(PyObject *cell)
{
    PyTypeObject *type = Py_TYPE(cell);
    if (cached.type != type || cached.version == 0 || cached.version != type->tp_version_tag)
        learn(type, &cached);
    return &cached;
}

/* ``obj.<name>`` (new reference): read at ``offset`` when known and set. */
static PyObject *
read_slot(PyObject *obj, Py_ssize_t offset, PyObject *name)
{
    PyObject *value = offset > 0 ? *(PyObject **)((char *)obj + offset) : NULL;
    return value != NULL ? Py_NewRef(value) : PyObject_GetAttr(obj, name);
}

/* ``obj.name(arg)``, dropping the result; -1 on error. */
static int
call_method(PyObject *obj, PyObject *name, PyObject *arg)
{
    PyObject *result = PyObject_CallMethodOneArg(obj, name, arg);
    Py_XDECREF(result);
    return result == NULL ? -1 : 0;
}

/* ``len(occupants) >= limit`` unless limit is None: 1, 0, or -1 on error. */
static int
at_capacity(PyObject *occupants, PyObject *limit)
{
    if (limit == Py_None)
        return 0;
    Py_ssize_t size = PyObject_Size(occupants);
    if (size < 0)
        return -1;
    PyObject *count = PyLong_FromSsize_t(size);
    if (count == NULL)
        return -1;
    int full = PyObject_RichCompareBool(count, limit, Py_GE);
    Py_DECREF(count);
    return full;
}

/* ``raise CellFullException(cell.coordinate)`` */
static int
raise_full(PyObject *cell)
{
    PyObject *coordinate = PyObject_GetAttr(cell, str_coordinate);
    PyObject *exc = coordinate == NULL ? NULL : PyObject_CallOneArg(exc_full, coordinate);
    Py_XDECREF(coordinate);
    if (exc != NULL)
        PyErr_SetObject((PyObject *)Py_TYPE(exc), exc);
    Py_XDECREF(exc);
    return -1;
}

/* Cell.add_agent's capacity check, then ``occupants.append(agent)``. */
static int
check_and_append(PyObject *cell, const layout_t *layout, PyObject *occupants, PyObject *agent)
{
    PyObject *limit = read_slot(cell, layout->capacity_at, str_capacity);
    if (limit == NULL)
        return -1;
    int full = at_capacity(occupants, limit);
    Py_DECREF(limit);
    if (full != 0)
        return full < 0 ? -1 : raise_full(cell);
    if (PyList_CheckExact(occupants))
        return PyList_Append(occupants, agent);
    return call_method(occupants, str_append, agent);
}

/* Cell.add_agent: capacity check, append, ``empty = False`` on the 0 -> 1 transition. */
static int
add_agent(PyObject *cell, const layout_t *layout, PyObject *agent)
{
    PyObject *occupants = read_slot(cell, layout->agents_at, str_agents);
    if (occupants == NULL)
        return -1;
    Py_ssize_t size = -1;
    if (check_and_append(cell, layout, occupants, agent) == 0)
        size = PyObject_Size(occupants);
    Py_DECREF(occupants);
    if (size < 0)
        return -1;
    return size == 1 ? PyObject_SetAttr(cell, str_empty, Py_False) : 0;
}

/* ``occupants.remove(agent)``; an exact list is searched as list.remove does. */
static int
remove_from(PyObject *occupants, PyObject *agent)
{
    if (!PyList_CheckExact(occupants))
        return call_method(occupants, str_remove, agent);
    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(occupants); i++) {
        PyObject *item = Py_NewRef(PyList_GET_ITEM(occupants, i));
        int same = PyObject_RichCompareBool(item, agent, Py_EQ);
        Py_DECREF(item);
        if (same != 0)
            return same < 0 ? -1 : PyList_SetSlice(occupants, i, i + 1, NULL);
    }
    PyErr_SetString(PyExc_ValueError, LIST_REMOVE_MISSING);
    return -1;
}

/* ``except ValueError as e: raise AgentMissingException(agent, cell.coordinate) from e``;
 * e is made the handled exception meanwhile, so what is raised gets it as __context__. */
static int
raise_missing(PyObject *cell, PyObject *agent)
{
    if (!PyErr_ExceptionMatches(PyExc_ValueError))
        return -1;
    PyObject *cause = PyErr_GetRaisedException();
    PyObject *outer = PyErr_GetHandledException();
    PyErr_SetHandledException(cause);
    PyObject *coordinate = PyObject_GetAttr(cell, str_coordinate);
    PyObject *args[] = {agent, coordinate};
    PyObject *exc = coordinate == NULL ? NULL : PyObject_Vectorcall(exc_missing, args, 2, NULL);
    Py_XDECREF(coordinate);
    if (exc != NULL) {
        PyException_SetCause(exc, Py_NewRef(cause));
        PyErr_SetObject((PyObject *)Py_TYPE(exc), exc);
        Py_DECREF(exc);
    }
    PyErr_SetHandledException(outer);
    Py_XDECREF(outer);
    Py_DECREF(cause);
    return -1;
}

/* Cell.remove_agent: ``_agents.remove``, then ``empty = True`` once none are left. */
static int
remove_agent(PyObject *cell, const layout_t *layout, PyObject *agent)
{
    PyObject *occupants = read_slot(cell, layout->agents_at, str_agents);
    if (occupants == NULL)
        return -1;
    int rc = remove_from(occupants, agent);
    Py_DECREF(occupants);
    if (rc < 0)
        return raise_missing(cell, agent);
    occupants = read_slot(cell, layout->agents_at, str_agents);
    if (occupants == NULL)
        return -1;
    int left = PyObject_IsTrue(occupants);
    Py_DECREF(occupants);
    if (left < 0)
        return -1;
    return left ? 0 : PyObject_SetAttr(cell, str_empty, Py_True);
}

/* ``cell.add_agent(agent)`` or ``cell.remove_agent(agent)``, inline when Cell's own. */
static int
on_cell(PyObject *cell, PyObject *agent, int adding)
{
    const layout_t *layout = layout_of(cell);
    if (adding ? layout->inline_add : layout->inline_remove)
        return adding ? add_agent(cell, layout, agent) : remove_agent(cell, layout, agent);
    return call_method(cell, adding ? str_add_agent : str_remove_agent, agent);
}

/* set_cell(agent, cell) -> None: HasCell.cell's setter. No-op for the same cell; else
 * cell.add_agent(agent) and old.remove_agent(agent) (each unless None), then
 * agent._modelly_cell = cell. A failed add leaves everything unchanged. */
static PyObject *
set_cell(PyObject *Py_UNUSED(module), PyObject *const *argv, Py_ssize_t nargs)
{
    if (nargs != 2)
        return PyErr_Format(PyExc_TypeError, "set_cell(agent, cell)");
    PyObject *agent = argv[0], *cell = argv[1];
    PyObject *old = PyObject_GetAttr(agent, str_cell_slot);
    if (old == NULL)
        return NULL;
    int rc = 0;
    if (cell != old) {
        if (cell != Py_None)
            rc = on_cell(cell, agent, 1);
        if (rc == 0 && old != Py_None)
            rc = on_cell(old, agent, 0);
        if (rc == 0)
            rc = PyObject_SetAttr(agent, str_cell_slot, cell);
    }
    Py_DECREF(old);
    if (rc < 0)
        return NULL;
    Py_RETURN_NONE;
}

/* bind(add_agent, remove_agent, full_exception, missing_exception) -> None */
static PyObject *
bind(PyObject *Py_UNUSED(module), PyObject *const *argv, Py_ssize_t nargs)
{
    if (nargs != 4)
        return PyErr_Format(PyExc_TypeError,
                            "bind(add_agent, remove_agent, full_exception, missing_exception)");
    Py_XSETREF(ref_add, Py_NewRef(argv[0]));
    Py_XSETREF(ref_remove, Py_NewRef(argv[1]));
    Py_XSETREF(exc_full, Py_NewRef(argv[2]));
    Py_XSETREF(exc_missing, Py_NewRef(argv[3]));
    cached.type = NULL; /* relearn every type against the new references */
    Py_RETURN_NONE;
}

static PyMethodDef module_methods[] = {
    {"set_cell", (PyCFunction)(void (*)(void))set_cell, METH_FASTCALL,
     "Move agent to cell (None: out of its cell): add first, then remove."},
    {"bind", (PyCFunction)(void (*)(void))bind, METH_FASTCALL,
     "Set the add_agent/remove_agent that set_cell may run inline, and their exceptions."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT, "fastcell",
    "Moving an agent between cells, in C.",
    -1, module_methods, NULL, NULL, NULL, NULL,
};

PyMODINIT_FUNC
PyInit_fastcell(void)
{
#ifdef Py_GIL_DISABLED
    /* The type cache and slot reads assume the GIL; free-threaded builds use py_set_cell. */
    PyErr_SetString(PyExc_ImportError, "fastcell is not built for free-threaded CPython");
    return NULL;
#endif
    struct { PyObject **slot; const char *text; } names[] = {
        {&str_agents, "_agents"}, {&str_capacity, "capacity"},
        {&str_coordinate, "coordinate"}, {&str_empty, "empty"}, {&str_append, "append"},
        {&str_remove, "remove"}, {&str_add_agent, "add_agent"},
        {&str_remove_agent, "remove_agent"}, {&str_cell_slot, "_modelly_cell"},
    };
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); i++) {
        *names[i].slot = PyUnicode_InternFromString(names[i].text);
        if (*names[i].slot == NULL)
            return NULL;
    }
    return PyModule_Create(&module_def);
}
