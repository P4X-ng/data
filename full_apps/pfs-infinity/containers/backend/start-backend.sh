#!/bin/sh
set -eu
# Force use of the in-image virtualenv for both Python and Hypercorn/Uvicorn
VENVDIR="${VIRTUAL_ENV:-/opt/venv}"
PY="$VENVDIR/bin/python"
HC="$VENVDIR/bin/hypercorn"
UV="$VENVDIR/bin/uvicorn"

BIND_ADDR="${BIND:-0.0.0.0}"
PORT="${WS_PORT:-${PORT:-8811}}"
TLS="${PFS_TLS:-1}"
CERT="${PFS_TLS_CERT:-/app/certs/dev.crt}"
KEY="${PFS_TLS_KEY:-/app/certs/dev.key}"

if [ "$TLS" = "1" ] || [ "$TLS" = "true" ] || [ "$TLS" = "TRUE" ]; then
  # Always ensure dev CA exists; ensure server cert exists (reissue if PFS_TLS_REISSUE=1)
  mkdir -p "$(dirname "$CERT")"
  "$PY" - <<'PY'
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
import datetime, os, ipaddress

base = '/app/certs'
cert_path = os.environ.get('PFS_TLS_CERT', f'{base}/dev.crt')
key_path = os.environ.get('PFS_TLS_KEY', f'{base}/dev.key')
ca_cert_path = f'{base}/dev_ca.crt'
ca_key_path = f'{base}/dev_ca.key'
reissue = os.environ.get('PFS_TLS_REISSUE','0') in ('1','true','TRUE','True')

# Build SANs
sans_env = os.environ.get('PFS_TLS_SANS','')
sans_list = [s.strip() for s in sans_env.split(',') if s.strip()]
default_dns = ['localhost', 'pfs-infinity.local']
default_ips = ['127.0.0.1']
hostname = os.uname().nodename if hasattr(os, 'uname') else os.environ.get('HOSTNAME','pfs-infinity')
if hostname and hostname not in default_dns:
    default_dns.append(hostname)

# Ensure CA exists
if not (os.path.isfile(ca_cert_path) and os.path.isfile(ca_key_path)):
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u'US'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'pfs-infinity-dev'),
        x509.NameAttribute(NameOID.COMMON_NAME, u'PFS Dev CA'),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    with open(ca_cert_path,'wb') as f: f.write(ca_cert.public_bytes(Encoding.PEM))
    with open(ca_key_path,'wb') as f: f.write(ca_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()))
else:
    from cryptography.hazmat.primitives import serialization as ser
    with open(ca_key_path,'rb') as f:
        ca_key = ser.load_pem_private_key(f.read(), password=None)
    with open(ca_cert_path,'rb') as f:
        ca_cert = x509.load_pem_x509_certificate(f.read())

# Build SAN entries
san_entries = []
for d in default_dns + sans_list:
    if not d:
        continue
    try:
        san_entries.append(x509.IPAddress(ipaddress.ip_address(d)))
    except ValueError:
        san_entries.append(x509.DNSName(d))
# Expand CIDR ranges if provided (comma-separated), add all usable hosts
cidrs_env = os.environ.get('PFS_TLS_SANS_CIDR','')
for c in [s.strip() for s in cidrs_env.split(',') if s.strip()]:
    try:
        net = ipaddress.ip_network(c, strict=False)
        for ip in net.hosts():
            san_entries.append(x509.IPAddress(ip))
    except Exception:
        pass
for ip in default_ips:
    san_entries.append(x509.IPAddress(ipaddress.ip_address(ip)))

# Issue server cert if missing or reissue requested
if reissue or (not (os.path.isfile(cert_path) and os.path.isfile(key_path))):
    srv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    srv_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u'US'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'pfs-infinity'),
        x509.NameAttribute(NameOID.COMMON_NAME, u'pfs-infinity.local'),
    ])
    now = datetime.datetime.utcnow()
    srv_cert = (
        x509.CertificateBuilder()
        .subject_name(srv_subject)
        .issuer_name(ca_cert.subject)
        .public_key(srv_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    with open(cert_path,'wb') as f: f.write(srv_cert.public_bytes(Encoding.PEM))
    with open(key_path,'wb') as f: f.write(srv_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()))
PY
  # Prefer Uvicorn for TLS serving stability
  exec "$UV" app.main:app --host "${BIND_ADDR}" --port "${PORT}" \
       --ssl-certfile "$CERT" --ssl-keyfile "$KEY" --log-level info --proxy-headers
else
  # Plain HTTP: prefer Uvicorn
  exec "$UV" app.main:app --host "${BIND_ADDR}" --port "${PORT}" --log-level info --proxy-headers
fi
