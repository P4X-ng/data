#include <Python.h>
#include <stdint.h>
#include <string.h>

// Very small PRP-ish permutation using xorshift/feistel-style round.
// This is a placeholder; replace with a stronger bijection later.
static inline uint32_t prp32(uint32_t x, uint32_t key){
    x ^= key * 0x9E3779B9u;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    x ^= (key ^ 0x85EBCA77u);
    return x;
}

// Bitpacker with tier persistence and simple 1-bit ping/pong and SYNC markers.

typedef struct {
    uint8_t *buf;      // output buffer
    Py_ssize_t cap;    // capacity in bytes
    Py_ssize_t pos;    // bit position from start
    int current_tier;  // -1 none, 0=L1,1=L2,2=L3
} bitwriter_t;

static inline int bw_init(bitwriter_t *w, Py_buffer *out){
    w->buf = (uint8_t*)out->buf;
    w->cap = out->len;
    w->pos = 0;
    w->current_tier = -1;
    memset(w->buf, 0, (size_t)w->cap);
    return 0;
}

static inline int bw_put_bits(bitwriter_t *w, uint32_t v, int nb){
    if(nb<=0) return 0;
    if(w->pos + nb > w->cap * 8) return -1;
    for(int i=nb-1;i>=0;--i){
        uint32_t bit = (v >> i) & 1u;
        Py_ssize_t byte = w->pos >> 3;
        int off = 7 - (w->pos & 7);
        w->buf[byte] |= (uint8_t)(bit << off);
        w->pos++;
    }
    return 0;
}

static inline int bw_set_tier(bitwriter_t *w, int tier){
    if(tier == w->current_tier) return 0; // persistent
    // 2-bit tier change: 00->L1, 01->L2, 10->L3
    switch(tier){
        case 0: if(bw_put_bits(w, 0b00, 2)) return -1; break;
        case 1: if(bw_put_bits(w, 0b01, 2)) return -1; break;
        case 2: if(bw_put_bits(w, 0b10, 2)) return -1; break;
        default: return -1;
    }
    w->current_tier = tier;
    return 0;
}

// Python API: pack_refs(out_bytes, tier, refs_bytes, ref_width_bits)
// - out_bytes: writable bytearray or memoryview
// - tier: 0,1,2 (L1/L2/L3)
// - refs_bytes: contiguous bytes of refs (1/2/4 each)
// - ref_width_bits: 8/16/32
static PyObject* py_pack_refs(PyObject *self, PyObject *args){
    PyObject *out_obj, *refs_obj;
    int tier, ref_bits;
    if(!PyArg_ParseTuple(args, "OiOi", &out_obj, &tier, &refs_obj, &ref_bits)){
        return NULL;
    }
    Py_buffer outv, refsv;
    if(PyObject_GetBuffer(out_obj, &outv, PyBUF_WRITABLE) < 0) return NULL;
    if(PyObject_GetBuffer(refs_obj, &refsv, PyBUF_SIMPLE) < 0){ PyBuffer_Release(&outv); return NULL; }

    bitwriter_t w; bw_init(&w, &outv);
    if(bw_set_tier(&w, tier)) goto err;

    const uint8_t *p = (const uint8_t*)refsv.buf;
    Py_ssize_t stride = ref_bits/8;
    Py_ssize_t n = refsv.len / stride;
    for(Py_ssize_t i=0;i<n;++i){
        if(ref_bits==8){ if(bw_put_bits(&w, p[i], 8)) goto err; }
        else if(ref_bits==16){
            uint16_t v; memcpy(&v, p + i*2, 2); v = (uint16_t)((v>>8)|((v&0xFF)<<8)); // host to big-endian bits order-ish
            if(bw_put_bits(&w, v, 16)) goto err;
        } else if(ref_bits==32){
            uint32_t v; memcpy(&v, p + i*4, 4);
            v = ((v>>24)&0xFF) | ((v>>8)&0xFF00) | ((v<<8)&0xFF0000) | ((v<<24)&0xFF000000);
            if(bw_put_bits(&w, v, 32)) goto err;
        } else { goto err; }
    }

    PyBuffer_Release(&refsv);
    PyBuffer_Release(&outv);
    return PyLong_FromSsize_t(w.pos);
err:
    PyBuffer_Release(&refsv);
    PyBuffer_Release(&outv);
    PyErr_SetString(PyExc_RuntimeError, "bitpack overflow or bad args");
    return NULL;
}

static PyMethodDef BitpackMethods[] = {
    {"pack_refs", py_pack_refs, METH_VARARGS, "Pack tiered references into a bitstream. Returns bits written."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef bitpackmodule = {
    PyModuleDef_HEAD_INIT,
    "_bitpack",
    "Bitstream packer for PacketFS",
    -1,
    BitpackMethods
};

PyMODINIT_FUNC PyInit__bitpack(void){
    return PyModule_Create(&bitpackmodule);
}

