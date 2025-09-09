#!/usr/bin/env python3
"""
Test PacketFS bitpack encoding/decoding roundtrip
Confirms the bug where encoding works but decoding is missing
"""

import sys
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from packetfs.protocol import ProtocolEncoder, ProtocolDecoder, SyncConfig

def test_bitpack_roundtrip():
    """Test encoding and decoding roundtrip"""
    print("🔍 Testing PacketFS bitpack encoding/decoding roundtrip")
    
    # Test data - simple pattern
    original_data = b"AAAA"  # 0x41, 0x41, 0x41, 0x41
    print(f"Original data: {original_data.hex()} ({original_data})")
    
    # Create encoder
    config = SyncConfig(window_pow2=16, window_crc16=True)
    encoder = ProtocolEncoder(config)
    
    # Encode data (like data_to_refs does)
    out = bytearray(len(original_data) * 2)  # Generous buffer
    
    try:
        bits = encoder.pack_refs(out, 0, original_data, 8)
        encoded_data = bytes(out[:(bits + 7) // 8])
        
        print(f"Encoded data: {encoded_data.hex()} ({len(encoded_data)} bytes, {bits} bits)")
        
        # Current broken decoding (what refs_to_data does)
        broken_decoded = encoded_data[:len(original_data)]
        print(f"Broken decode: {broken_decoded.hex()} ({broken_decoded})")
        
        # Check if they match
        matches = original_data == broken_decoded
        print(f"Data matches: {matches}")
        
        if not matches:
            print("🚨 BUG CONFIRMED: Encoding happens but decoding is broken!")
            print("   The current implementation just truncates encoded data")
            print("   instead of properly decoding it back to original data.")
            
            # Show byte-by-byte differences
            for i, (orig, decoded) in enumerate(zip(original_data, broken_decoded)):
                print(f"   Byte {i}: 0x{orig:02x} -> 0x{decoded:02x}")
        else:
            print("✅ Encoding/decoding works correctly")
            
    except Exception as e:
        print(f"❌ Error during encoding: {e}")
        return False
        
    return not matches

def test_multiple_patterns():
    """Test with various data patterns"""
    patterns = [
        (b"AAAA", "All A's"),
        (b"\x00\x00\x00\x00", "All zeros"), 
        (b"\x01\x02\x03\x04", "Sequential"),
        (b"\xFF\xFF\xFF\xFF", "All 0xFF"),
        (b"\xAA\x55\xAA\x55", "Alternating")
    ]
    
    print(f"\n🧪 Testing multiple patterns:")
    config = SyncConfig(window_pow2=16, window_crc16=True)
    encoder = ProtocolEncoder(config)
    
    bug_confirmed = False
    
    for pattern, description in patterns:
        print(f"\n  Pattern: {description} - {pattern.hex()}")
        
        out = bytearray(len(pattern) * 2)
        bits = encoder.pack_refs(out, 0, pattern, 8)
        encoded = bytes(out[:(bits + 7) // 8])
        broken_decoded = encoded[:len(pattern)]
        
        matches = pattern == broken_decoded
        print(f"    Encoded: {encoded.hex()}")
        print(f"    Decoded: {broken_decoded.hex()}")
        print(f"    Match: {matches}")
        
        if not matches:
            bug_confirmed = True
    
    return bug_confirmed

if __name__ == "__main__":
    print("=" * 60)
    
    # Test basic roundtrip
    basic_bug = test_bitpack_roundtrip()
    
    # Test multiple patterns
    pattern_bugs = test_multiple_patterns()
    
    print(f"\n" + "=" * 60)
    if basic_bug or pattern_bugs:
        print("🚨 CRITICAL BUG CONFIRMED:")
        print("   PacketFS encoding works but decoding is completely broken!")
        print("   The refs_to_data() function needs to be implemented properly.")
        print("   Currently it just truncates encoded data instead of decoding it.")
    else:
        print("✅ No encoding/decoding issues found")
