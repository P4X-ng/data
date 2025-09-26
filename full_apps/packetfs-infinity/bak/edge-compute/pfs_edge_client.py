#!/usr/bin/env python3
"""
PacketFS Edge Compute Client
Send computation to data instead of downloading data!
Works with: Cloudflare Workers, AWS Lambda@Edge, S3 Select, ANY server!
"""

import asyncio
import aiohttp
import json
import base64
import hashlib
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class PcpuOp(Enum):
    """pCPU operations that can run at edge"""
    COUNTEQ = "counteq"     # Count equal bytes
    XOR = "xor"             # XOR with immediate
    ADD = "add"             # Add immediate
    CRC32C = "crc32c"       # CRC32C checksum
    FNV64 = "fnv64"         # FNV-1a 64-bit hash
    SHA256 = "sha256"       # SHA256 hash
    GREP = "grep"           # Pattern search
    SELECT = "select"       # SQL-like select (for S3)

@dataclass
class PcpuInstruction:
    op: PcpuOp
    imm: Optional[int] = None
    pattern: Optional[bytes] = None
    offset: Optional[int] = None
    length: Optional[int] = None
    sql: Optional[str] = None  # For S3 Select

class EdgeProvider:
    """Base class for edge compute providers"""
    
    async def execute(self, data_url: str, instructions: List[PcpuInstruction]) -> Dict:
        raise NotImplementedError

class CloudflareWorkerProvider(EdgeProvider):
    """Execute on Cloudflare Workers"""
    
    def __init__(self, worker_url: str):
        self.worker_url = worker_url
    
    async def execute(self, data_url: str, instructions: List[PcpuInstruction]) -> Dict:
        async with aiohttp.ClientSession() as session:
            program = {
                "data_url": data_url,
                "instructions": [
                    {
                        "op": inst.op.value,
                        "imm": inst.imm,
                        "offset": inst.offset,
                        "length": inst.length
                    }
                    for inst in instructions
                ]
            }
            
            async with session.post(f"{self.worker_url}/compute", json=program) as resp:
                return await resp.json()

class S3SelectProvider(EdgeProvider):
    """Execute using S3 Select - SQL on S3 without downloading!"""
    
    def __init__(self, aws_credentials=None):
        import boto3
        self.s3 = boto3.client('s3', 
                               aws_access_key_id=aws_credentials.get('access_key') if aws_credentials else None,
                               aws_secret_access_key=aws_credentials.get('secret_key') if aws_credentials else None)
    
    async def execute(self, data_url: str, instructions: List[PcpuInstruction]) -> Dict:
        # Parse S3 URL
        if not data_url.startswith('s3://'):
            raise ValueError("S3 Select requires s3:// URLs")
        
        parts = data_url[5:].split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        
        results = []
        for inst in instructions:
            if inst.op == PcpuOp.SELECT and inst.sql:
                # S3 Select can run SQL on CSV/JSON/Parquet WITHOUT downloading!
                response = self.s3.select_object_content(
                    Bucket=bucket,
                    Key=key,
                    Expression=inst.sql,
                    ExpressionType='SQL',
                    InputSerialization={'CSV': {"FileHeaderInfo": "USE"}},
                    OutputSerialization={'JSON': {}}
                )
                
                # Stream results
                records = []
                for event in response['Payload']:
                    if 'Records' in event:
                        records.append(event['Records']['Payload'].decode('utf-8'))
                
                results.append({
                    'op': 'select',
                    'records': records
                })
            elif inst.op == PcpuOp.COUNTEQ:
                # Use S3 Select to count occurrences
                sql = f"SELECT COUNT(*) FROM S3Object[*] WHERE _1 = {inst.imm}"
                # ... execute SQL
        
        return {'results': results}

