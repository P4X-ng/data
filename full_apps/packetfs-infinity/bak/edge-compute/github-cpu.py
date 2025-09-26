#!/usr/bin/env python3
"""
GitHub-as-CPU: Turn GitHub Issues into computation primitives!

Operations:
- CREATE issue = increment counter
- CLOSE issue = decrement counter  
- LABEL issue = set bits
- COMMENT count = accumulator value
- Gist content = data storage

Example: Count zeros in a file by creating issues!
"""

import requests
import time
import json
import hashlib
from typing import Dict, List

class GitHubCPU:
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo  # format: "username/repo"
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = f'https://api.github.com/repos/{repo}'
    
    def execute_counteq(self, data: bytes, needle: int) -> Dict:
        """Count bytes equal to needle by creating GitHub issues!"""
        
        # Create a unique computation ID
        comp_id = hashlib.md5(data[:32]).hexdigest()[:8]
        
        print(f"🚀 GitHub CPU: Counting {needle} in {len(data)} bytes")
        print(f"   Computation ID: {comp_id}")
        
        # Create issues for each matching byte!
        count = 0
        issues_created = []
        
        for i, byte in enumerate(data[:100]):  # Limit to 100 bytes for demo
            if byte == needle:
                # CREATE ISSUE = INCREMENT COUNTER!
                issue_data = {
                    'title': f'CPU-{comp_id}: Found {needle} at offset {i}',
                    'body': f'PacketFS GitHub CPU computation\n\nByte value: {byte}\nOffset: {i}\nNeedle: {needle}',
                    'labels': [f'cpu-{comp_id}', 'counteq', f'value-{needle}']
                }
                
                try:
                    resp = requests.post(f'{self.base_url}/issues', 
                                       headers=self.headers, 
                                       json=issue_data)
                    if resp.status_code == 201:
                        issue = resp.json()
                        issues_created.append(issue['number'])
                        count += 1
                        print(f"   ✅ Issue #{issue['number']}: Found {needle} at {i}")
                    else:
                        print(f"   ❌ Failed to create issue: {resp.status_code}")
                        break
                        
                    # Rate limiting respect
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    break
        
        # Store result in a Gist (GitHub's "memory")
        result = {
            'computation_id': comp_id,
            'operation': 'counteq',
            'needle': needle,
            'count': count,
            'data_size': len(data),
            'issues_created': issues_created,
            'timestamp': time.time()
        }
        
        gist_data = {
            'description': f'PacketFS GitHub CPU Result: {comp_id}',
            'public': False,
            'files': {
                f'result-{comp_id}.json': {
                    'content': json.dumps(result, indent=2)
                }
            }
        }
        
        try:
            gist_resp = requests.post('https://api.github.com/gists',
                                    headers=self.headers,
                                    json=gist_data)
            if gist_resp.status_code == 201:
                gist = gist_resp.json()
                result['result_gist'] = gist['html_url']
                print(f"   💾 Result stored: {gist['html_url']}")
        except Exception as e:
            print(f"   ⚠️  Couldn't store result: {e}")
        
        return result
    
    def cleanup_computation(self, comp_id: str):
        """Close all issues for a computation (cleanup)"""
        print(f"🧹 Cleaning up computation {comp_id}")
        
        # Find issues with our label
        resp = requests.get(f'{self.base_url}/issues',
                          headers=self.headers,
                          params={'labels': f'cpu-{comp_id}', 'state': 'open'})
        
        if resp.status_code == 200:
            issues = resp.json()
            for issue in issues:
                # Close issue = decrement counter
                close_resp = requests.patch(f'{self.base_url}/issues/{issue["number"]}',
                                          headers=self.headers,
                                          json={'state': 'closed'})
                if close_resp.status_code == 200:
                    print(f"   ✅ Closed issue #{issue['number']}")
                time.sleep(0.1)

def demo_github_cpu():
    """Demo: Use GitHub as a CPU to count zeros"""
    
    # You'd need a real token and repo
    token = "ghp_YOUR_TOKEN_HERE"  # Replace with real token
    repo = "your-username/cpu-test-repo"  # Replace with real repo
    
    if token == "ghp_YOUR_TOKEN_HERE":
        print("❌ Need real GitHub token and repo!")
        print("   1. Create a GitHub repo")
        print("   2. Generate a personal access token")
        print("   3. Update token/repo in this script")
        return
    
    cpu = GitHubCPU(token, repo)
    
    # Test data: count zeros
    test_data = bytes([0, 1, 0, 2, 0, 3, 0, 4, 0])
    
    print("🤖 GitHub CPU Demo: Counting zeros")
    print(f"   Data: {list(test_data)}")
    
    result = cpu.execute_counteq(test_data, 0)
    
    print(f"\n📊 RESULT:")
    print(f"   Count: {result['count']}")
    print(f"   Issues created: {len(result['issues_created'])}")
    print(f"   GitHub repo: https://github.com/{repo}/issues")
    
    # Cleanup after demo
    input("\nPress Enter to cleanup (close all issues)...")
    cpu.cleanup_computation(result['computation_id'])

if __name__ == '__main__':
    demo_github_cpu()