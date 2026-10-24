/*
 * modelly._native: looking a name up on a type without running it, in the
 * public C API only (PyType_GetDict, 3.12+; PyMemberDescrObject is in the
 * cpython/ headers). Included by fastcell.c after <Python.h> and ftcompat.h.
 *
 * Every object found is held by a new reference while it is used, so a class
 * changed by another thread of a free-threaded build cannot free it meanwhile.
 */
#ifndef MODELLY_TYPELOOKUP_H
#define MODELLY_TYPELOOKUP_H

/* ``type.__mro__`` as a new reference (NULL, no error, when it has none yet). */
static PyObject *
type_mro(PyTypeObject *type)
{
#ifdef Py_GIL_DISABLED
    static const char mro_name[] = "__mro__"; /* read through the type's lock */
    PyObject *mro = PyObject_GetAttrString((PyObject *)type, mro_name);
    if (mro == NULL)
        PyErr_Clear();
    else if (!PyTuple_Check(mro))
        Py_CLEAR(mro);
    return mro;
#else
    return Py_XNewRef(type->tp_mro);
#endif
}

/* What _PyType_Lookup finds: ``name`` in the first class of the MRO that defines
 * it, no descriptor run. A new reference; NULL, no error, when absent. */
static PyObject *
mro_lookup(PyTypeObject *type, PyObject *name)
{
    PyObject *mro = type_mro(type), *found = NULL;
    Py_ssize_t size = mro != NULL ? PyTuple_GET_SIZE(mro) : 0;
    for (Py_ssize_t i = 0; i < size && found == NULL && !PyErr_Occurred(); i++) {
        PyObject *dict = PyType_GetDict((PyTypeObject *)PyTuple_GET_ITEM(mro, i));
        if (dict != NULL)
            (void)PyDict_GetItemRef(dict, name, &found);
        Py_XDECREF(dict);
    }
    Py_XDECREF(mro);
    PyErr_Clear(); /* as in _PyType_Lookup, a failed lookup only means "not found" */
    return found;
}

/* Whether ``name`` resolves on ``type`` to the very object ``expected``. */
static int
mro_is(PyTypeObject *type, PyObject *name, PyObject *expected)
{
    PyObject *found = mro_lookup(type, name);
    Py_XDECREF(found); /* compared by address only */
    return found != NULL && found == expected;
}

/* Offset of the plain object slot ``name`` on ``type`` (its member descriptor's), else 0. */
static Py_ssize_t
slot_offset(PyTypeObject *type, PyObject *name)
{
    PyObject *descr = mro_lookup(type, name);
    Py_ssize_t offset = 0;
    if (descr != NULL && Py_IS_TYPE(descr, &PyMemberDescr_Type)) {
        PyMemberDef *member = ((PyMemberDescrObject *)descr)->d_member;
        offset = member->type == Py_T_OBJECT_EX ? member->offset : 0;
    }
    Py_XDECREF(descr);
    return offset;
}

#endif /* MODELLY_TYPELOOKUP_H */
