#!/usr/bin/env python3
"""
Simple UDP file transfer for benchmarking against PacketFS
"""

import socket
import struct
import time
import sys
import threading
from pathlib import Path

def udp_server(host="0.0.0.0", port=9999, output_file="received_udp.bin"):
    """UDP server that receives file chunks"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    
    print(f"📡 UDP Server listening on {host}:{port}")
    
    chunks = {}
    total_chunks = 0
    
    with open(output_file, 'wb') as f:
        while True:
            try:
                data, addr = sock.recvfrom(8192 + 8)  # 8KB data + header
                
                if len(data) < 8:
                    continue
                    
                # Parse header: chunk_id (4 bytes), total_chunks (4 bytes)
                chunk_id, total_chunks = struct.unpack('!II', data[:8])
                chunk_data = data[8:]
                
                chunks[chunk_id] = chunk_data
                
                if len(chunks) % 1000 == 0:
                    print(f"📥 Received {len(chunks)} chunks")
                
                # Check if we have all chunks
                if len(chunks) == total_chunks:
                    print(f"✅ All {total_chunks} chunks received, writing file...")
                    
                    # Write chunks in order
                    for i in range(total_chunks):
                        if i in chunks:
                            f.write(chunks[i])
                    break
                    
            except Exception as e:
                print(f"❌ Server error: {e}")
                break
    
    sock.close()
    print(f"💾 File saved: {output_file}")

def udp_client(host, port, file_path, chunk_size=8192):
    """UDP client that sends file chunks"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    file_size = Path(file_path).stat().st_size
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    
    print(f"📤 Sending {file_path} ({file_size:,} bytes) in {total_chunks} chunks")
    
    start_time = time.time()
    
    with open(file_path, 'rb') as f:
        for chunk_id in range(total_chunks):
            chunk_data = f.read(chunk_size)
            
            # Create packet: header + data
            header = struct.pack('!II', chunk_id, total_chunks)
            packet = header + chunk_data
            
            sock.sendto(packet, (host, port))
            
            if (chunk_id + 1) % 1000 == 0:
                print(f"📤 Sent {chunk_id + 1}/{total_chunks} chunks")
    
    transfer_time = time.time() - start_time
    throughput = file_size / (1024 * 1024) / transfer_time
    
    print(f"✅ Transfer complete: {throughput:.2f} MB/s ({transfer_time:.2f} seconds)")
    
    sock.close()
    return throughput, transfer_time

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="UDP File Transfer Test")
    parser.add_argument('mode', choices=['server', 'client'])
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=9999)
    parser.add_argument('--file', help='File to send (client mode)')
    parser.add_argument('--output', default='received_udp.bin', help='Output file (server mode)')
    
    args = parser.parse_args()
    
    if args.mode == 'server':
        udp_server(args.host, args.port, args.output)
    else:
        if not args.file:
            print("❌ Client mode requires --file")
            sys.exit(1)
        udp_client(args.host, args.port, args.file)
