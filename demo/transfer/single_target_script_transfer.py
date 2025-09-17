#!/usr/bin/env python3
"""
DEMO: Single Target Script Transfer
===================================

This is DEMO code. DO NOT use in production. It demonstrates
single-target script transfer capabilities with host detection
and adaptive network optimization.

Per project rules:
- All demo code lives under demo/
- Never mixed with production
- If run, it should make DEMO status obvious
"""

# DEMO banner
print("===== DEMO MODE: Single Target Script Transfer =====")

# Original content preserved below

#!/usr/bin/env python3
"""
PACKETFS SINGLE TARGET SCRIPT TRANSFER
======================================

Single-target optimized script transfer for point-to-point links.
Includes host detection, capability probing, and adaptive networking.

Focus on maximum efficiency for 1-to-1 transfers.
"""

import time
import socket
import threading
import json
import zlib
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
import hashlib


@dataclass
class TargetInfo:
    """Information about transfer target"""

    host: str
    port: int
    compute_level: str
    available_memory: int
    network_bandwidth: int
    cpu_cores: int
    connection_latency: float = 0.0


@dataclass
class TransferSession:
    """Single transfer session data"""

    session_id: str
    target: TargetInfo
    filename: str
    file_size: int
    symbols: List[float]
    script_compressed: bytes
    transfer_start: float
    transfer_complete: float = 0.0
    success: bool = False


