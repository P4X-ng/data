#!/usr/bin/env python3
"""
Debug Network CPU - With lots of logging to see what's happening
"""

import sqlite3
import socket
import time
import sys

def test_db():
    """Test if we can read the asset database"""
    print("🔍 Testing asset database...")
    
    try:
        conn = sqlite3.connect("mega_assets.db")
        count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        print(f"✅ Database has {count} assets")
        
        # Show fastest 5
        fastest = conn.execute("""
            SELECT host, port, protocol, avg_latency 
            FROM assets ORDER BY avg_latency ASC LIMIT 5
        """).fetchall()
        
        print("Top 5 fastest assets:")
        for host, port, protocol, latency in fastest:
            print(f"  {host}:{port} ({protocol}) - {latency*1000:.1f}ms")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_single_socket():
    """Test a single socket operation with logging"""
    print(f"\n🔌 Testing single socket operation...")
    
    try:
        print("  Creating socket...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        print("  Setting timeout...")
        sock.settimeout(0.1)
        
        print("  Connecting to 127.0.0.1:22...")
        start = time.time()
        result = sock.connect_ex(('127.0.0.1', 22))
        latency = time.time() - start
        
        print(f"  Connection result: {result}")
        print(f"  Latency: {latency*1000:.1f}ms")
        
        sock.close()
        print("  Socket closed")
        
        return result
        
    except Exception as e:
        print(f"❌ Socket error: {e}")
        return None

def simple_add(a, b):
    """Simple ADD operation with logging"""
    print(f"\n➕ ADD({a}, {b}) with network verification...")
    
    # Basic computation
    result = (a + b) % 256
    print(f"  Basic result: {result}")
    
    # Network verification
    try:
        print("  Network verification...")
        sock_result = test_single_socket()
        if sock_result is not None:
            final_result = (result + sock_result) % 256
            print(f"  Network-modified result: {final_result}")
            return final_result
        else:
            print("  Using basic result (network failed)")
            return result
    except Exception as e:
        print(f"  Network error: {e}")
        return result

def main():
    print("🐛 DEBUG NETWORK CPU")
    print("=" * 30)
    
    # Test database
    if not test_db():
        print("❌ Database test failed, creating minimal assets...")
        # Create minimal database for testing
        conn = sqlite3.connect("debug_assets.db")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                host TEXT, port INTEGER, protocol TEXT, 
                avg_latency REAL, instruction_potential TEXT
            )
        """)
        conn.execute("""
            INSERT INTO assets VALUES 
            ('127.0.0.1', 22, 'TCP', 0.001, 'FAST_OP'),
            ('127.0.0.1', 80, 'TCP', 0.002, 'FAST_OP')
        """)
        conn.commit()
        conn.close()
        print("✅ Created debug database")
    
    # Test single socket
    test_single_socket()
    
    # Test simple computation
    result1 = simple_add(5, 3)
    result2 = simple_add(10, 7)
    
    print(f"\n📊 Results:")
    print(f"  5 + 3 = {result1}")
    print(f"  10 + 7 = {result2}")
    
    print(f"\n✅ Debug complete!")

if __name__ == "__main__":
    main()