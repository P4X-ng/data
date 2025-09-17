#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef __x86_64__
#include <immintrin.h>
#endif
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>
#ifdef __linux__
#include <sched.h>
#include <linux/mman.h>
#endif
#ifdef __APPLE__
#include <sys/sysctl.h>
#endif
#ifdef HAVE_LIBNUMA
#include <numa.h>
#include <numaif.h>
#endif

// Simple CLI parsing helpers
static void die(const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
    exit(1);
}

static long get_cpu_count(void){
#ifdef __APPLE__
    int nm[2]; size_t len = 4; uint32_t count;
    nm[0] = CTL_HW; nm[1] = HW_AVAILCPU;
    sysctl(nm, 2, &count, &len, NULL, 0);
    if(count < 1){ nm[1] = HW_NCPU; sysctl(nm, 2, &count, &len, NULL, 0); if(count < 1) count = 1; }
    return (long)count;
#else
    long n = sysconf(_SC_NPROCESSORS_ONLN);
    return n > 0 ? n : 1;
#endif
}

typedef struct {
    uint8_t *out_base;      // mapped output file
    size_t out_size;        // total file size
    const uint8_t *blob;    // mapped shared memory blob
    size_t blob_size;
    size_t seg_len;         // bytes per segment
    size_t count;           // number of segments
    size_t start_offset;    // initial offset within blob
    size_t stride;          // stride per segment
    uint8_t delta;          // additive delta per byte
    size_t start_idx;       // first segment index to process (inclusive)
    size_t end_idx;         // last segment index to process (exclusive)
    int cpu_id;             // CPU to pin this worker to (-1 = no pin)
    size_t batch;           // segments to process per inner batch (>=1)
    bool coalesce;          // coalesce contiguous segments when stride == seg_len
    int numa_node;          // NUMA node to run on (-1 = none)
} job_t;

static inline void add_delta_vec(uint8_t *dst, const uint8_t *src, size_t n, uint8_t delta){
#ifdef __x86_64__
    __m128i vdelta = _mm_set1_epi8((char)delta);
    while(n >= 16){
        __m128i v = _mm_loadu_si128((const __m128i*)src);
        v = _mm_add_epi8(v, vdelta);
        _mm_storeu_si128((__m128i*)dst, v);
        src += 16; dst += 16; n -= 16;
    }
#endif
    // tail
    for(size_t i=0;i<n;i++) dst[i] = (uint8_t)(src[i] + delta);
}

static inline void copy_small_vec(uint8_t *dst, const uint8_t *src, size_t n){
#ifdef __x86_64__
    // Unrolled 16-byte copies up to 128B
    while(n >= 64){
        __m128i v0 = _mm_loadu_si128((const __m128i*)(src + 0));
        __m128i v1 = _mm_loadu_si128((const __m128i*)(src + 16));
        __m128i v2 = _mm_loadu_si128((const __m128i*)(src + 32));
        __m128i v3 = _mm_loadu_si128((const __m128i*)(src + 48));
        _mm_storeu_si128((__m128i*)(dst + 0), v0);
        _mm_storeu_si128((__m128i*)(dst + 16), v1);
        _mm_storeu_si128((__m128i*)(dst + 32), v2);
        _mm_storeu_si128((__m128i*)(dst + 48), v3);
        src += 64; dst += 64; n -= 64;
    }
    while(n >= 16){
        __m128i v = _mm_loadu_si128((const __m128i*)src);
        _mm_storeu_si128((__m128i*)dst, v);
        src += 16; dst += 16; n -= 16;
    }
#endif
    // tail
    while(n--) *dst++ = *src++;
}

