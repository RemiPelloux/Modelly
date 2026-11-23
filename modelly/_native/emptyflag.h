/*
 * modelly._native: ``cell.empty`` on a grid, in C.
 *
 * A grid backs ``cell.empty`` with its bool "empty" layer and, once it has one, tells
 * its index of empty cells (modelly/space/grid/base.py, _install_empty_accessor). Every
 * move that empties or fills a cell writes it, from set_cell's inline add and remove.
 * EmptyFlag(array, fallback) is a data descriptor doing what the Python property
 * ``fallback`` does: read or write the layer at ``cell.coordinate``, then call
 * ``cell._empties_index.set_empty(cell, value)`` when that is not None. It reads the
 * array's buffer directly when the coordinate is a tuple of in-range ints, one per
 * axis; anything else (another coordinate, a delete) goes to ``fallback``, so what
 * Python would raise is raised.
 *
 * Included by fastcell.c after ftcompat.h.
 */
#ifndef MODELLY_EMPTYFLAG_H
#define MODELLY_EMPTYFLAG_H

#include <stdint.h>

#define EMPTY_FLAG_MAX_AXES 8

static PyObject *str_empties_index, *str_set_empty;

typedef struct {
    PyObject_HEAD
    Py_buffer view;     /* the layer, writable bytes; holds a reference to the array */
    PyObject *fallback; /* the Python property doing the same, for every other case */
} emptyflag_t;

/* The byte of ``cell``'s coordinate in the layer, or NULL (no error set) when the
 * coordinate is not a tuple of in-range ints, one per axis. NULL with an error set
 * when reading ``coordinate`` failed. */
static char *
flag_at(emptyflag_t *self, PyObject *cell)
{
    PyObject *coordinate = PyObject_GetAttr(cell, str_coordinate);
    if (coordinate == NULL)
        return NULL;
    char *at = NULL;
    Py_ssize_t axes = self->view.ndim;
    if (PyTuple_CheckExact(coordinate) && PyTuple_GET_SIZE(coordinate) == axes) {
        at = (char *)self->view.buf;
        for (Py_ssize_t i = 0; i < axes && at != NULL; i++) {
            PyObject *item = PyTuple_GET_ITEM(coordinate, i);
            Py_ssize_t index = PyLong_CheckExact(item) ? PyLong_AsSsize_t(item) : -1;
            if (index == -1 && PyErr_Occurred())
                PyErr_Clear(); /* too large: the fallback raises what Python would */
            if (index < 0 || index >= self->view.shape[i])
                at = NULL;
            else
                at += index * self->view.strides[i];
        }
    }
    Py_DECREF(coordinate);
    return at;
}

/* ``cell._empties_index.set_empty(cell, value)`` unless the index is None. */
static int
tell_index(PyObject *cell, PyObject *value)
{
    PyObject *index = PyObject_GetAttr(cell, str_empties_index);
    if (index == NULL)
        return -1;
    int rc = 0;
    if (index != Py_None) {
        PyObject *args[] = {index, cell, value};
        PyObject *result = PyObject_VectorcallMethod(
            str_set_empty, args, 3 | PY_VECTORCALL_ARGUMENTS_OFFSET, NULL);
        rc = result == NULL ? -1 : 0;
        Py_XDECREF(result);
    }
    Py_DECREF(index);
    return rc;
}

static PyObject *
emptyflag_get(PyObject *op, PyObject *cell, PyObject *type)
{
    emptyflag_t *self = (emptyflag_t *)op;
    if (cell == NULL || cell == Py_None)
        return Py_NewRef(op); /* on the class, like a property */
    char *at = flag_at(self, cell);
    if (at != NULL)
        return PyBool_FromLong(*at != 0);
    if (PyErr_Occurred())
        return NULL;
    return Py_TYPE(self->fallback)->tp_descr_get(self->fallback, cell, type);
}

