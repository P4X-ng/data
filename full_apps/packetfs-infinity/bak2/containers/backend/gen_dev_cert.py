from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
import datetime, os
base = '/app/certs'
os.makedirs(base, exist_ok=True)
cert_path = f'{base}/dev.crt'
key_path = f'{base}/dev.key'
if not (os.path.isfile(cert_path) and os.path.isfile(key_path)):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'pfs-infinity'),
        x509.NameAttribute(NameOID.COMMON_NAME, 'pfs-infinity.local'),
    ])
    cert = (x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=825))
            .sign(key, hashes.SHA256()))
    with open(cert_path,'wb') as f: f.write(cert.public_bytes(Encoding.PEM))
    with open(key_path,'wb') as f: f.write(key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()))
print("[cert-gen] dev cert/key present")
