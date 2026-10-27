/*
 * modelly._native: the heap behind fastevents.c's EventHeap, the standard
 * library's heapq ported step for step onto an array of entries that carry
 * their event's ordering keys.
 *
 * A comparison is Event.__lt__: time, then priority, then unique_id. For an
 * Event (the class itself, bound by bind()) whose time is a float, a numpy
 * float64 or an int of magnitude at most 2**53 (all exact as a double) and whose
 * priority and unique_id fit in 64 bits, the keys are read once at push and
 * compared as C numbers, which gives what __lt__ gives. Any other entry is
 * compared by calling ``<`` on the events, as heapq does, and its CANCELED
 * property is read instead of the _canceled attribute.
 *
 * Included by fastevents.c after <Python.h> and ftcompat.h.
 */
#ifndef MODELLY_EVENTHEAP_H
#define MODELLY_EVENTHEAP_H

#define MAX_EXACT_INT 9007199254740992LL /* 2**53: larger ints are not exact doubles */
#define MIN_CAPACITY 16
#define GROWTH_FACTOR 2

typedef struct {
    PyObject *event; /* a strong reference */
    double time;
    long long priority, uid;
    int fast; /* the keys above are valid: compare them instead of calling __lt__ */
} entry_t;

typedef struct {
    PyObject_HEAD
    entry_t *items;
    Py_ssize_t size, capacity, canceled;
    int busy; /* inside a sift or a callback of this heap: the array must not change */
} heap_t;

static PyTypeObject *event_type = NULL;   /* modelly.time.events.Event, from bind() */
static PyTypeObject *float64_type = NULL; /* numpy.float64, from bind() */
static PyObject *str_time, *str_priority, *str_uid, *str_canceled, *str_owner, *str_canceled_prop;

/* 1 and the value when ``value`` is exactly a double that compares as it does, else 0. */
static int
exact_double(PyObject *value, double *out)
{
    if (PyFloat_CheckExact(value) || Py_TYPE(value) == float64_type) {
        *out = PyFloat_AS_DOUBLE(value);
        return 1;
    }
    if (!PyLong_CheckExact(value) && !PyBool_Check(value))
        return 0;
    int overflow;
    long long number = PyLong_AsLongLongAndOverflow(value, &overflow);
    if (overflow || number > MAX_EXACT_INT || number < -MAX_EXACT_INT)
        return 0;
    *out = (double)number;
    return 1;
}

/* 1 and the value when attribute ``name`` is an int that fits in 64 bits, 0 if not, -1 on error. */
static int
attr_int64(PyObject *event, PyObject *name, long long *out)
{
    PyObject *value = PyObject_GetAttr(event, name);
    if (value == NULL)
        return -1;
    int overflow = 1;
    if (PyLong_CheckExact(value))
        *out = PyLong_AsLongLongAndOverflow(value, &overflow);
    Py_DECREF(value);
    return !overflow;
}

/* Fill ``entry``'s keys; entry->fast says whether they can be compared in C. -1 on error. */
static int
read_keys(PyObject *event, entry_t *entry)
{
    entry->fast = 0;
    if (event_type == NULL || Py_TYPE(event) != event_type)
        return 0;
    PyObject *time = PyObject_GetAttr(event, str_time);
    if (time == NULL)
        return -1;
    int exact = exact_double(time, &entry->time);
    Py_DECREF(time);
    int priority = exact ? attr_int64(event, str_priority, &entry->priority) : 0;
    int uid = priority > 0 ? attr_int64(event, str_uid, &entry->uid) : 0;
    if (priority < 0 || uid < 0)
        return -1;
    entry->fast = uid > 0;
    return 0;
}

/* a < b as Event.__lt__ decides: 1, 0, or -1 on error. */
static int
less(const entry_t *a, const entry_t *b)
{
    if (!a->fast || !b->fast)
        return PyObject_RichCompareBool(a->event, b->event, Py_LT);
    if (a->time != b->time)
        return a->time < b->time;
    if (a->priority != b->priority)
        return a->priority < b->priority;
    return a->uid < b->uid;
}

