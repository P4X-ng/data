#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <pthread.h>
#include <unistd.h>
#ifdef __x86_64__
#include <immintrin.h>
#endif

static inline double now_sec(){
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

typedef struct {
    uint8_t *dst;
    const uint8_t *src;
    size_t size;
    uint8_t delta;
    int threads;
    int tid;
} job_t;

static inline void add_delta(uint8_t *dst, const uint8_t *src, size_t n, uint8_t delta){
#ifdef __x86_64__
    __m128i vdelta = _mm_set1_epi8((char)delta);
    while(n >= 16){
        __m128i v = _mm_loadu_si128((const __m128i*)src);
        v = _mm_add_epi8(v, vdelta);
        _mm_storeu_si128((__m128i*)dst, v);
        src += 16; dst += 16; n -= 16;
    }
#endif
    for(size_t i=0;i<n;i++) dst[i] = (uint8_t)(src[i] + delta);
}

static void *worker(void *arg){
    job_t *jb = (job_t*)arg;
    size_t chunk = jb->size / (size_t)jb->threads;
    size_t start = (size_t)jb->tid * chunk;
    size_t end = (jb->tid == jb->threads-1) ? jb->size : start + chunk;
    add_delta(jb->dst + start, jb->src + start, end - start, jb->delta);
    return NULL;
}

int main(int argc, char **argv){
    size_t size_mb = 100, size_bytes;
    int threads = (int)sysconf(_SC_NPROCESSORS_ONLN);
    int delta = 0;
    int dumb = 0; // single-threaded mode if set
    for(int i=1; i<argc; i++){
        if(strcmp(argv[i], "--size-mb")==0 && i+1<argc) size_mb = strtoull(argv[++i], NULL, 10);
        else if(strcmp(argv[i], "--threads")==0 && i+1<argc) threads = atoi(argv[++i]);
        else if(strcmp(argv[i], "--delta")==0 && i+1<argc) delta = atoi(argv[++i]) & 0xFF;
        else if(strcmp(argv[i], "--dumb")==0) dumb = 1;
    }
    size_bytes = size_mb * (1ULL<<20);
    uint8_t *src = aligned_alloc(64, size_bytes);
    uint8_t *dst = aligned_alloc(64, size_bytes);
    if(!src || !dst){ fprintf(stderr, "alloc failed\n"); return 1; }
    // Fill src deterministically
    for(size_t i=0;i<size_bytes;i++) src[i] = (uint8_t)(i * 1315423911u);

    double t0 = now_sec();
    if(dumb){
        // Single-threaded baseline
        add_delta(dst, src, size_bytes, (uint8_t)delta);
    } else {
        pthread_t *tids = calloc((size_t)threads, sizeof(pthread_t));
        job_t *jobs = calloc((size_t)threads, sizeof(job_t));
        for(int t=0;t<threads;t++){
            jobs[t].dst = dst; jobs[t].src = src; jobs[t].size = size_bytes; jobs[t].delta = (uint8_t)delta; jobs[t].threads = threads; jobs[t].tid = t;
            pthread_create(&tids[t], NULL, worker, &jobs[t]);
        }
        for(int t=0;t<threads;t++) pthread_join(tids[t], NULL);
        free(tids); free(jobs);
    }
    double t1 = now_sec();

    double elapsed = t1 - t0;
    double mbps = (size_mb / elapsed);
    printf("CPU baseline: size=%zu MB, threads=%d, delta=%d, dumb=%d\n", size_mb, dumb ? 1 : threads, delta, dumb);
    printf("Elapsed: %.3f s, Throughput: %.2f MB/s\n", elapsed, mbps);

    free(src); free(dst);
    return 0;
}
