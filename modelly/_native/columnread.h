/*
 * modelly._native: ``getattr(agent, name)`` for a Column attribute without calling
 * its Python getter, for fastset.c's attr_values (AgentSet.get, agg and the
 * DataCollector's attribute reporters).
 *
 * On an agent class a Column is a property whose getter, made by
 * modelly.core.column_access.column_property, carries its position in the
 * ``_modelly_column`` attribute and reads
 * ``agent._column_table._views[position][agent._column_row]``. column_get runs
 * those same reads in C, so it returns the very object the getter would; on any
 * error it calls getattr, which runs the getter and raises what it raises
 * (ColumnMissingError for a removed agent).
 *
 * A few agent types are cached per call, each with its column's position
 * (revalidated on the type's version tag, so a class changed meanwhile is looked
 * up again) and the view of the last table read; the views are dropped after
 * every plain getattr, which may run Python code that grows a table.
 *
 * Included by fastset.c after ftcompat.h and typelookup.h.
 */
#ifndef MODELLY_COLUMNREAD_H
#define MODELLY_COLUMNREAD_H

#define COLUMN_CACHE_SLOTS 8 /* agent types remembered per call; more are evicted in turn */

static PyObject *str_fget, *str_column_mark, *str_column_table, *str_column_row, *str_views;

typedef struct {
    PyTypeObject *type;     /* a new reference; NULL for a free slot */
    unsigned int version;   /* its version tag when learned; 0 means "look up every time" */
    Py_ssize_t position;    /* the column's index in its table's _views, or -1 */
    PyObject *table, *view; /* the last table read for this type and its view of the column */
} column_slot_t;

typedef struct {
    column_slot_t slots[COLUMN_CACHE_SLOTS];
    int next;      /* the slot a new type takes */
    int has_views; /* some slot holds a view */
} column_cache_t;

/* Drop the cached views (the types and positions stay). */
static void
forget_views(column_cache_t *cache)
{
    if (!cache->has_views)
        return;
    cache->has_views = 0;
    for (int i = 0; i < COLUMN_CACHE_SLOTS; i++) {
        Py_CLEAR(cache->slots[i].table);
        Py_CLEAR(cache->slots[i].view);
    }
}

/* Release everything the cache holds. */
static void
forget_columns(column_cache_t *cache)
{
    forget_views(cache);
    for (int i = 0; i < COLUMN_CACHE_SLOTS; i++)
        Py_CLEAR(cache->slots[i].type);
}

/* The position the Column property ``name`` of ``type`` reads, or -1 if it is something else. */
static Py_ssize_t
column_position(PyTypeObject *type, PyObject *name)
{
    if (type->tp_getattro != PyObject_GenericGetAttr)
        return -1; /* a custom __getattribute__ decides itself */
    PyObject *descr = mro_lookup(type, name), *fget = NULL, *mark = NULL;
    if (descr != NULL && Py_IS_TYPE(descr, &PyProperty_Type))
        fget = PyObject_GetAttr(descr, str_fget);
    if (fget != NULL && PyFunction_Check(fget))
        mark = PyObject_GetAttr(fget, str_column_mark);
    Py_ssize_t position = mark != NULL && PyLong_CheckExact(mark) ? PyLong_AsSsize_t(mark) : -1;
    Py_XDECREF(descr);
    Py_XDECREF(fget);
    Py_XDECREF(mark);
    PyErr_Clear(); /* not a Column property: getattr reads it */
    return position < 0 ? -1 : position;
}

/* The slot of ``type``, learned (or relearned after a class change) when needed. */
static column_slot_t *
type_slot(column_cache_t *cache, PyTypeObject *type, PyObject *name)
{
    column_slot_t *slot = NULL;
    for (int i = 0; i < COLUMN_CACHE_SLOTS && slot == NULL; i++)
        if (cache->slots[i].type == type)
            slot = &cache->slots[i];
    unsigned int version = LOAD_RELAXED_U32(&type->tp_version_tag);
    if (slot != NULL && slot->version != 0 && slot->version == version)
        return slot;
    if (slot == NULL) {
        slot = &cache->slots[cache->next];
        cache->next = (cache->next + 1) % COLUMN_CACHE_SLOTS;
    }
    Py_XSETREF(slot->type, (PyTypeObject *)Py_NewRef(type));
    slot->position = column_position(type, name);
    slot->version = PyUnstable_Type_AssignVersionTag(type) ? LOAD_RELAXED_U32(&type->tp_version_tag) : 0;
    Py_CLEAR(slot->table);
    Py_CLEAR(slot->view);
    return slot;
}

/* Cache ``table._views[position]`` in ``slot``; -1 on error. */
static int
learn_table(column_cache_t *cache, column_slot_t *slot, PyObject *table)
{
    PyObject *views = PyObject_GetAttr(table, str_views);
    PyObject *view = views == NULL ? NULL : PySequence_GetItem(views, slot->position);
    Py_XDECREF(views);
    if (view == NULL)
        return -1;
    Py_XSETREF(slot->table, Py_NewRef(table));
    Py_XSETREF(slot->view, view);
    cache->has_views = 1;
    return 0;
}

/* ``agent._column_table._views[position][agent._column_row]``; NULL on error. */
static PyObject *
read_column(PyObject *agent, column_cache_t *cache, column_slot_t *slot)
{
    PyObject *table = PyObject_GetAttr(agent, str_column_table), *row, *value = NULL;
    if (table == NULL)
        return NULL;
    int known = table == slot->table || learn_table(cache, slot, table) == 0;
    Py_DECREF(table);
    row = known ? PyObject_GetAttr(agent, str_column_row) : NULL;
    if (row != NULL)
        value = PyObject_GetItem(slot->view, row);
    Py_XDECREF(row);
    return value;
}

/* ``getattr(agent, name)``: a Column read in C, anything else (or any error) by getattr. */
static PyObject *
column_get(PyObject *agent, PyObject *name, column_cache_t *cache)
{
    column_slot_t *slot = type_slot(cache, Py_TYPE(agent), name);
    if (slot->position >= 0) {
        PyObject *value = read_column(agent, cache, slot);
        if (value != NULL)
            return value;
        PyErr_Clear(); /* the getter runs again below and raises its own error */
    }
    forget_views(cache); /* getattr may run Python code that grows a table */
    return PyObject_GetAttr(agent, name);
}

/* Intern the names column_get reads; -1 on error. */
static int
columnread_init(void)
{
    str_fget = PyUnicode_InternFromString("fget");
    str_column_mark = PyUnicode_InternFromString("_modelly_column");
    str_column_table = PyUnicode_InternFromString("_column_table");
    str_column_row = PyUnicode_InternFromString("_column_row");
    str_views = PyUnicode_InternFromString("_views");
    return str_fget && str_column_mark && str_column_table && str_column_row && str_views ? 0 : -1;
}

#endif /* MODELLY_COLUMNREAD_H */
