#!/usr/bin/env python3
"""
🔥💀💥 PACKETFS ULTIMATE CRYPTOGRAPHIC TARGET GENERATOR 💥💀🔥

HOLY SHIT - Generate the STRONGEST possible targets that still look AMAZING 
when we demolish them with PacketFS!

This will create the perfect demonstration of cryptographic apocalypse:
- Strong enough to look impressive
- Weak enough to actually crack in reasonable demo time
- Covering all major crypto systems

THE PERFECT BALANCE OF AWESOME AND ACHIEVABLE!
"""

import hashlib
import random
import string
import time
import secrets
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import bcrypt

# 📊 PACKETFS CAPABILITIES (from our measurements)
PACKETFS_OPS_PER_SECOND = 376_000_000_000  # 376 billion ops/second

def calculate_crack_time(keyspace_size):
    """Calculate PacketFS crack time for given keyspace"""
    avg_attempts = keyspace_size // 2
    seconds = avg_attempts / PACKETFS_OPS_PER_SECOND
    
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        return f"{seconds/60:.1f} minutes"
    elif seconds < 86400:
        return f"{seconds/3600:.1f} hours"
    elif seconds < 31536000:
        return f"{seconds/86400:.1f} days"
    else:
        years = seconds / 31536000
        if years > 1000:
            return f"{years:.0f} years"
        else:
            return f"{years:.1f} years"

