/*
 * modelly._native: CPython's Mersenne Twister state (Modules/_randommodule.c)
 * and the draws fastrng.c makes on it, bit for bit as random.Random makes them.
 * Included by fastrng.c after <Python.h>. The caller holds the generator's
 * critical section (a no-op on GIL builds) around every function here.
 */
#ifndef MODELLY_MTDRAWS_H
#define MODELLY_MTDRAWS_H

#include <math.h>
#include <stdint.h>
#include <string.h>
#ifdef _MSC_VER
#include <intrin.h> /* _BitScanReverse: MSVC has no __builtin_clz */
#endif

#define MT_N 624
#define MT_M 397
#define MATRIX_A 0x9908b0dfU
#define UPPER_MASK 0x80000000U
#define LOWER_MASK 0x7fffffffU
#define WORD_RANGE 4294967296LL /* 2**32: the fast paths draw below this */
#define INT_BOUND (1LL << 62)   /* randint's fast path: both ends within +-2**62 */

#define SMALL_SET_SIZE 21      /* random.sample: small set minus empty list */
#define SAMPLE_SET_THRESHOLD 5 /* above this k the set size grows */

/* CPython's Modules/_randommodule.c RandomObject, unchanged since 3.2. */
typedef struct {
    PyObject_HEAD
    int index;
    uint32_t state[MT_N];
} RandomObject;

/* Refill the state with the next MT_N words. */
static void
twist(uint32_t *mt)
{
    static const uint32_t mag01[2] = {0x0U, MATRIX_A};
    uint32_t y;
    int kk;
    for (kk = 0; kk < MT_N - MT_M; kk++) {
        y = (mt[kk] & UPPER_MASK) | (mt[kk + 1] & LOWER_MASK);
        mt[kk] = mt[kk + MT_M] ^ (y >> 1) ^ mag01[y & 0x1U];
    }
    for (; kk < MT_N - 1; kk++) {
        y = (mt[kk] & UPPER_MASK) | (mt[kk + 1] & LOWER_MASK);
        mt[kk] = mt[kk + (MT_M - MT_N)] ^ (y >> 1) ^ mag01[y & 0x1U];
    }
    y = (mt[MT_N - 1] & UPPER_MASK) | (mt[0] & LOWER_MASK);
    mt[MT_N - 1] = mt[MT_M - 1] ^ (y >> 1) ^ mag01[y & 0x1U];
}

static inline uint32_t
genrand_uint32(RandomObject *self)
{
    if (self->index >= MT_N) {
        twist(self->state);
        self->index = 0;
    }
    uint32_t y = self->state[self->index++];
    y ^= (y >> 11);
    y ^= (y << 7) & 0x9d2c5680U;
    y ^= (y << 15) & 0xefc60000U;
    y ^= (y >> 18);
    return y;
}

/* n.bit_length() for n > 0. */
static inline int
bit_length32(uint32_t n)
{
#ifdef _MSC_VER
    unsigned long top;
    _BitScanReverse(&top, n);
    return (int)top + 1;
#else
    return 32 - __builtin_clz(n);
#endif
}

/* _randbelow_with_getrandbits for 0 < n < 2**32: k = n.bit_length(),
 * then getrandbits(k) until below n; getrandbits(k <= 32) is the top k bits
 * of one word. */
static inline uint32_t
below32(RandomObject *self, uint32_t n)
{
    int k = bit_length32(n);
    uint32_t r = genrand_uint32(self) >> (32 - k);
    while (r >= n)
        r = genrand_uint32(self) >> (32 - k);
    return r;
}

/* random.sample's pool path (n <= setsize): draw from a shrinking copy. */
static int
sample_pool(RandomObject *self, PyObject **items, Py_ssize_t n, Py_ssize_t k, PyObject **out)
{
    PyObject **pool = PyMem_Malloc((size_t)(n > 0 ? n : 1) * sizeof(PyObject *));
    if (pool == NULL)
        return -1;
    memcpy(pool, items, (size_t)n * sizeof(PyObject *));
    for (Py_ssize_t i = 0; i < k; i++) {
        uint32_t j = below32(self, (uint32_t)(n - i));
        out[i] = Py_NewRef(pool[j]);
        pool[j] = pool[n - i - 1];
    }
    PyMem_Free(pool);
    return 0;
}

/* random.sample's set path: redraw an index already selected. */
static int
sample_set(RandomObject *self, PyObject **items, Py_ssize_t n, Py_ssize_t k, PyObject **out)
{
    unsigned char *seen = PyMem_Calloc((size_t)(n / 8 + 1), 1);
    if (seen == NULL)
        return -1;
    for (Py_ssize_t i = 0; i < k; i++) {
        uint32_t j = below32(self, (uint32_t)n);
        while (seen[j >> 3] & (1u << (j & 7)))
            j = below32(self, (uint32_t)n);
        seen[j >> 3] |= (unsigned char)(1u << (j & 7));
        out[i] = Py_NewRef(items[j]);
    }
    PyMem_Free(seen);
    return 0;
}

/* random.Random.sample for 0 <= k <= n items, both code paths reproduced draw for draw. */
static PyObject *
sample_indices(RandomObject *self, PyObject **items, Py_ssize_t n, Py_ssize_t k)
{
    Py_ssize_t setsize = SMALL_SET_SIZE;
    if (k > SAMPLE_SET_THRESHOLD)
        /* 4 ** ceil(math.log(k * 3, 4)), with math.log's own double arithmetic */
        setsize += (Py_ssize_t)1 << (2 * (int)ceil(log((double)(k * 3)) / log(4.0)));
    PyObject *result = PyList_New(k);
    if (result == NULL)
        return NULL;
    PyObject **out = ((PyListObject *)result)->ob_item;
    int rc = n <= setsize ? sample_pool(self, items, n, k, out) : sample_set(self, items, n, k, out);
    if (rc < 0) {
        Py_DECREF(result); /* the unset items are NULL, which list dealloc skips */
        return PyErr_NoMemory();
    }
    return result;
}

#endif /* MODELLY_MTDRAWS_H */
