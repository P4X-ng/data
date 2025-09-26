#!/usr/bin/env python3
"""
PASTEBIN FIBONACCI BENCHMARK 🚀📝

Distributed Fibonacci computation using Pastebin as CPU!
Each paste = one Fibonacci number calculation
Benchmark: How fast can we compute Fib(N) using paste creation?

Strategy:
- Create paste for each Fib number
- Use paste URLs as "memory addresses" 
- Previous pastes store intermediate results
- Final paste contains the answer
- Measure pastes/second throughput!
"""

import requests
import time
import json
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

class PastebinFibonacciBench:
    def __init__(self, api_key: str, max_workers: int = 5):
        self.api_key = api_key
        self.max_workers = max_workers
        self.pastes_created = []
        self.creation_times = []
        self.lock = threading.Lock()
        
        print(f"🚀 Pastebin Fibonacci Benchmark")
        print(f"   Max workers: {max_workers}")
        print(f"   Rate limiting: 1 paste/second per worker")
    
    def create_paste_safe(self, title: str, content: str, syntax: str = 'text') -> Optional[str]:
        """Thread-safe paste creation with timing"""
        paste_data = {
            'api_dev_key': self.api_key,
            'api_option': 'paste',
            'api_paste_code': content,
            'api_paste_name': title,
            'api_paste_format': syntax,
            'api_paste_private': 1,  # Unlisted
            'api_paste_expire_date': '1H'  # 1 hour expiry
        }
        
        start_time = time.time()
        try:
            resp = requests.post('https://pastebin.com/api/api_post.php', data=paste_data)
            end_time = time.time()
            
            if resp.text.startswith('https://pastebin.com/'):
                url = resp.text.strip()
                
                with self.lock:
                    self.pastes_created.append(url)
                    self.creation_times.append(end_time - start_time)
                
                return url
            else:
                print(f"   ❌ Paste failed: {resp.text}")
                return None
                
        except Exception as e:
            print(f"   ❌ Paste error: {e}")
            return None
    
    def compute_fib_sequential(self, n: int) -> Dict:
        """Sequential Fibonacci using pastes - baseline"""
        print(f"📝 Sequential Fibonacci: Fib({n})")
        
        comp_id = hashlib.md5(f"seq-fib-{n}".encode()).hexdigest()[:8]
        start_time = time.time()
        
        # Base cases
        if n <= 1:
            content = f"""Fibonacci Base Case
Fib({n}) = {n}
Computation: Sequential
ID: {comp_id}
Result: {n}
"""
            url = self.create_paste_safe(f"Fib-{comp_id}-{n}", content)
            return {
                'n': n,
                'result': n,
                'method': 'sequential',
                'pastes': 1,
                'urls': [url] if url else [],
                'duration': time.time() - start_time
            }
        
        # Compute iteratively, one paste per number
        fib_prev, fib_curr = 0, 1
        urls = []
        
        for i in range(2, n + 1):
            fib_next = fib_prev + fib_curr
            
            content = f"""Fibonacci Step {i}
Fib({i}) = Fib({i-1}) + Fib({i-2})
Fib({i}) = {fib_curr} + {fib_prev} = {fib_next}

Computation: Sequential
ID: {comp_id}
Step: {i}/{n}
Progress: {i/n*100:.1f}%

Previous results stored in pastes:
- Fib({i-2}) = {fib_prev}
- Fib({i-1}) = {fib_curr}
- Fib({i}) = {fib_next}

Pastebin IS the CPU! 🚀
"""
            
            url = self.create_paste_safe(f"Fib-{comp_id}-{i}", content, 'text')
            if url:
                urls.append(url)
                print(f"   📝 Fib({i}) = {fib_next} -> {url}")
            
            fib_prev, fib_curr = fib_curr, fib_next
            
            # Rate limiting
            time.sleep(1.1)
        
        duration = time.time() - start_time
        
        return {
            'n': n,
            'result': fib_curr,
            'method': 'sequential',
            'pastes': len(urls),
            'urls': urls,
            'duration': duration,
            'pastes_per_second': len(urls) / duration if duration > 0 else 0
        }
    
    def compute_fib_parallel(self, n: int) -> Dict:
        """Parallel Fibonacci using ThreadPool - MAXIMUM PASTE SPEED!"""
        print(f"⚡ Parallel Fibonacci: Fib({n}) with {self.max_workers} workers")
        
        comp_id = hashlib.md5(f"par-fib-{n}".encode()).hexdigest()[:8]
        start_time = time.time()
        
        # Pre-compute all Fibonacci numbers
        fib_numbers = [0, 1]
        for i in range(2, n + 1):
            fib_numbers.append(fib_numbers[i-1] + fib_numbers[i-2])
        
        def create_fib_paste(i: int) -> Optional[str]:
            """Create paste for Fib(i) - runs in parallel!"""
            fib_val = fib_numbers[i]
            
            content = f"""🚀 PARALLEL Fibonacci Computation
Fib({i}) = {fib_val}

Computation Details:
- Method: Parallel ThreadPool
- Workers: {self.max_workers}
- Computation ID: {comp_id}
- Thread: {threading.current_thread().name}
- Timestamp: {time.time()}

Mathematical Verification:
"""
            
            if i >= 2:
                content += f"- Fib({i}) = Fib({i-1}) + Fib({i-2})\n"
                content += f"- Fib({i}) = {fib_numbers[i-1]} + {fib_numbers[i-2]} = {fib_val}\n"
            else:
                content += f"- Base case: Fib({i}) = {fib_val}\n"
            
            content += f"""
Binary: {bin(fib_val)}
Hex: 0x{fib_val:x}
Digits: {len(str(fib_val))}

🤯 PASTEBIN PARALLEL PROCESSING!
Each paste created simultaneously!
Maximum distributed computation speed!
"""
            
            # Add small delay per worker to respect rate limits
            time.sleep(1.2)
            
            return self.create_paste_safe(f"ParFib-{comp_id}-{i:03d}", content, 'text')
        
        # Launch parallel paste creation!
        urls = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all paste creation jobs
            future_to_i = {executor.submit(create_fib_paste, i): i for i in range(n + 1)}
            
            # Collect results as they complete
            for future in as_completed(future_to_i):
                i = future_to_i[future]
                try:
                    url = future.result()
                    if url:
                        urls.append((i, url))
                        print(f"   ⚡ Fib({i}) = {fib_numbers[i]} -> {url}")
                except Exception as e:
                    print(f"   ❌ Failed Fib({i}): {e}")
        
        duration = time.time() - start_time
        
        # Sort URLs by Fibonacci index
        urls.sort(key=lambda x: x[0])
        url_list = [url for _, url in urls]
        
        return {
            'n': n,
            'result': fib_numbers[n],
            'method': 'parallel',
            'pastes': len(url_list),
            'urls': url_list,
            'duration': duration,
            'pastes_per_second': len(url_list) / duration if duration > 0 else 0,
            'workers': self.max_workers
        }
    
    def benchmark_comparison(self, n: int) -> Dict:
        """Compare sequential vs parallel Fibonacci computation"""
        print(f"🏁 FIBONACCI BENCHMARK: Fib({n})")
        print("=" * 50)
        
        results = {}
        
        # Sequential benchmark
        print("\n1️⃣ SEQUENTIAL METHOD:")
        seq_result = self.compute_fib_sequential(n)
        results['sequential'] = seq_result
        
        print(f"   ✅ Result: Fib({n}) = {seq_result['result']}")
        print(f"   📝 Pastes: {seq_result['pastes']}")
        print(f"   ⏱️  Duration: {seq_result['duration']:.2f}s")
        print(f"   🚀 Speed: {seq_result['pastes_per_second']:.2f} pastes/sec")
        
        # Wait between tests
        print("\n⏳ Waiting 5 seconds before parallel test...")
        time.sleep(5)
        
        # Parallel benchmark
        print("\n2️⃣ PARALLEL METHOD:")
        par_result = self.compute_fib_parallel(n)
        results['parallel'] = par_result
        
        print(f"   ✅ Result: Fib({n}) = {par_result['result']}")
        print(f"   📝 Pastes: {par_result['pastes']}")
        print(f"   ⏱️  Duration: {par_result['duration']:.2f}s")
        print(f"   🚀 Speed: {par_result['pastes_per_second']:.2f} pastes/sec")
        print(f"   👥 Workers: {par_result['workers']}")
        
        # Comparison
        speedup = par_result['pastes_per_second'] / seq_result['pastes_per_second'] if seq_result['pastes_per_second'] > 0 else 0
        
        print(f"\n🏆 BENCHMARK RESULTS:")
        print(f"   Speedup: {speedup:.2f}x faster")
        print(f"   Total pastes created: {seq_result['pastes'] + par_result['pastes']}")
        print(f"   Peak paste rate: {max(seq_result['pastes_per_second'], par_result['pastes_per_second']):.2f}/sec")
        
        results['comparison'] = {
            'speedup': speedup,
            'total_pastes': seq_result['pastes'] + par_result['pastes'],
            'peak_rate': max(seq_result['pastes_per_second'], par_result['pastes_per_second'])
        }
        
        return results

