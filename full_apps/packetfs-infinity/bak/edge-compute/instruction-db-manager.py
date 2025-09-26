#!/usr/bin/env python3
"""
Instruction Database Manager - Add/modify network-based CPU instructions
"""

import sqlite3
import json
from typing import Dict, List

class InstructionManager:
    def __init__(self, db_path: str = "instructions.db"):
        self.db_path = db_path
    
    def add_instruction(self, opcode: str, method: str, endpoint: str, payload: str = "", parser: str = "default"):
        """Add a new instruction mapping"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO instructions VALUES (?, ?, ?, ?, ?)",
            (opcode, method, endpoint, payload, parser)
        )
        conn.commit()
        conn.close()
        print(f"✅ Added {opcode}: {method} {endpoint}")
    
    def list_instructions(self) -> List[Dict]:
        """List all available instructions"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT * FROM instructions ORDER BY opcode").fetchall()
        conn.close()
        
        instructions = []
        for row in rows:
            instructions.append({
                "opcode": row[0],
                "method": row[1], 
                "endpoint": row[2],
                "payload": row[3],
                "parser": row[4]
            })
        return instructions
    
    def remove_instruction(self, opcode: str):
        """Remove an instruction"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM instructions WHERE opcode = ?", (opcode,))
        conn.commit()
        conn.close()
        print(f"🗑️ Removed {opcode}")

def main():
    manager = InstructionManager()
    
    print("🔧 Instruction Database Manager")
    print("Commands: add, list, remove, presets, quit")
    
    while True:
        cmd = input("\n> ").strip().lower()
        
        if cmd == "quit" or cmd == "q":
            break
            
        elif cmd == "list" or cmd == "l":
            instructions = manager.list_instructions()
            print(f"\n📋 {len(instructions)} instructions:")
            for instr in instructions:
                print(f"  {instr['opcode']:8} {instr['method']:6} {instr['endpoint']}")
                if instr['payload']:
                    print(f"           payload: {instr['payload']}")
        
        elif cmd == "add" or cmd == "a":
            print("Add new instruction:")
            opcode = input("  Opcode (e.g. XOR): ").strip().upper()
            method = input("  Method (DNS/HTTP/PING): ").strip().upper()
            endpoint = input("  Endpoint: ").strip()
            payload = input("  Payload (optional): ").strip()
            parser = input("  Parser (optional): ").strip() or "default"
            
            manager.add_instruction(opcode, method, endpoint, payload, parser)
        
        elif cmd == "remove" or cmd == "r":
            opcode = input("Opcode to remove: ").strip().upper()
            manager.remove_instruction(opcode)
        
        elif cmd == "presets" or cmd == "p":
            print("🎯 Adding preset instructions...")
            
            # Advanced math operations
            manager.add_instruction("XOR", "DNS", "8.8.8.8", "TXT {a}.xor.{b}.bit.local", "dns_bit_parser")
            manager.add_instruction("AND", "HTTP", "httpbin.org/headers", "X-Bit-A: {a}\nX-Bit-B: {b}", "header_bit_parser")
            manager.add_instruction("OR", "PING", "bit{a}.or{b}.1.1.1.1", "", "ping_bit_parser")
            
            # Memory operations using CDN
            manager.add_instruction("LOAD", "HTTP", "cdn.jsdelivr.net/npm/lodash@{addr}/package.json", "", "cdn_load_parser")
            manager.add_instruction("STORE", "HTTP", "httpbin.org/put", '{"addr": {addr}, "value": {value}}', "store_parser")
            
            # Stack operations using email bounces
            manager.add_instruction("PUSH", "SMTP", "push{value}@nonexistent-{stack_ptr}.com", "", "bounce_parser")
            manager.add_instruction("POP", "SMTP", "pop@stack-{stack_ptr}.com", "", "bounce_pop_parser")
            
            # Conditional jumps using SSL cert serial numbers
            manager.add_instruction("JZ", "TLS", "cert{addr}.badssl.com:443", "", "cert_serial_parser")
            manager.add_instruction("JNZ", "TLS", "expired{addr}.badssl.com:443", "", "cert_expired_parser")
            
            # I/O using NTP timestamps
            manager.add_instruction("IN", "NTP", "pool.ntp.org", "port={port}", "ntp_timestamp_parser")
            manager.add_instruction("OUT", "NTP", "{value}.ntp.local", "", "ntp_out_parser")
            
            print("✅ Added 10 preset instructions")
        
        else:
            print("Unknown command. Try: add, list, remove, presets, quit")

if __name__ == "__main__":
    main()