/* heapq._siftdown: move the entry at ``pos`` up towards ``start`` while it is smaller. */
static int
sift_down(heap_t *h, Py_ssize_t start, Py_ssize_t pos)
{
    entry_t item = h->items[pos];
    int rc = 0;
    while (pos > start) {
        Py_ssize_t parent = (pos - 1) >> 1;
        if ((rc = less(&item, &h->items[parent])) <= 0)
            break;
        h->items[pos] = h->items[parent];
        pos = parent;
    }
    h->items[pos] = item;
    return rc < 0 ? -1 : 0;
}

/* heapq._siftup: move the smaller child up to a leaf, then sift the entry down there. */
static int
sift_up(heap_t *h, Py_ssize_t pos)
{
    Py_ssize_t start = pos, limit = h->size / 2;
    entry_t item = h->items[pos];
    while (pos < limit) {
        Py_ssize_t child = 2 * pos + 1;
        if (child + 1 < h->size) {
            int lt = less(&h->items[child], &h->items[child + 1]);
            if (lt < 0) {
                h->items[pos] = item;
                return -1;
            }
            child += lt ^ 1; /* the right child unless the left one is smaller */
        }
        h->items[pos] = h->items[child];
        pos = child;
    }
    h->items[pos] = item;
    return sift_down(h, start, pos);
}

/* heapq.heapify: sift every parent, last first. */
static int
heapify(heap_t *h)
{
    int rc = 0;
    for (Py_ssize_t i = h->size / 2 - 1; rc == 0 && i >= 0; i--)
        rc = sift_up(h, i);
    return rc;
}

/* heapq.heappop: remove the root and return it as a new reference; NULL on error. */
static PyObject *
pop_root(heap_t *h)
{
    entry_t last = h->items[--h->size];
    if (h->size == 0)
        return last.event;
    PyObject *root = h->items[0].event;
    h->items[0] = last;
    h->busy = 1;
    int rc = sift_up(h, 0);
    h->busy = 0;
    if (rc < 0)
        Py_CLEAR(root);
    return root;
}

/* Whether ``event`` is canceled: an Event's _canceled attribute, else its CANCELED. */
static int
is_canceled(PyObject *event, int fast)
{
    PyObject *flag = PyObject_GetAttr(event, fast ? str_canceled : str_canceled_prop);
    if (flag == NULL)
        return -1;
    int truth = PyObject_IsTrue(flag);
    Py_DECREF(flag);
    return truth;
}

/* ``entry.event.time <= until``: 1, 0, or -1 on error. */
static int
is_due(const entry_t *entry, PyObject *until, int until_exact, double limit)
{
    if (entry->fast && until_exact)
        return entry->time <= limit;
    PyObject *time = PyObject_GetAttr(entry->event, str_time);
    if (time == NULL)
        return -1;
    int due = PyObject_RichCompareBool(time, until, Py_LE);
    Py_DECREF(time);
    return due;
}

/* RuntimeError when called back from inside a sift or a callback of this heap. */
static int
check_idle(heap_t *h)
{
    if (!h->busy)
        return 0;
    PyErr_SetString(PyExc_RuntimeError, "event list changed while it was being reordered");
    return -1;
}

/* Room for one more entry; -1 on error. */
static int
reserve(heap_t *h)
{
    if (h->size < h->capacity)
        return 0;
    Py_ssize_t capacity = h->capacity < MIN_CAPACITY ? MIN_CAPACITY : h->capacity * GROWTH_FACTOR;
    entry_t *items = capacity > PY_SSIZE_T_MAX / (Py_ssize_t)sizeof(entry_t)
                         ? NULL
                         : PyMem_Realloc(h->items, (size_t)capacity * sizeof(entry_t));
    if (items == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    h->items = items;
    h->capacity = capacity;
    return 0;
}

/* Put ``event`` at the end of the array, unsifted; -1 on error. */
static int
append(heap_t *h, PyObject *event)
{
    entry_t entry;
    if (read_keys(event, &entry) < 0 || reserve(h) < 0)
        return -1;
    entry.event = Py_NewRef(event);
    h->items[h->size++] = entry;
    return 0;
}

/* The popped live event, detached from its list (``_owner = None``). */
static PyObject *
detach(PyObject *event)
{
    if (event != NULL && PyObject_SetAttr(event, str_owner, Py_None) < 0)
        Py_CLEAR(event);
    return event;
}

#endif /* MODELLY_EVENTHEAP_H */
