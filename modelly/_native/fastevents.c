/*
 * modelly._native.fastevents: the event list's binary heap, in C.
 *
 * EventHeap ports PyEventHeap of modelly/_native/events.py, which stays the
 * reference and the fallback: the same heapq steps on the same comparisons
 * (eventheap.h), so both keep the same array and pop the same events in the
 * same order; tests/native/test_events.py runs them side by side. The keys of an
 * event are read when it is pushed: its time and priority must not change while
 * it is on a list (they never could without breaking the heap).
 *
 * - push(event):    heapq.heappush
 * - pop():          EventList.pop_event, skipping canceled events
 * - pop_due(until): the next live event if its time is <= until, else None
 * - compact(), clear(), events(), len(), ``in``, and the ``canceled`` count
 *
 * Free-threaded builds: every method holds the heap's critical section. A
 * comparison or CANCELED property that calls back into the same heap gets
 * RuntimeError, since the array has a hole while it is being sifted.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stddef.h> /* offsetof */

#include "ftcompat.h"
#include "eventheap.h" /* entry_t, heap_t, the keys, the heapq steps */
#include "eventops.h"  /* push_impl, pop_impl, pop_due_impl, compact_impl, ... */

/* Run ``call`` inside the heap's critical section and return its result. */
#define LOCKED(h, call)                \
    PyObject *result;                  \
    Py_BEGIN_CRITICAL_SECTION(h);      \
    result = (call);                   \
    Py_END_CRITICAL_SECTION();         \
    return result

static PyObject *heap_push(heap_t *h, PyObject *event) { LOCKED(h, push_impl(h, event)); }
static PyObject *heap_pop(heap_t *h, PyObject *Py_UNUSED(x)) { LOCKED(h, pop_impl(h)); }
static PyObject *heap_pop_due(heap_t *h, PyObject *until) { LOCKED(h, pop_due_impl(h, until)); }
static PyObject *heap_compact(heap_t *h, PyObject *Py_UNUSED(x)) { LOCKED(h, compact_impl(h)); }
static PyObject *heap_clear(heap_t *h, PyObject *Py_UNUSED(x)) { LOCKED(h, clear_impl(h)); }
static PyObject *heap_events(heap_t *h, PyObject *Py_UNUSED(x)) { LOCKED(h, events_impl(h)); }

static Py_ssize_t
heap_len(heap_t *h)
{
    return h->size;
}

/* ``event in heap``: list membership over the array (identity, then ==). */
static int
heap_contains(heap_t *h, PyObject *event)
{
    int found = 0;
    Py_BEGIN_CRITICAL_SECTION(h);
    found = check_idle(h);
    h->busy = found == 0;
    for (Py_ssize_t i = 0; found == 0 && i < h->size; i++)
        found = PyObject_RichCompareBool(h->items[i].event, event, Py_EQ);
    h->busy = 0;
    Py_END_CRITICAL_SECTION();
    return found;
}

/* EventHeap(events=()): a heap holding ``events`` in their given order (already a heap). */
static PyObject *
heap_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"events", NULL};
    PyObject *events = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|O:EventHeap", keywords, &events))
        return NULL;
    heap_t *h = (heap_t *)type->tp_alloc(type, 0);
    PyObject *items = h == NULL || events == NULL ? NULL : PySequence_List(events);
    for (Py_ssize_t i = 0; items != NULL && i < PyList_GET_SIZE(items); i++)
        if (append(h, PyList_GET_ITEM(items, i)) < 0)
            Py_CLEAR(items);
    if (h != NULL && events != NULL && items == NULL)
        Py_CLEAR(h);
    Py_XDECREF(items);
    return (PyObject *)h;
}

static int
heap_traverse(heap_t *h, visitproc visit, void *arg)
{
    for (Py_ssize_t i = 0; i < h->size; i++)
        Py_VISIT(h->items[i].event);
    return 0;
}

