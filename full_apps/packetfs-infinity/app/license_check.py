#!/usr/bin/env /home/punk/.venv/bin/python
"""
PacketFS License Validation System
Controlled distribution with license keys
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import base64

# License file location
LICENSE_FILE = Path("/etc/packetfs/license.key")
LICENSE_CACHE = Path("/var/lib/packetfs/.license_cache")

class LicenseValidator:
    """License key validation for PacketFS Utils"""
    
    # Your secret salt (change this!)
    SECRET_SALT = "F3_PACKETFS_95_PERCENT_COMPRESSION_2025_PUNK"
    
    def __init__(self):
        self.valid = False
        self.expiry = None
        self.features = []
        self.licensee = None
        
    def generate_key(self, licensee: str, days_valid: int = 365, features: list = None):
        """
        Generate a license key for distribution
        Only you have this function!
        """
        if features is None:
            features = ["transfer", "compress", "cluster", "web"]
            
        # Create license data
        license_data = {
            "licensee": licensee,
            "issued": datetime.now().isoformat(),
            "expires": (datetime.now() + timedelta(days=days_valid)).isoformat(),
            "features": features,
            "version": "1.0.0"
        }
        
        # Create signature
        data_str = json.dumps(license_data, sort_keys=True)
        signature = hashlib.sha256(
            (data_str + self.SECRET_SALT).encode()
        ).hexdigest()
        
        # Combine and encode
        full_license = {
            "data": license_data,
            "signature": signature
        }
        
        # Base64 encode for distribution
        license_key = base64.b64encode(
            json.dumps(full_license).encode()
        ).decode('ascii')
        
        # Format nicely
        formatted_key = ""
        for i in range(0, len(license_key), 64):
            formatted_key += license_key[i:i+64] + "\n"
            
        return formatted_key.strip()
    
    def validate_key(self, license_key: str) -> bool:
        """
        Validate a license key
        """
        try:
            # Decode key
            license_key = license_key.replace("\n", "").replace(" ", "")
            decoded = base64.b64decode(license_key)
            license_obj = json.loads(decoded)
            
            # Extract data and signature
            license_data = license_obj.get("data")
            provided_signature = license_obj.get("signature")
            
            if not license_data or not provided_signature:
                return False
            
            # Verify signature
            data_str = json.dumps(license_data, sort_keys=True)
            expected_signature = hashlib.sha256(
                (data_str + self.SECRET_SALT).encode()
            ).hexdigest()
            
            if provided_signature != expected_signature:
                print("[!] Invalid license signature")
                return False
            
            # Check expiry
            expires = datetime.fromisoformat(license_data["expires"])
            if datetime.now() > expires:
                print("[!] License expired")
                return False
            
            # Store validated info
            self.valid = True
            self.expiry = expires
            self.features = license_data.get("features", [])
            self.licensee = license_data.get("licensee")
            
            # Cache the validation
            self._cache_validation()
            
            return True
            
        except Exception as e:
            print(f"[!] License validation error: {e}")
            return False
    
    def check_license(self) -> bool:
        """
        Check if valid license exists
        """
        # First check cache
        if self._check_cache():
            return True
            
        # Check license file
        if LICENSE_FILE.exists():
            with open(LICENSE_FILE, 'r') as f:
                key = f.read().strip()
                return self.validate_key(key)
        
        # No license found
        return False
    
    def _cache_validation(self):
        """Cache validation result"""
        try:
            LICENSE_CACHE.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {
                "valid": self.valid,
                "expiry": self.expiry.isoformat() if self.expiry else None,
                "features": self.features,
                "licensee": self.licensee,
                "checked": datetime.now().isoformat()
            }
            with open(LICENSE_CACHE, 'w') as f:
                json.dump(cache_data, f)
        except:
            pass
    
    def _check_cache(self) -> bool:
        """Check cached validation"""
        try:
            if LICENSE_CACHE.exists():
                with open(LICENSE_CACHE, 'r') as f:
                    cache = json.load(f)
                
                # Check if cache is recent (within 1 hour)
                checked = datetime.fromisoformat(cache["checked"])
                if datetime.now() - checked < timedelta(hours=1):
                    self.valid = cache["valid"]
                    self.expiry = datetime.fromisoformat(cache["expiry"]) if cache["expiry"] else None
                    self.features = cache["features"]
                    self.licensee = cache["licensee"]
                    return self.valid
        except:
            pass
        return False
    
    def require_feature(self, feature: str) -> bool:
        """Check if a specific feature is licensed"""
        if not self.valid:
            return False
        return feature in self.features or "all" in self.features


# License check decorator for Flask routes
def require_license(feature: str = None):
    """Decorator to require valid license for routes"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            validator = LicenseValidator()
            if not validator.check_license():
                return {"error": "Valid license required"}, 403
            if feature and not validator.require_feature(feature):
                return {"error": f"Feature '{feature}' not licensed"}, 403
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


def check_or_trial():
    """
    Check license or offer trial mode
    """
    validator = LicenseValidator()
    
    if validator.check_license():
        print(f"[+] Licensed to: {validator.licensee}")
        print(f"[+] Expires: {validator.expiry.strftime('%Y-%m-%d')}")
        print(f"[+] Features: {', '.join(validator.features)}")
        return True
    else:
        print("""
[*] PacketFS Transfer Utilities - License Required
===================================================

No valid license found at /etc/packetfs/license.key

This software achieves 95% compression rates and lightning-fast transfers
using revolutionary F3 protocol technology.

Options:
1. Contact for a license key
2. Run in demo mode (limited to 10MB files)

To install a license:
  sudo mkdir -p /etc/packetfs
  sudo nano /etc/packetfs/license.key
  # Paste your license key and save

Demo mode will start in 10 seconds...
""")
        time.sleep(10)
        return False


# CLI tool for license management (for you only!)
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PacketFS License Manager")
    parser.add_argument("--generate", action="store_true", help="Generate a new license")
    parser.add_argument("--validate", help="Validate a license file")
    parser.add_argument("--licensee", help="Licensee name for generation")
    parser.add_argument("--days", type=int, default=365, help="Days valid")
    parser.add_argument("--features", help="Comma-separated features")
    
    args = parser.parse_args()
    
    validator = LicenseValidator()
    
    if args.generate:
        if not args.licensee:
            print("[!] --licensee required for generation")
            sys.exit(1)
            
        features = args.features.split(",") if args.features else None
        key = validator.generate_key(args.licensee, args.days, features)
        
        print(f"\n[+] License generated for: {args.licensee}")
        print(f"[+] Valid for: {args.days} days")
        print(f"[+] Features: {features or 'all'}")
        print("\n" + "="*70)
        print("LICENSE KEY:")
        print("="*70)
        print(key)
        print("="*70)
        
        # Save to file
        filename = f"license_{args.licensee.replace(' ', '_')}.key"
        with open(filename, 'w') as f:
            f.write(key)
        print(f"\n[+] Saved to: {filename}")
        
    elif args.validate:
        with open(args.validate, 'r') as f:
            key = f.read()
        
        if validator.validate_key(key):
            print(f"[+] License VALID")
            print(f"[+] Licensee: {validator.licensee}")
            print(f"[+] Expires: {validator.expiry}")
            print(f"[+] Features: {validator.features}")
        else:
            print("[!] License INVALID")
            sys.exit(1)
    
    else:
        parser.print_help()