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
    const char *host = getenv("HOST"); if (!host) host = "127.0.0.1";
    const char *port_s = getenv("PORT"); int port = port_s ? atoi(port_s) : 9000;
    const char *len_s = getenv("LEN"); int payload_len = len_s ? atoi(len_s) : 1024;
    const char *dur_s = getenv("DURATION"); double duration_s = dur_s ? atof(dur_s) : 5.0;
    const char *pps_s = getenv("PPS"); double pps = pps_s ? atof(pps_s) : 0.0; /* 0 = unthrottled */

    if (payload_len < 0 || payload_len > 65507 - (int)sizeof(yeet_hdr_v0_t)) {
        fprintf(stderr, "LEN must be between 0 and %d\n", 65507 - (int)sizeof(yeet_hdr_v0_t));
        return 2;
    }

    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) { perror("socket"); return 1; }
    /* Optional send buffer size */
    const char *sbuf_s = getenv("SENDBUF");
    if (sbuf_s) {
        int snd = atoi(sbuf_s);
        if (snd > 0) (void)setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &snd, sizeof(snd));
    }

    struct sockaddr_in dst = {0};
    dst.sin_family = AF_INET;
    dst.sin_port = htons((uint16_t)port);
    if (inet_pton(AF_INET, host, &dst.sin_addr) != 1) {
        fprintf(stderr, "bad HOST %s\n", host); return 2;
    }

    size_t pkt_len = sizeof(yeet_hdr_v0_t) + (size_t)payload_len;
    uint8_t *pkt = (uint8_t*)malloc(pkt_len);
    if (!pkt) { perror("malloc"); return 1; }
    memset(pkt + sizeof(yeet_hdr_v0_t), 0xAB, (size_t)payload_len);

    uint64_t seq = 0;
    uint64_t start = now_ns();
    uint64_t next_report = start + 500000000ull; /* 0.5 s */
    uint64_t end = start + (uint64_t)(duration_s * 1e9);
    uint64_t sent_bytes = 0, sent_pkts = 0;

    double interval_ns = 0.0;
    if (pps > 0.0) interval_ns = 1e9 / pps;
    uint64_t next_deadline = start;

    while (now_ns() < end) {
        yeet_hdr_v0_t *h = (yeet_hdr_v0_t*)pkt;
        yeet_fill_hdr(h, seq++, (uint16_t)payload_len);
        ssize_t n = sendto(fd, pkt, pkt_len, 0, (struct sockaddr*)&dst, sizeof(dst));
        if (n < 0) {
            if (errno == EINTR) continue; perror("sendto"); break;
        }
        sent_bytes += (uint64_t)n;
        sent_pkts++;

        uint64_t t = now_ns();
        if (t >= next_report) {
            double dt = (double)(t - start) / 1e9;
            double gbps = (sent_bytes / (1024.0*1024.0*1024.0)) / dt;
            fprintf(stdout, "[yeet] pkts=%llu bytes=%llu elapsed=%.3f s rate=%.3f GiB/s\n",
                    (unsigned long long)sent_pkts, (unsigned long long)sent_bytes, dt, gbps);
            next_report = t + 500000000ull;
        }
        if (interval_ns > 0.0) {
            next_deadline += (uint64_t)interval_ns;
            while (now_ns() < next_deadline) { /* busy wait */ }
        }
    }
    close(fd);
    return 0;
}
