#!/usr/bin/env python3
"""
Asset Spider - Continuously scan internet for fast computation endpoints
"""

import asyncio
import aiohttp
import sqlite3
import time
from typing import List, Dict, Optional

class AssetSpider:
    def __init__(self, db_path: str = "assets.db"):
        self.db_path = db_path
        self.session = None
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS endpoints (
                url TEXT PRIMARY KEY,
                avg_latency REAL,
                success_rate REAL,
                last_checked INTEGER,
                instruction_type TEXT,
                status TEXT DEFAULT 'active'
            )
        """)
        conn.commit()
        conn.close()
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=2.0)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_endpoint(self, url: str) -> Optional[Dict]:
        """Test endpoint speed and reliability"""
        attempts = 3
        latencies = []
        successes = 0
        
        for _ in range(attempts):
            try:
                start = time.time()
                async with self.session.get(url) as resp:
                    latency = time.time() - start
                    if resp.status < 500:  # Consider 4xx as success for our purposes
                        latencies.append(latency)
                        successes += 1
            except:
                pass
        
        if latencies:
            return {
                'url': url,
                'avg_latency': sum(latencies) / len(latencies),
                'success_rate': successes / attempts,
                'last_checked': int(time.time())
            }
        return None
    
    async def scan_httpbin_variants(self):
        """Scan httpbin and similar services"""
        base_urls = [
            "https://httpbin.org/status/{}",
            "https://httpstat.us/{}",
            "https://postman-echo.com/status/{}",
            "https://reqres.in/api/users/{}",
        ]
        
        status_codes = [200, 201, 204, 301, 302, 400, 401, 404, 500]
        
        tasks = []
        for base_url in base_urls:
            for code in status_codes:
                url = base_url.format(code)
                tasks.append(self.test_endpoint(url))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Store results
        conn = sqlite3.connect(self.db_path)
        for result in results:
            if isinstance(result, dict):
                conn.execute("""
                    INSERT OR REPLACE INTO endpoints 
                    (url, avg_latency, success_rate, last_checked, instruction_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (result['url'], result['avg_latency'], result['success_rate'], 
                     result['last_checked'], 'HTTP_STATUS'))
        conn.commit()
        conn.close()
        
        valid_results = [r for r in results if isinstance(r, dict)]
        print(f"✅ Scanned {len(tasks)} endpoints, {len(valid_results)} valid")
    
    async def scan_cdn_endpoints(self):
        """Scan CDN endpoints for memory operations"""
        cdn_urls = [
            "https://cdn.jsdelivr.net/npm/lodash@{}/package.json",
            "https://unpkg.com/react@{}/package.json", 
            "https://cdnjs.cloudflare.com/ajax/libs/jquery/{}/jquery.min.js",
        ]
        
        versions = ["1.0.0", "2.0.0", "3.0.0", "latest"]
        
        tasks = []
        for base_url in cdn_urls:
            for version in versions:
                url = base_url.format(version)
                tasks.append(self.test_endpoint(url))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        conn = sqlite3.connect(self.db_path)
        for result in results:
            if isinstance(result, dict):
                conn.execute("""
                    INSERT OR REPLACE INTO endpoints 
                    (url, avg_latency, success_rate, last_checked, instruction_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (result['url'], result['avg_latency'], result['success_rate'],
                     result['last_checked'], 'CDN_MEMORY'))
        conn.commit()
        conn.close()
        
        valid_results = [r for r in results if isinstance(r, dict)]
        print(f"✅ Scanned CDN endpoints, {len(valid_results)} valid")
    
    def get_fastest_endpoints(self, instruction_type: str = None, limit: int = 10) -> List[Dict]:
        """Get fastest endpoints for instruction type"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT url, avg_latency, success_rate, instruction_type
            FROM endpoints 
            WHERE status = 'active' AND success_rate > 0.5
        """
        params = []
        
        if instruction_type:
            query += " AND instruction_type = ?"
            params.append(instruction_type)
        
        query += " ORDER BY avg_latency ASC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        conn.close()
        
        return [{'url': row[0], 'latency': row[1], 'success_rate': row[2], 'type': row[3]} 
                for row in rows]
    
    def stats(self):
        """Show database stats"""
        conn = sqlite3.connect(self.db_path)
        
        total = conn.execute("SELECT COUNT(*) FROM endpoints").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM endpoints WHERE status='active'").fetchone()[0]
        
        by_type = conn.execute("""
            SELECT instruction_type, COUNT(*), AVG(avg_latency)
            FROM endpoints WHERE status='active'
            GROUP BY instruction_type
        """).fetchall()
        
        conn.close()
        
        print(f"📊 Asset Database Stats")
        print(f"Total endpoints: {total}")
        print(f"Active endpoints: {active}")
        print("\nBy instruction type:")
        for type_name, count, avg_latency in by_type:
            print(f"  {type_name}: {count} endpoints, {avg_latency:.3f}s avg")

async def main():
    print("🕷️ Network Asset Spider")
    print("=" * 30)
    
    async with AssetSpider() as spider:
        print("Scanning HTTP status endpoints...")
        await spider.scan_httpbin_variants()
        
        print("Scanning CDN endpoints...")
        await spider.scan_cdn_endpoints()
        
        print("\nFastest HTTP endpoints:")
        fastest = spider.get_fastest_endpoints('HTTP_STATUS', 5)
        for endpoint in fastest:
            print(f"  {endpoint['url']} - {endpoint['latency']:.3f}s")
        
        spider.stats()

if __name__ == "__main__":
    asyncio.run(main())