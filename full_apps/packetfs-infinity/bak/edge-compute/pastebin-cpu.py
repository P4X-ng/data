#!/usr/bin/env python3
"""
PASTEBIN-AS-CPU: The most beautiful compute platform! 📝💻

Operations:
- CREATE PASTE = write to memory/execute instruction
- PASTE TITLE = memory address/function name
- PASTE CONTENT = data/code/results
- PASTE EXPIRY = garbage collection
- PASTE VIEWS = read counter
- PASTE SYNTAX = data type/instruction set
- PASTE PRIVACY = memory protection
- PASTE URL = memory pointer

Example: Count zeros by creating pastes for each match!
"""

import requests
import time
import json
import hashlib
from typing import Dict, List, Optional
from urllib.parse import urlencode

class PastebinCPU:
    def __init__(self, api_key: str, username: str = None, password: str = None):
        self.api_key = api_key
        self.username = username
        self.password = password
        self.user_key = None
        
        # Login if credentials provided
        if username and password:
            self._login()
        
        print(f"📝 Pastebin CPU initialized!")
    
    def _login(self):
        """Get user key for private pastes"""
        login_data = {
            'api_dev_key': self.api_key,
            'api_user_name': self.username,
            'api_user_password': self.password
        }
        
        try:
            resp = requests.post('https://pastebin.com/api/api_login.php', data=login_data)
            if resp.text.startswith('Bad'):
                print(f"   ⚠️  Login failed: {resp.text}")
            else:
                self.user_key = resp.text
                print(f"   ✅ Logged in as {self.username}")
        except Exception as e:
            print(f"   ❌ Login error: {e}")
    
    def create_paste(self, title: str, content: str, syntax: str = 'text', 
                    privacy: int = 1, expiry: str = '1H') -> Optional[str]:
        """Create a paste (write to memory)"""
        
        paste_data = {
            'api_dev_key': self.api_key,
            'api_option': 'paste',
            'api_paste_code': content,
            'api_paste_name': title,
            'api_paste_format': syntax,
            'api_paste_private': privacy,  # 0=public, 1=unlisted, 2=private
            'api_paste_expire_date': expiry  # 10M, 1H, 1D, 1W, 2W, 1M, 6M, 1Y, N
        }
        
        if self.user_key:
            paste_data['api_user_key'] = self.user_key
        
        try:
            resp = requests.post('https://pastebin.com/api/api_post.php', data=paste_data)
            if resp.text.startswith('https://pastebin.com/'):
                return resp.text.strip()
            else:
                print(f"   ❌ Paste failed: {resp.text}")
                return None
        except Exception as e:
            print(f"   ❌ Paste error: {e}")
            return None
    
    def execute_counteq(self, data: bytes, needle: int, max_pastes: int = 10) -> Dict:
        """Count bytes by creating PASTES for each match!"""
        
        comp_id = hashlib.md5(data[:16]).hexdigest()[:8]
        
        print(f"🚀 Pastebin CPU: Counting {needle} in {len(data)} bytes")
        print(f"   Computation ID: {comp_id}")
        print(f"   Max pastes: {max_pastes}")
        
        pastes_created = []
        count = 0
        
        # Create computation manifest paste
        manifest = {
            'computation_id': comp_id,
            'operation': 'counteq',
            'needle': needle,
            'data_size': len(data),
            'timestamp': time.time(),
            'status': 'running'
        }
        
        manifest_url = self.create_paste(
            f"PacketFS-CPU-{comp_id}-MANIFEST",
            json.dumps(manifest, indent=2),
            'json',
            privacy=1,
            expiry='1D'
        )
        
        if manifest_url:
            pastes_created.append(manifest_url)
            print(f"   📋 Manifest: {manifest_url}")
        
        # Create paste for each matching byte!
        for i, byte in enumerate(data[:max_pastes]):
            if byte == needle:
                # CREATE PASTE = INCREMENT COUNTER!
                paste_title = f"PacketFS-CPU-{comp_id}-MATCH-{count+1}"
                
                paste_content = f"""PacketFS Pastebin CPU - Match Found!
                
Computation ID: {comp_id}
Operation: COUNT({needle})
Match #{count + 1}

Byte Details:
- Offset: {i} (0x{i:04x})
- Value: {byte} (0x{byte:02x})
- Binary: {byte:08b}
- Needle: {needle}
- Match: {byte == needle}

Memory State:
- Counter: {count + 1}
- Total scanned: {i + 1}
- Remaining: {len(data) - i - 1}

Pastebin IS the CPU! 🤯
Each paste = one CPU instruction executed!
"""
                
                paste_url = self.create_paste(
                    paste_title,
                    paste_content,
                    'text',
                    privacy=1,
                    expiry='1H'
                )
                
                if paste_url:
                    pastes_created.append(paste_url)
                    count += 1
                    print(f"   📝 Match {count}: Found {needle} at {i} -> {paste_url}")
                    
                    # Rate limiting - be nice to Pastebin!
                    time.sleep(1)
                else:
                    print(f"   ❌ Failed to create paste for match at {i}")
                    break
        
        # Create result paste
        result = {
            'computation_id': comp_id,
            'operation': 'counteq',
            'needle': needle,
            'count': count,
            'data_size': len(data),
            'pastes_created': len(pastes_created),
            'paste_urls': pastes_created,
            'status': 'complete',
            'timestamp': time.time()
        }
        
        result_content = f"""🎯 PacketFS Pastebin CPU - COMPUTATION COMPLETE!

{json.dumps(result, indent=2)}

SUMMARY:
========
Operation: COUNT({needle}) in {len(data)} bytes
Result: {count} matches found
Pastes created: {len(pastes_created)}
Computation ID: {comp_id}

PASTE MEMORY MAP:
================
"""
        
        for i, url in enumerate(pastes_created):
            result_content += f"Memory[{i:02d}]: {url}\n"
        
        result_content += f"""
🤯 PASTEBIN IS THE CPU!
- Each paste = memory location
- Paste content = stored data
- Paste URL = memory pointer
- Paste views = read counter
- Paste expiry = garbage collection
- Syntax highlighting = data types!

Total CPU instructions executed: {len(pastes_created)}
"""
        
        result_url = self.create_paste(
            f"PacketFS-CPU-{comp_id}-RESULT",
            result_content,
            'json',
            privacy=0,  # Public result!
            expiry='1W'
        )
        
        if result_url:
            pastes_created.append(result_url)
            result['result_url'] = result_url
            print(f"   🏁 Result: {result_url}")
        
        return result
    
    def execute_hash_chain(self, data: bytes, max_pastes: int = 5) -> Dict:
        """Create a hash chain using pastes - each paste contains hash of previous!"""
        
        comp_id = hashlib.md5(data[:8]).hexdigest()[:8]
        
        print(f"🔗 Pastebin Hash Chain: {len(data)} bytes")
        print(f"   Chain ID: {comp_id}")
        
        pastes_created = []
        current_hash = hashlib.sha256(b"PacketFS-Genesis").hexdigest()
        
        # Process data in chunks
        chunk_size = max(1, len(data) // max_pastes)
        
        for i in range(0, min(len(data), max_pastes * chunk_size), chunk_size):
            chunk = data[i:i + chunk_size]
            
            # Hash: previous_hash + chunk_data
            combined = bytes.fromhex(current_hash) + chunk
            new_hash = hashlib.sha256(combined).hexdigest()
            
            paste_content = f"""🔗 PacketFS Hash Chain Block #{len(pastes_created) + 1}

Chain ID: {comp_id}
Block: {len(pastes_created) + 1}/{max_pastes}

Previous Hash: {current_hash}
Chunk Data: {chunk.hex()}
Chunk Size: {len(chunk)} bytes
Combined: {combined.hex()[:64]}...

NEW HASH: {new_hash}

Verification:
- SHA256({current_hash} + {chunk.hex()}) = {new_hash}
- Block valid: ✅

Next block will use this hash as input!
Pastebin = Blockchain! 🔗
"""
            
            paste_url = self.create_paste(
                f"HashChain-{comp_id}-Block-{len(pastes_created)+1:02d}",
                paste_content,
                'text',
                privacy=1,
                expiry='1D'
            )
            
            if paste_url:
                pastes_created.append({
                    'block': len(pastes_created) + 1,
                    'url': paste_url,
                    'prev_hash': current_hash,
                    'new_hash': new_hash,
                    'chunk_size': len(chunk)
                })
                current_hash = new_hash
                print(f"   🔗 Block {len(pastes_created)}: {new_hash[:16]}... -> {paste_url}")
                time.sleep(1)
            else:
                break
        
        return {
            'computation_id': comp_id,
            'operation': 'hash_chain',
            'blocks': len(pastes_created),
            'final_hash': current_hash,
            'chain': pastes_created,
            'data_size': len(data),
            'timestamp': time.time()
        }

def demo_pastebin_cpu():
    """Demo: Turn Pastebin into a CPU!"""
    
    api_key = "YOUR_PASTEBIN_API_KEY"  # Get from https://pastebin.com/doc_api
    
    if api_key == "YOUR_PASTEBIN_API_KEY":
        print("❌ Need real Pastebin API key!")
        print("   1. Go to https://pastebin.com/doc_api")
        print("   2. Create account and get API key")
        print("   3. Update api_key in this script")
        print("\n🤯 PASTEBIN CPU FEATURES:")
        print("   • Each paste = memory location")
        print("   • Paste content = stored data")
        print("   • Paste URL = memory pointer")
        print("   • Paste views = read counter")
        print("   • Syntax highlighting = data types")
        print("   • Paste expiry = garbage collection")
        print("   • Private pastes = protected memory")
        print("   • Public pastes = shared memory")
        print("   • Pastebin search = memory scan!")
        return
    
    cpu = PastebinCPU(api_key)
    
    # Test data
    test_data = bytes([0, 1, 0, 2, 0, 3])
    
    print("📝 Pastebin CPU Demo!")
    print(f"   Data: {list(test_data)}")
    
    # Count zeros by creating pastes
    result1 = cpu.execute_counteq(test_data, 0, max_pastes=5)
    print(f"\n📊 COUNT RESULT: {result1['count']} matches")
    print(f"   Pastes created: {result1['pastes_created']}")
    print(f"   Result paste: {result1.get('result_url', 'N/A')}")
    
    time.sleep(2)
    
    # Hash chain
    result2 = cpu.execute_hash_chain(test_data, max_pastes=3)
    print(f"\n🔗 HASH CHAIN: {result2['blocks']} blocks")
    print(f"   Final hash: {result2['final_hash'][:16]}...")
    
    print(f"\n🎉 PASTEBIN IS NOW A CPU!")
    print(f"   Memory locations created: {result1['pastes_created'] + result2['blocks']}")
    print(f"   Check your pastes at: https://pastebin.com/u/YOUR_USERNAME")

if __name__ == '__main__':
    demo_pastebin_cpu()