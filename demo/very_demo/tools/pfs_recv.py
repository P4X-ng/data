import argparse
import socket
import struct
from packetfs.protocol import ProtocolDecoder, SyncConfig

ETH_P_PFS = 0x1337


def recv_frames(ifname: str):
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_PFS))
    s.bind((ifname, 0))
    dec = ProtocolDecoder(SyncConfig(window_pow2=16, window_crc16=True))
    while True:
        frame = s.recv(2048)
        # strip Ethernet header (14 bytes)
        payload = frame[14:]
        info = dec.scan_for_sync(payload)
        if info:
            win, crc = info
            print(f"Got frame payload {len(payload)} bytes | SYNC window={win} crc=0x{crc:04x}")
        else:
            print(f"Got frame payload {len(payload)} bytes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", required=True)
    args = ap.parse_args()
    recv_frames(args.iface)

if __name__ == "__main__":
    main()