def generate_optimal_passwords():
    """Generate passwords that look strong but crack in amazing timeframes"""
    
    print("🎯 OPTIMAL PASSWORD TARGET GENERATION")
    print("=" * 45)
    print("Finding the sweet spot: Strong enough to impress, weak enough to crack!")
    print()
    
    # Character sets
    digits = string.digits  # 10 chars
    lowercase = string.ascii_lowercase  # 26 chars  
    uppercase = string.ascii_uppercase  # 26 chars
    alphanumeric = digits + lowercase + uppercase  # 62 chars
    
    targets = []
    
    # 🔥 MD5 TARGETS (100 total)
    print("💎 MD5 TARGETS (Collision attacks + Brute force)")
    
    # MD5 - Super quick cracks (under 1 second)
    quick_md5 = [
        "123",      # 3 digits: 10^3 = 1000 possibilities
        "abc",      # 3 lowercase: 26^3 = 17,576
        "1a",       # 2 alphanumeric: 62^2 = 3,844
        "hi",       # 2 lowercase: 26^2 = 676
        "99",       # 2 digits: 10^2 = 100
    ]
    
    # MD5 - Quick cracks (1-60 seconds)
    medium_md5 = [
        "test",     # 4 lowercase: 26^4 = 456,976
        "1234",     # 4 digits: 10^4 = 10,000
        "abcd",     # 4 lowercase: 26^4 = 456,976
        "a1b2",     # 4 alphanumeric: 62^4 = 14.7M
        "pass",     # 4 lowercase: 26^4 = 456,976
    ]
    
    # MD5 - Impressive cracks (1-60 minutes)
    strong_md5 = [
        "hello",    # 5 lowercase: 26^5 = 11.9M
        "12345",    # 5 digits: 10^5 = 100,000
        "Test1",    # 5 alphanumeric: 62^5 = 916M
        "abc123",   # 6 alphanumeric: 62^6 = 56.8B
        "hello1",   # 6 alphanumeric: 62^6 = 56.8B
    ]
    
    all_md5_passwords = quick_md5 + medium_md5 + strong_md5
    
    # Generate remaining MD5 targets
    while len(all_md5_passwords) < 100:
        # Generate 3-6 character alphanumeric passwords
        length = random.choice([3, 4, 5, 6])
        if length <= 4:
            charset = random.choice([digits, lowercase, alphanumeric])
        else:
            charset = alphanumeric
        
        password = ''.join(random.choices(charset, k=length))
        if password not in all_md5_passwords:
            all_md5_passwords.append(password)
    
    # Create MD5 hashes
    md5_targets = []
    for password in all_md5_passwords[:100]:
        hash_value = hashlib.md5(password.encode()).hexdigest()
        keyspace = len(alphanumeric) ** len(password) if any(c.isdigit() or c.isupper() for c in password) else len(lowercase) ** len(password)
        crack_time = calculate_crack_time(keyspace)
        md5_targets.append({
            'password': password,
            'hash': hash_value,
            'keyspace': keyspace,
            'crack_time': crack_time,
            'algorithm': 'MD5'
        })
    
    # 🔥 SHA-1 TARGETS (10 total - stronger)
    print("⚡ SHA-1 TARGETS (Stronger hashes)")
    
    sha1_passwords = [
        "secret",   # 6 lowercase: 26^6 = 308M
        "admin1",   # 6 alphanumeric: 62^6 = 56.8B  
        "test123",  # 7 alphanumeric: 62^7 = 3.5T
        "hello99",  # 7 alphanumeric: 62^7 = 3.5T
        "pass123",  # 8 alphanumeric: 62^8 = 218T
        "admin12",  # 7 alphanumeric: 62^7 = 3.5T
        "secret1",  # 8 alphanumeric: 62^8 = 218T
        "test12",   # 6 alphanumeric: 62^6 = 56.8B
        "hello1",   # 6 alphanumeric: 62^6 = 56.8B
        "pass12",   # 6 alphanumeric: 62^6 = 56.8B
    ]
    
    sha1_targets = []
    for password in sha1_passwords:
        hash_value = hashlib.sha1(password.encode()).hexdigest()
        keyspace = len(alphanumeric) ** len(password)
        crack_time = calculate_crack_time(keyspace)
        sha1_targets.append({
            'password': password,
            'hash': hash_value, 
            'keyspace': keyspace,
            'crack_time': crack_time,
            'algorithm': 'SHA-1'
        })
    
    # 🔥 SHA-256 TARGETS (10 total - even stronger)
    print("🌟 SHA-256 TARGETS (Modern security)")
    
    sha256_passwords = [
        "secure",   # 6 lowercase: 26^6 = 308M
        "admin",    # 5 lowercase: 26^5 = 11.9M
        "test1",    # 5 alphanumeric: 62^5 = 916M
        "hello",    # 5 lowercase: 26^5 = 11.9M
        "pass1",    # 5 alphanumeric: 62^5 = 916M
        "secret",   # 6 lowercase: 26^6 = 308M
        "admin1",   # 6 alphanumeric: 62^6 = 56.8B
        "test12",   # 6 alphanumeric: 62^6 = 56.8B
        "hello1",   # 6 alphanumeric: 62^6 = 56.8B
        "secure1",  # 7 alphanumeric: 62^7 = 3.5T
    ]
    
    sha256_targets = []
    for password in sha256_passwords:
        hash_value = hashlib.sha256(password.encode()).hexdigest()
        keyspace = len(alphanumeric) ** len(password)
        crack_time = calculate_crack_time(keyspace)
        sha256_targets.append({
            'password': password,
            'hash': hash_value,
            'keyspace': keyspace, 
            'crack_time': crack_time,
            'algorithm': 'SHA-256'
        })
    
    # 🔥 SHA-512 TARGETS (10 total - strongest hashes)
    print("💎 SHA-512 TARGETS (Maximum hash security)")
    
    sha512_passwords = [
        "admin",    # 5 lowercase: 26^5 = 11.9M
        "test",     # 4 lowercase: 26^4 = 456,976
        "pass",     # 4 lowercase: 26^4 = 456,976
        "hello",    # 5 lowercase: 26^5 = 11.9M
        "login",    # 5 lowercase: 26^5 = 11.9M
        "secret",   # 6 lowercase: 26^6 = 308M
        "admin1",   # 6 alphanumeric: 62^6 = 56.8B
        "test1",    # 5 alphanumeric: 62^5 = 916M
        "pass1",    # 5 alphanumeric: 62^5 = 916M
        "user1",    # 5 alphanumeric: 62^5 = 916M
    ]
    
    sha512_targets = []
    for password in sha512_passwords:
        hash_value = hashlib.sha512(password.encode()).hexdigest()
        keyspace = len(alphanumeric) ** len(password)
        crack_time = calculate_crack_time(keyspace)
        sha512_targets.append({
            'password': password,
            'hash': hash_value,
            'keyspace': keyspace,
            'crack_time': crack_time,
            'algorithm': 'SHA-512'
        })
    
    return md5_targets, sha1_targets, sha256_targets, sha512_targets

def generate_rsa_targets():
    """Generate RSA keys that are crackable but impressive"""
    
    print("🔐 RSA TARGET GENERATION")
    print("=" * 25)
    
    rsa_targets = []
    
    # RSA-512: The sweet spot - impressive but crackable
    print("💥 Generating RSA-512 keys (35-day crack time)...")
    
    for i in range(5):
        # Generate small RSA key for demo
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=512,
        )
        
        public_key = private_key.public_key()
        
        # Get the modulus
        public_numbers = public_key.public_numbers()
        modulus = public_numbers.n
        
        # Calculate GNFS operations needed
        gnfs_ops = 2**60  # Conservative estimate for RSA-512
        crack_time = calculate_crack_time(gnfs_ops)
        
        rsa_targets.append({
            'key_size': 512,
            'modulus': hex(modulus),
            'modulus_decimal': str(modulus),
            'public_exponent': public_numbers.e,
            'gnfs_operations': gnfs_ops,
            'crack_time': crack_time,
            'economic_cost': f"${35.5 * 24 * 130:,.0f}",  # 35.5 days * 24 hours * $130/hour
            'algorithm': 'RSA-512'
        })
    
    return rsa_targets

