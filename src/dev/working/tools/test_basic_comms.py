#!/usr/bin/env python3
"""
Basic PacketFS communication test with timing and validation.
Tests send/receive functionality and measures baseline performance.
"""
import time
import threading
import argparse
import sys
import queue
from typing import List, Tuple
import socket
import struct
from dataclasses import dataclass

from packetfs.rawio import send_frames, get_if_mac, make_eth_header
from packetfs.protocol import ProtocolEncoder, ProtocolDecoder, SyncConfig
from packetfs import _bitpack

ETH_P_PFS = 0x1337


@dataclass
class TestResult:
    frames_sent: int
    frames_received: int
    sync_frames_detected: int
    total_time: float
    throughput_pps: float
    avg_frame_size: float
    sync_errors: int = 0


def create_test_payload(enc: ProtocolEncoder, ref_count: int = 64) -> bytes:
    """Generate a test payload with specified number of refs."""
    out = bytearray(1500)  # Max Ethernet payload
    refs = bytes((i % 256) for i in range(ref_count))

    if _bitpack is None:
        raise RuntimeError("C extension not available")

    bits = enc.pack_refs(out, 0, refs, 8)  # L1 tier, 8-bit refs
    extra = enc.maybe_sync()

    nbytes = (bits + 7) // 8
    payload = bytearray(out[:nbytes])

    if extra:
        payload += extra

    return bytes(payload)


def receiver_thread(ifname: str, test_duration: float, result_queue: queue.Queue):
    """Receiver thread that captures and analyzes frames."""
    try:
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_PFS))
        s.bind((ifname, 0))
        s.settimeout(1.0)  # 1 second timeout

        dec = ProtocolDecoder(SyncConfig(window_pow2=16, window_crc16=True))

        frames_received = 0
        sync_frames = 0
        sync_errors = 0
        total_frame_size = 0
        start_time = time.time()

        print(f"🔍 Receiver starting on {ifname}...")

        while time.time() - start_time < test_duration:
            try:
                frame = s.recv(2048)
                frames_received += 1

                # Strip Ethernet header (14 bytes)
                payload = frame[14:]
                total_frame_size += len(payload)

                # Check for SYNC
                sync_info = dec.scan_for_sync(payload)
                if sync_info:
                    win, crc = sync_info
                    sync_frames += 1
                    print(
                        f"📡 SYNC frame #{sync_frames}: window={win}, crc=0x{crc:04x}"
                    )
                else:
                    print(f"📦 Data frame #{frames_received}: {len(payload)} bytes")

            except socket.timeout:
                continue
            except Exception as e:
                print(f"⚠️  Receiver error: {e}")
                sync_errors += 1

        elapsed = time.time() - start_time
        avg_frame_size = (
            total_frame_size / frames_received if frames_received > 0 else 0
        )
        throughput = frames_received / elapsed if elapsed > 0 else 0

        result = TestResult(
            frames_sent=0,  # Will be filled by sender
            frames_received=frames_received,
            sync_frames_detected=sync_frames,
            total_time=elapsed,
            throughput_pps=throughput,
            avg_frame_size=avg_frame_size,
            sync_errors=sync_errors,
        )

        result_queue.put(result)
        print(f"🏁 Receiver finished: {frames_received} frames, {throughput:.1f} pps")

    except Exception as e:
        print(f"💥 Receiver thread failed: {e}")
        result_queue.put(None)


