#ifndef PFS_HUGEBLOB_H
#define PFS_HUGEBLOB_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    void* addr;
    size_t size;
    int fd;
    int hugetlbfs;   // 1 if backed by hugetlbfs file, 0 otherwise
    size_t page_size; // backing page size (2MB typical for hugetlbfs, else system page)
    int keep_file;   // if hugetlbfs-backed: do not truncate to 0 on unmap when set
    char name[256];  // optional name for hugetlbfs file
    char dir[256];   // optional directory for hugetlbfs mount
} PfsHugeBlob;

// Try to map a hugetlbfs file of the given size under huge_dir (e.g., /dev/hugepages).
// On success, returns 0 and fills out; on failure returns -1.
int pfs_hugeblob_map_file(const char* huge_dir, const char* name, size_t size, PfsHugeBlob* out);

// Map a blob using hugetlbfs if possible; otherwise fallback to anonymous mmap with MADV_HUGEPAGE hint.
// huge_dir can be NULL to skip the hugetlbfs attempt.
int pfs_hugeblob_map(size_t size, const char* huge_dir, const char* name, PfsHugeBlob* out);

// Control whether unmap will truncate the hugetlbfs file to 0 (default) or keep it as-is.
void pfs_hugeblob_set_keep(PfsHugeBlob* blob, int keep);

// Prefault/populate the mapping to avoid soft faults during streaming.
// touch_bytes: number of bytes to write per page (typically 1) to ensure population.
void pfs_hugeblob_prefault(PfsHugeBlob* blob, size_t touch_bytes);

// Fill the blob with a deterministic pseudorandom pattern based on seed (for validation/replay stability).
void pfs_hugeblob_fill(PfsHugeBlob* blob, uint64_t seed);

// Unmap and clean up. If hugetlbfs file-backed, truncates and closes fd.
void pfs_hugeblob_unmap(PfsHugeBlob* blob);

#endif // PFS_HUGEBLOB_H

