#!/usr/bin/env python3
import os
import ssl
import socket
import json
import time
import tempfile
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple

DEFAULT_PORT = int(os.getenv("PFS_MERGE_PORT", "9876"))

@dataclass
class TLSConfig:
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    cafile: Optional[str] = None
    require_client_cert: bool = True

    @classmethod
    def auto(cls) -> "TLSConfig":
        # 1) Explicit environment variables take precedence
        c_env = os.getenv("PFS_TLS_CERT")
        k_env = os.getenv("PFS_TLS_KEY")
        ca_env = os.getenv("PFS_TLS_CA")
        if c_env and k_env and os.path.isfile(c_env) and os.path.isfile(k_env):
            return cls(certfile=c_env, keyfile=k_env, cafile=ca_env if (ca_env and os.path.isfile(ca_env)) else None)
        # 2) Let's Encrypt live path if domain provided
        le_name = os.getenv("PFS_TLS_LE_NAME")
        if le_name:
            le_dir = os.path.join("/etc/letsencrypt/live", le_name)
            cert = os.path.join(le_dir, "fullchain.pem")
            key = os.path.join(le_dir, "privkey.pem")
            if os.path.isfile(cert) and os.path.isfile(key):
                # Optionally use chain as CA for mutual TLS if desired
                ca = os.path.join(le_dir, "chain.pem")
                caf = ca if os.path.isfile(ca) else None
                return cls(certfile=cert, keyfile=key, cafile=caf)
        # 3) Self-signed fallback (unless explicitly disabled)
        if os.getenv("PFS_TLS_DISABLE", "0") != "1":
            try:
                cert, key = _generate_self_signed()
                return cls(certfile=cert, keyfile=key, cafile=None)
            except Exception:
                pass
        # 4) No TLS material detected or disabled; run plaintext
        return cls(certfile=None, keyfile=None, cafile=None, require_client_cert=False)

def _generate_self_signed() -> Tuple[str, str]:
    """Generate ephemeral self-signed cert/key via openssl and return paths (cert, key)."""
    tmpdir = tempfile.mkdtemp(prefix="pfs-merge-ssl-")
    cert_path = os.path.join(tmpdir, "cert.pem")
    key_path = os.path.join(tmpdir, "key.pem")
    subj = os.getenv("PFS_TLS_SUBJ", "/CN=pfs-merge")
    cmd = [
        "openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
        "-x509", "-days", os.getenv("PFS_TLS_DAYS", "365"),
        "-subj", subj,
        "-keyout", key_path,
        "-out", cert_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return cert_path, key_path

class Transport:
    def __init__(self, host: str, port: int = DEFAULT_PORT, tls: Optional[TLSConfig] = None, server: bool = False):
        self.host = host
        self.port = port
        self.tls = tls or TLSConfig.auto()
        self.server = server
        self.sock: Optional[socket.socket] = None

    def _wrap(self, sock: socket.socket, server_side: bool) -> socket.socket:
        if not self.tls.certfile or not self.tls.keyfile:
            return sock
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH if server_side else ssl.Purpose.SERVER_AUTH)
        if server_side:
            ctx.load_cert_chain(certfile=self.tls.certfile, keyfile=self.tls.keyfile)
            if self.tls.cafile:
                ctx.load_verify_locations(cafile=self.tls.cafile)
                if self.tls.require_client_cert:
                    ctx.verify_mode = ssl.CERT_REQUIRED
        else:
            if self.tls.cafile:
                ctx.load_verify_locations(cafile=self.tls.cafile)
            ctx.check_hostname = False
        return ctx.wrap_socket(sock, server_side=server_side)

    def listen(self):
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind((self.host, self.port))
        ls.listen(16)
        return ls

    def accept(self, ls: socket.socket) -> Tuple[socket.socket, Tuple[str, int]]:
        c, addr = ls.accept()
        try:
            c = self._wrap(c, server_side=True)
        except Exception:
            c.close()
            raise
        return c, addr

    def connect(self, timeout=5.0) -> socket.socket:
        s = socket.create_connection((self.host, self.port), timeout=timeout)
        try:
            s = self._wrap(s, server_side=False)
        except Exception:
            s.close()
            raise
        self.sock = s
        return s

# Minimal protocol: announce and request merge root
# This will evolve into chunked directory metadata exchange + on-demand file reads

def send_json(sock: socket.socket, obj: dict):
    data = json.dumps(obj).encode()
    hdr = len(data).to_bytes(4, 'big')
    sock.sendall(hdr + data)

def recv_json(sock: socket.socket) -> dict:
    hdr = sock.recv(4)
    if len(hdr) < 4:
        raise ConnectionError("short read on header")
    n = int.from_bytes(hdr, 'big')
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("short read on body")
        buf += chunk
    return json.loads(buf.decode())
