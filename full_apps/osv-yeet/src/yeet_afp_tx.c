#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <net/ethernet.h>
#include <netpacket/packet.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include "../include/afp.h"
#include "../include/pfs_raw.h"

/* TX via PACKET_TX_RING (TPACKET_V2). Batches by filling multiple frames then a single sendto() kick. */

#ifndef TPACKET2_HDRLEN
#include <linux/if_packet.h>
#endif

static uint64_t now_ns(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + (uint64_t)ts.tv_nsec; }

static void build_eth(uint8_t *dst, const uint8_t dmac[6], const uint8_t smac[6], uint16_t ethertype){
    struct ether_header *eh = (struct ether_header*)dst;
    memcpy(eh->ether_dhost, dmac, 6);
    memcpy(eh->ether_shost, smac, 6);
    eh->ether_type = htons(ethertype);
}

int main(int argc, char **argv){
    const char *iface = getenv("IFACE"); if(!iface) iface = "lo";
    const char *dst_s = getenv("DST_MAC");
    const char *len_s = getenv("LEN"); int payload_len = len_s? atoi(len_s): 1024;
    const char *dur_s = getenv("DURATION"); double duration_s = dur_s? atof(dur_s): 5.0;
    const char *op_s = getenv("PFS_OP"); int op = op_s? atoi(op_s): 0; /* 0 none, 1 xor, 2 add */
    const char *imm_s = getenv("IMM"); int imm = imm_s? atoi(imm_s): 0;
    const char *batch_s = getenv("BATCH_FRAMES"); int batch_frames = batch_s? atoi(batch_s): 256;
    const char *frame_sz_s = getenv("FRAME_SZ"); int frame_sz = frame_sz_s? atoi(frame_sz_s): 2048;
    const char *block_sz_s = getenv("BLOCK_SZ"); int block_sz = block_sz_s? atoi(block_sz_s): (1<<20);
    const char *blocks_s = getenv("BLOCKS"); int blocks = blocks_s? atoi(blocks_s): 64;

    if (payload_len < 32 || payload_len > frame_sz - 128){
        fprintf(stderr, "LEN out of range for frame size %d\n", frame_sz); return 2;
    }

    int sock = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (sock < 0){ perror("socket"); return 1; }

    /* PACKET_QDISC_BYPASS to avoid qdisc */
    int one = 1; setsockopt(sock, SOL_PACKET, PACKET_QDISC_BYPASS, &one, sizeof(one));

    /* TX ring (TPACKET_V2) */
    struct tpacket_req req; memset(&req, 0, sizeof(req));
    req.tp_block_size = block_sz;
    req.tp_block_nr   = blocks;
    req.tp_frame_size = frame_sz;
    req.tp_frame_nr   = (req.tp_block_size / req.tp_frame_size) * req.tp_block_nr;

    int ver = TPACKET_V2; if (setsockopt(sock, SOL_PACKET, PACKET_VERSION, &ver, sizeof(ver)) < 0) { perror("PACKET_VERSION"); return 1; }
    if (setsockopt(sock, SOL_PACKET, PACKET_TX_RING, &req, sizeof(req)) < 0){ perror("PACKET_TX_RING"); return 1; }

    size_t map_len = (size_t)req.tp_block_size * req.tp_block_nr;
    uint8_t *ring = (uint8_t*)mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED, sock, 0);
    if (ring == MAP_FAILED){ perror("mmap"); return 1; }

    /* Bind to iface */
    int ifindex = afp_get_ifindex(sock, iface);
    if (ifindex < 0){ fprintf(stderr, "bad IFACE %s\n", iface); return 2; }

    uint8_t smac[6] = {0}; afp_get_hwaddr(sock, iface, smac);
    uint8_t dmac[6]; if (dst_s && afp_parse_mac(dst_s, dmac) == 0) { /* ok */ } else { memset(dmac, 0xFF, 6); }

    struct sockaddr_ll sll; memset(&sll, 0, sizeof(sll));
    sll.sll_family = AF_PACKET; sll.sll_protocol = htons(PFS_ETHERTYPE); sll.sll_ifindex = ifindex;
    sll.sll_halen = 6; memcpy(sll.sll_addr, dmac, 6);

    size_t eth_len = sizeof(struct ether_header);
    size_t pfs_len = sizeof(pfs_hdr_t);
    size_t total_l2 = eth_len + pfs_len + (size_t)payload_len;

    /* Loop */
    uint64_t seq = 0; uint64_t start = now_ns(); uint64_t end = start + (uint64_t)(duration_s * 1e9);
    uint32_t frame = 0; uint32_t sent_batches = 0; uint64_t sent_bytes = 0;

    while (now_ns() < end){
        int produced = 0;
        while (produced < batch_frames){
            uint8_t *ptr = ring + (size_t)frame * req.tp_frame_size;
            struct tpacket2_hdr *tph = (struct tpacket2_hdr*)ptr;
            if (!(tph->tp_status & TP_STATUS_AVAILABLE)){
                /* Ring full: kick TX */
                break;
            }
            uint8_t *data = ptr + TPACKET_ALIGN(sizeof(*tph));
            /* Build L2 */
            build_eth(data, dmac, smac, PFS_ETHERTYPE);
            pfs_hdr_t *ph = (pfs_hdr_t*)(data + eth_len);
            pfs_fill_hdr(ph, seq++, (uint32_t)payload_len, (uint8_t)op, (uint8_t)imm);
            uint8_t *pl = (uint8_t*)(ph + 1);
            /* Payload pattern: zero or simple ramp */
            for (int i=0;i<payload_len;i++) pl[i] = (uint8_t)(i + imm);

            tph->tp_len = (uint32_t)total_l2;
            tph->tp_snaplen = (uint32_t)total_l2;
            tph->tp_mac = TPACKET_ALIGN(sizeof(*tph));
            tph->tp_net = tph->tp_mac + sizeof(struct ether_header);
            __sync_synchronize();
            tph->tp_status = TP_STATUS_SEND_REQUEST;

            frame = (frame + 1) % req.tp_frame_nr;
            produced++;
        }
        if (produced == 0){
            /* Ring saturated; yield by sending */
        }
        /* Kick TX for produced or pending */
        if (sendto(sock, NULL, 0, 0, (struct sockaddr*)&sll, sizeof(sll)) < 0) {
            if (errno == EAGAIN || errno == ENOBUFS) continue; perror("sendto"); break;
        }
        sent_batches++;
        sent_bytes += (uint64_t)produced * total_l2;
    }

    double secs = (double)(now_ns() - start) / 1e9;
    double mbps = (sent_bytes / (1024.0*1024.0)) / (secs > 0 ? secs : 1);
    fprintf(stdout, "[afp-tx] bytes=%llu time=%.3f MB/s=%.2f batches=%u\n",
            (unsigned long long)sent_bytes, secs, mbps, sent_batches);
    munmap(ring, map_len);
    return 0;
}
