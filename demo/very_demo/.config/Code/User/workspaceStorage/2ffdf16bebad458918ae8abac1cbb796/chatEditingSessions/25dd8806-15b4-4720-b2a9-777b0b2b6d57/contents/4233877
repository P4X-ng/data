#!/usr/bin/env python3
"""Python rewrite of the Ruby `msfd` helper.

This is an intentionally lightweight, Python-native approximation of the
original Ruby script. The real Ruby version shares a single Metasploit
Framework instance across multiple interactive console clients by loading a
plugin inside the Ruby environment. Fully duplicating that behavior in Python
would require a port of large parts of Metasploit.

Design goals (pragmatic subset):
  * Expose a line-based TCP (optionally TLS) service.
  * Each inbound client gets a dedicated pseudo-terminal running `msfconsole`.
  * Provide allow/deny host filtering similar to -A / -D.
  * Support command-line flags close to the original: -a -p -s -f -A -D -q -h.

Limitations:
  * Does NOT multiplex a single framework instance; each client spawns its own `msfconsole`.
  * Banner suppression only hides the Python wrapper banner, not msfconsole's.
  * SSL is opportunistic and uses a generated self-signed certificate unless
    MSF_SSL_CERT / MSF_SSL_KEY env vars point at existing files.

Future improvements (easy extensions):
  * Reuse a single background msfconsole via RPC JSON API instead of spawning.
  * Add idle timeouts and max session limits.

"""
from __future__ import annotations

import argparse
import ipaddress
import os
import selectors
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="msfd.py", add_help=False,
                                description="Lightweight TCP fan-out for msfconsole (Python approximation)")
    p.add_argument('-a', dest='host', default='127.0.0.1', help='Bind to this IP address instead of loopback')
    p.add_argument('-p', dest='port', type=int, default=55554, help='Bind to this port instead of 55554')
    p.add_argument('-s', dest='ssl', action='store_true', help='Use SSL')
    p.add_argument('-f', dest='foreground', action='store_true', help='Run the daemon in the foreground')
    p.add_argument('-A', dest='allow', help='Comma-separated list of hosts allowed to connect')
    p.add_argument('-D', dest='deny', help='Comma-separated list of hosts denied from connecting')
    p.add_argument('-q', dest='quiet', action='store_true', help='Do not print the banner on startup')
    p.add_argument('-h', '--help', action='help', help='Help banner')
    return p.parse_args(argv)


def build_filter(list_arg: str | None):
    if not list_arg:
        return set()
    out = set()
    for token in list_arg.split(','):
        token = token.strip()
        if not token:
            continue
        try:
            out.add(ipaddress.ip_network(token, strict=False))
        except ValueError:
            print(f"[!] Ignoring invalid address/network token: {token}", file=sys.stderr)
    return out


def addr_allowed(addr: str, allow_list, deny_list) -> bool:
    ip = ipaddress.ip_address(addr)
    if deny_list and any(ip in net for net in deny_list):
        return False
    if allow_list:
        return any(ip in net for net in allow_list)
    return True  # default allow when no allow list


def ensure_cert() -> tuple[str, str]:
    # Use env-provided cert/key if present
    cert = os.getenv('MSF_SSL_CERT')
    key = os.getenv('MSF_SSL_KEY')
    if cert and key and Path(cert).is_file() and Path(key).is_file():
        return cert, key
    # Generate ephemeral self-signed cert
    import datetime, hashlib
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        print('[!] cryptography not installed; cannot generate self-signed certificate. Install with pip install cryptography.', file=sys.stderr)
        sys.exit(2)
    key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u'msfd-local')
    ])
    now = datetime.datetime.utcnow()
    cert_obj = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key_obj.public_key())
        .serial_number(int.from_bytes(hashlib.sha256(os.urandom(16)).digest()[:16], 'big'))
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=2))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(u'localhost')]), critical=False)
        .sign(key_obj, hashes.SHA256())
    )
    tmpdir = tempfile.mkdtemp(prefix='msfd-')
    cert_path = os.path.join(tmpdir, 'cert.pem')
    key_path = os.path.join(tmpdir, 'key.pem')
    with open(cert_path, 'wb') as f:
        f.write(cert_obj.public_bytes(serialization.Encoding.PEM))
    with open(key_path, 'wb') as f:
        f.write(key_obj.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    return cert_path, key_path


def spawn_msfconsole() -> subprocess.Popen:
    # Prefer local ./msfconsole script if present
    candidate = Path(__file__).parent / 'msfconsole'
    cmd = [str(candidate)] if candidate.exists() and os.access(candidate, os.X_OK) else ['msfconsole']
    # -q quiet banner (Ruby msfconsole) if supported
    cmd.append('-q')
    # Force interactive mode
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)


def handle_client(conn: socket.socket, addr: tuple[str, int]):
    peer = f"{addr[0]}:{addr[1]}"
    print(f"[*] Client connected {peer}")
    proc = spawn_msfconsole()
    sel = selectors.DefaultSelector()
    sel.register(conn, selectors.EVENT_READ, 'client')
    sel.register(proc.stdout, selectors.EVENT_READ, 'msf')
    try:
        conn.sendall(b"Welcome to msfd (Python wrapper) - individual msfconsole instance\n")
        while True:
            for key, _ in sel.select():
                if key.data == 'client':
                    data = conn.recv(4096)
                    if not data:
                        return
                    if proc.poll() is not None:
                        return
                    try:
                        proc.stdin.write(data.decode('utf-8', errors='ignore'))
                        proc.stdin.flush()
                    except Exception:
                        return
                else:  # msf output
                    line = proc.stdout.readline()
                    if not line:
                        return
                    try:
                        conn.sendall(line.encode('utf-8', errors='ignore'))
                    except Exception:
                        return
    finally:
        proc.kill()
        conn.close()
        print(f"[*] Client disconnected {peer}")


def main():
    args = parse_args()
    allow = build_filter(args.allow)
    deny = build_filter(args.deny)

    if not args.foreground:
        # Basic daemonization (POSIX)
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)
        sys.stdout.flush()
        sys.stderr.flush()
        with open(os.devnull, 'rb') as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        with open(os.devnull, 'ab') as devnull:
            os.dup2(devnull.fileno(), sys.stdout.fileno())
            os.dup2(devnull.fileno(), sys.stderr.fileno())

    if not args.quiet:
        print(f"[*] Initializing msfd Python wrapper on {args.host}:{args.port} SSL={'yes' if args.ssl else 'no'}")

    sock = socket.socket(socket.AF_INET6 if ':' in args.host else socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(50)

    ssl_context = None
    if args.ssl:
        cert_path, key_path = ensure_cert()
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)

    stop = threading.Event()

    def sig_handler(signum, frame):  # noqa: ARG001
        stop.set()
        try:
            sock.close()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    while not stop.is_set():
        try:
            conn, addr = sock.accept()
        except OSError:
            break
        if not addr_allowed(addr[0], allow, deny):
            try:
                conn.sendall(b"Access denied by policy\n")
            except Exception:
                pass
            conn.close()
            continue
        if ssl_context:
            try:
                conn = ssl_context.wrap_socket(conn, server_side=True)
            except ssl.SSLError as e:
                print(f"[!] SSL handshake failed: {e}")
                conn.close()
                continue
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

    print('[*] msfd shutting down')


if __name__ == '__main__':
    main()
