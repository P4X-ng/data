#!/usr/bin/env python3
"""
Comprehensive unit tests for PacketFS protocol layer.
Tests CRC functions, bitpack C extension, encoder/decoder state machines.
"""
import pytest
import struct
from unittest.mock import Mock, patch
from packetfs.protocol import (
    crc16_ccitt, ProtocolEncoder, ProtocolDecoder, SyncConfig,
    SYNC_MARK, SYNC_ACK
)


class TestCRC16CCITT:
    """Test CRC16-CCITT implementation"""
    
    def test_empty_data(self):
        """Test CRC on empty data"""
        assert crc16_ccitt(b'') == 0xFFFF
    
    def test_single_byte(self):
        """Test CRC on single byte"""
        result = crc16_ccitt(b'\x00')
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF
    
    def test_known_vectors(self):
        """Test CRC against known vectors"""
        # Test vector: "123456789" -> 0x29B1
        test_data = b'123456789'
        expected = 0x29B1
        result = crc16_ccitt(test_data)
        assert result == expected, f"Expected {expected:04x}, got {result:04x}"
    
    def test_different_poly_init(self):
        """Test CRC with different polynomial and init"""
        data = b'test'
        crc1 = crc16_ccitt(data, poly=0x1021, init=0xFFFF)
        crc2 = crc16_ccitt(data, poly=0x1021, init=0x0000)
        assert crc1 != crc2
    
    def test_large_data(self):
        """Test CRC on large data blocks"""
        large_data = b'A' * 1024
        result = crc16_ccitt(large_data)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF
    
    def test_deterministic(self):
        """Test that CRC is deterministic"""
        data = b'test data for determinism check'
        crc1 = crc16_ccitt(data)
        crc2 = crc16_ccitt(data)
        assert crc1 == crc2


