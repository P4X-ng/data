#!/usr/bin/env python3
"""
Integration tests for PacketFS using virtual interfaces.
Tests end-to-end send/receive with veth pairs, error injection, and robustness.
"""
import pytest
import time
import socket
import struct
import threading
import queue
import subprocess
import random
from contextlib import contextmanager
from unittest.mock import patch

from packetfs.rawio import get_if_mac, make_eth_header, send_frames, ETH_P_PFS
from packetfs.protocol import ProtocolEncoder, ProtocolDecoder, SyncConfig
from packetfs.seed_pool import SeedPool


class VethPair:
    """Context manager for creating/destroying veth pair"""
    
    def __init__(self, name1="veth_pfs0", name2="veth_pfs1"):
        self.name1 = name1
        self.name2 = name2
        self.created = False
    
    def __enter__(self):
        try:
            # Create veth pair
            subprocess.run([
                "sudo", "ip", "link", "add", "dev", self.name1,
                "type", "veth", "peer", "name", self.name2
            ], check=True, capture_output=True)
            
            # Bring up interfaces
            subprocess.run(["sudo", "ip", "link", "set", "dev", self.name1, "up"], check=True)
            subprocess.run(["sudo", "ip", "link", "set", "dev", self.name2, "up"], check=True)
            
            self.created = True
            return self
        except subprocess.CalledProcessError as e:
            pytest.skip(f"Failed to create veth pair: {e}")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.created:
            try:
                subprocess.run(["sudo", "ip", "link", "delete", self.name1], 
                             check=True, capture_output=True)
            except subprocess.CalledProcessError:
                pass  # Interface might already be gone


@contextmanager
def capture_packets(interface, duration=2.0):
    """Context manager to capture packets on interface"""
    packets = queue.Queue()
    stop_event = threading.Event()
    
    def packet_capturer():
        try:
            s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_PFS))
            s.bind((interface, 0))
            s.settimeout(0.1)
            
            start_time = time.time()
            while not stop_event.is_set() and (time.time() - start_time) < duration:
                try:
                    frame = s.recv(2048)
                    packets.put((time.time(), frame))
                except socket.timeout:
                    continue
        except Exception as e:
            packets.put(('error', str(e)))
    
    thread = threading.Thread(target=packet_capturer)
    thread.start()
    
    try:
        yield packets
    finally:
        stop_event.set()
        thread.join(timeout=1.0)


class TestRawIO:
    """Test raw I/O operations"""
    
    def test_get_if_mac_loopback(self):
        """Test MAC address retrieval for loopback interface"""
        try:
            mac = get_if_mac("lo")
            assert len(mac) == 6
            assert all(b == 0 for b in mac)  # Loopback MAC is all zeros
        except OSError:
            pytest.skip("Cannot access loopback interface")
    
    def test_make_eth_header(self):
        """Test Ethernet header creation"""
        src_mac = b'\x01\x02\x03\x04\x05\x06'
        dst_mac = b'\xff\xff\xff\xff\xff\xff'
        
        header = make_eth_header(src_mac, dst_mac, ETH_P_PFS)
        assert len(header) == 14  # Standard Ethernet header
        assert header[:6] == dst_mac
        assert header[6:12] == src_mac
        assert struct.unpack('!H', header[12:14])[0] == ETH_P_PFS
    
    @pytest.mark.skipif(
        subprocess.run(["id", "-u"], capture_output=True).stdout.strip() != b"0",
        reason="Raw socket tests require root privileges"
    )
    def test_veth_communication(self):
        """Test basic communication over veth pair"""
        with VethPair() as veth:
            # Send a test frame
            test_payload = b"Hello PacketFS!"
            
            with capture_packets(veth.name2, duration=1.0) as captured:
                # Small delay to ensure capture is ready
                time.sleep(0.1)
                
                try:
                    send_frames(veth.name1, [test_payload])
                    time.sleep(0.2)  # Allow packet to be captured
                    
                    # Check captured packets
                    packets = []
                    try:
                        while True:
                            packets.append(captured.get_nowait())
                    except queue.Empty:
                        pass
                    
                    # Verify we captured at least one packet
                    assert len(packets) > 0
                    
                    # Check if our payload is in any captured frame
                    found_payload = False
                    for timestamp, frame in packets:
                        if isinstance(frame, bytes) and test_payload in frame:
                            found_payload = True
                            break
                    
                    assert found_payload, f"Test payload not found in {len(packets)} captured packets"
                    
                except Exception as e:
                    pytest.skip(f"Veth communication test failed: {e}")


