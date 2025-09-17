#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

// Realtek RTL8168/8169 interesting registers
#define R816X_TNPDS_LO 0x20  // TX Normal Priority Desc Start Low
#define R816X_TNPDS_HI 0x24  // High
#define R816X_RDSAR_LO 0xE4  // RX Desc Start Low
#define R816X_RDSAR_HI 0xE8  // High

static int parse_resource_ranges(const char* bdf, unsigned long long ranges[6][3]){
    char p[256];
    snprintf(p, sizeof(p), "/sys/bus/pci/devices/%s/resource", bdf);
    FILE* f = fopen(p, "r");
    if(!f) return -1;
    char line[256]; int i=0;
    while(i<6 && fgets(line, sizeof(line), f)){
        // Each line: start end flags (hex)
        unsigned long long start=0, end=0, flags=0;
        if(sscanf(line, "%llx %llx %llx", &start, &end, &flags)==3){
            ranges[i][0]=start; ranges[i][1]=end; ranges[i][2]=flags; i++;
        }
    }
    fclose(f); return 0;
}

static int choose_bar(const unsigned long long ranges[6][3]){
    // Prefer BAR4 when present (16 KiB MMIO on these revs), else BAR2, else BAR0
    if(ranges[4][1] > ranges[4][0]) return 4;
    if(ranges[2][1] > ranges[2][0]) return 2;
    if(ranges[0][1] > ranges[0][0]) return 0;
    return -1;
}

int main(int argc, char** argv){
    const char* bdf = "0000:82:00.0"; // default
    if(argc >= 2){ bdf = argv[1]; }

    unsigned long long ranges[6][3] = {0};
    if(parse_resource_ranges(bdf, ranges)!=0){
        fprintf(stderr, "[rtl_peek_mmio] Failed to read resource ranges for %s: %s\n", bdf, strerror(errno));
        return 1;
    }
    int bar = choose_bar(ranges);
    if(bar < 0){ fprintf(stderr, "[rtl_peek_mmio] No suitable BAR for %s\n", bdf); return 1; }

    // First attempt: sysfs resource mmap (may be disallowed)
    char path[256]; snprintf(path, sizeof(path), "/sys/bus/pci/devices/%s/resource%d", bdf, bar);
    int fd = open(path, O_RDONLY);
    size_t len = (size_t)(ranges[bar][1] - ranges[bar][0] + 1);
    void* mm = MAP_FAILED;
    if(fd >= 0){
        mm = mmap(NULL, len, PROT_READ, MAP_SHARED, fd, 0);
    }

    if(mm == MAP_FAILED){
        if(fd >= 0) close(fd);
        // Fallback: /dev/mem map of BAR phys
        int memfd = open("/dev/mem", O_RDONLY | O_SYNC);
        if(memfd < 0){ fprintf(stderr, "[rtl_peek_mmio] /dev/mem open failed: %s\n", strerror(errno)); return 1; }
        off_t phys = (off_t)ranges[bar][0];
        size_t pagesz = (size_t)sysconf(_SC_PAGESIZE);
        off_t page_base = phys & ~(off_t)(pagesz - 1);
        size_t off_in_page = (size_t)(phys - page_base);
        size_t map_len = off_in_page + len;
        void* map = mmap(NULL, map_len, PROT_READ, MAP_SHARED, memfd, page_base);
        if(map == MAP_FAILED){ fprintf(stderr, "[rtl_peek_mmio] /dev/mem mmap failed: %s\n", strerror(errno)); close(memfd); return 1; }
        volatile uint8_t* base = (volatile uint8_t*)map + off_in_page;
        uint32_t t_lo = *(volatile uint32_t*)(base + R816X_TNPDS_LO);
        uint32_t t_hi = *(volatile uint32_t*)(base + R816X_TNPDS_HI);
        uint32_t r_lo = *(volatile uint32_t*)(base + R816X_RDSAR_LO);
        uint32_t r_hi = *(volatile uint32_t*)(base + R816X_RDSAR_HI);
        uint64_t t_base = ((uint64_t)t_hi << 32) | t_lo;
        uint64_t r_base = ((uint64_t)r_hi << 32) | r_lo;
        printf("rtl_peek_mmio: bdf=%s bar=%d phys=[0x%016llx..0x%016llx] size=%llu via /dev/mem\n", bdf, bar,
               ranges[bar][0], ranges[bar][1], (unsigned long long)len);
        printf("  TNPDS base = 0x%016" PRIx64 "\n", t_base);
        printf("  RDSAR base = 0x%016" PRIx64 "\n", r_base);
        munmap((void*)map, map_len); close(memfd);
        return 0;
    } else {
        volatile uint8_t* base = (volatile uint8_t*)mm;
        uint32_t t_lo = *(volatile uint32_t*)(base + R816X_TNPDS_LO);
        uint32_t t_hi = *(volatile uint32_t*)(base + R816X_TNPDS_HI);
        uint32_t r_lo = *(volatile uint32_t*)(base + R816X_RDSAR_LO);
        uint32_t r_hi = *(volatile uint32_t*)(base + R816X_RDSAR_HI);
        uint64_t t_base = ((uint64_t)t_hi << 32) | t_lo;
        uint64_t r_base = ((uint64_t)r_hi << 32) | r_lo;
        printf("rtl_peek_mmio: bdf=%s bar=%d file=%s\n", bdf, bar, path);
        printf("  BAR%u phys=[0x%016llx..0x%016llx] size=%llu\n", bar,
               ranges[bar][0], ranges[bar][1], (unsigned long long)len);
        printf("  TNPDS base = 0x%016" PRIx64 "\n", t_base);
        printf("  RDSAR base = 0x%016" PRIx64 "\n", r_base);
        munmap(mm, len); close(fd);
        return 0;
    }
}

