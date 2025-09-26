// SPDX-License-Identifier: GPL-2.0
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

// XSK socket map: one entry per RX queue (key == queue id)
struct {
    __uint(type, BPF_MAP_TYPE_XSKMAP);
    __uint(max_entries, 256);
    __type(key, __u32);
    __type(value, __u32);
} xsks_map SEC(".maps");

// Minimal redirector: if a userspace XSK is bound for this queue, redirect; otherwise pass
SEC("xdp")
int xdp_redirect_xsk(struct xdp_md *ctx)
{
    __u32 qid = ctx->rx_queue_index;
    // bpf_redirect_map returns XDP_REDIRECT if key is valid, else XDP_PASS
    if (bpf_map_lookup_elem(&xsks_map, &qid))
        return bpf_redirect_map(&xsks_map, qid, 0);
    return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";

