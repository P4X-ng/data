// SPDX-License-Identifier: MIT
// Userspace helper to control /dev/pfs_ringpeek (PacketFS read-only MMIO window)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>

#include "../../../realsrc/packetfs/uapi/pfs_ringpeek.h"

static void usage(const char* prog){
    fprintf(stderr, "Usage: %s --bar N --offset HEX --len N [--device /dev/pfs_ringpeek] [--hexdump]\n", prog);
}

static void hexline(uint64_t off, const unsigned char* p, size_t n){
    fprintf(stdout, "%08llx  ", (unsigned long long)off);
    for(size_t i=0;i<16;i++){
        if(i<n) fprintf(stdout, "%02x ", p[i]); else fprintf(stdout, "   ");
        if(i==7) fputc(' ', stdout);
    }
    fputc(' ', stdout);
    for(size_t i=0;i<16;i++){
        unsigned char c = (i<n)?p[i]:'.';
        fputc((c>=32 && c<127)?c:'.', stdout);
    }
    fputc('\n', stdout);
}

int main(int argc, char** argv){
    const char* dev = "/dev/pfs_ringpeek";
    int hexdump = 0;
    struct pfs_ringpeek_window win = {0};

    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i], "--device") && i+1<argc){ dev = argv[++i]; }
        else if(!strcmp(argv[i], "--bar") && i+1<argc){ win.bar = (uint32_t)strtoul(argv[++i], NULL, 0); }
        else if(!strcmp(argv[i], "--offset") && i+1<argc){ win.offset = strtoull(argv[++i], NULL, 0); }
        else if(!strcmp(argv[i], "--len") && i+1<argc){ win.length = (uint32_t)strtoul(argv[++i], NULL, 0); }
        else if(!strcmp(argv[i], "--hexdump")){ hexdump = 1; }
        else { usage(argv[0]); return 2; }
    }
    if(win.length == 0){ usage(argv[0]); return 2; }

    int fd = open(dev, O_RDONLY);
    if(fd < 0){ perror("open pfs_ringpeek"); return 1; }

    if(ioctl(fd, PFS_RINGPEEK_IOC_SET_WINDOW, &win) != 0){ perror("ioctl SET_WINDOW"); close(fd); return 1; }

    unsigned char* buf = (unsigned char*)malloc(win.length);
    if(!buf){ perror("malloc"); close(fd); return 1; }

    ssize_t r = read(fd, buf, win.length);
    if(r < 0){ perror("read"); free(buf); close(fd); return 1; }

    if(hexdump){
        size_t off = 0;
        while(off < (size_t)r){
            size_t n = ((size_t)r - off) > 16 ? 16 : ((size_t)r - off);
            hexline(win.offset + off, buf + off, n);
            off += n;
        }
    } else {
        if(write(STDOUT_FILENO, buf, (size_t)r) < 0){ perror("write stdout"); }
    }

    free(buf);
    close(fd);
    return 0;
}