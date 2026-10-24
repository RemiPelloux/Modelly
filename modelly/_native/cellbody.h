/*
 * modelly._native: the bodies of Cell.add_agent and Cell.remove_agent
 * (modelly/space/cells/cell.py), ported line by line for fastcell.c's set_cell.
 * Same calls, same order, same exceptions as the Python methods.
 *
 * Included by fastcell.c after its interned names (str_*), layout_t and
 * bound(), which these functions use.
 */
#ifndef MODELLY_CELLBODY_H
#define MODELLY_CELLBODY_H

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

/* ``raise CellFullException(cell.coordinate, agent)`` */
static int
raise_full(PyObject *cell, PyObject *agent)
{
    PyObject *coordinate = PyObject_GetAttr(cell, str_coordinate), *type = bound(&exc_full);
    PyObject *args[] = {coordinate, agent};
    PyObject *exc = coordinate == NULL ? NULL : PyObject_Vectorcall(type, args, 2, NULL);
    Py_XDECREF(coordinate);
    Py_XDECREF(type);
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
        return full < 0 ? -1 : raise_full(cell, agent);
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

/* ``occupants.remove(agent)``; an exact list is searched as list.remove does, except on a
 * free-threaded build, where list.remove itself runs (it searches under the list's lock). */
static int
remove_from(PyObject *occupants, PyObject *agent)
{
#ifdef Py_GIL_DISABLED
    const int search_here = 0;
#else
    const int search_here = PyList_CheckExact(occupants);
#endif
    if (!search_here)
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
    PyObject *coordinate = PyObject_GetAttr(cell, str_coordinate), *type = bound(&exc_missing);
    PyObject *args[] = {agent, coordinate};
    PyObject *exc = coordinate == NULL ? NULL : PyObject_Vectorcall(type, args, 2, NULL);
    Py_XDECREF(coordinate);
    Py_XDECREF(type);
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

#endif /* MODELLY_CELLBODY_H */
