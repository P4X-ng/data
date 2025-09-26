#!/usr/bin/env python3
"""
Mega Asset Spider - Catalog EVERYTHING as CPU resources
Every network response is a potential computation result
"""

import socket
import time
import threading
import sqlite3
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

class MegaSpider:
    def __init__(self, db_path="mega_assets.db"):
        self.db_path = db_path
        self.executor = ThreadPoolExecutor(max_workers=50)
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY,
                host TEXT,
                port INTEGER,
                protocol TEXT,
                response_type TEXT,
                avg_latency REAL,
                success_rate REAL,
                last_value INTEGER,
                instruction_potential TEXT,
                last_checked INTEGER
            )
        """)
        conn.commit()
        conn.close()
    
    def test_tcp_port(self, host, port, timeout=0.1):
        """Test TCP port - even closed ports give us data!"""
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            latency = time.time() - start
            
            # Every result is useful:
            # 0 = connected, 111 = refused, 110 = timeout
            return {
                'host': host,
                'port': port,
                'protocol': 'TCP',
                'response_type': 'CONNECTION',
                'latency': latency,
                'value': result,
                'success': True  # Even failures are successes!
            }
        except Exception as e:
            return None
    
    def test_udp_port(self, host, port=53):
        """Test UDP - DNS queries, DHCP, NTP, etc."""
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.1)
            
            # Send different payloads based on port
            if port == 53:  # DNS
                payload = b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06google\x03com\x00\x00\x01\x00\x01'
            elif port == 123:  # NTP
                payload = b'\x1b' + b'\x00' * 47
            else:  # Generic
                payload = b'PING'
            
            sock.sendto(payload, (host, port))
            try:
                data, addr = sock.recvfrom(512)
                response_len = len(data)
            except:
                response_len = 0
            
            sock.close()
            latency = time.time() - start
            
            return {
                'host': host,
                'port': port,
                'protocol': 'UDP',
                'response_type': 'PACKET',
                'latency': latency,
                'value': response_len,
                'success': True
            }
        except:
            return None
    
    def scan_ip_range(self, base_ip, count=100):
        """Scan IP range for assets"""
        print(f"🕷️ Scanning {count} IPs from {base_ip}")
        
        # Generate IP list
        base_parts = base_ip.split('.')
        base_int = int(base_parts[3])
        
        tasks = []
        common_ports = [22, 23, 53, 80, 443, 8080, 3389, 5432, 3306, 6379, 25, 110, 143, 993, 995]
        
        for i in range(count):
            ip_int = (base_int + i) % 256
            ip = f"{base_parts[0]}.{base_parts[1]}.{base_parts[2]}.{ip_int}"
            
            # Test multiple ports per IP
            for port in random.sample(common_ports, 3):  # Random 3 ports per IP
                tasks.append(self.executor.submit(self.test_tcp_port, ip, port))
            
            # Test UDP DNS
            tasks.append(self.executor.submit(self.test_udp_port, ip, 53))
        
        # Collect results
        results = []
        for future in as_completed(tasks):
            result = future.result()
            if result:
                results.append(result)
        
        # Store in database
        self._store_results(results)
        print(f"✅ Found {len(results)} assets")
        return results
    
    def scan_public_dns(self):
        """Scan public DNS servers - guaranteed fast responses"""
        dns_servers = [
            '8.8.8.8', '8.8.4.4',  # Google
            '1.1.1.1', '1.0.0.1',  # Cloudflare
            '208.67.222.222', '208.67.220.220',  # OpenDNS
            '9.9.9.9', '149.112.112.112',  # Quad9
            '76.76.19.19', '76.223.100.101',  # Alternate DNS
        ]
        
        print(f"🌐 Scanning {len(dns_servers)} public DNS servers")
        
        tasks = []
        for dns in dns_servers:
            # Test both TCP and UDP DNS
            tasks.append(self.executor.submit(self.test_tcp_port, dns, 53))
            tasks.append(self.executor.submit(self.test_udp_port, dns, 53))
        
        results = [f.result() for f in tasks if f.result()]
        self._store_results(results)
        print(f"✅ DNS servers: {len(results)} responses")
        return results
    
    def scan_localhost_ports(self):
        """Scan localhost - instant responses!"""
        print("🏠 Scanning localhost ports")
        
        # Scan wide port range on localhost
        tasks = []
        for port in range(1, 1000, 10):  # Every 10th port
            tasks.append(self.executor.submit(self.test_tcp_port, '127.0.0.1', port))
        
        results = [f.result() for f in tasks if f.result()]
        self._store_results(results)
        print(f"✅ Localhost: {len(results)} ports scanned")
        return results
    
    def _store_results(self, results):
        """Store results in database"""
        conn = sqlite3.connect(self.db_path)
        
        for result in results:
            # Determine instruction potential based on characteristics
            if result['latency'] < 0.01:  # <10ms
                potential = "FAST_OP"
            elif result['protocol'] == 'UDP':
                potential = "MEMORY_OP"
            elif result['response_type'] == 'CONNECTION':
                potential = "LOGIC_OP"
            else:
                potential = "GENERAL_OP"
            
            conn.execute("""
                INSERT OR REPLACE INTO assets 
                (host, port, protocol, response_type, avg_latency, success_rate, 
                 last_value, instruction_potential, last_checked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['host'], result['port'], result['protocol'],
                result['response_type'], result['latency'], 1.0,
                result['value'], potential, int(time.time())
            ))
        
        conn.commit()
        conn.close()
    
    def get_fastest_assets(self, limit=20):
        """Get fastest assets for CPU operations"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT host, port, protocol, avg_latency, instruction_potential, last_value
            FROM assets 
            ORDER BY avg_latency ASC 
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        
        return [{'host': r[0], 'port': r[1], 'protocol': r[2], 
                'latency': r[3], 'potential': r[4], 'value': r[5]} for r in rows]
    
    def stats(self):
        """Show asset database stats"""
        conn = sqlite3.connect(self.db_path)
        
        total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        by_potential = conn.execute("""
            SELECT instruction_potential, COUNT(*), AVG(avg_latency)
            FROM assets GROUP BY instruction_potential
        """).fetchall()
        
        fastest = conn.execute("""
            SELECT host, port, avg_latency FROM assets 
            ORDER BY avg_latency ASC LIMIT 5
        """).fetchall()
        
        conn.close()
        
        print(f"📊 Asset Database Stats")
        print(f"Total assets: {total}")
        print("\nBy instruction potential:")
        for potential, count, avg_lat in by_potential:
            print(f"  {potential:12}: {count:3} assets, {avg_lat*1000:.1f}ms avg")
        
        print(f"\nFastest 5 assets:")
        for host, port, lat in fastest:
            print(f"  {host}:{port} - {lat*1000:.1f}ms")

def main():
    print("🕷️ MEGA ASSET SPIDER")
    print("Cataloging the entire internet as CPU resources...")
    print("=" * 50)
    
    spider = MegaSpider()
    
    # Scan different asset types
    spider.scan_localhost_ports()
    spider.scan_public_dns()
    spider.scan_ip_range("192.168.1.1", 50)  # Local network
    spider.scan_ip_range("10.0.0.1", 30)     # Another common range
    
    # Show results
    spider.stats()
    
    print(f"\n🚀 Top 10 fastest assets for CPU operations:")
    fastest = spider.get_fastest_assets(10)
    for asset in fastest:
        print(f"  {asset['host']}:{asset['port']} ({asset['protocol']}) - {asset['latency']*1000:.1f}ms - {asset['potential']}")

if __name__ == "__main__":
    main()