class TestSyncConfig:
    """Test synchronization configuration"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = SyncConfig()
        assert config.window_pow2 == 16
        assert config.window_crc16 == True
    
    def test_custom_config(self):
        """Test custom configuration values"""
        config = SyncConfig(window_pow2=12, window_crc16=False)
        assert config.window_pow2 == 12
        assert config.window_crc16 == False
    
    def test_window_size_calculation(self):
        """Test window size calculations"""
        config = SyncConfig(window_pow2=6)
        expected_mask = (1 << 6) - 1  # 63
        encoder = ProtocolEncoder(config)
        assert encoder.window_mask == expected_mask


class TestProtocolEncoder:
    """Test protocol encoder functionality"""
    
    def test_default_initialization(self):
        """Test encoder with default config"""
        encoder = ProtocolEncoder()
        assert encoder.sync.window_pow2 == 16
        assert encoder.sync.window_crc16 == True
        assert encoder.ref_count == 0
        assert encoder._tier == -1
        assert encoder._window_id == 0
    
    def test_custom_initialization(self):
        """Test encoder with custom config"""
        config = SyncConfig(window_pow2=8, window_crc16=False)
        encoder = ProtocolEncoder(config)
        assert encoder.sync.window_pow2 == 8
        assert encoder.sync.window_crc16 == False
        assert encoder.window_mask == 255  # 2^8 - 1
    
    def test_pack_refs_no_extension(self):
        """Test pack_refs when C extension unavailable"""
        # Temporarily set the module-level _bitpack to None
        from importlib import reload
        import packetfs.protocol as proto
        original = proto._bitpack
        try:
            proto._bitpack = None
            encoder = ProtocolEncoder()
            out = bytearray(100)
            refs = b'\x01\x02\x03\x04'
            with pytest.raises(RuntimeError, match="C extension _bitpack not available"):
                encoder.pack_refs(out, 0, refs, 8)
        finally:
            proto._bitpack = original
    
    @pytest.fixture
    def encoder_with_bitpack(self):
        """Fixture providing encoder with working bitpack"""
        try:
            import packetfs._bitpack
            return ProtocolEncoder()
        except ImportError:
            pytest.skip("C extension not available")
    
    def test_pack_refs_success(self, encoder_with_bitpack):
        """Test successful ref packing"""
        encoder = encoder_with_bitpack
        out = bytearray(100)
        refs = b'\x01\x02\x03\x04'  # 4 bytes = 4 refs at 8 bits each
        
        bits = encoder.pack_refs(out, 0, refs, 8)
        assert isinstance(bits, int)
        assert bits > 0
        assert encoder.ref_count == 4  # 4 refs packed
    
    def test_ref_count_update(self, encoder_with_bitpack):
        """Test reference counter updates correctly"""
        encoder = encoder_with_bitpack
        out = bytearray(100)
        
        # Pack 8-bit refs
        refs_8 = b'\x01\x02'  # 2 refs
        encoder.pack_refs(out, 0, refs_8, 8)
        assert encoder.ref_count == 2
        
        # Pack 16-bit refs
        refs_16 = struct.pack('>HH', 0x1234, 0x5678)  # 2 refs
        encoder.pack_refs(out, 1, refs_16, 16)
        assert encoder.ref_count == 4
        
        # Pack 32-bit refs
        refs_32 = struct.pack('>I', 0x12345678)  # 1 ref
        encoder.pack_refs(out, 2, refs_32, 32)
        assert encoder.ref_count == 5
    
    def test_sync_window_boundary(self, encoder_with_bitpack):
        """Test sync frame generation at window boundary"""
        config = SyncConfig(window_pow2=3, window_crc16=True)  # 8 refs per window
        encoder = ProtocolEncoder(config)
        out = bytearray(100)
        
        # Pack 7 refs - should not generate sync
        refs = b'\x01' * 7
        encoder.pack_refs(out, 0, refs, 8)
        sync1 = encoder.maybe_sync()
        assert sync1 is None
        
        # Pack 1 more ref - should generate sync at boundary
        refs = b'\x08'
        encoder.pack_refs(out, 0, refs, 8)
        sync2 = encoder.maybe_sync()
        assert sync2 is not None
        assert len(sync2) == 5  # SYNC_MARK + window_id(2) + crc16(2)
        assert sync2[0] == SYNC_MARK
    
    def test_sync_without_crc(self, encoder_with_bitpack):
        """Test sync frame without CRC"""
        config = SyncConfig(window_pow2=3, window_crc16=False)
        encoder = ProtocolEncoder(config)
        out = bytearray(100)
        
        # Fill window
        refs = b'\x01' * 8
        encoder.pack_refs(out, 0, refs, 8)
        sync = encoder.maybe_sync()
        
        assert sync is not None
        assert len(sync) == 3  # SYNC_MARK + window_id(2), no CRC
        assert sync[0] == SYNC_MARK
    
    def test_window_id_increment(self, encoder_with_bitpack):
        """Test window ID increments correctly"""
        config = SyncConfig(window_pow2=3, window_crc16=False)
        encoder = ProtocolEncoder(config)
        out = bytearray(100)
        
        # Generate first sync
        refs = b'\x01' * 8
        encoder.pack_refs(out, 0, refs, 8)
        sync1 = encoder.maybe_sync()
        window_id_1 = int.from_bytes(sync1[1:3], 'big')
        
        # Generate second sync
        encoder.pack_refs(out, 0, refs, 8)
        sync2 = encoder.maybe_sync()
        window_id_2 = int.from_bytes(sync2[1:3], 'big')
        
        assert window_id_2 == (window_id_1 + 1) & 0xFFFF
    
    def test_window_id_rollover(self, encoder_with_bitpack):
        """Test window ID rollover at 16-bit boundary"""
        config = SyncConfig(window_pow2=1, window_crc16=False)  # 2 refs per window
        encoder = ProtocolEncoder(config)
        encoder._window_id = 0xFFFF  # Set to max value
        out = bytearray(100)
        
        # Generate sync at rollover point
        refs = b'\x01\x02'
        encoder.pack_refs(out, 0, refs, 8)
        sync = encoder.maybe_sync()
        
        # Next window ID should be 0
        refs = b'\x03\x04'
        encoder.pack_refs(out, 0, refs, 8)
        sync_after = encoder.maybe_sync()
        window_id = int.from_bytes(sync_after[1:3], 'big')
        assert window_id == 0
    
    def test_crc_accumulation(self, encoder_with_bitpack):
        """Test CRC accumulation across refs in window"""
        config = SyncConfig(window_pow2=2, window_crc16=True)  # 4 refs per window
        encoder = ProtocolEncoder(config)
        out = bytearray(100)
        
        # Pack refs and check CRC accumulation
        refs1 = b'\x01\x02'
        encoder.pack_refs(out, 0, refs1, 8)
        assert len(encoder._win_crc_accum) == 2
        
        refs2 = b'\x03\x04'
        encoder.pack_refs(out, 0, refs2, 8)
        assert len(encoder._win_crc_accum) == 4
        
        # Generate sync and verify CRC reset
        sync = encoder.maybe_sync()
        assert sync is not None
        assert len(encoder._win_crc_accum) == 0
    
    def test_ref_count_overflow(self, encoder_with_bitpack):
        """Test reference counter overflow handling"""
        encoder = ProtocolEncoder()
        encoder.ref_count = 0xFFFFFFFF  # Max 32-bit value
        out = bytearray(100)
        
        # Should wrap around to 0
        refs = b'\x01'
        encoder.pack_refs(out, 0, refs, 8)
        assert encoder.ref_count == 0


class TestProtocolDecoder:
    """Test protocol decoder functionality"""
    
    def test_default_initialization(self):
        """Test decoder with default config"""
        decoder = ProtocolDecoder()
        assert decoder.sync.window_pow2 == 16
        assert decoder.sync.window_crc16 == True
    
    def test_scan_for_sync_not_found(self):
        """Test sync scan when no sync mark present"""
        decoder = ProtocolDecoder()
        payload = b'\x01\x02\x03\x04\x05'
        result = decoder.scan_for_sync(payload)
        assert result is None
    
    def test_scan_for_sync_found(self):
        """Test sync scan when sync mark present"""
        decoder = ProtocolDecoder()
        # Create sync frame: SYNC_MARK + window_id + crc16
        sync_frame = bytes([SYNC_MARK]) + (0x1234).to_bytes(2, 'big') + (0x5678).to_bytes(2, 'big')
        payload = b'\x01\x02' + sync_frame + b'\x03\x04'
        
        result = decoder.scan_for_sync(payload)
        assert result is not None
        window_id, crc = result
        assert window_id == 0x1234
        assert crc == 0x5678
    
    def test_scan_for_sync_incomplete(self):
        """Test sync scan with incomplete sync frame"""
        decoder = ProtocolDecoder()
        # Incomplete sync frame (missing CRC)
        payload = bytes([SYNC_MARK]) + (0x1234).to_bytes(2, 'big')
        
        result = decoder.scan_for_sync(payload)
        assert result is None
    
    def test_scan_for_sync_without_crc(self):
        """Test sync scan without CRC enabled"""
        config = SyncConfig(window_crc16=False)
        decoder = ProtocolDecoder(config)
        sync_frame = bytes([SYNC_MARK]) + (0x1234).to_bytes(2, 'big')
        payload = sync_frame
        
        result = decoder.scan_for_sync(payload)
        assert result is not None
        window_id, crc = result
        assert window_id == 0x1234
        assert crc == 0  # No CRC when disabled
    
    def test_scan_multiple_sync_frames(self):
        """Test scan finds first sync frame"""
        decoder = ProtocolDecoder()
        sync1 = bytes([SYNC_MARK]) + (0x1111).to_bytes(2, 'big') + (0x2222).to_bytes(2, 'big')
        sync2 = bytes([SYNC_MARK]) + (0x3333).to_bytes(2, 'big') + (0x4444).to_bytes(2, 'big')
        payload = b'\x00' + sync1 + b'\x00' + sync2
        
        result = decoder.scan_for_sync(payload)
        assert result is not None
        window_id, crc = result
        assert window_id == 0x1111
        assert crc == 0x2222


class TestProtocolIntegration:
    """Integration tests for encoder/decoder pair"""
    
    @pytest.fixture
    def encoder_decoder_pair(self):
        """Fixture providing matched encoder/decoder pair"""
        try:
            import packetfs._bitpack
            config = SyncConfig(window_pow2=3, window_crc16=True)  # 8 refs per window
            encoder = ProtocolEncoder(config)
            decoder = ProtocolDecoder(config)
            return encoder, decoder
        except ImportError:
            pytest.skip("C extension not available")
    
    def test_end_to_end_sync(self, encoder_decoder_pair):
        """Test end-to-end sync frame generation and detection"""
        encoder, decoder = encoder_decoder_pair
        out = bytearray(1000)
        
        # Generate data to trigger sync
        refs = b'\x01\x02\x03\x04\x05\x06\x07\x08'  # Exactly 8 refs
        bits = encoder.pack_refs(out, 0, refs, 8)
        sync_frame = encoder.maybe_sync()
        
        assert sync_frame is not None
        
        # Combine packed data and sync frame
        data_bytes = (bits + 7) // 8
        payload = bytes(out[:data_bytes]) + sync_frame
        
        # Decode sync frame
        result = decoder.scan_for_sync(payload)
        assert result is not None
        window_id, crc = result
        assert isinstance(window_id, int)
        assert isinstance(crc, int)
    
    def test_crc_validation(self, encoder_decoder_pair):
        """Test CRC validation between encoder and decoder"""
        encoder, decoder = encoder_decoder_pair
        out = bytearray(1000)
        
        # Use known data for CRC validation
        test_refs = b'\x12\x34\x56\x78\xAB\xCD\xEF\x01'
        bits = encoder.pack_refs(out, 0, test_refs, 8)
        sync_frame = encoder.maybe_sync()
        
        assert sync_frame is not None
        
        # Extract CRC from sync frame
        _, decoder_crc = decoder.scan_for_sync(sync_frame)
        
        # Manually calculate expected CRC
        expected_crc = crc16_ccitt(test_refs)
        assert decoder_crc == expected_crc


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