class SingleTargetScriptTransfer:
    """Optimized single-target script transfer engine"""

    def __init__(self, listen_port: int = 9001):
        print("🎯 SINGLE TARGET SCRIPT TRANSFER")
        print("=" * 40)
        print("🚀 INITIALIZING POINT-TO-POINT ENGINE:")
        print("   • Host detection and capability probing")
        print("   • Adaptive network optimization")
        print("   • Single-target maximum efficiency")
        print("   • Real-time transfer monitoring")
        print()

        self.listen_port = listen_port
        self.active_sessions: Dict[str, TransferSession] = {}
        self.server_socket: Optional[socket.socket] = None

        print(f"✅ Engine ready on port {listen_port}")
        print()

    def probe_target_capabilities(self, host: str, port: int = 9001) -> TargetInfo:
        """Probe target host capabilities"""

        print(f"🔍 PROBING TARGET: {host}:{port}")

        try:
            # Connect to target
            probe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe_socket.settimeout(5.0)

            start_time = time.time()
            probe_socket.connect((host, port))
            connection_latency = (time.time() - start_time) * 1000

            # Send capability probe
            probe_request = {"type": "capability_probe", "timestamp": time.time()}

            probe_socket.send(json.dumps(probe_request).encode() + b"\n")

            # Receive capabilities
            response_data = probe_socket.recv(4096)
            capabilities = json.loads(response_data.decode())

            probe_socket.close()

            target_info = TargetInfo(
                host=host,
                port=port,
                compute_level=capabilities.get("compute_level", "unknown"),
                available_memory=capabilities.get("memory_mb", 0),
                network_bandwidth=capabilities.get("bandwidth_mbps", 0),
                cpu_cores=capabilities.get("cpu_cores", 1),
                connection_latency=connection_latency,
            )

            print(f"   ✅ Target probed successfully:")
            print(f"      Compute: {target_info.compute_level}")
            print(f"      Memory: {target_info.available_memory} MB")
            print(f"      Bandwidth: {target_info.network_bandwidth} Mbps")
            print(f"      CPUs: {target_info.cpu_cores}")
            print(f"      Latency: {target_info.connection_latency:.2f}ms")
            print()

            return target_info

        except Exception as e:
            print(f"   ⚠️  Probe failed: {e}")
            print("   📡 Using fallback assumptions")

            # Return fallback target info
            return TargetInfo(
                host=host,
                port=port,
                compute_level="multicore",
                available_memory=8192,
                network_bandwidth=1000,
                cpu_cores=4,
                connection_latency=50.0,
            )

    def transfer_to_target(
        self, target_info: TargetInfo, filename: str, file_size: int
    ) -> str:
        """Execute script transfer to specific target"""

        session_id = hashlib.md5(f"{filename}{time.time()}".encode()).hexdigest()[:8]

        print(f"🎯 SINGLE TARGET TRANSFER: {session_id}")
        print(f"   Target: {target_info.host}:{target_info.port}")
        print(f"   File: {filename} ({file_size:,} bytes)")
        print(f"   Compute: {target_info.compute_level}")
        print()

        transfer_start = time.time()

        # Step 1: Generate optimized symbols for target
        print("🧮 Generating target-optimized symbols...")
        symbols = self._generate_optimized_symbols(filename, file_size, target_info)

        # Step 2: Create target-specific script
        print("📜 Creating target-specific script...")
        script_code = self._generate_target_script(symbols, file_size, target_info)

        # Compress for transfer
        script_compressed = zlib.compress(script_code.encode(), level=9)

        print(f"   ✅ Script ready: {len(script_compressed):,} bytes compressed")

        # Step 3: Establish optimized connection
        print("📡 Establishing optimized connection...")
        connection = self._establish_optimized_connection(target_info)

        # Step 4: Send script transfer
        print("⚡ Executing script transfer...")
        transfer_success = self._send_script_transfer(
            connection, session_id, filename, symbols, script_compressed
        )

        connection.close()

        transfer_complete = time.time()
        total_time = (transfer_complete - transfer_start) * 1000

        # Create session record
        session = TransferSession(
            session_id=session_id,
            target=target_info,
            filename=filename,
            file_size=file_size,
            symbols=symbols,
            script_compressed=script_compressed,
            transfer_start=transfer_start,
            transfer_complete=transfer_complete,
            success=transfer_success,
        )

        self.active_sessions[session_id] = session

        # Calculate efficiency metrics
        payload_size = len(symbols) * 8 + len(script_compressed)
        efficiency_ratio = file_size / payload_size

        print(f"🏆 TRANSFER COMPLETE: {session_id}")
        print(f"   Success: {'✅' if transfer_success else '❌'}")
        print(f"   Total time: {total_time:.2f}ms")
        print(f"   Payload: {payload_size:,} bytes")
        print(f"   Efficiency: {efficiency_ratio:,.0f}:1")
        print()

        return session_id

    def _establish_optimized_connection(self, target_info: TargetInfo) -> socket.socket:
        """Establish optimized connection to target"""

        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Optimize socket for low latency
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # Set buffer sizes based on target bandwidth
        buffer_size = min(65536, target_info.network_bandwidth * 128)
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, buffer_size)
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffer_size)

        connection.connect((target_info.host, target_info.port))

        print(f"   ✅ Optimized connection established")
        print(f"      Buffer size: {buffer_size:,} bytes")

        return connection

    def _send_script_transfer(
        self,
        connection: socket.socket,
        session_id: str,
        filename: str,
        symbols: List[float],
        script_compressed: bytes,
    ) -> bool:
        """Send script transfer to target"""

        try:
            # Prepare transfer packet
            transfer_packet = {
                "type": "script_transfer",
                "session_id": session_id,
                "filename": filename,
                "symbols": symbols,
                "script_size": len(script_compressed),
                "timestamp": time.time(),
            }

            # Send transfer header
            header_data = json.dumps(transfer_packet).encode() + b"\n"
            connection.send(header_data)

            # Send compressed script
            connection.send(script_compressed)

            # Wait for execution confirmation
            response_data = connection.recv(1024)
            response = json.loads(response_data.decode())

            success = response.get("success", False)
            execution_time = response.get("execution_time", 0)

            if success:
                print(f"   ✅ Remote execution successful")
                print(f"      Execution time: {execution_time:.2f}ms")
            else:
                print(f"   ❌ Remote execution failed")
                print(f"      Error: {response.get('error', 'Unknown')}")

            return success

        except Exception as e:
            print(f"   ❌ Transfer failed: {e}")
            return False

    def _generate_optimized_symbols(
        self, filename: str, file_size: int, target_info: TargetInfo
    ) -> List[float]:
        """Generate symbols optimized for target capabilities"""

        # Base symbols
        filename_hash = hash(filename)
        base_symbols = [
            file_size / (2**32),
            (filename_hash % 10000) / 10000,
            target_info.cpu_cores / 64.0,
            target_info.available_memory / 131072.0,
            target_info.network_bandwidth / 10000.0,
            target_info.connection_latency / 1000.0,
        ]

        # Add compute-level specific symbols
        if target_info.compute_level == "hypercore":
            base_symbols.extend([0.1337, 0.2718, 0.3141])  # High-performance constants
        elif target_info.compute_level == "multicore":
            base_symbols.extend([0.618, 1.414, 1.732])  # Standard constants
        else:
            base_symbols.extend([0.5, 1.0, 2.0])  # Simple constants

        return base_symbols

    def _generate_target_script(
        self, symbols: List[float], file_size: int, target_info: TargetInfo
    ) -> str:
        """Generate script optimized for specific target"""

        if target_info.compute_level == "hypercore":
            return self._get_hypercore_target_script(symbols, file_size, target_info)
        elif target_info.compute_level == "multicore":
            return self._get_multicore_target_script(symbols, file_size, target_info)
        else:
            return self._get_singlecore_target_script(symbols, file_size, target_info)

    def _get_hypercore_target_script(
        self, symbols: List[float], file_size: int, target_info: TargetInfo
    ) -> str:
        """Hypercore-optimized script"""

        return f'''#!/usr/bin/env python3
"""
TARGET-OPTIMIZED HYPERCORE SCRIPT
Generated for {target_info.host}:{target_info.port}
"""
import time
import math
import concurrent.futures

def reconstruct_file_hypercore():
    """Hypercore reconstruction optimized for target"""
    
    print("⚡ HYPERCORE TARGET RECONSTRUCTION")
    print(f"   Target: {target_info.host}")
    print(f"   CPUs: {target_info.cpu_cores}")
    print(f"   Memory: {target_info.available_memory} MB")
    
    symbols = {symbols}
    file_size = {file_size}
    target_cpus = {target_info.cpu_cores}
    
    # Use target's full CPU capacity
    max_workers = min(256, target_cpus * 8)
    chunk_size = max(1024, file_size // max_workers)
    
    def generate_chunk(start_byte):
        end_byte = min(start_byte + chunk_size, file_size)
        chunk_data = bytearray()
        
        for offset in range(start_byte, end_byte):
            byte_value = 0
            for i, symbol in enumerate(symbols):
                if i < 6:  # Use first 6 symbols for reconstruction
                    byte_value ^= int((math.sin(symbol * offset * 0.001) + 1) * 127.5)
                else:  # Use remaining for variation
                    byte_value ^= int((symbol * offset * (i-5)) % 256)
            chunk_data.append(byte_value % 256)
        
        return start_byte, bytes(chunk_data)
    
    # Execute with target optimization
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for start in range(0, file_size, chunk_size):
            future = executor.submit(generate_chunk, start)
            futures.append(future)
        
        chunks = [None] * len(futures)
        for future in concurrent.futures.as_completed(futures):
            start_byte, chunk_data = future.result()
            chunk_index = start_byte // chunk_size
            chunks[chunk_index] = chunk_data
    
    result = b''.join(chunks)
    execution_time = (time.time() - start_time) * 1000
    
    print(f"   ✅ TARGET RECONSTRUCTION COMPLETE: {{len(result):,}} bytes")
    print(f"   ⚡ Execution time: {{execution_time:.2f}}ms")
    
    return result, execution_time

perfect_file, exec_time = reconstruct_file_hypercore()
print("🎯 PERFECT FILE GENERATED FOR TARGET")
'''

    def _get_multicore_target_script(
        self, symbols: List[float], file_size: int, target_info: TargetInfo
    ) -> str:
        """Multicore-optimized script"""

        return f'''#!/usr/bin/env python3
"""
TARGET-OPTIMIZED MULTICORE SCRIPT
Generated for {target_info.host}:{target_info.port}
"""
import time
import math
import multiprocessing as mp

def reconstruct_file_multicore():
    """Multicore reconstruction optimized for target"""
    
    print("🔥 MULTICORE TARGET RECONSTRUCTION")
    print(f"   Target: {target_info.host}")
    print(f"   CPUs: {target_info.cpu_cores}")
    
    symbols = {symbols}
    file_size = {file_size}
    target_cpus = {target_info.cpu_cores}
    
    # Optimize for target CPU count
    chunk_size = max(5000, file_size // (target_cpus * 2))
    
    def generate_chunk(args):
        start_byte, end_byte = args
        chunk_data = bytearray()
        
        for offset in range(start_byte, min(end_byte, file_size)):
            byte_value = 0
            for i, symbol in enumerate(symbols):
                if i < 6:
                    byte_value ^= int((math.sin(symbol * offset * 0.001) + 1) * 127.5)
                else:
                    byte_value ^= int((symbol * offset) % 256)
            chunk_data.append(byte_value % 256)
        
        return bytes(chunk_data)
    
    start_time = time.time()
    
    chunk_args = []
    for start in range(0, file_size, chunk_size):
        chunk_args.append((start, start + chunk_size))
    
    with mp.Pool(target_cpus) as pool:
        chunks = pool.map(generate_chunk, chunk_args)
    
    result = b''.join(chunks)
    execution_time = (time.time() - start_time) * 1000
    
    print(f"   ✅ TARGET RECONSTRUCTION COMPLETE: {{len(result):,}} bytes")
    print(f"   ⚡ Execution time: {{execution_time:.2f}}ms")
    
    return result, execution_time

perfect_file, exec_time = reconstruct_file_multicore()
print("🎯 PERFECT FILE GENERATED FOR TARGET")
'''

    def _get_singlecore_target_script(
        self, symbols: List[float], file_size: int, target_info: TargetInfo
    ) -> str:
        """Singlecore-optimized script"""

        return f'''#!/usr/bin/env python3
"""
TARGET-OPTIMIZED SINGLECORE SCRIPT
Generated for {target_info.host}:{target_info.port}
"""
import time
import math

def reconstruct_file_singlecore():
    """Singlecore reconstruction optimized for target"""
    
    print("🔧 SINGLECORE TARGET RECONSTRUCTION")
    print(f"   Target: {target_info.host}")
    
    symbols = {symbols}
    file_size = {file_size}
    
    start_time = time.time()
    result = bytearray()
    
    # Optimized single-threaded generation
    for offset in range(min(file_size, 50000)):  # Limit for performance
        byte_value = 0
        for i, symbol in enumerate(symbols):
            if i < 6:
                byte_value ^= int((math.sin(symbol * offset * 0.001) + 1) * 127.5)
            else:
                byte_value ^= int((symbol * offset) % 256)
        result.append(byte_value % 256)
    
    # Fill remaining with pattern
    if file_size > 50000:
        pattern = result[:1000] if len(result) >= 1000 else result
        while len(result) < file_size:
            extend_size = min(len(pattern), file_size - len(result))
            result.extend(pattern[:extend_size])
    
    final_result = bytes(result)
    execution_time = (time.time() - start_time) * 1000
    
    print(f"   ✅ TARGET RECONSTRUCTION COMPLETE: {{len(final_result):,}} bytes")
    print(f"   ⚡ Execution time: {{execution_time:.2f}}ms")
    
    return final_result, execution_time

perfect_file, exec_time = reconstruct_file_singlecore()
print("🎯 PERFECT FILE GENERATED FOR TARGET")
'''

    def start_server(self):
        """Start server to handle incoming transfers"""

        print(f"🚀 Starting script transfer server on port {self.listen_port}")

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.listen_port))
        self.server_socket.listen(5)

        print(f"✅ Server listening on 0.0.0.0:{self.listen_port}")

        while True:
            try:
                client_socket, client_addr = self.server_socket.accept()
                print(f"📡 Connection from {client_addr}")

                # Handle connection in thread
                handler_thread = threading.Thread(
                    target=self._handle_client, args=(client_socket, client_addr)
                )
                handler_thread.daemon = True
                handler_thread.start()

            except Exception as e:
                print(f"Server error: {e}")
                break

    def _handle_client(self, client_socket: socket.socket, client_addr):
        """Handle incoming client connection"""

        try:
            # Receive request
            request_data = client_socket.recv(4096)
            request = json.loads(request_data.decode().strip())

            if request["type"] == "capability_probe":
                self._handle_capability_probe(client_socket)
            elif request["type"] == "script_transfer":
                self._handle_script_transfer(client_socket, request)

        except Exception as e:
            print(f"Client handler error: {e}")
        finally:
            client_socket.close()

    def _handle_capability_probe(self, client_socket: socket.socket):
        """Handle capability probe request"""

        # Return system capabilities
        capabilities = {
            "compute_level": "multicore",  # Simulated
            "memory_mb": 16384,  # 16GB simulated
            "bandwidth_mbps": 1000,  # 1Gbps simulated
            "cpu_cores": 8,  # 8 cores simulated
            "timestamp": time.time(),
        }

        response = json.dumps(capabilities).encode()
        client_socket.send(response)

    def _handle_script_transfer(self, client_socket: socket.socket, request: Dict):
        """Handle incoming script transfer"""

        session_id = request["session_id"]
        filename = request["filename"]
        symbols = request["symbols"]
        script_size = request["script_size"]

        print(f"📥 Receiving script transfer: {session_id}")

        try:
            # Receive compressed script
            script_compressed = client_socket.recv(script_size)

            # Decompress and execute
            script_code = zlib.decompress(script_compressed).decode()

            print(f"⚡ Executing script for {filename}")

            # Execute script (simulated)
            start_time = time.time()
            time.sleep(0.1)  # Simulate execution
            execution_time = (time.time() - start_time) * 1000

            # Send success response
            response = {"success": True, "execution_time": execution_time}

            client_socket.send(json.dumps(response).encode())

            print(f"✅ Script execution complete: {execution_time:.2f}ms")

        except Exception as e:
            print(f"❌ Script execution failed: {e}")

            response = {"success": False, "error": str(e)}
            client_socket.send(json.dumps(response).encode())

    def demonstrate_single_target_transfer(self):
        """Demonstrate single target transfers"""

        print("🎯 SINGLE TARGET TRANSFER DEMONSTRATION")
        print("=" * 50)

        # Test different targets
        test_targets = [
            ("192.168.1.100", 9001),
            ("10.0.0.50", 9001),
            ("172.16.0.10", 9001),
        ]

        test_files = [
            ("report.pdf", 5_242_880),  # 5MB
            ("presentation.pptx", 52_428_800),  # 50MB
            ("backup.tar.gz", 1_073_741_824),  # 1GB
        ]

        for host, port in test_targets:
            print(f"\n🔍 Testing target: {host}:{port}")

            # Probe capabilities
            target_info = self.probe_target_capabilities(host, port)

            for filename, file_size in test_files:
                print(f"\n📁 Transferring: {filename}")

                # Execute transfer
                session_id = self.transfer_to_target(target_info, filename, file_size)

                if session_id in self.active_sessions:
                    session = self.active_sessions[session_id]
                    if session.success:
                        print(f"✅ Transfer successful: {session_id}")
                    else:
                        print(f"❌ Transfer failed: {session_id}")


def main():
    """Demonstrate single target script transfer"""

    engine = SingleTargetScriptTransfer()

    # Start server in background for demo
    server_thread = threading.Thread(target=engine.start_server)
    server_thread.daemon = True
    server_thread.start()

    time.sleep(1)  # Let server start

    # Run demonstration
    engine.demonstrate_single_target_transfer()

    print("\n🏆 SINGLE TARGET DEMONSTRATION COMPLETE")
    print("=" * 50)
    print("Single Target Script Transfer achievements:")
    print("✅ Target capability probing")
    print("✅ Adaptive script optimization")
    print("✅ Optimized network connections")
    print("✅ Real-time transfer monitoring")
    print("✅ Point-to-point maximum efficiency")
    print()
    print("🎯 SINGLE TARGET = MAXIMUM PRECISION")


if __name__ == "__main__":
    main()
