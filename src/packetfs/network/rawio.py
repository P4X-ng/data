import socket
import struct
from typing import Iterable

ETH_P_ALL = 0x0003
ETH_P_PFS = 0x1337  # provisional EtherType
DEST_MAC = b"\xff\xff\xff\xff\xff\xff"


def make_eth_header(src_mac: bytes, dst_mac: bytes = DEST_MAC, ethertype: int = ETH_P_PFS) -> bytes:
    return dst_mac + src_mac + struct.pack('!H', ethertype)


def get_if_mac(ifname: str) -> bytes:
    import fcntl, os
    SIOCGIFHWADDR = 0x8927
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ifr = struct.pack('256s', ifname[:15].encode())
    res = fcntl.ioctl(s.fileno(), SIOCGIFHWADDR, ifr)
    return res[18:24]


def open_tx_socket(ifname: str):
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
    s.bind((ifname, 0))
    return s


def send_frames(ifname: str, payloads: Iterable[bytes]):
    mac = get_if_mac(ifname)
    eth = make_eth_header(mac)
    s = open_tx_socket(ifname)
    for pl in payloads:
        frame = eth + pl
        if len(frame) < 60:
            frame += b"\x00" * (60 - len(frame))
        s.send(frame)
