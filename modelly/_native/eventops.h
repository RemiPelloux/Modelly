/*
 * modelly._native: the operations of fastevents.c's EventHeap, each the body of
 * one method of PyEventHeap (modelly/_native/events.py) on the heap of eventheap.h.
 * They run inside the heap's critical section (fastevents.c's LOCKED).
 *
 * Included by fastevents.c after eventheap.h.
 */
#ifndef MODELLY_EVENTOPS_H
#define MODELLY_EVENTOPS_H

enum { ROOT_FUTURE = 0, ROOT_DUE = 1, ROOT_CANCELED = 2 };

static PyObject *
push_impl(heap_t *h, PyObject *event)
{
    if (check_idle(h) < 0 || append(h, event) < 0)
        return NULL;
    h->busy = 1;
    int rc = sift_down(h, 0, h->size - 1);
    h->busy = 0;
    return rc < 0 ? NULL : Py_NewRef(Py_None);
}

static PyObject *
pop_impl(heap_t *h)
{
    if (check_idle(h) < 0)
        return NULL;
    while (h->size > 0) {
        int fast = h->items[0].fast;
        PyObject *event = pop_root(h);
        int canceled = event == NULL ? -1 : is_canceled(event, fast);
        if (canceled == 0)
            return detach(event);
        Py_XDECREF(event);
        if (canceled < 0)
            return NULL;
        h->canceled--;
    }
    PyErr_SetString(PyExc_IndexError, "Event list is empty");
    return NULL;
}

/* Whether the root is canceled, due by ``until`` or in the future; -1 on error. */
static int
root_state(heap_t *h, PyObject *until, int until_exact, double limit)
{
    entry_t root = h->items[0];
    h->busy = 1;
    int canceled = is_canceled(root.event, root.fast);
    int due = canceled != 0 ? 0 : is_due(&root, until, until_exact, limit);
    h->busy = 0;
    if (canceled < 0 || due < 0)
        return -1;
    return canceled ? ROOT_CANCELED : due;
}

static PyObject *
pop_due_impl(heap_t *h, PyObject *until)
{
    double limit = 0.0;
    int until_exact = exact_double(until, &limit);
    if (check_idle(h) < 0)
        return NULL;
    while (h->size > 0) {
        int state = root_state(h, until, until_exact, limit);
        if (state < 0)
            return NULL;
        if (state == ROOT_FUTURE)
            Py_RETURN_NONE;
        PyObject *event = pop_root(h);
        if (state == ROOT_DUE || event == NULL)
            return detach(event);
        h->canceled--;
        Py_DECREF(event);
    }
    Py_RETURN_NONE;
}

/* Move the canceled events out of the array into a new list that owns them; NULL on error. */
static PyObject *
take_canceled(heap_t *h)
{
    char *dead = PyMem_Calloc((size_t)h->size + 1, 1);
    Py_ssize_t n_dead = 0, kept = 0, j = 0;
    if (dead == NULL)
        return PyErr_NoMemory();
    for (Py_ssize_t i = 0; i < h->size; i++) {
        int canceled = is_canceled(h->items[i].event, h->items[i].fast);
        if (canceled < 0) {
            PyMem_Free(dead);
            return NULL;
        }
        n_dead += dead[i] = (char)canceled;
    }
    PyObject *dropped = PyList_New(n_dead);
    for (Py_ssize_t i = 0; dropped != NULL && i < h->size; i++) {
        if (dead[i])
            PyList_SET_ITEM(dropped, j++, h->items[i].event); /* the list takes our reference */
        else
            h->items[kept++] = h->items[i];
    }
    if (dropped != NULL)
        h->size = kept;
    PyMem_Free(dead);
    return dropped;
}

static PyObject *
compact_impl(heap_t *h)
{
    if (check_idle(h) < 0)
        return NULL;
    h->busy = 1;
    PyObject *dropped = take_canceled(h);
    int rc = dropped == NULL ? -1 : heapify(h);
    h->busy = 0;
    if (rc == 0)
        h->canceled = 0;
    Py_XDECREF(dropped); /* the canceled events go once the heap is whole again */
    return rc < 0 ? NULL : Py_NewRef(Py_None);
}

/* Empty the heap first, then release the old entries (``_owner = None`` if ``detaching``). */
static int
release_all(heap_t *h, int detaching)
{
    entry_t *items = h->items;
    Py_ssize_t size = h->size;
    h->items = NULL;
    h->size = h->capacity = h->canceled = 0;
    int rc = 0;
    for (Py_ssize_t i = 0; i < size; i++) {
        if (detaching && rc == 0 && PyObject_SetAttr(items[i].event, str_owner, Py_None) < 0)
            rc = -1;
        Py_DECREF(items[i].event);
    }
    PyMem_Free(items);
    return rc;
}

static PyObject *
clear_impl(heap_t *h)
{
    if (check_idle(h) < 0 || release_all(h, 1) < 0)
        return NULL;
    Py_RETURN_NONE;
}

static PyObject *
events_impl(heap_t *h)
{
    if (check_idle(h) < 0)
        return NULL;
    PyObject *events = PyList_New(h->size);
    for (Py_ssize_t i = 0; events != NULL && i < h->size; i++)
        PyList_SET_ITEM(events, i, Py_NewRef(h->items[i].event));
    return events;
}

#endif /* MODELLY_EVENTOPS_H */
