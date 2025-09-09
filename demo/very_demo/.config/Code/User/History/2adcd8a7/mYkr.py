#!/usr/bin/env python3
"""Python rewrite (scaffold) of `msfdb`.

The original Ruby script manages PostgreSQL clusters, initializes Metasploit
databases, and controls the Metasploit web service / JSON-RPC services.

This Python version provides a pragmatic subset:
  * Initialize (create) PostgreSQL databases/users via psycopg2.
  * Write a YAML `database.yml` similar to the Ruby version.
  * Start/stop/status for a lightweight Flask web service (placeholder for the real msf-ws).
  * Basic credential + token auth for the placeholder web service.

It does NOT:
  * Manage system-wide postgres clusters (relies on an existing server).
  * Migrate Metasploit schema (placeholder only).
  * Provide full parity with the Ruby service.

Commands:
  init, reinit, delete, status, start, stop, restart

Components:
  database, webservice (default: both)
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml  # type: ignore

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:  # noqa: BLE001
    psycopg2 = None  # type: ignore


BASE_DIR = Path(__file__).resolve().parent
LOCALCONF = Path.home() / '.msf4'
DB_CONF = LOCALCONF / 'database.yml'
WS_PID = LOCALCONF / 'msf-ws.pid'
WS_LOG = LOCALCONF / 'logs' / 'msf-ws.log'
WS_CERT = LOCALCONF / 'msf-ws-cert.pem'
WS_KEY = LOCALCONF / 'msf-ws-key.pem'


def ensure_dirs():
    (LOCALCONF / 'logs').mkdir(parents=True, exist_ok=True)


@dataclass
class Options:
    component: Optional[str] = None
    msf_db_name: str = 'msf'
    msf_db_user: str = 'msf'
    msf_db_pass: Optional[str] = None
    msftest_db_name: str = 'msftest'
    msftest_db_user: str = 'msftest'
    msftest_db_pass: Optional[str] = None
    db_host: str = '127.0.0.1'
    db_port: int = 5432
    db_pool: int = 200
    address: str = '127.0.0.1'
    port: int = 5443
    ssl: bool = True
    ssl_disable_verify: bool = True
    ws_user: Optional[str] = None
    ws_pass: Optional[str] = None
    delete_existing_data: bool = True


def parse_args(argv=None) -> tuple[Options, list[str]]:
    parser = argparse.ArgumentParser(prog='msfdb.py', add_help=True)
    parser.add_argument('command', nargs='?', help='init|reinit|delete|status|start|stop|restart')
    parser.add_argument('--component', choices=['database', 'webservice'], help='Target a specific component')
    parser.add_argument('--db-host', default='127.0.0.1')
    parser.add_argument('--db-port', type=int, default=5432)
    parser.add_argument('--db-name', default='msf')
    parser.add_argument('--db-user', default='msf')
    parser.add_argument('--db-test-name', default='msftest')
    parser.add_argument('--db-test-user', default='msftest')
    parser.add_argument('--address', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5443)
    parser.add_argument('--no-ssl', action='store_true')
    parser.add_argument('--keep-data', action='store_true', help='Do not delete existing data on reinit')
    parser.add_argument('--ws-user')
    parser.add_argument('--ws-pass')
    args = parser.parse_args(argv)
    opts = Options(
        component=args.component,
        msf_db_name=args.db_name,
        msf_db_user=args.db_user,
        msftest_db_name=args.db_test_name,
        msftest_db_user=args.db_test_user,
        db_host=args.db_host,
        db_port=args.db_port,
        address=args.address,
        port=args.port,
        ssl=not args.no_ssl,
        delete_existing_data=not args.keep_data,
        ws_user=args.ws_user,
        ws_pass=args.ws_pass,
    )
    return opts, [args.command] if args.command else []


def pw_gen():
    import secrets
    return secrets.token_urlsafe(24)


def load_db_config():
    if DB_CONF.is_file():
        with open(DB_CONF, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return None


def write_db_config(opts: Options):
    ensure_dirs()
    content = textwrap.dedent(f"""
    development: &pgsql
      adapter: postgresql
      database: {opts.msf_db_name}
      username: {opts.msf_db_user}
      password: {opts.msf_db_pass}
      host: {opts.db_host}
      port: {opts.db_port}
      pool: {opts.db_pool}

    production: &production
      <<: *pgsql

    test:
      <<: *pgsql
      database: {opts.msftest_db_name}
      username: {opts.msftest_db_user}
      password: {opts.msftest_db_pass}
    """
    ).strip() + '\n'
    with open(DB_CONF, 'w', encoding='utf-8') as f:
        f.write(content)
    os.chmod(DB_CONF, 0o640)
    print(f'[*] Wrote {DB_CONF}')


def db_connect(dbname: str, opts: Options):  # returns connection or None
    if psycopg2 is None:
        print('[-] psycopg2 not installed, database operations unavailable')
        return None
    try:
        return psycopg2.connect(host=opts.db_host, port=opts.db_port, dbname=dbname, user=opts.msf_db_user, password=opts.msf_db_pass)
    except Exception:  # noqa: BLE001
        return None


def create_db_and_user(opts: Options):
    if psycopg2 is None:
        return
    admin_pass = os.getenv('PGPASSWORD')
    admin_user = os.getenv('PGUSER', 'postgres')
    try:
        conn = psycopg2.connect(host=opts.db_host, port=opts.db_port, dbname='postgres', user=admin_user, password=admin_pass)
    except Exception as e:  # noqa: BLE001
        print(f'[-] Could not connect to postgres to initialize databases: {e}')
        return
    conn.autocommit = True
    cur = conn.cursor()
    for user, pw in [(opts.msf_db_user, opts.msf_db_pass), (opts.msftest_db_user, opts.msftest_db_pass)]:
        try:
            cur.execute(sql.SQL('CREATE USER {} WITH PASSWORD %s').format(sql.Identifier(user)), [pw])
            print(f'[*] Created user {user}')
        except Exception:
            pass
    for db in [opts.msf_db_name, opts.msftest_db_name]:
        try:
            cur.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(db), sql.Identifier(opts.msf_db_user)))
            print(f'[*] Created database {db}')
        except Exception:
            pass
    cur.close()
    conn.close()


def status_db(opts: Options):
    if psycopg2 is None:
        print('[*] Database status: unavailable (psycopg2 missing)')
        return
    conn = db_connect(opts.msf_db_name, opts)
    if conn:
        print('[*] Database status: RUNNING')
        conn.close()
    else:
        print('[*] Database status: INACTIVE or not initialized')


def delete_db(opts: Options):
    if psycopg2 is None:
        return
    admin_pass = os.getenv('PGPASSWORD')
    admin_user = os.getenv('PGUSER', 'postgres')
    try:
        conn = psycopg2.connect(host=opts.db_host, port=opts.db_port, dbname='postgres', user=admin_user, password=admin_pass)
    except Exception:
        return
    conn.autocommit = True
    cur = conn.cursor()
    for db in [opts.msf_db_name, opts.msftest_db_name]:
        try:
            cur.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(db)))
            print(f'[*] Dropped database {db}')
        except Exception:
            pass
    for user in [opts.msf_db_user, opts.msftest_db_user]:
        try:
            cur.execute(sql.SQL('DROP USER IF EXISTS {}').format(sql.Identifier(user)))
            print(f'[*] Dropped user {user}')
        except Exception:
            pass
    cur.close()
    conn.close()


def generate_self_signed(cert_path: Path, key_path: Path):
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime, hashlib, secrets
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u'msf-ws')])
        now = datetime.datetime.utcnow()
        cert = (x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(subject)
                .public_key(key.public_key())
                .serial_number(int.from_bytes(hashlib.sha256(secrets.token_bytes(16)).digest()[:16], 'big'))
                .not_valid_before(now)
                .not_valid_after(now + datetime.timedelta(days=2))
                .sign(key, hashes.SHA256()))
        with open(cert_path, 'wb') as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        with open(key_path, 'wb') as f:
            f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    except Exception as e:  # noqa: BLE001
        print(f'[-] Failed to generate self-signed cert: {e}')


def start_webservice(opts: Options):
    if WS_PID.is_file():
        print('[*] Web service already started')
        return
    ensure_dirs()
    if opts.ssl and (not WS_CERT.is_file() or not WS_KEY.is_file()):
        generate_self_signed(WS_CERT, WS_KEY)
    # Launch flask app in background
    cmd = [sys.executable, '-u', '-m', 'msfdb_webservice', '--host', opts.address, '--port', str(opts.port)]
    env = os.environ.copy()
    env['MSFDB_CONFIG'] = str(DB_CONF)
    env['MSFDB_WS_USER'] = opts.ws_user or 'msf'
    env['MSFDB_WS_PASS'] = opts.ws_pass or (pw_gen())
    env['MSFDB_SSL'] = '1' if opts.ssl else '0'
    env['MSFDB_SSL_CERT'] = str(WS_CERT)
    env['MSFDB_SSL_KEY'] = str(WS_KEY)
    with open(WS_LOG, 'ab') as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=lf, env=env)
    WS_PID.write_text(str(proc.pid))
    print(f'[*] Started web service PID {proc.pid} (log: {WS_LOG})')


def stop_webservice():
    if not WS_PID.is_file():
        print('[*] Web service not running')
        return
    try:
        pid = int(WS_PID.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        print(f'[*] Sent SIGTERM to PID {pid}')
    except Exception as e:  # noqa: BLE001
        print(f'[-] Failed stopping web service: {e}')
    try:
        WS_PID.unlink()
    except Exception:
        pass


def status_webservice():
    if not WS_PID.is_file():
        print('[*] Web service status: INACTIVE')
        return
    try:
        pid = int(WS_PID.read_text().strip())
        os.kill(pid, 0)
        print(f'[*] Web service status: RUNNING (PID {pid})')
    except Exception:
        print('[*] Web service status: STALE PID FILE')


def delete_webservice():
    stop_webservice()
    for f in [WS_CERT, WS_KEY]:
        try:
            f.unlink()
        except Exception:
            pass
    print('[*] Deleted web service artifacts')


def command_init(opts: Options):
    if opts.component in (None, 'database'):
        if not opts.msf_db_pass:
            opts.msf_db_pass = pw_gen()
        if not opts.msftest_db_pass:
            opts.msftest_db_pass = pw_gen()
        write_db_config(opts)
        create_db_and_user(opts)
        print('[*] (Placeholder) Would run schema migrations here')
    if opts.component in (None, 'webservice'):
        if not opts.ws_user:
            opts.ws_user = 'msf'
        if not opts.ws_pass:
            opts.ws_pass = pw_gen()
        start_webservice(opts)


def command_reinit(opts: Options):
    if opts.component in (None, 'database') and opts.delete_existing_data:
        delete_db(opts)
    if opts.component in (None, 'webservice'):
        delete_webservice()
    command_init(opts)


def command_delete(opts: Options):
    if opts.component in (None, 'webservice'):
        delete_webservice()
    if opts.component in (None, 'database'):
        delete_db(opts)


def command_status(opts: Options):
    if opts.component in (None, 'database'):
        status_db(opts)
    if opts.component in (None, 'webservice'):
        status_webservice()


def command_start(opts: Options):
    if opts.component in (None, 'webservice'):
        start_webservice(opts)
    if opts.component in (None, 'database'):
        status_db(opts)


def command_stop(opts: Options):
    if opts.component in (None, 'webservice'):
        stop_webservice()


def command_restart(opts: Options):
    command_stop(opts)
    time.sleep(0.5)
    command_start(opts)


def main():
    opts, commands = parse_args()
    if not commands:
        print('No command provided (init|reinit|delete|status|start|stop|restart)')
        sys.exit(1)
    cmd = commands[0]
    dispatch = {
        'init': command_init,
        'reinit': command_reinit,
        'delete': command_delete,
        'status': command_status,
        'start': command_start,
        'stop': command_stop,
        'restart': command_restart,
    }
    if cmd not in dispatch:
        print(f'Unknown command: {cmd}')
        sys.exit(1)
    dispatch[cmd](opts)


if __name__ == '__main__':
    main()
