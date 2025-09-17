// SPDX-License-Identifier: GPL-2.0-only
// Minimal XDP loader for PacketFS AF_XDP redirect program.
// Usage:
//   pfs_xdp_loader attach --iface IFACE [--mode drv|skb|auto] [--obj PATH] [--prog xdp_redirect_xsk] [--pin /sys/fs/bpf/packetfs]
//   pfs_xdp_loader detach --iface IFACE [--mode drv|skb|auto]
//   pfs_xdp_loader status --iface IFACE
// Notes:
//   - Tries native driver mode first, then falls back to generic (skb) mode.
//   - Pins xsks_map if --pin is provided (as pin_dir/xsks_map).

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/if_link.h>
#include <net/if.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <bpf/bpf.h>
#include <bpf/libbpf.h>

static void die(const char* fmt, ...) {
    va_list ap; va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap);
    fputc('\n', stderr); exit(1);
}

static void warnx(const char* fmt, ...) {
    va_list ap; va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap);
    fputc('\n', stderr);
}

static int ensure_dir(const char* path, mode_t mode){
    struct stat st; if(stat(path, &st) == 0){ if(S_ISDIR(st.st_mode)) return 0; errno = ENOTDIR; return -1; }
    return mkdir(path, mode);
}

static int get_ifindex(const char* ifname){
    int ifindex = if_nametoindex(ifname);
    if(ifindex == 0) die("if_nametoindex(%s): %s", ifname, strerror(errno));
    return ifindex;
}

static const char* mode_str(int flags){
    if(flags & XDP_FLAGS_DRV_MODE) return "drv";
    if(flags & XDP_FLAGS_SKB_MODE) return "skb";
    return "auto";
}

static int attach_prog(int ifindex, int prog_fd, int req_flags){
    // Try requested/native first, then fallback to skb
    int ret = bpf_xdp_attach(ifindex, prog_fd, req_flags | XDP_FLAGS_UPDATE_IF_NOEXIST, NULL);
    if(ret < 0){
        // Retry without UPDATE_IF_NOEXIST
        (void)bpf_xdp_detach(ifindex, req_flags, NULL);
        ret = bpf_xdp_attach(ifindex, prog_fd, req_flags, NULL);
    }
    if(ret < 0 && !(req_flags & XDP_FLAGS_SKB_MODE)){
        // Fallback to SKB
        int skb_flags = XDP_FLAGS_SKB_MODE | (req_flags & XDP_FLAGS_REPLACE) ? XDP_FLAGS_REPLACE : 0;
        (void)bpf_xdp_detach(ifindex, skb_flags, NULL);
        ret = bpf_xdp_attach(ifindex, prog_fd, skb_flags, NULL);
        if(ret == 0) warnx("Fell back to XDP generic (skb) mode");
    }
    return ret;
}

static int query_mode(int ifindex, __u32* out_prog_id){
    struct xdp_link_info info = {0};
    int ret = bpf_xdp_query_id(ifindex, XDP_FLAGS_DRV_MODE, &info); // kernel may set info.id
    if(ret == 0 && info.id){ *out_prog_id = info.id; return XDP_FLAGS_DRV_MODE; }
    ret = bpf_xdp_query_id(ifindex, XDP_FLAGS_SKB_MODE, &info);
    if(ret == 0 && info.id){ *out_prog_id = info.id; return XDP_FLAGS_SKB_MODE; }
    *out_prog_id = 0; return 0;
}

static int pin_xsks_map(struct bpf_object* obj, const char* pin_dir){
    if(!pin_dir || !*pin_dir) return 0;
    if(ensure_dir(pin_dir, 0755) != 0){ warnx("pin dir %s: %s", pin_dir, strerror(errno)); return -1; }
    struct bpf_map* map = bpf_object__find_map_by_name(obj, "xsks_map");
    if(!map){ warnx("xsks_map not found in object"); return -1; }
    int map_fd = bpf_map__fd(map);
    if(map_fd < 0){ warnx("xsks_map fd invalid"); return -1; }
    char path[512]; snprintf(path, sizeof(path), "%s/%s", pin_dir, "xsks_map");
    if(bpf_obj_pin(map_fd, path) != 0){ warnx("pin xsks_map: %s", strerror(errno)); return -1; }
    return 0;
}