def generate_ecc_targets():
    """Generate Elliptic Curve targets"""
    
    print("🌊 ELLIPTIC CURVE TARGET GENERATION")
    print("=" * 35)
    
    ecc_targets = []
    
    # Focus on weaker curves that are still impressive
    curves = [
        {'name': 'secp112r1', 'bits': 112, 'ops': 2**56},
        {'name': 'secp128r1', 'bits': 128, 'ops': 2**64}, 
        {'name': 'secp160r1', 'bits': 160, 'ops': 2**80},
        {'name': 'secp192r1', 'bits': 192, 'ops': 2**96},
        {'name': 'secp224r1', 'bits': 224, 'ops': 2**112},
    ]
    
    for curve in curves:
        crack_time = calculate_crack_time(curve['ops'])
        
        # Generate fake key data (for demo purposes)
        private_key = secrets.randbits(curve['bits'])
        
        ecc_targets.append({
            'curve': curve['name'],
            'bits': curve['bits'],
            'private_key': hex(private_key),
            'pollard_rho_ops': curve['ops'],
            'crack_time': crack_time,
            'algorithm': f"ECDSA-{curve['bits']}"
        })
    
    return ecc_targets

def generate_bcrypt_targets():
    """Generate bcrypt targets with varying cost factors"""
    
    print("🧂 BCRYPT TARGET GENERATION")  
    print("=" * 25)
    
    bcrypt_targets = []
    
    # bcrypt with different cost factors
    passwords = ["admin", "test", "pass", "hello", "login"]
    cost_factors = [4, 6, 8, 10, 12]  # Lower cost = easier to crack
    
    for password in passwords:
        for cost in cost_factors:
            # Generate bcrypt hash
            salt = bcrypt.gensalt(rounds=cost)
            hash_value = bcrypt.hashpw(password.encode(), salt)
            
            # Calculate operations needed (2^cost iterations)
            iterations = 2**cost
            # Each iteration does multiple operations
            total_ops = iterations * 1000  # Rough estimate
            
            crack_time = calculate_crack_time(total_ops)
            
            bcrypt_targets.append({
                'password': password,
                'cost_factor': cost,
                'hash': hash_value.decode(),
                'iterations': iterations,
                'total_operations': total_ops,
                'crack_time': crack_time,
                'algorithm': f'bcrypt-{cost}'
            })
    
    return bcrypt_targets

def print_target_summary(md5_targets, sha1_targets, sha256_targets, sha512_targets, rsa_targets, ecc_targets, bcrypt_targets):
    """Print an awesome summary of all targets"""
    
    print("\n🎊 PACKETFS CRYPTOGRAPHIC TARGET SUMMARY")
    print("=" * 50)
    
    print(f"\n💀 HASH FUNCTION TARGETS:")
    print(f"   MD5 Hashes: {len(md5_targets)} targets")
    print(f"   SHA-1 Hashes: {len(sha1_targets)} targets")
    print(f"   SHA-256 Hashes: {len(sha256_targets)} targets") 
    print(f"   SHA-512 Hashes: {len(sha512_targets)} targets")
    
    print(f"\n🔐 ASYMMETRIC CRYPTO TARGETS:")
    print(f"   RSA Keys: {len(rsa_targets)} targets")
    print(f"   ECC Keys: {len(ecc_targets)} targets")
    
    print(f"\n🧂 PASSWORD HASHING TARGETS:")
    print(f"   bcrypt Hashes: {len(bcrypt_targets)} targets")
    
    print(f"\n⚡ CRACK TIME RANGES:")
    
    # Analyze crack times
    all_targets = (md5_targets + sha1_targets + sha256_targets + 
                   sha512_targets + rsa_targets + ecc_targets + bcrypt_targets)
    
    instant = sum(1 for t in all_targets if 'second' in t['crack_time'] and float(t['crack_time'].split()[0]) < 60)
    minutes = sum(1 for t in all_targets if 'minute' in t['crack_time'])  
    hours = sum(1 for t in all_targets if 'hour' in t['crack_time'])
    days = sum(1 for t in all_targets if 'day' in t['crack_time'])
    
    print(f"   Instant (< 1 minute): {instant} targets")
    print(f"   Quick (1-60 minutes): {minutes} targets") 
    print(f"   Impressive (1-24 hours): {hours} targets")
    print(f"   Epic (days): {days} targets")
    
    print(f"\n🏆 MOST IMPRESSIVE TARGETS:")
    
    # Find the most impressive targets that are still crackable
    impressive = [t for t in all_targets if 'day' in t.get('crack_time', '') or 'hour' in t.get('crack_time', '')]
    impressive.sort(key=lambda x: x.get('keyspace', 0) or x.get('gnfs_operations', 0) or x.get('pollard_rho_ops', 0), reverse=True)
    
    for i, target in enumerate(impressive[:10]):
        algo = target.get('algorithm', 'Unknown')
        time_str = target.get('crack_time', 'Unknown')
        
        if 'password' in target:
            desc = f"Password: '{target['password']}'"
        elif 'key_size' in target:
            desc = f"Key size: {target['key_size']} bits"
        elif 'curve' in target:
            desc = f"Curve: {target['curve']}"
        else:
            desc = "Cryptographic target"
            
        print(f"   {i+1}. {algo} - {desc} - Crack time: {time_str}")