static void *worker(void *arg){
    job_t *jb = (job_t*)arg;
#ifdef HAVE_LIBNUMA
    if(jb->numa_node >= 0){
        numa_run_on_node(jb->numa_node);
        numa_set_localalloc();
    }
#endif
#ifdef __linux__
    if(jb->cpu_id >= 0){
        cpu_set_t set; CPU_ZERO(&set); CPU_SET((unsigned)jb->cpu_id, &set);
        pthread_setaffinity_np(pthread_self(), sizeof(set), &set);
    }
#endif
    const uint8_t *blob = jb->blob;
    size_t blob_size = jb->blob_size;
    uint8_t *out = jb->out_base;
    size_t seg_len = jb->seg_len;
    size_t stride = jb->stride;
    size_t start_offset = jb->start_offset;
    uint8_t delta = jb->delta;

    size_t batch = jb->batch > 0 ? jb->batch : 1;
    for(size_t i = jb->start_idx; i < jb->end_idx; i += batch){
        size_t upto = i + batch;
        if(upto > jb->end_idx) upto = jb->end_idx;
        // Prefetch next blob location of first segment in next batch
        size_t next_i = upto;
        if(next_i < jb->end_idx){
            size_t next_off = (start_offset + next_i * stride) % blob_size;
#ifdef __GNUC__
            __builtin_prefetch(blob + next_off, 0, 3);
#endif
        }
        for(size_t j = i; j < upto; j++){
            size_t file_off = j * seg_len;
            if(file_off >= jb->out_size) break;

            if(jb->coalesce && stride == seg_len){
                // Merge as many contiguous segments as fit in [j,upto)
                size_t last_j = j;
                size_t total_len = 0;
                while(last_j < upto){
                    size_t seg_file_off = last_j * seg_len;
                    if(seg_file_off >= jb->out_size) break;
                    size_t seg_n = seg_len;
                    if(seg_file_off + seg_n > jb->out_size) seg_n = jb->out_size - seg_file_off;
                    total_len += seg_n;
                    last_j++;
                }
                size_t off = (start_offset + j * stride) % blob_size;
                uint8_t *dst = out + file_off;
                size_t remaining = total_len;
                if(delta == 0){
                    while(remaining > 0){
                        size_t cont = blob_size - off;
                        size_t chunk = remaining < cont ? remaining : cont;
                        if(chunk <= 128) copy_small_vec(dst, blob + off, chunk); else memcpy(dst, blob + off, chunk);
                        dst += chunk;
                        off = (off + chunk) % blob_size;
                        remaining -= chunk;
                    }
                } else {
                    while(remaining > 0){
                        size_t cont = blob_size - off;
                        size_t chunk = remaining < cont ? remaining : cont;
                        const uint8_t *src = blob + off;
                        add_delta_vec(dst, src, chunk, delta);
                        dst += chunk;
                        off = (off + chunk) % blob_size;
                        remaining -= chunk;
                    }
                }
                j = last_j - 1; // for-loop will ++ to last_j
            } else {
                size_t n = seg_len;
                if(file_off + n > jb->out_size) n = jb->out_size - file_off;
                size_t off = (start_offset + j * stride) % blob_size;
                uint8_t *dst = out + file_off;
                if(delta == 0){
                    // Fast path: direct copy, handle wrap
                    size_t cont = blob_size - off;
                    if(cont >= n){
                        if(n <= 128) copy_small_vec(dst, blob + off, n); else memcpy(dst, blob + off, n);
                    } else {
                        if(cont <= 128) copy_small_vec(dst, blob + off, cont); else memcpy(dst, blob + off, cont);
                        size_t tail = n - cont;
                        if(tail <= 128) copy_small_vec(dst + cont, blob, tail); else memcpy(dst + cont, blob, tail);
                    }
                } else {
                    // Apply additive delta modulo 256
                    size_t copied = 0;
                    while(copied < n){
                        size_t cont = blob_size - off;
                        size_t chunk = (n - copied < cont) ? (n - copied) : cont;
                        const uint8_t *src = blob + off;
                        add_delta_vec(dst + copied, src, chunk, delta);
                        copied += chunk;
                        off = (off + chunk) % blob_size;
                    }
                }
            }
        }
    }
    return NULL;
}

static const char *get_arg(int argc, char **argv, const char *key){
    for(int i=1;i<argc-1;i++) if(strcmp(argv[i], key)==0) return argv[i+1];
    return NULL;
}

static bool has_flag(int argc, char **argv, const char *key){
    for(int i=1;i<argc;i++) if(strcmp(argv[i], key)==0) return true;
    return false;
}