int main(int argc, char** argv){
    if(argc < 2){
        fprintf(stderr,
            "Usage: %s <attach|detach|status> --iface IFACE [--mode drv|skb|auto] [--obj PATH] [--prog NAME] [--pin DIR]\n",
            argv[0]);
        return 2;
    }
    const char* cmd = argv[1];
    const char* ifname = NULL;
    const char* obj_path = "realsrc/packetfs/network/afxdp/bpf/build/pfs_kern.bpf.o";
    const char* prog_name = "xdp_redirect_xsk";
    const char* pin_dir = NULL;
    int mode_flags = XDP_FLAGS_DRV_MODE; // default to driver/native

    for(int i=2;i<argc;i++){
        if(!strcmp(argv[i], "--iface") && i+1<argc) ifname = argv[++i];
        else if((!strcmp(argv[i], "--dev") || !strcmp(argv[i], "--device")) && i+1<argc) ifname = argv[++i];
        else if(!strcmp(argv[i], "--obj") && i+1<argc) obj_path = argv[++i];
        else if(!strcmp(argv[i], "--prog") && i+1<argc) prog_name = argv[++i];
        else if(!strcmp(argv[i], "--pin") && i+1<argc) pin_dir = argv[++i];
        else if(!strcmp(argv[i], "--mode") && i+1<argc) {
            const char* m = argv[++i];
            if(!strcmp(m, "drv")) mode_flags = XDP_FLAGS_DRV_MODE;
            else if(!strcmp(m, "skb")) mode_flags = XDP_FLAGS_SKB_MODE;
            else mode_flags = 0; // auto
        }
        else if(!strcmp(argv[i], "-h") || !strcmp(argv[i], "--help")){
            fprintf(stderr, "See usage above.\n");
            return 0;
        }
    }
    if(!ifname) die("--iface required");
    int ifindex = get_ifindex(ifname);

    if(!strcmp(cmd, "attach")){
        struct bpf_object* obj = bpf_object__open_file(obj_path, NULL);
        if(!obj) die("open bpf obj %s: %s", obj_path, strerror(errno));
        if(bpf_object__load(obj) != 0) die("load bpf obj: %s", strerror(errno));
        struct bpf_program* prog = bpf_object__find_program_by_name(obj, prog_name);
        if(!prog) die("program '%s' not found in %s", prog_name, obj_path);
        int prog_fd = bpf_program__fd(prog);
        if(prog_fd < 0) die("program fd invalid");

        int ret = attach_prog(ifindex, prog_fd, mode_flags);
        if(ret < 0){
            die("attach failed on %s (mode=%s): %s", ifname, mode_str(mode_flags), strerror(-ret));
        }
        (void)pin_xsks_map(obj, pin_dir);
        __u32 id=0; int m=query_mode(ifindex,&id);
        fprintf(stderr, "[XDP] attached iface=%s mode=%s prog_id=%u\n", ifname, (m==XDP_FLAGS_DRV_MODE?"drv":(m==XDP_FLAGS_SKB_MODE?"skb":"unknown")), id);
        bpf_object__close(obj);
        return 0;
    }
    else if(!strcmp(cmd, "detach")){
        // Try both modes
        (void)bpf_xdp_detach(ifindex, XDP_FLAGS_DRV_MODE, NULL);
        (void)bpf_xdp_detach(ifindex, XDP_FLAGS_SKB_MODE, NULL);
        fprintf(stderr, "[XDP] detached iface=%s\n", ifname);
        return 0;
    }
    else if(!strcmp(cmd, "status")){
        __u32 id=0; int m = query_mode(ifindex, &id);
        if(id){ fprintf(stderr, "[XDP] iface=%s mode=%s prog_id=%u\n", ifname, (m==XDP_FLAGS_DRV_MODE?"drv":(m==XDP_FLAGS_SKB_MODE?"skb":"unknown")), id); return 0; }
        fprintf(stderr, "[XDP] iface=%s not attached\n", ifname);
        return 1;
    }
    else {
        die("Unknown command: %s", cmd);
    }
}