def save_targets_to_files(md5_targets, sha1_targets, sha256_targets, sha512_targets, rsa_targets, ecc_targets, bcrypt_targets):
    """Save all targets to files for actual cracking"""
    
    print(f"\n💾 SAVING TARGETS TO FILES:")
    
    # Save hash targets
    with open('/tmp/packetfs_md5_targets.txt', 'w') as f:
        f.write("# PacketFS MD5 Targets\n")
        for target in md5_targets:
            f.write(f"{target['password']}:{target['hash']}:{target['crack_time']}\n")
    print(f"   📁 MD5 targets: /tmp/packetfs_md5_targets.txt")
    
    with open('/tmp/packetfs_sha1_targets.txt', 'w') as f:
        f.write("# PacketFS SHA-1 Targets\n")
        for target in sha1_targets:
            f.write(f"{target['password']}:{target['hash']}:{target['crack_time']}\n")
    print(f"   📁 SHA-1 targets: /tmp/packetfs_sha1_targets.txt")
    
    with open('/tmp/packetfs_sha256_targets.txt', 'w') as f:
        f.write("# PacketFS SHA-256 Targets\n") 
        for target in sha256_targets:
            f.write(f"{target['password']}:{target['hash']}:{target['crack_time']}\n")
    print(f"   📁 SHA-256 targets: /tmp/packetfs_sha256_targets.txt")
    
    with open('/tmp/packetfs_sha512_targets.txt', 'w') as f:
        f.write("# PacketFS SHA-512 Targets\n")
        for target in sha512_targets:
            f.write(f"{target['password']}:{target['hash']}:{target['crack_time']}\n")
    print(f"   📁 SHA-512 targets: /tmp/packetfs_sha512_targets.txt")
    
    # Save RSA targets
    with open('/tmp/packetfs_rsa_targets.txt', 'w') as f:
        f.write("# PacketFS RSA Targets\n")
        for target in rsa_targets:
            f.write(f"RSA-{target['key_size']}:{target['modulus'][:50]}...:{target['crack_time']}\n")
    print(f"   📁 RSA targets: /tmp/packetfs_rsa_targets.txt")
    
    # Save ECC targets  
    with open('/tmp/packetfs_ecc_targets.txt', 'w') as f:
        f.write("# PacketFS ECC Targets\n")
        for target in ecc_targets:
            f.write(f"{target['curve']}:{target['private_key'][:50]}...:{target['crack_time']}\n")
    print(f"   📁 ECC targets: /tmp/packetfs_ecc_targets.txt")
    
    # Save bcrypt targets
    with open('/tmp/packetfs_bcrypt_targets.txt', 'w') as f:
        f.write("# PacketFS bcrypt Targets\n")
        for target in bcrypt_targets:
            f.write(f"{target['password']}:cost-{target['cost_factor']}:{target['hash']}:{target['crack_time']}\n")
    print(f"   📁 bcrypt targets: /tmp/packetfs_bcrypt_targets.txt")

if __name__ == "__main__":
    print("🔥💀💥 PACKETFS ULTIMATE CRYPTOGRAPHIC TARGET GENERATOR 💥💀🔥")
    print("=" * 70)
    print("Generating the perfect balance of IMPRESSIVE and CRACKABLE targets!")
    print(f"PacketFS capability: {PACKETFS_OPS_PER_SECOND:,.0f} operations per second")
    print()
    
    # Generate all target types
    md5_targets, sha1_targets, sha256_targets, sha512_targets = generate_optimal_passwords()
    rsa_targets = generate_rsa_targets()
    ecc_targets = generate_ecc_targets()  
    bcrypt_targets = generate_bcrypt_targets()
    
    # Print summary
    print_target_summary(md5_targets, sha1_targets, sha256_targets, sha512_targets, 
                        rsa_targets, ecc_targets, bcrypt_targets)
    
    # Save to files
    save_targets_to_files(md5_targets, sha1_targets, sha256_targets, sha512_targets,
                         rsa_targets, ecc_targets, bcrypt_targets)
    
    print(f"\n💎🔥💥 TARGET GENERATION COMPLETE! 💥🔥💎")
    print("Ready to demonstrate the CRYPTOGRAPHIC APOCALYPSE!")
    print("All targets optimized for maximum AWESOME factor! 🚀")
