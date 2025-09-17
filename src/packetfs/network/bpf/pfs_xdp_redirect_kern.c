// SPDX-License-Identifier: GPL-2.0
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_XSKMAP);
    __uint(max_entries, 64);
    __type(key, __u32);
    __type(value, __u32);
} xsks_map SEC(".maps");

SEC("xdp")
int xdp_redirect(struct xdp_md *ctx)
{
    __u32 qid = ctx->rx_queue_index;
    return bpf_redirect_map(&xsks_map, qid, 0);
}

char LICENSE[] SEC("license") = "GPL";

