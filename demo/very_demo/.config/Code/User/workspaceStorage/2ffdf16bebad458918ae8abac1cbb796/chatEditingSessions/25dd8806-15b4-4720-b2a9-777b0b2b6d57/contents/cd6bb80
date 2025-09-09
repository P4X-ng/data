#!/usr/bin/env python3
"""Python rewrite of `msfupdate` (subset functionality).

Primary focus: managing a git-based checkout (the most common scenario when
using a Python-centric workflow). Binary/offline installers are represented
as stubs.

Implements:
  * --git-remote REMOTE (default upstream)
  * --git-branch BRANCH (default master)
  * --offline-file FILE (stub)
  * -h / --help

Behavior mirrors the Ruby version where sensible:
  * Verifies user ownership of directory (skipped if forced with --no-owner-check)
  * Stashes local changes before pulling; does not auto-pop
  * Installs/updates Python requirements (if requirements.txt present)
  * Does NOT run bundler (Ruby) steps.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd=None, check=True, capture=False):
    if capture:
        return subprocess.run(cmd, cwd=cwd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc = subprocess.run(cmd, cwd=cwd, check=check)
    return proc


def git_available() -> bool:
    return subprocess.call(['git', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog='msfupdate.py', add_help=False,
                                description='Update a metasploit-framework git checkout (Python rewrite)')
    p.add_argument('--git-remote', default='upstream', help='git remote to use (default upstream)')
    p.add_argument('--git-branch', default='master', help='git branch to use (default master)')
    p.add_argument('--offline-file', help='offline update file (stub)')
    p.add_argument('--no-owner-check', action='store_true', help='skip ownership check')
    p.add_argument('--no-stash', action='store_true', help='do not stash local changes')
    p.add_argument('-h', '--help', action='help', help='show help')
    return p.parse_args(argv)


def ensure_upstream(repo_dir: Path):
    try:
        out = run(['git', 'remote', 'show', 'upstream'], cwd=repo_dir, check=False, capture=True)
        if out.returncode == 0 and 'rapid7/metasploit-framework' in out.stdout:
            return
    except Exception:  # noqa: BLE001
        pass
    print('[*] Adding upstream remote (rapid7/metasploit-framework)')
    run(['git', 'remote', 'add', 'upstream', 'https://github.com/rapid7/metasploit-framework.git'], cwd=repo_dir, check=False)


def update_git(repo_dir: Path, remote: str, branch: str, stash: bool):
    if not git_available():
        print('[-] git not available', file=sys.stderr)
        sys.exit(3)
    ensure_upstream(repo_dir)
    if stash:
        # detect dirty
        dirty = subprocess.run(['git', 'diff', '--quiet'], cwd=repo_dir)
        if dirty.returncode != 0:
            print('[*] Stashing local changes')
            run(['git', 'stash'], cwd=repo_dir, check=False)
    print(f"[*] Resetting and updating {remote}/{branch}")
    run(['git', 'fetch', remote], cwd=repo_dir, check=False)
    run(['git', 'checkout', branch], cwd=repo_dir, check=False)
    run(['git', 'reset', '--hard', f'{remote}/{branch}'], cwd=repo_dir, check=False)


def install_python_requirements(repo_dir: Path):
    req = repo_dir / 'requirements.txt'
    if req.is_file():
        print('[*] Installing Python requirements (pip)')
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(req)])


def main():
    args = parse_args()
    repo_dir = Path(__file__).resolve().parent
    print('[*] Attempting to update the Metasploit Framework (Python wrapper)')
    if not args.no_owner_check:
        try:
            st = repo_dir.stat()
            if st.st_uid != os.getuid():
                print('[-] ERROR: current user does not own the Metasploit directory (use --no-owner-check to override)', file=sys.stderr)
                sys.exit(10)
        except Exception as e:  # noqa: BLE001
            print(f'[!] Ownership check failed (continuing): {e}')
    if args.offline_file:
        print('[!] Offline update not implemented in Python version (stub)')
    update_git(repo_dir, args.git_remote, args.git_branch, not args.no_stash)
    install_python_requirements(repo_dir)
    print('[*] Update complete')


if __name__ == '__main__':
    main()
