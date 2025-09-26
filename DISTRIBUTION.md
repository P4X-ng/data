# PacketFS Utils - Private Distribution Guide

## 🔐 Controlled Release Strategy

This software contains proprietary F3 protocol technology achieving 95% compression rates. 
Distribution is controlled via license keys.

## Building the Package

```bash
# Build the .deb package
./build-deb.sh

# Output: packetfs-utils_1.0.0-1_amd64.deb
```

## License Key Generation (Private - DO NOT SHARE)

```bash
# Generate a license key for a specific user/organization
cd full_apps/pfs-infinity/app
/home/punk/.venv/bin/python license_check.py \
    --generate \
    --licensee "Company Name" \
    --days 365 \
    --features transfer,compress,cluster,web

# This creates: license_Company_Name.key
```

### License Features:
- `transfer` - File transfer capabilities
- `compress` - F3 compression technology
- `cluster` - Cluster mode operations
- `web` - Web interface access
- `all` - All features enabled

## Distribution Process

### For Trusted Partners:

1. **Generate unique license**:
```bash
/home/punk/.venv/bin/python license_check.py \
    --generate \
    --licensee "Partner Corp" \
    --days 30
```

2. **Send two files**:
   - `packetfs-utils_1.0.0-1_amd64.deb`
   - `license_Partner_Corp.key`

3. **Installation instructions for them**:
```bash
# Install package
sudo dpkg -i packetfs-utils_1.0.0-1_amd64.deb
sudo apt-get install -f

# Install license
sudo mkdir -p /etc/packetfs
sudo cp license_Partner_Corp.key /etc/packetfs/license.key

# Start service
sudo systemctl start packetfs-transfer
```

### For Demo/Trial Users:

The software includes a 10-second delay demo mode with limited features:
- Max 10MB file size
- No cluster mode
- Watermarked transfers

They can run without a license but with limitations.

## Security Measures

### License Protection:
- SHA256 signed licenses with secret salt
- Expiration dates enforced
- Feature-based access control
- Cached validation (1 hour)

### Package Protection:
- No public repository distribution
- Manual .deb file sharing only
- License required for full features
- Demo mode limitations

### Secret Salt:
The `SECRET_SALT` in `license_check.py` is your master key. 
**NEVER share the license generation code!**

Current salt: `F3_PACKETFS_95_PERCENT_COMPRESSION_2025_PUNK`
(Change this in production!)

## Private Repository Setup (Optional)

If you want to host your own APT repository:

```bash
# Create repository structure
mkdir -p ~/apt-repo/pool/main/p/packetfs-utils
mkdir -p ~/apt-repo/dists/stable/main/binary-amd64

# Copy package
cp packetfs-utils_*.deb ~/apt-repo/pool/main/p/packetfs-utils/

# Generate package index
cd ~/apt-repo
dpkg-scanpackages pool/ > dists/stable/main/binary-amd64/Packages
gzip -c dists/stable/main/binary-amd64/Packages > \
     dists/stable/main/binary-amd64/Packages.gz

# Create Release file
cat > dists/stable/Release << EOF
Origin: PacketFS Private
Label: PacketFS Private
Suite: stable
Codename: stable
Version: 1.0
Architectures: amd64
Components: main
Description: Private PacketFS Repository
EOF

# Serve via nginx (with auth)
# Add to nginx config:
location /apt-repo {
    auth_basic "PacketFS Repository";
    auth_basic_user_file /etc/nginx/.htpasswd;
    autoindex on;
}
```

## Tracking Distributed Licenses

Keep a private log of issued licenses:

```bash
# Create license log
cat >> ~/licenses_issued.log << EOF
$(date): Partner Corp - 30 days - trial features
$(date): Customer Inc - 365 days - all features
EOF
```

## Revocation (Future)

To revoke a license, you could:
1. Maintain a revocation list on your server
2. Have the software check the list periodically
3. Disable features for revoked licenses

## Legal Considerations

Consider adding:
- EULA (End User License Agreement)
- Terms of Service
- Non-disclosure agreements
- Distribution agreements

## Contact for Licenses

Set up a controlled channel:
- Private email: packetfs-licenses@[your-domain]
- Encrypted communications (GPG)
- Manual vetting process

---

**Remember**: You hold the keys to F3 technology. Every license issued is traceable back to you. Distribute wisely! 🔐