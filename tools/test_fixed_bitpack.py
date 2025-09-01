#!/usr/bin/env python3
"""
Test the FIXED PacketFS bitpack encoding/decoding roundtrip
"""

import sys
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from packetfs.protocol import ProtocolEncoder, ProtocolDecoder, SyncConfig

def test_fixed_roundtrip():
    """Test encoding and decoding with the fix"""
    print("🔧 Testing FIXED PacketFS bitpack encoding/decoding roundtrip")
    
    # Test data - the same pattern that was corrupted before
    original_data = b"AAAA"  # 0x41, 0x41, 0x41, 0x41
    print(f"Original data: {original_data.hex()} ({original_data})")
    
    # Create encoder
    config = SyncConfig(window_pow2=16, window_crc16=True)
    encoder = ProtocolEncoder(config)
    
    # Encode data
    out = bytearray(len(original_data) * 2)
    bits = encoder.pack_refs(out, 0, original_data, 8)
    encoded_data = bytes(out[:(bits + 7) // 8])
    print(f"Encoded data: {encoded_data.hex()} ({len(encoded_data)} bytes, {bits} bits)")
    
    # NEW: Proper decoding using unpack_refs
    try:
        from packetfs import _bitpack
        decoded_data = _bitpack.unpack_refs(encoded_data, len(original_data), 8)
        print(f"Decoded data: {decoded_data.hex()} ({decoded_data})")
        
        # Check if they match
        matches = original_data == decoded_data
        print(f"Data matches: {matches}")
        
        if matches:
            print("✅ ENCODING/DECODING FIXED!")
        else:
            print("❌ Still broken - showing differences:")
            for i, (orig, decoded) in enumerate(zip(original_data, decoded_data)):
                print(f"   Byte {i}: 0x{orig:02x} -> 0x{decoded:02x}")
            
        return matches
        
    except Exception as e:
        print(f"❌ Error during decoding: {e}")
        return False

def test_packetfs_file_transfer_functions():
    """Test the actual file transfer functions"""
    print(f"\n🧪 Testing PacketFS file transfer encode/decode functions")
    
    # Import the fixed transfer functions
    sys.path.insert(0, str(Path(__file__).parent))
    from packetfs_file_transfer import PacketFSFileTransfer
    
    pfs = PacketFSFileTransfer()
    
    # Test data that was corrupted before
    test_data = b"AAAA"
    print(f"Original: {test_data.hex()} ({test_data})")
    
    # Encode
    refs = pfs.data_to_refs(test_data)
    print(f"Encoded:  {refs.hex()}")
    
    # Decode
    decoded = pfs.refs_to_data(refs, len(test_data))
    print(f"Decoded:  {decoded.hex()} ({decoded})")
    
    # Check
    matches = test_data == decoded
    print(f"Match: {matches}")
    
    return matches

if __name__ == "__main__":
    print("=" * 60)
    
    # Test basic C extension roundtrip
    c_fixed = test_fixed_roundtrip()
    
    # Test file transfer functions 
    transfer_fixed = test_packetfs_file_transfer_functions()
    
    print(f"\n" + "=" * 60)
    if c_fixed and transfer_fixed:
        print("🎉 SUCCESS: PacketFS encoding/decoding is now FIXED!")
        print("   The data corruption bug has been resolved.")
        print("   File transfers should now preserve data integrity.")
    else:
        print("❌ Some issues remain - check the output above")