def main():
    """Run the Pastebin Fibonacci benchmark!"""
    
    api_key = "YOUR_PASTEBIN_API_KEY"  # Get from https://pastebin.com/doc_api
    
    if api_key == "YOUR_PASTEBIN_API_KEY":
        print("❌ Need real Pastebin API key!")
        print("   1. Go to https://pastebin.com/doc_api")
        print("   2. Create account and get API key")
        print("   3. Update api_key in this script")
        print("\n🚀 WHAT WE'LL BENCHMARK:")
        print("   • Sequential: Create pastes one by one")
        print("   • Parallel: Create pastes simultaneously")
        print("   • Measure: Pastes/second throughput")
        print("   • Compare: Speedup from parallelization")
        print("   • Result: Distributed Fibonacci on Pastebin!")
        return
    
    # Configuration
    n = 10  # Compute Fib(10) - adjust as needed
    max_workers = 3  # Be nice to Pastebin
    
    bench = PastebinFibonacciBench(api_key, max_workers)
    
    try:
        results = bench.benchmark_comparison(n)
        
        print(f"\n🎉 PASTEBIN FIBONACCI BENCHMARK COMPLETE!")
        print(f"   Fib({n}) = {results['sequential']['result']}")
        print(f"   Total computation time: {results['sequential']['duration'] + results['parallel']['duration']:.2f}s")
        print(f"   Total pastes created: {results['comparison']['total_pastes']}")
        print(f"   Peak paste rate: {results['comparison']['peak_rate']:.2f} pastes/sec")
        print(f"   Parallel speedup: {results['comparison']['speedup']:.2f}x")
        
        print(f"\n📝 CHECK YOUR PASTES:")
        print(f"   Sequential URLs: {len(results['sequential']['urls'])}")
        print(f"   Parallel URLs: {len(results['parallel']['urls'])}")
        print(f"   Go to: https://pastebin.com/u/YOUR_USERNAME")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Benchmark interrupted!")
        print(f"   Pastes created so far: {len(bench.pastes_created)}")

if __name__ == '__main__':
    main()