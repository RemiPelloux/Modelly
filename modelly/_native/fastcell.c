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
 *
 * Free-threaded builds: the type cache is per thread, bind() and its readers
 * share one lock, slots are read through getattr (which takes the object's
 * lock) and an exact list's remove runs list.remove itself.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "ftcompat.h"   /* item_or_end, THREAD_LOCAL, LOCK, relaxed loads */
#include "typelookup.h" /* mro_is, slot_offset */

#define LIST_REMOVE_MISSING "list.remove(x): x not in list" /* list.remove's own */

/* Interned attribute names, set at import (str_cell_slot is "_modelly_cell"). */
static PyObject *str_agents, *str_capacity, *str_coordinate, *str_empty, *str_append,
    *str_remove, *str_add_agent, *str_remove_agent, *str_cell_slot;

/* Set by bind(), under binding_lock: Cell.add_agent, Cell.remove_agent and their
 * exceptions, and a count of the binds, which tells every thread to relearn. */
#define BOUND_COUNT 4
static PyObject *ref_add, *ref_remove, *exc_full, *exc_missing;
static unsigned int generation = 1;
DECLARE_LOCK(binding_lock);

/* What one cell type resolves; valid while ``type`` keeps ``version`` and no bind
 * happened since ``generation``. */
typedef struct {
    PyTypeObject *type; /* compared by address only, together with version */
    unsigned int version, generation;
    int inline_add, inline_remove;
    Py_ssize_t agents_at, capacity_at; /* slot offsets, 0: use getattr */
} layout_t;

/* One per thread on a free-threaded build, so no thread sees another's half-written entry. */
static THREAD_LOCAL layout_t cached = {NULL, 0, 0, 0, 0, 0, 0};

/* A new reference to one of the bound objects, read under the lock. */
static PyObject *
bound(PyObject **slot)
{
    LOCK(binding_lock);
    PyObject *value = Py_XNewRef(*slot);
    UNLOCK(binding_lock);
    return value;
}

/* Fill ``out`` for ``type``. Inline only for dict-less, generically accessed types. On a
 * free-threaded build slots are read through getattr, which takes the object's lock. */
static void
learn(PyTypeObject *type, layout_t *out)
{
    int plain = type->tp_dictoffset == 0 && !(type->tp_flags & Py_TPFLAGS_MANAGED_DICT)
                && type->tp_getattro == PyObject_GenericGetAttr;
#ifdef Py_GIL_DISABLED
    int by_offset = 0;
#else
    int by_offset = plain;
#endif
    out->type = type;
    out->version = PyUnstable_Type_AssignVersionTag(type) ? LOAD_RELAXED_U32(&type->tp_version_tag) : 0;
    PyObject *add = bound(&ref_add), *remove = bound(&ref_remove);
    out->generation = LOAD_RELAXED_U32(&generation);
    out->inline_add = plain && add != NULL && mro_is(type, str_add_agent, add);
    out->inline_remove = plain && remove != NULL && mro_is(type, str_remove_agent, remove);
    Py_XDECREF(add);
    Py_XDECREF(remove);
    out->agents_at = by_offset ? slot_offset(type, str_agents) : 0;
    out->capacity_at = by_offset ? slot_offset(type, str_capacity) : 0;
}

/* The layout of ``cell``'s type, relearned when the type, its version or the binding changed. */
static const layout_t *
layout_of(PyObject *cell)
{
    PyTypeObject *type = Py_TYPE(cell);
    if (cached.type != type || cached.version == 0
        || cached.version != LOAD_RELAXED_U32(&type->tp_version_tag)
        || cached.generation != LOAD_RELAXED_U32(&generation))
        learn(type, &cached);
    return &cached;
}
#include "cellbody.h" /* add_agent, remove_agent: Cell's own bodies, inline */

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
    if (nargs != BOUND_COUNT)
        return PyErr_Format(PyExc_TypeError,
                            "bind(add_agent, remove_agent, full_exception, missing_exception)");
    PyObject **slots[] = {&ref_add, &ref_remove, &exc_full, &exc_missing};
    PyObject *old[BOUND_COUNT];
    LOCK(binding_lock);
    for (int i = 0; i < BOUND_COUNT; i++) {
        old[i] = *slots[i];
        *slots[i] = Py_NewRef(argv[i]);
    }
    STORE_RELAXED_U32(&generation, generation + 1); /* every thread relearns every type */
    UNLOCK(binding_lock);
    for (int i = 0; i < BOUND_COUNT; i++)
        Py_XDECREF(old[i]); /* outside the lock: a finalizer may run Python code */
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
    PyObject *module = PyModule_Create(&module_def);
    if (module != NULL && DECLARE_NO_GIL(module) < 0)
        Py_CLEAR(module);
    return module;
}