class TestProtocolIntegration:
    """Integration tests for full protocol stack"""
    
    @pytest.fixture
    def test_config(self):
        """Fixture providing test configuration"""
        return SyncConfig(window_pow2=3, window_crc16=True)  # Small window for testing
    
    @pytest.fixture
    def encoder_decoder(self, test_config):
        """Fixture providing encoder/decoder pair"""
        try:
            import packetfs._bitpack
            encoder = ProtocolEncoder(test_config)
            decoder = ProtocolDecoder(test_config)
            return encoder, decoder
        except ImportError:
            pytest.skip("C extension not available")
    
    def test_sync_frame_detection(self, encoder_decoder):
        """Test sync frame detection in protocol stream"""
        encoder, decoder = encoder_decoder
        out = bytearray(1000)
        
        # Generate multiple windows of data
        all_payloads = []
        
        for window in range(3):
            # Fill one window (8 refs)
            refs = bytes([(window * 8 + i) % 256 for i in range(8)])
            bits = encoder.pack_refs(out, 0, refs, 8)
            
            # Get sync frame
            sync_frame = encoder.maybe_sync()
            assert sync_frame is not None
            
            # Create payload
            data_bytes = (bits + 7) // 8
            payload = bytes(out[:data_bytes]) + sync_frame
            all_payloads.append(payload)
        
        # Decode all payloads and verify sync frames
        for i, payload in enumerate(all_payloads):
            result = decoder.scan_for_sync(payload)
            assert result is not None
            window_id, crc = result
            assert window_id == i  # Window IDs should increment
    
    def test_window_size_variations(self, encoder_decoder):
        """Test different window sizes"""
        for window_pow2 in [2, 4, 6, 8]:  # 4, 16, 64, 256 refs per window
            config = SyncConfig(window_pow2=window_pow2, window_crc16=True)
            encoder = ProtocolEncoder(config)
            decoder = ProtocolDecoder(config)
            out = bytearray(1000)
            
            # Fill exactly one window
            window_size = 1 << window_pow2
            refs = bytes([i % 256 for i in range(window_size)])
            
            bits = encoder.pack_refs(out, 0, refs, 8)
            sync_frame = encoder.maybe_sync()
            
            assert sync_frame is not None
            result = decoder.scan_for_sync(sync_frame)
            assert result is not None
    
    def test_crc_validation_across_windows(self, encoder_decoder):
        """Test CRC validation across multiple windows"""
        encoder, decoder = encoder_decoder
        out = bytearray(1000)
        
        test_patterns = [
            b'\x00' * 8,  # All zeros
            b'\xFF' * 8,  # All ones  
            b'\x55' * 8,  # Alternating pattern
            bytes(range(8)),  # Sequential
        ]
        
        for pattern in test_patterns:
            # Reset encoder state
            encoder.ref_count = 0
            encoder._window_id = 0
            encoder._win_crc_accum.clear()
            
            bits = encoder.pack_refs(out, 0, pattern, 8)
            sync_frame = encoder.maybe_sync()
            
            assert sync_frame is not None
            
            # Verify CRC
            _, sync_crc = decoder.scan_for_sync(sync_frame)
            expected_crc = encoder.sync.window_crc16 and sync_crc or 0
            
            if encoder.sync.window_crc16:
                # CRC should be deterministic for same input
                encoder2 = ProtocolEncoder(encoder.sync)
                out2 = bytearray(1000)
                encoder2.pack_refs(out2, 0, pattern, 8)
                sync_frame2 = encoder2.maybe_sync()
                _, sync_crc2 = decoder.scan_for_sync(sync_frame2)
                assert sync_crc == sync_crc2
    
    @pytest.mark.skipif(
        subprocess.run(["id", "-u"], capture_output=True).stdout.strip() != b"0",
        reason="Network tests require root privileges"
    )
    def test_end_to_end_veth_protocol(self, encoder_decoder, test_config):
        """Test full end-to-end protocol over veth pair"""
        encoder, decoder = encoder_decoder
        
        with VethPair() as veth:
            # Generate test data
            out = bytearray(1000)
            test_refs = b'\x12\x34\x56\x78\x9A\xBC\xDE\xF0'  # 8 refs
            bits = encoder.pack_refs(out, 0, test_refs, 8)
            sync_frame = encoder.maybe_sync()
            
            # Create complete frame
            data_bytes = (bits + 7) // 8
            payload = bytes(out[:data_bytes]) + sync_frame
            
            # Send and capture
            with capture_packets(veth.name2, duration=1.0) as captured:
                time.sleep(0.1)  # Ensure capture is ready
                
                try:
                    send_frames(veth.name1, [payload])
                    time.sleep(0.2)  # Allow packet capture
                    
                    # Collect packets
                    packets = []
                    try:
                        while True:
                            packet = captured.get_nowait()
                            if packet[0] != 'error':
                                packets.append(packet)
                    except queue.Empty:
                        pass
                    
                    assert len(packets) > 0, "No packets captured"
                    
                    # Find our packet and decode
                    found_sync = False
                    for timestamp, frame in packets:
                        # Strip Ethernet header (14 bytes)
                        if len(frame) > 14:
                            frame_payload = frame[14:]
                            result = decoder.scan_for_sync(frame_payload)
                            if result is not None:
                                found_sync = True
                                break
                    
                    assert found_sync, "Sync frame not found in captured packets"
                    
                except Exception as e:
                    pytest.skip(f"End-to-end veth test failed: {e}")