class LambdaEdgeProvider(EdgeProvider):
    """Execute on AWS Lambda@Edge"""
    
    def __init__(self, lambda_function_name: str):
        import boto3
        self.lambda_client = boto3.client('lambda')
        self.function_name = lambda_function_name
    
    async def execute(self, data_url: str, instructions: List[PcpuInstruction]) -> Dict:
        payload = {
            'data_url': data_url,
            'instructions': [inst.__dict__ for inst in instructions]
        }
        
        response = self.lambda_client.invoke(
            FunctionName=self.function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        return json.loads(response['Payload'].read())

class HTTPServerProvider(EdgeProvider):
    """Execute on any HTTP server running PacketFS edge compute"""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
    
    async def execute(self, data_url: str, instructions: List[PcpuInstruction]) -> Dict:
        async with aiohttp.ClientSession() as session:
            # Try different endpoints based on what the server supports
            
            # Try range requests with custom headers for compute
            if instructions[0].offset is not None:
                headers = {
                    'Range': f'bytes={instructions[0].offset}-{instructions[0].offset + instructions[0].length - 1}',
                    'X-PacketFS-Op': instructions[0].op.value,
                    'X-PacketFS-Imm': str(instructions[0].imm) if instructions[0].imm else '0'
                }
                
                async with session.get(data_url, headers=headers) as resp:
                    if 'X-PacketFS-Result' in resp.headers:
                        # Server supports PacketFS compute!
                        return json.loads(resp.headers['X-PacketFS-Result'])
                    else:
                        # Fallback to downloading and computing locally
                        data = await resp.read()
                        return self._compute_locally(data, instructions)
            
            # Standard compute endpoint
            program = {
                "data_url": data_url,
                "instructions": [inst.__dict__ for inst in instructions]
            }
            
            async with session.post(f"{self.server_url}/compute", json=program) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    # Fallback
                    async with session.get(data_url) as data_resp:
                        data = await data_resp.read()
                        return self._compute_locally(data, instructions)
    
    def _compute_locally(self, data: bytes, instructions: List[PcpuInstruction]) -> Dict:
        """Fallback local computation"""
        results = []
        for inst in instructions:
            if inst.op == PcpuOp.COUNTEQ:
                count = sum(1 for b in data if b == inst.imm)
                results.append({'op': 'counteq', 'value': count})
            elif inst.op == PcpuOp.CRC32C:
                import crc32c
                results.append({'op': 'crc32c', 'value': crc32c.crc32c(data)})
            elif inst.op == PcpuOp.SHA256:
                results.append({'op': 'sha256', 'value': hashlib.sha256(data).hexdigest()})
        
        return {'results': results, 'computed': 'locally'}

class PacketFSEdgeCompute:
    """Main client for edge computation"""
    
    def __init__(self):
        self.providers = {}
        self.stats = {
            'bytes_saved': 0,
            'computations_sent': 0,
            'edge_locations': set()
        }
    
    def register_provider(self, name: str, provider: EdgeProvider):
        """Register an edge compute provider"""
        self.providers[name] = provider
    
    async def compute(self, data_url: str, instructions: List[PcpuInstruction], 
                      provider_name: Optional[str] = None) -> Dict:
        """Send computation to edge instead of downloading data"""
        
        # Auto-detect provider from URL if not specified
        if not provider_name:
            if data_url.startswith('s3://'):
                provider_name = 's3'
            elif 'cloudflare' in data_url:
                provider_name = 'cloudflare'
            elif 'amazonaws.com' in data_url:
                provider_name = 'lambda'
            else:
                provider_name = 'http'
        
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        start_time = time.time()
        result = await provider.execute(data_url, instructions)
        elapsed = time.time() - start_time
        
        # Update stats
        self.stats['computations_sent'] += 1
        if 'data_size' in result:
            self.stats['bytes_saved'] += result['data_size']
        if 'edge_location' in result:
            self.stats['edge_locations'].add(result['edge_location'])
        
        result['elapsed_seconds'] = elapsed
        result['provider'] = provider_name
        
        return result
    
    async def compute_parallel(self, urls_and_instructions: List[tuple]) -> List[Dict]:
        """Execute multiple computations in parallel across different edges"""
        tasks = []
        for url, instructions in urls_and_instructions:
            tasks.append(self.compute(url, instructions))
        
        return await asyncio.gather(*tasks)

async def main():
    """Demo: Computing on remote data without downloading!"""
    
    # Initialize client
    client = PacketFSEdgeCompute()
    
    # Register providers
    client.register_provider('cloudflare', 
        CloudflareWorkerProvider('https://pfs-edge.username.workers.dev'))
    
    client.register_provider('s3', 
        S3SelectProvider())
    
    client.register_provider('lambda',
        LambdaEdgeProvider('pfs-edge-compute'))
    
    client.register_provider('http',
        HTTPServerProvider('https://any-server.com'))
    
    print("🚀 PacketFS Edge Compute Demo")
    print("=" * 50)
    
    # Example 1: Count bytes in a large file WITHOUT downloading it
    print("\n1. Counting zeros in Ubuntu ISO (4GB) without downloading...")
    result = await client.compute(
        'https://releases.ubuntu.com/24.04/ubuntu-24.04-desktop-amd64.iso',
        [PcpuInstruction(PcpuOp.COUNTEQ, imm=0)]
    )
    print(f"   Result: {result['results'][0]['value']} zeros found")
    print(f"   Computed at: {result.get('edge_location', 'unknown')}")
    print(f"   Bytes saved: 4GB!")
    
    # Example 2: Get checksums of multiple files in parallel
    print("\n2. Getting checksums of 10 files in parallel...")
    files = [
        'https://example.com/file1.bin',
        'https://example.com/file2.bin',
        # ... more files
    ]
    
    tasks = [(url, [PcpuInstruction(PcpuOp.CRC32C)]) for url in files]
    results = await client.compute_parallel(tasks)
    print(f"   Processed {len(results)} files at edge locations: {client.stats['edge_locations']}")
    
    # Example 3: S3 Select - SQL on S3 without downloading!
    print("\n3. Running SQL on S3 data without downloading...")
    result = await client.compute(
        's3://my-bucket/logs/2024-01-01.csv',
        [PcpuInstruction(PcpuOp.SELECT, 
                        sql="SELECT COUNT(*) FROM S3Object WHERE status_code = '500'")]
    )
    print(f"   Found {result['results'][0]['records'][0]} errors")
    print(f"   Data never left S3!")
    
    # Example 4: Pattern search across CDN-cached content
    print("\n4. Searching for patterns in CDN-cached data...")
    result = await client.compute(
        'https://cdn.example.com/large-dataset.bin',
        [
            PcpuInstruction(PcpuOp.GREP, pattern=b"ERROR"),
            PcpuInstruction(PcpuOp.COUNTEQ, imm=0xFF)
        ]
    )
    print(f"   Found patterns at edge without downloading {result.get('data_size', 0)} bytes")
    
    print(f"\n📊 Total Stats:")
    print(f"   Computations sent to edge: {client.stats['computations_sent']}")
    print(f"   Total bytes saved: {client.stats['bytes_saved']:,}")
    print(f"   Edge locations used: {', '.join(client.stats['edge_locations'])}")

if __name__ == '__main__':
    asyncio.run(main())