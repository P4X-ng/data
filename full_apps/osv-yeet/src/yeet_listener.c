#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include "../include/proto.h"

static uint64_t now_ns(void) {
    struct timeval tv; gettimeofday(&tv, NULL);
    return (uint64_t)tv.tv_sec * 1000000000ull + (uint64_t)tv.tv_usec * 1000ull;
}

int main(int argc, char **argv) {
    const char *addr_s = getenv("ADDR"); if (!addr_s) addr_s = "0.0.0.0";
    const char *port_s = getenv("PORT"); int port = port_s ? atoi(port_s) : 9000;
    const char *dur_s = getenv("DURATION"); double duration_s = dur_s ? atof(dur_s) : 0.0; /* 0 = infinite */
    const char *rep_ms_s = getenv("REPORT_MS"); int report_ms = rep_ms_s ? atoi(rep_ms_s) : 500;
    const char *quiet_s = getenv("QUIET"); int quiet = quiet_s ? atoi(quiet_s) : 0;

    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) { perror("socket"); return 1; }

    int yes = 1; (void)setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
    /* Optional receive buffer size */
    const char *rbuf_s = getenv("RECVBUF");
    if (rbuf_s) {
        int rcv = atoi(rbuf_s);
        if (rcv > 0) (void)setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &rcv, sizeof(rcv));
    }

    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_port = htons((uint16_t)port);
    if (inet_pton(AF_INET, addr_s, &addr.sin_addr) != 1) {
        fprintf(stderr, "bad ADDR %s\n", addr_s); return 2;
    }
    if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) { perror("bind"); return 1; }

    uint8_t buf[65536];
    uint64_t start = now_ns();
    uint64_t next_report = start + (uint64_t)report_ms * 1000000ull;
    uint64_t end = (duration_s > 0.0) ? start + (uint64_t)(duration_s * 1e9) : 0;

    uint64_t pkts = 0, bytes = 0;
    uint64_t last_seq = 0; int have_last = 0; uint64_t drops = 0;

    if (!quiet) {
        fprintf(stdout, "[yeet-listen] bind=%s:%d report=%dms duration=%s\n", addr_s, port, report_ms,
                (duration_s > 0.0 ? "finite" : "infinite"));
    }

    for (;;) {
        struct sockaddr_in src; socklen_t slen = sizeof(src);
        ssize_t n = recvfrom(fd, buf, sizeof(buf), 0, (struct sockaddr*)&src, &slen);
        if (n < 0) {
            if (errno == EINTR) continue; perror("recvfrom"); break;
        }
        if ((size_t)n < sizeof(yeet_hdr_v0_t)) continue; /* ignore runt */

        yeet_hdr_v0_t h; memcpy(&h, buf, sizeof(h));
        if (h.magic != YEET_MAGIC || h.ver != YEET_VER) continue; /* ignore non-yeet */
        if (h.hdr_len != (uint16_t)sizeof(yeet_hdr_v0_t)) continue; /* guard */
        uint64_t seq = h.seq;
        uint16_t payload_len = h.len;
        (void)payload_len; /* could validate n == sizeof(h)+payload */

        pkts++; bytes += (uint64_t)n;
        if (have_last && seq > last_seq + 1) drops += (seq - last_seq - 1);
        if (!have_last) have_last = 1; if (seq > last_seq) last_seq = seq;

        uint64_t t = now_ns();
        if (t >= next_report && !quiet) {
            double dt = (double)(t - start) / 1e9;
            double gib_s = (bytes / (1024.0*1024.0*1024.0)) / dt;
            double mpps = (pkts / 1e6) / dt;
            fprintf(stdout, "[yeet-listen] pkts=%llu bytes=%llu drops=%llu elapsed=%.3f s rate=%.3f GiB/s, %.3f Mpps\n",
                    (unsigned long long)pkts, (unsigned long long)bytes, (unsigned long long)drops, dt, gib_s, mpps);
            next_report = t + (uint64_t)report_ms * 1000000ull;
        }
        if (end && t >= end) break;
    }

    close(fd);
    return 0;
}
