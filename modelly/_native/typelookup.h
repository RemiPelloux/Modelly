/*
 * modelly._native: looking a name up on a type without running it, in the
 * public C API only (PyType_GetDict, 3.12+; PyMemberDescrObject is in the
 * cpython/ headers). Included by fastcell.c; needs <Python.h> first.
 */
#ifndef MODELLY_TYPELOOKUP_H
#define MODELLY_TYPELOOKUP_H

/* What _PyType_Lookup finds: ``name`` in the first class of the MRO that defines
 * it, no descriptor run. Borrowed (the class dict holds it); NULL when absent. */
static PyObject *
mro_lookup(PyTypeObject *type, PyObject *name)
{
    PyObject *mro = type->tp_mro, *found = NULL;
    Py_ssize_t size = mro != NULL ? PyTuple_GET_SIZE(mro) : 0;
    for (Py_ssize_t i = 0; i < size && found == NULL && !PyErr_Occurred(); i++) {
        PyObject *dict = PyType_GetDict((PyTypeObject *)PyTuple_GET_ITEM(mro, i));
        found = dict != NULL ? PyDict_GetItemWithError(dict, name) : NULL;
        Py_XDECREF(dict);
    }
    PyErr_Clear(); /* as in _PyType_Lookup, a failed lookup only means "not found" */
    return found;
}

/* Offset of the plain object slot ``name`` on ``type`` (its member descriptor's), else 0. */
static Py_ssize_t
slot_offset(PyTypeObject *type, PyObject *name)
{
    PyObject *descr = mro_lookup(type, name);
    if (descr == NULL || !Py_IS_TYPE(descr, &PyMemberDescr_Type))
        return 0;
    PyMemberDef *member = ((PyMemberDescrObject *)descr)->d_member;
    return member->type == Py_T_OBJECT_EX ? member->offset : 0;
}

#endif /* MODELLY_TYPELOOKUP_H */