int main(int argc, char **argv){
    const char *blob_name = get_arg(argc, argv, "--blob-name");
    const char *blob_size_s = get_arg(argc, argv, "--blob-size"); // bytes
    const char *out_path = get_arg(argc, argv, "--out");
    const char *file_size_s = get_arg(argc, argv, "--file-size"); // bytes
    const char *count_s = get_arg(argc, argv, "--count");
    const char *seg_len_s = get_arg(argc, argv, "--seg-len");
    const char *start_off_s = get_arg(argc, argv, "--start-offset");
    const char *stride_s = get_arg(argc, argv, "--stride");
    const char *delta_s = get_arg(argc, argv, "--delta");
    const char *threads_s = get_arg(argc, argv, "--threads");
    const char *aff_s = get_arg(argc, argv, "--affinity");
    const char *madvise_s = get_arg(argc, argv, "--madvise");
    const char *huge_s = get_arg(argc, argv, "--hugehint");
    const char *batch_s = get_arg(argc, argv, "--batch");
    const char *coalesce_s = get_arg(argc, argv, "--coalesce");
    const char *numa_s = get_arg(argc, argv, "--numa"); // auto|none|node:N
    const char *numa_interleave_s = get_arg(argc, argv, "--numa-interleave"); // 0|1
    // New optional flags
    const char *mlock_s = get_arg(argc, argv, "--mlock"); // 0|1
    const char *out_huge_dir = get_arg(argc, argv, "--out-hugefs-dir"); // path to hugetlbfs mount
    const char *blob_file = get_arg(argc, argv, "--blob-file"); // optional: path to blob file (hugetlbfs)

    if(!blob_name || !blob_size_s || !out_path || !file_size_s || !count_s || !seg_len_s || !start_off_s || !stride_s || !delta_s){
        die("Usage: %s --blob-name NAME --blob-size BYTES --out PATH --file-size BYTES --count N --seg-len BYTES --start-offset BYTES --stride BYTES --delta 0..255 [--threads N] [--madvise 0|1] [--hugehint 0|1] [--mlock 0|1] [--out-hugefs-dir DIR]", argv[0]);
    }

    size_t blob_size = strtoull(blob_size_s, NULL, 10);
    size_t file_size = strtoull(file_size_s, NULL, 10);
    size_t count = strtoull(count_s, NULL, 10);
    size_t seg_len = strtoull(seg_len_s, NULL, 10);
    size_t start_offset = strtoull(start_off_s, NULL, 10);
    size_t stride = strtoull(stride_s, NULL, 10);
    int delta = atoi(delta_s) & 0xFF;

    long threads = threads_s ? strtol(threads_s, NULL, 10) : get_cpu_count();
    if(threads < 1) threads = 1;
    bool use_affinity = aff_s ? (strcmp(aff_s, "0") != 0 && strcasecmp(aff_s, "false") != 0) : true;
    bool use_madvise = madvise_s ? (strcmp(madvise_s, "0") != 0 && strcasecmp(madvise_s, "false") != 0) : true;
    bool use_huge = huge_s ? (strcmp(huge_s, "0") != 0 && strcasecmp(huge_s, "false") != 0) : false;
    size_t batch = batch_s ? (size_t)strtoull(batch_s, NULL, 10) : 1;
    if(batch == 0) batch = 1;
    bool use_coalesce = coalesce_s ? (strcmp(coalesce_s, "0") != 0 && strcasecmp(coalesce_s, "false") != 0) : true;
    bool lock_pages = mlock_s ? ((strcmp(mlock_s, "0") != 0) && (strcasecmp(mlock_s, "false") != 0)) : false;

    // NUMA selection
    bool want_numa = true;
    int force_node = -1;
    if(numa_s){
        if(strcasecmp(numa_s, "none") == 0) want_numa = false;
        else if(strncasecmp(numa_s, "node:", 5) == 0){
            want_numa = true;
            force_node = atoi(numa_s + 5);
        } else {
            // auto
            want_numa = true;
        }
    }
    bool numa_interleave = (numa_interleave_s ? (strcmp(numa_interleave_s, "0") != 0 && strcasecmp(numa_interleave_s, "false") != 0) : false);

    // Ensure blob name starts with '/'
    char shm_name[512];
    if(blob_name[0] == '/') snprintf(shm_name, sizeof(shm_name), "%s", blob_name);
    else snprintf(shm_name, sizeof(shm_name), "/%s", blob_name);

    const uint8_t *blob = NULL;
    size_t map_len_blob = blob_size;
    if(blob_file && blob_file[0] != '\0'){
        // Map blob from file path (e.g., hugetlbfs)
        int bfd = open(blob_file, O_RDONLY);
        if(bfd < 0) die("open blob_file failed: %s", strerror(errno));
        struct stat st; if(fstat(bfd, &st) != 0) die("fstat blob_file failed: %s", strerror(errno));
        if((size_t)st.st_size < blob_size) die("blob_file smaller (%zu) than requested blob_size (%zu)", (size_t)st.st_size, blob_size);
        map_len_blob = (size_t)st.st_size;
        int mmap_flags_blob = MAP_SHARED;
#ifdef MAP_POPULATE
        mmap_flags_blob |= MAP_POPULATE;
#endif
        blob = mmap(NULL, map_len_blob, PROT_READ, mmap_flags_blob, bfd, 0);
        if(blob == MAP_FAILED) die("mmap blob_file failed: %s", strerror(errno));
        close(bfd);
    } else {
        // Open shared memory
        int shm_fd = shm_open(shm_name, O_RDONLY, 0);
        if(shm_fd < 0) die("shm_open('%s') failed: %s", shm_name, strerror(errno));
        struct stat st; if(fstat(shm_fd, &st) != 0) die("fstat shm failed: %s", strerror(errno));
        if((size_t)st.st_size < blob_size) die("shared memory smaller (%zu) than requested blob_size (%zu)", (size_t)st.st_size, blob_size);
        map_len_blob = blob_size;
        int mmap_flags_blob = MAP_SHARED;
#ifdef MAP_POPULATE
        mmap_flags_blob |= MAP_POPULATE;
#endif
        blob = mmap(NULL, map_len_blob, PROT_READ, mmap_flags_blob, shm_fd, 0);
        if(blob == MAP_FAILED) die("mmap shm failed: %s", strerror(errno));
        close(shm_fd);
    }

    // Prepare output mapping (regular fs or hugetlbfs)
    uint8_t *out = NULL;
    int out_fd = -1;
    bool out_on_hugefs = false;
    char huge_tmp_path[512] = {0};

    if(out_huge_dir && out_huge_dir[0] != '\0'){
        char tmpl[512];
        snprintf(tmpl, sizeof(tmpl), "%s/pfs_out_XXXXXX", out_huge_dir);
        int hfd = mkstemp(tmpl);
        if(hfd < 0) die("mkstemp in hugefs dir failed: %s", strerror(errno));
        // ftruncate may require rounding up to huge page size (2MB or 1GB)
        size_t map_len_out = file_size;
        if(ftruncate(hfd, (off_t)map_len_out) != 0){
            if(errno == EINVAL){
                // try 2MB multiple
                size_t two_mb = 2UL*1024UL*1024UL;
                size_t s2 = (file_size + two_mb - 1) / two_mb * two_mb;
                if(ftruncate(hfd, (off_t)s2) != 0){
                    // try 1GB multiple
                    size_t one_g = 1024UL*1024UL*1024UL;
                    size_t s3 = (file_size + one_g - 1) / one_g * one_g;
                    if(ftruncate(hfd, (off_t)s3) != 0){
                        die("ftruncate hugefs out failed: %s", strerror(errno));
                    } else {
                        map_len_out = s3;
                    }
                } else {
                    map_len_out = s2;
                }
            } else {
                die("ftruncate hugefs out failed: %s", strerror(errno));
            }
        }
        int mmap_flags_out = MAP_SHARED;
#ifdef MAP_POPULATE
        // For NUMA first-touch, avoid pre-population
        if(!(want_numa)) mmap_flags_out |= MAP_POPULATE;
#endif
        out = mmap(NULL, map_len_out, PROT_WRITE | PROT_READ, mmap_flags_out, hfd, 0);
        if(out == MAP_FAILED) die("mmap hugefs out failed: %s", strerror(errno));
        out_fd = hfd;
        out_on_hugefs = true;
        snprintf(huge_tmp_path, sizeof(huge_tmp_path), "%s", tmpl);
        // Note: we'll msync/munmap using map_len_out, but only write file_size bytes
    } else {
        int ofd = open(out_path, O_CREAT | O_TRUNC | O_RDWR, 0644);
        if(ofd < 0) die("open out failed: %s", strerror(errno));
        if(ftruncate(ofd, (off_t)file_size) != 0) die("ftruncate out failed: %s", strerror(errno));
        int mmap_flags_out = MAP_SHARED;
#ifdef MAP_POPULATE
        // For NUMA first-touch, avoid pre-population
        if(!(want_numa)) mmap_flags_out |= MAP_POPULATE;
#endif
        out = mmap(NULL, file_size, PROT_WRITE | PROT_READ, mmap_flags_out, ofd, 0);
        if(out == MAP_FAILED) die("mmap out failed: %s", strerror(errno));
        out_fd = ofd;
    }

    // Advise kernel on access patterns
#ifdef __linux__
    if(use_madvise){
        madvise((void*)blob, blob_size, MADV_WILLNEED);
        madvise(out, file_size, MADV_WILLNEED);
#ifdef MADV_SEQUENTIAL
        madvise(out, file_size, MADV_SEQUENTIAL);
#endif
#ifdef MADV_HUGEPAGE
        if(use_huge) { madvise(out, file_size, MADV_HUGEPAGE); madvise((void*)blob, blob_size, MADV_HUGEPAGE); }
#endif
    }
    // Optional: lock pages into RAM (best effort)
    if(lock_pages){
        if(mlock((void*)blob, map_len_blob) != 0){ fprintf(stderr, "Warning: mlock(blob) failed: %s\n", strerror(errno)); }
        if(mlock(out, file_size) != 0){ fprintf(stderr, "Warning: mlock(out) failed: %s\n", strerror(errno)); }
    }
#endif
#ifdef HAVE_LIBNUMA
    bool have_numa = (numa_available() != -1);
    if(!(have_numa)) want_numa = false;
    if(want_numa && numa_interleave){
        struct bitmask *all = numa_all_nodes_ptr;
        numa_set_interleave_mask(all);
    }
#endif

    // Create threads and partition work by segment index
    pthread_t *tids = calloc((size_t)threads, sizeof(pthread_t));
    job_t *jobs = calloc((size_t)threads, sizeof(job_t));
    if(!tids || !jobs) die("alloc threads failed");

    size_t per = count / (size_t)threads;
    long ncpus = get_cpu_count();
    int nnodes = 1;
#ifdef HAVE_LIBNUMA
    if(want_numa){ nnodes = numa_max_node() + 1; }
#endif
    size_t rem = count % (size_t)threads;
    size_t cur = 0;
    for(long i=0;i<threads;i++){
        size_t take = per + (i < rem ? 1 : 0);
        jobs[i].out_base = out;
        jobs[i].out_size = file_size;
        jobs[i].blob = blob;
        jobs[i].blob_size = blob_size;
        jobs[i].seg_len = seg_len;
        jobs[i].count = count;
        jobs[i].start_offset = start_offset;
        jobs[i].stride = stride;
        jobs[i].delta = (uint8_t)delta;
        jobs[i].start_idx = cur;
        jobs[i].end_idx = cur + take;
        jobs[i].cpu_id = (use_affinity ? (int)(i % (ncpus > 0 ? ncpus : 1)) : -1);
        jobs[i].batch = batch;
        jobs[i].coalesce = use_coalesce;
#ifdef HAVE_LIBNUMA
        int nd = -1;
        if(want_numa){ nd = (force_node >= 0 ? force_node : (int)(i % nnodes)); }
        jobs[i].numa_node = nd;
#else
        jobs[i].numa_node = -1;
#endif
        cur += take;
        if(pthread_create(&tids[i], NULL, worker, &jobs[i]) != 0) die("pthread_create failed");
    }

    for(long i=0;i<threads;i++) pthread_join(tids[i], NULL);

    // Flush and unmap
    // We don't know actual map length here if hugefs rounded; use file_size as minimum.
    // For safety, msync/munmap should match the length passed to mmap. Track via out_fd and fstat.
    size_t map_len_used = file_size;
    if(out_fd >= 0){ struct stat st_out; if(fstat(out_fd, &st_out) == 0 && (size_t)st_out.st_size >= file_size) map_len_used = (size_t)st_out.st_size; }
    msync(out, map_len_used, MS_SYNC);
    munmap((void*)blob, map_len_blob);
    munmap(out, map_len_used);
    if(out_fd >= 0) close(out_fd);
    if(out_on_hugefs && huge_tmp_path[0] != '\0') unlink(huge_tmp_path);

    free(tids); free(jobs);
    return 0;
}