static int
emptyflag_set(PyObject *op, PyObject *cell, PyObject *value)
{
    emptyflag_t *self = (emptyflag_t *)op;
    char *at = value == NULL ? NULL : flag_at(self, cell);
    if (at == NULL) {
        if (PyErr_Occurred())
            return -1;
        return Py_TYPE(self->fallback)->tp_descr_set(self->fallback, cell, value);
    }
    int truth = PyObject_IsTrue(value);
    if (truth < 0)
        return -1;
    *at = (char)truth;
    return tell_index(cell, value);
}

/* EmptyFlag(array, fallback): ``array`` a writable bool array, ``fallback`` a property. */
static PyObject *
emptyflag_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    PyObject *array, *fallback;
    if (!PyArg_ParseTuple(args, "OO:EmptyFlag", &array, &fallback))
        return NULL;
    PyTypeObject *kind = Py_TYPE(fallback);
    if (kind->tp_descr_get == NULL || kind->tp_descr_set == NULL)
        return PyErr_Format(PyExc_TypeError, "EmptyFlag: the fallback must be a data descriptor");
    emptyflag_t *self = (emptyflag_t *)type->tp_alloc(type, 0);
    if (self == NULL)
        return NULL;
    if (PyObject_GetBuffer(array, &self->view, PyBUF_STRIDES | PyBUF_WRITABLE | PyBUF_FORMAT) < 0) {
        Py_DECREF(self);
        return NULL;
    }
    int bools = self->view.itemsize == 1 && self->view.format != NULL
                && strcmp(self->view.format, "?") == 0;
    if (!bools || self->view.ndim < 1 || self->view.ndim > EMPTY_FLAG_MAX_AXES) {
        Py_DECREF(self);
        return PyErr_Format(PyExc_TypeError, "EmptyFlag: a bool array of 1 to %d axes",
                            EMPTY_FLAG_MAX_AXES);
    }
    self->fallback = Py_NewRef(fallback);
    return (PyObject *)self;
}

static void
emptyflag_dealloc(PyObject *op)
{
    emptyflag_t *self = (emptyflag_t *)op;
    if (self->view.obj != NULL)
        PyBuffer_Release(&self->view);
    Py_XDECREF(self->fallback);
    Py_TYPE(op)->tp_free(op);
}

/* The property's own documentation, so help(Cell.empty) reads the same. */
static PyObject *
emptyflag_doc(PyObject *op, void *Py_UNUSED(closure))
{
    return PyObject_GetAttrString(((emptyflag_t *)op)->fallback, "__doc__");
}

static PyGetSetDef emptyflag_getset[] = {
    {"__doc__", emptyflag_doc, NULL, NULL, NULL},
    {NULL, NULL, NULL, NULL, NULL},
};

static PyType_Slot emptyflag_slots[] = {
    {Py_tp_new, emptyflag_new},
    {Py_tp_dealloc, emptyflag_dealloc},
    {Py_tp_descr_get, emptyflag_get},
    {Py_tp_descr_set, emptyflag_set},
    {Py_tp_getset, emptyflag_getset},
    {0, NULL},
};

static PyType_Spec emptyflag_spec = {
    "modelly._native.fastcell.EmptyFlag", sizeof(emptyflag_t), 0,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_IMMUTABLETYPE, emptyflag_slots,
};

/* Add EmptyFlag to ``module``; -1 on failure. */
static int
add_emptyflag(PyObject *module)
{
    str_empties_index = PyUnicode_InternFromString("_empties_index");
    str_set_empty = PyUnicode_InternFromString("set_empty");
    if (str_empties_index == NULL || str_set_empty == NULL)
        return -1;
    PyObject *type = PyType_FromSpec(&emptyflag_spec);
    if (type == NULL)
        return -1;
    int rc = PyModule_AddObjectRef(module, "EmptyFlag", type);
    Py_DECREF(type);
    return rc;
}

#endif /* MODELLY_EMPTYFLAG_H */