static int
heap_tp_clear(heap_t *h)
{
    return release_all(h, 0);
}

static void
heap_dealloc(heap_t *h)
{
    PyObject_GC_UnTrack(h);
    release_all(h, 0);
    Py_TYPE(h)->tp_free((PyObject *)h);
}

#define METHOD(name, flags, doc) {#name, (PyCFunction)(void (*)(void))heap_##name, flags, doc}
static PyMethodDef heap_methods[] = {
    METHOD(push, METH_O, "Add an event (heapq.heappush)."),
    METHOD(pop, METH_NOARGS, "Remove and return the first live event; IndexError when none."),
    METHOD(pop_due, METH_O, "The first live event if its time is <= until (removed), else None."),
    METHOD(compact, METH_NOARGS, "Drop the canceled events and rebuild the heap."),
    METHOD(clear, METH_NOARGS, "Detach and drop every event."),
    METHOD(events, METH_NOARGS, "The events, canceled ones included, in heap order."),
    {NULL, NULL, 0, NULL},
};

static PyMemberDef heap_members[] = {
    {"canceled", Py_T_PYSSIZET, offsetof(heap_t, canceled), 0, "Canceled events still held."},
    {NULL, 0, 0, 0, NULL},
};

static PySequenceMethods heap_sequence = {
    .sq_length = (lenfunc)heap_len,
    .sq_contains = (objobjproc)heap_contains,
};

static PyTypeObject heap_type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "modelly._native.fastevents.EventHeap",
    .tp_doc = "The event list's binary heap: time, then priority, then insertion order.",
    .tp_basicsize = sizeof(heap_t),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_new = heap_new,
    .tp_dealloc = (destructor)heap_dealloc,
    .tp_traverse = (traverseproc)heap_traverse,
    .tp_clear = (inquiry)heap_tp_clear,
    .tp_methods = heap_methods,
    .tp_members = heap_members,
    .tp_as_sequence = &heap_sequence,
};

/* bind(event_type, float64_type): the class whose keys are compared in C, and numpy.float64. */
static PyObject *
bind(PyObject *Py_UNUSED(module), PyObject *const *argv, Py_ssize_t nargs)
{
    if (nargs != 2 || !PyType_Check(argv[0]) || !PyType_Check(argv[1])) {
        PyErr_SetString(PyExc_TypeError, "bind(event_type, float64_type)");
        return NULL;
    }
    Py_XSETREF(event_type, (PyTypeObject *)Py_NewRef(argv[0]));
    Py_XSETREF(float64_type, (PyTypeObject *)Py_NewRef(argv[1]));
    Py_RETURN_NONE;
}

static PyMethodDef module_methods[] = {
    {"bind", (PyCFunction)(void (*)(void))bind, METH_FASTCALL,
     "Set the event class whose keys are compared in C, and numpy.float64."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT, "fastevents", "The event list's binary heap, in C.",
    -1, module_methods, NULL, NULL, NULL, NULL,
};

/* Intern one attribute name into ``slot``; -1 on error. */
static int
intern(PyObject **slot, const char *name)
{
    *slot = PyUnicode_InternFromString(name);
    return *slot == NULL ? -1 : 0;
}

PyMODINIT_FUNC
PyInit_fastevents(void)
{
    if (intern(&str_time, "time") < 0 || intern(&str_priority, "priority") < 0
        || intern(&str_uid, "unique_id") < 0 || intern(&str_canceled, "_canceled") < 0
        || intern(&str_owner, "_owner") < 0 || intern(&str_canceled_prop, "CANCELED") < 0
        || PyType_Ready(&heap_type) < 0)
        return NULL;
    PyObject *module = PyModule_Create(&module_def);
    if (module != NULL
        && (PyModule_AddObjectRef(module, "EventHeap", (PyObject *)&heap_type) < 0
            || DECLARE_NO_GIL(module) < 0))
        Py_CLEAR(module);
    return module;
}