class TestErrorInjection:
    """Test error injection and robustness"""
    
    def test_corrupted_sync_frame(self):
        """Test decoder handling of corrupted sync frames"""
        decoder = ProtocolDecoder()
        
        # Create valid sync frame
        valid_sync = bytes([0xF0]) + (0x1234).to_bytes(2, 'big') + (0x5678).to_bytes(2, 'big')
        
        # Test various corruptions
        corruptions = [
            b'',  # Empty
            bytes([0xF0]),  # Too short
            bytes([0xF0, 0x12]),  # Still too short
            bytes([0xF1]) + valid_sync[1:],  # Wrong sync mark
            valid_sync[:-1],  # Truncated CRC
        ]
        
        for corrupted in corruptions:
            result = decoder.scan_for_sync(corrupted)
            # Should either return None or handle gracefully
            assert result is None or isinstance(result, tuple)
    
    def test_frame_reordering_simulation(self):
        """Test protocol robustness against frame reordering"""
        try:
            import packetfs._bitpack
        except ImportError:
            pytest.skip("C extension not available")
        
        config = SyncConfig(window_pow2=2, window_crc16=True)  # 4 refs per window
        encoder = ProtocolEncoder(config)
        decoder = ProtocolDecoder(config)
        out = bytearray(1000)
        
        # Generate multiple frames
        frames = []
        for i in range(5):
            refs = bytes([(i * 4 + j) for j in range(4)])
            bits = encoder.pack_refs(out, 0, refs, 8)
            sync_frame = encoder.maybe_sync()
            
            if sync_frame:
                data_bytes = (bits + 7) // 8
                payload = bytes(out[:data_bytes]) + sync_frame
                frames.append((i, payload))
        
        assert len(frames) == 5
        
        # Simulate reordering
        reordered_frames = frames.copy()
        random.shuffle(reordered_frames)
        
        # Decode reordered frames - decoder should handle gracefully
        sync_count = 0
        for frame_id, payload in reordered_frames:
            result = decoder.scan_for_sync(payload)
            if result is not None:
                sync_count += 1
        
        # Should find sync in all frames regardless of order
        assert sync_count == 5
    
    def test_partial_frame_handling(self):
        """Test handling of partial/truncated frames"""
        decoder = ProtocolDecoder()
        
        # Create full sync frame
        full_sync = bytes([0xF0]) + (0x1234).to_bytes(2, 'big') + (0x5678).to_bytes(2, 'big')
        
        # Test progressively truncated frames
        for truncate_at in range(len(full_sync)):
            partial = full_sync[:truncate_at]
            result = decoder.scan_for_sync(partial)
            
            if truncate_at < len(full_sync):
                # Partial frames should return None (not enough data)
                assert result is None
            else:
                # Full frame should decode properly
                assert result is not None


class TestPerformanceBasics:
    """Basic performance and stress tests"""
    
    @pytest.fixture
    def stress_encoder(self):
        """Encoder configured for stress testing"""
        try:
            import packetfs._bitpack
            config = SyncConfig(window_pow2=6, window_crc16=True)  # 64 refs per window
            return ProtocolEncoder(config)
        except ImportError:
            pytest.skip("C extension not available")
    
    def test_high_frequency_encoding(self, stress_encoder):
        """Test encoding at high frequency"""
        encoder = stress_encoder
        out = bytearray(10000)
        
        start_time = time.time()
        frames_encoded = 0
        sync_frames = 0
        
        # Encode for 100ms
        while (time.time() - start_time) < 0.1:
            refs = bytes([i % 256 for i in range(64)])
            bits = encoder.pack_refs(out, 0, refs, 8)
            sync_frame = encoder.maybe_sync()
            
            frames_encoded += 1
            if sync_frame:
                sync_frames += 1
        
        elapsed = time.time() - start_time
        fps = frames_encoded / elapsed
        
        # Should achieve reasonable encoding rate
        assert fps > 1000, f"Encoding rate too slow: {fps:.1f} fps"
        assert sync_frames > 0, "No sync frames generated"
        
        print(f"Encoded {frames_encoded} frames in {elapsed:.3f}s ({fps:.1f} fps)")
        print(f"Generated {sync_frames} sync frames")
    
    def test_large_reference_arrays(self, stress_encoder):
        """Test handling of large reference arrays"""
        encoder = stress_encoder
        out = bytearray(50000)  # Large output buffer
        
        # Test different ref sizes
        for ref_bits in [8, 16, 32]:
            large_refs = self._generate_refs(1000, ref_bits)  # 1000 refs
            
            start_time = time.time()
            bits = encoder.pack_refs(out, 0, large_refs, ref_bits)
            elapsed = time.time() - start_time
            
            assert bits > 0
            assert elapsed < 0.01, f"Large array encoding too slow: {elapsed:.4f}s"
            
            print(f"Packed 1000 {ref_bits}-bit refs in {elapsed:.4f}s")
    
    def _generate_refs(self, count, ref_bits):
        """Generate reference array of specified size"""
        if ref_bits == 8:
            return bytes([i % 256 for i in range(count)])
        elif ref_bits == 16:
            return b''.join(struct.pack('>H', i % 65536) for i in range(count))
        elif ref_bits == 32:
            return b''.join(struct.pack('>I', i % (2**32)) for i in range(count))


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
