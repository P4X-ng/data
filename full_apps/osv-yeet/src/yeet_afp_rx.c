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

#ifndef TPACKET3_HDRLEN
#include <linux/if_packet.h>
#endif

/* RX via TPACKET_V3 PACKET_RX_RING with block batching */

static uint64_t now_ns(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + (uint64_t)ts.tv_nsec; }

static inline void cpu_op_apply(uint8_t *p, size_t n, int op, uint8_t imm){
    if (op == 1){ for (size_t i=0;i<n;i++) p[i] ^= imm; }
    else if (op == 2){ for (size_t i=0;i<n;i++) p[i] = (uint8_t)(p[i] + imm); }
}

int main(int argc, char **argv){
    const char *iface = getenv("IFACE"); if(!iface) iface = "lo";
    const char *dur_s = getenv("DURATION"); double duration_s = dur_s? atof(dur_s): 5.0;
    const char *rep_ms_s = getenv("REPORT_MS"); int report_ms = rep_ms_s? atoi(rep_ms_s): 500;
    const char *op_s = getenv("PFS_OP"); int op = op_s? atoi(op_s): 0;
    const char *imm_s = getenv("IMM"); uint8_t imm = imm_s? (uint8_t)atoi(imm_s): 0;
    const char *frame_sz_s = getenv("FRAME_SZ"); int frame_sz = frame_sz_s? atoi(frame_sz_s): 2048;
    const char *block_sz_s = getenv("BLOCK_SZ"); int block_sz = block_sz_s? atoi(block_sz_s): (1<<20);
    const char *frames_pb_s = getenv("FRAMES_PER_BLOCK"); int frames_pb = frames_pb_s? atoi(frames_pb_s): 512;
    const char *blocks_s = getenv("BLOCKS"); int blocks = blocks_s? atoi(blocks_s): 64;
    const char *retire_ms_s = getenv("RETIRE_MS"); int retire_ms = retire_ms_s? atoi(retire_ms_s): 100;

    int sock = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (sock < 0){ perror("socket"); return 1; }

    struct tpacket_req3 req; memset(&req, 0, sizeof(req));
    req.tp_frame_size = frame_sz;
    req.tp_block_size = block_sz;
    req.tp_frames_per_block = frames_pb;
    req.tp_block_nr = blocks;
    req.tp_retire_blk_tov = retire_ms; /* ms */
    req.tp_feature_req_word = TP_FT_REQ_FILL_RXHASH;

    int ver = TPACKET_V3; if (setsockopt(sock, SOL_PACKET, PACKET_VERSION, &ver, sizeof(ver)) < 0){ perror("PACKET_VERSION"); return 1; }
    if (setsockopt(sock, SOL_PACKET, PACKET_RX_RING, &req, sizeof(req)) < 0){ perror("PACKET_RX_RING"); return 1; }

    size_t map_len = (size_t)req.tp_block_size * req.tp_block_nr;
    uint8_t *ring = (uint8_t*)mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED, sock, 0);
    if (ring == MAP_FAILED){ perror("mmap"); return 1; }

    /* Bind */
    int ifindex = afp_get_ifindex(sock, iface);
    if (ifindex < 0){ fprintf(stderr, "bad IFACE %s\n", iface); return 2; }
    struct sockaddr_ll sll; memset(&sll, 0, sizeof(sll));
    sll.sll_family = AF_PACKET; sll.sll_protocol = htons(ETH_P_ALL); sll.sll_ifindex = ifindex;
    if (bind(sock, (struct sockaddr*)&sll, sizeof(sll)) < 0){ perror("bind"); return 1; }

    /* Optional promisc to ensure loopback of our packets is visible */
    struct packet_mreq mreq; memset(&mreq, 0, sizeof(mreq));
    mreq.mr_ifindex = ifindex; mreq.mr_type = PACKET_MR_PROMISC;
    setsockopt(sock, SOL_PACKET, PACKET_ADD_MEMBERSHIP, &mreq, sizeof(mreq));

    uint64_t start = now_ns(); uint64_t end = start + (uint64_t)(duration_s * 1e9);
    uint64_t next_report = start + (uint64_t)report_ms * 1000000ull;
    uint64_t bytes = 0, pkts = 0; uint64_t pcpu_ops = 0;

    uint32_t block_num = 0; (void)block_num;
    /* Iterate blocks circularly */
    for(;;){
        struct tpacket_block_desc *bd = (struct tpacket_block_desc*)(ring + block_num * req.tp_block_size);
        if ((bd->hdr.bh1.block_status & TP_STATUS_USER) == 0){
            /* Sleep briefly */
            struct timespec ts = {0, 1000000}; nanosleep(&ts, NULL);
            if (now_ns() >= end) break; else continue;
        }
        /* Walk frames in this block */
        uint32_t off = bd->hdr.bh1.offset_to_first_pkt;
        for (uint32_t i=0; i<bd->hdr.bh1.num_pkts; i++){
            struct tpacket3_hdr *tp3 = (struct tpacket3_hdr*)((uint8_t*)bd + off);
            uint8_t *mac = (uint8_t*)tp3 + tp3->tp_mac;
            uint8_t *net = (uint8_t*)tp3 + tp3->tp_net;
            (void)net;
            if (tp3->tp_snaplen >= sizeof(struct ether_header) + sizeof(pfs_hdr_t)){
                struct ether_header *eh = (struct ether_header*)mac;
                if (ntohs(eh->ether_type) == PFS_ETHERTYPE){
                    pfs_hdr_t *ph = (pfs_hdr_t*)(mac + sizeof(struct ether_header));
                    size_t pay = tp3->tp_snaplen - sizeof(struct ether_header) - sizeof(pfs_hdr_t);
                    uint8_t *pl = (uint8_t*)(ph + 1);
                    if (op) cpu_op_apply(pl, pay, op, imm);
                }
            }
            bytes += tp3->tp_snaplen; pkts++;
            off += tp3->tp_next_offset;
        }
        __sync_synchronize();
        bd->hdr.bh1.block_status = TP_STATUS_KERNEL;
        block_num = (block_num + 1) % req.tp_block_nr;

        uint64_t t = now_ns();
        if (t >= next_report){
            double dt = (double)(t - start) / 1e9;
            double mbps = (bytes / (1024.0*1024.0)) / (dt>0?dt:1);
            fprintf(stdout, "[afp-rx] pkts=%llu bytes=%llu elapsed=%.3f MB/s=%.2f\n",
                    (unsigned long long)pkts, (unsigned long long)bytes, dt, mbps);
            next_report = t + (uint64_t)report_ms * 1000000ull;
        }
        if (now_ns() >= end) break;
    }

    munmap(ring, map_len);
    return 0;
}
