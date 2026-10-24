/*
 * modelly._native: what the C modules need to run the same on every CPython
 * they are built for, the GIL build (3.12+) and the free-threaded one (3.13t+).
 * Included after <Python.h>.
 *
 * - The 3.13 reference-returning accessors (PyList_GetItemRef, PyDict_GetItemRef,
 *   PyWeakref_GetRef), back-ported to 3.12 on the borrowed-reference calls.
 * - The per-object critical sections, empty blocks before 3.13 (as they are on
 *   every GIL build).
 * - THREAD_LOCAL and relaxed atomic loads, for state a free-threaded build keeps
 *   per thread or reads while another thread may write it. Compiler-specific
 *   spellings stay inside the #if blocks.
 */
#ifndef MODELLY_FTCOMPAT_H
#define MODELLY_FTCOMPAT_H

#if PY_VERSION_HEX < 0x030D0000
static inline PyObject *
PyList_GetItemRef(PyObject *list, Py_ssize_t index)
{
    PyObject *item = PyList_GetItem(list, index);
    return item != NULL ? Py_NewRef(item) : NULL;
}

/* 1 and a new reference when found, 0 when not, -1 on error. */
static inline int
PyDict_GetItemRef(PyObject *dict, PyObject *key, PyObject **result)
{
    PyObject *item = PyDict_GetItemWithError(dict, key);
    *result = item != NULL ? Py_NewRef(item) : NULL;
    return item != NULL ? 1 : (PyErr_Occurred() ? -1 : 0);
}

/* 1 and a new reference when alive, 0 and NULL when dead, -1 when not a weakref. */
static inline int
PyWeakref_GetRef(PyObject *ref, PyObject **result)
{
    PyObject *target = PyWeakref_GetObject(ref);
    *result = target != NULL && target != Py_None ? Py_NewRef(target) : NULL;
    return target == NULL ? -1 : *result != NULL;
}

#define Py_BEGIN_CRITICAL_SECTION(op) {
#define Py_END_CRITICAL_SECTION() }
#define Py_BEGIN_CRITICAL_SECTION2(a, b) {
#define Py_END_CRITICAL_SECTION2() }
#endif /* before 3.13 */

#ifdef Py_GIL_DISABLED
#if defined(_MSC_VER)
#include <intrin.h>
#define THREAD_LOCAL __declspec(thread)
#define LOAD_RELAXED_U32(ptr) ((unsigned int)__iso_volatile_load32((const volatile __int32 *)(ptr)))
#define STORE_RELAXED_U32(ptr, value) __iso_volatile_store32((volatile __int32 *)(ptr), (__int32)(value))
#else
#define THREAD_LOCAL _Thread_local
#define LOAD_RELAXED_U32(ptr) __atomic_load_n((ptr), __ATOMIC_RELAXED)
#define STORE_RELAXED_U32(ptr, value) __atomic_store_n((ptr), (value), __ATOMIC_RELAXED)
#endif
/* One lock for state that every thread shares and that changes rarely. */
#define DECLARE_LOCK(name) static PyMutex name = {0}
#define LOCK(name) PyMutex_Lock(&(name))
#define UNLOCK(name) PyMutex_Unlock(&(name))
/* Single-phase init: tell the interpreter not to turn the GIL back on for this module. */
#define DECLARE_NO_GIL(module) PyUnstable_Module_SetGIL((module), Py_MOD_GIL_NOT_USED)
#else
#define THREAD_LOCAL
#define LOAD_RELAXED_U32(ptr) (*(ptr))
#define STORE_RELAXED_U32(ptr, value) (*(ptr) = (value))
#define DECLARE_LOCK(name) typedef int name##_unused_lock
#define LOCK(name) ((void)0)
#define UNLOCK(name) ((void)0)
#define DECLARE_NO_GIL(module) 0
#endif /* Py_GIL_DISABLED */

/* ``list[index]`` as a new reference, or NULL with no error set once past the end.
 * Free-threaded: another thread may shrink the list between a length check and the
 * read, so the read checks the bounds itself; with the GIL nothing can, and the
 * inline macros are used. */
static inline PyObject *
item_or_end(PyObject *list, Py_ssize_t index)
{
#ifdef Py_GIL_DISABLED
    PyObject *item = PyList_GetItemRef(list, index);
    if (item == NULL)
        PyErr_Clear(); /* IndexError: the caller checked that ``list`` is a list */
    return item;
#else
    return index < PyList_GET_SIZE(list) ? Py_NewRef(PyList_GET_ITEM(list, index)) : NULL;
#endif
}

#endif /* MODELLY_FTCOMPAT_H */