def sender_test(
    ifname: str, frame_count: int, frame_interval: float = 0.001
) -> TestResult:
    """Send test frames and measure performance."""
    enc = ProtocolEncoder(
        SyncConfig(window_pow2=6, window_crc16=True)
    )  # 2^6 = 64 refs per window

    payloads = []
    for i in range(frame_count):
        payload = create_test_payload(enc, 64)  # 64 refs per frame
        payloads.append(payload)

    print(f"🚀 Sending {frame_count} frames on {ifname}...")

    start_time = time.time()

    mac = get_if_mac(ifname)
    eth_header = make_eth_header(mac)
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
    s.bind((ifname, 0))

    frames_sent = 0
    total_payload_size = 0

    try:
        for i, payload in enumerate(payloads):
            frame = eth_header + payload
            if len(frame) < 60:
                frame = frame + b"\x00" * (60 - len(frame))

            s.send(frame)
            frames_sent += 1
            total_payload_size += len(payload)

            if frame_interval > 0:
                time.sleep(frame_interval)

            if (i + 1) % 10 == 0:
                print(f"📤 Sent {i + 1}/{frame_count} frames...")

    except Exception as e:
        print(f"⚠️  Sender error: {e}")
    finally:
        s.close()

    elapsed = time.time() - start_time
    throughput = frames_sent / elapsed if elapsed > 0 else 0
    avg_frame_size = total_payload_size / frames_sent if frames_sent > 0 else 0

    return TestResult(
        frames_sent=frames_sent,
        frames_received=0,  # Will be filled by receiver
        sync_frames_detected=0,
        total_time=elapsed,
        throughput_pps=throughput,
        avg_frame_size=avg_frame_size,
    )


def main():
    parser = argparse.ArgumentParser(description="PacketFS Basic Communication Test")
    parser.add_argument("--tx-iface", required=True, help="Transmit interface")
    parser.add_argument("--rx-iface", required=True, help="Receive interface")
    parser.add_argument(
        "--frames", type=int, default=100, help="Number of frames to send"
    )
    parser.add_argument(
        "--interval", type=float, default=0.01, help="Interval between frames (seconds)"
    )
    parser.add_argument(
        "--duration", type=float, default=30.0, help="Test duration (seconds)"
    )

    args = parser.parse_args()

    print("🎯 PacketFS Basic Communication Test")
    print(f"📡 TX: {args.tx_iface} -> RX: {args.rx_iface}")
    print(f"📊 Frames: {args.frames}, Interval: {args.interval}s")
    print("-" * 50)

    # Start receiver thread
    result_queue = queue.Queue()
    rx_thread = threading.Thread(
        target=receiver_thread, args=(args.rx_iface, args.duration, result_queue)
    )
    rx_thread.daemon = True
    rx_thread.start()

    # Give receiver time to start
    time.sleep(0.5)

    # Run sender
    tx_result = sender_test(args.tx_iface, args.frames, args.interval)

    # Wait for receiver results
    try:
        rx_result = result_queue.get(timeout=5.0)
    except queue.Empty:
        print("⚠️  Receiver timeout!")
        rx_result = None

    rx_thread.join(timeout=2.0)

    print("\n" + "=" * 60)
    print("🏆 TEST RESULTS")
    print("=" * 60)

    if rx_result:
        print(f"📤 Frames Sent:        {tx_result.frames_sent}")
        print(f"📥 Frames Received:    {rx_result.frames_received}")
        print(f"📡 SYNC Frames:        {rx_result.sync_frames_detected}")
        print(f"⚠️  SYNC Errors:        {rx_result.sync_errors}")
        print(
            f"⏱️  Total Time:         {max(tx_result.total_time, rx_result.total_time):.3f}s"
        )
        print(f"🚀 TX Throughput:      {tx_result.throughput_pps:.1f} pps")
        print(f"📨 RX Throughput:      {rx_result.throughput_pps:.1f} pps")
        print(f"📏 Avg Frame Size:     {tx_result.avg_frame_size:.1f} bytes")

        success_rate = (
            (rx_result.frames_received / tx_result.frames_sent) * 100
            if tx_result.frames_sent > 0
            else 0
        )
        print(f"✅ Success Rate:       {success_rate:.1f}%")

        if success_rate > 95:
            print("\n🎉 TEST PASSED! PacketFS communication working!")
        else:
            print(f"\n❌ TEST FAILED! Low success rate: {success_rate:.1f}%")
            return 1
    else:
        print("❌ Receiver failed to provide results")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
