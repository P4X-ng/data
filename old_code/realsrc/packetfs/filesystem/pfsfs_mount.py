from __future__ import annotations

import errno
import json
import os
import stat
import threading
import tempfile
import uuid
from typing import Dict, List, Tuple

from fuse import FUSE, FuseOSError, Operations  # type: ignore

from .virtual_blob import VirtualBlob
from .iprog_recon import reconstruct_window_from_iprog_entry
from .blob_fs import BlobFS, BlobConfig
from .iprog import build_iprog_for_file_bytes, build_iprog_palette, BlobFingerprint


class PacketFSFuse(Operations):
    def __init__(self, iprog_dir: str, blob_name: str, blob_size: int, blob_seed: int, meta_dir: str, window_size: int = 65536, embed_pvrt: bool = True, read_only: bool = False):
        self.iprog_dir = iprog_dir
        self.meta_dir = meta_dir
        os.makedirs(self.iprog_dir, exist_ok=True)
        os.makedirs(self.meta_dir, exist_ok=True)
        self.window_size = int(window_size)
        self.embed_pvrt = bool(embed_pvrt)
        self.read_only = bool(read_only)
        # Blob and FS
        self.vb = VirtualBlob(blob_name, blob_size, blob_seed)
        self.vb.create_or_attach(create=True)
        # Ensure palette region and deterministic fill are present
        try:
            self.vb.ensure_filled()
        except Exception:
            pass
        self.blob_cfg = BlobConfig(name=blob_name, size_bytes=blob_size, seed=blob_seed, meta_dir=self.meta_dir)
        self.blobfs = BlobFS(self.blob_cfg)
        self.fp = BlobFingerprint(name=blob_name, size=blob_size, seed=blob_seed)
        # Index: filename -> iprog (dict)
        self.files: Dict[str, dict] = {}
        # Pending open files (for write): name -> {tmp_path, fh, size}
        self.pending: Dict[str, dict] = {}
        self._load_index()
        self._lock = threading.RLock()
        self._fh_counter = 3
        self._fh_map: Dict[int, str] = {}

    def destroy(self, path):
        try:
            self.blobfs.close()
            self.vb.close()
        except Exception:
            pass

    def _load_index(self):
        for entry in os.scandir(self.iprog_dir):
            if not entry.is_file() or not entry.name.endswith('.iprog.json'):
                continue
            try:
                with open(entry.path, 'r', encoding='utf-8') as f:
                    iprog = json.load(f)
                name = iprog.get('file') or entry.name[:-11]
                # Ensure unique names by appending (#) if collision
                base = name
                idx = 1
                while name in self.files:
                    idx += 1
                    name = f"{base}({idx})"
                self.files[name] = iprog
            except Exception:
                continue

    # Filesystem methods
    def getattr(self, path, fh=None):
        if path == '/' or path == b'/':
            st = dict(st_mode=(stat.S_IFDIR | 0o755), st_nlink=2)
            return st
        name = path.lstrip('/')
        ip = self.files.get(name)
        if ip is None:
            p = self.pending.get(name)
            if p is not None:
                size = int(p.get('size', 0))
                return dict(st_mode=(stat.S_IFREG | 0o644), st_nlink=1, st_size=size)
            raise FuseOSError(errno.ENOENT)
        size = int(ip.get('size', 0))
        mode = stat.S_IFREG | (0o444 if self.read_only else 0o644)
        st = dict(st_mode=mode, st_nlink=1, st_size=size)
        return st

    def readdir(self, path, fh):
        if path != '/':
            raise FuseOSError(errno.ENOTDIR)
        entries = ['.', '..'] + sorted(list(self.files.keys()) + list(self.pending.keys()))
        for e in entries:
            yield e

    def open(self, path, flags):
        name = path.lstrip('/')
        if name in self.pending:
            # opening a pending file for writing or reading: allow both
            fh = self._alloc_fh(name)
            return fh
        if name not in self.files:
            raise FuseOSError(errno.ENOENT)
        # Existing file: allow read-only unless read_only=False and O_TRUNC specified
        if (flags & os.O_ACCMODE) != os.O_RDONLY:
            # If O_TRUNC, treat as recreate
            if (flags & os.O_TRUNC) and not self.read_only:
                return self._create_new(name, mode=0o644)
            raise FuseOSError(errno.EACCES)
        fh = self._alloc_fh(name)
        return fh

    def create(self, path, mode, fi=None):
        if self.read_only:
            raise FuseOSError(errno.EROFS)
        name = path.lstrip('/')
        return self._create_new(name, mode)

    def _create_new(self, name: str, mode: int):
        with self._lock:
            if name in self.files:
                # Overwrite: move to pending
                pass
            tmp_dir = os.path.join(self.meta_dir, 'tmp')
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.part")
            f = open(tmp_path, 'wb+')
            self.pending[name] = {"tmp": tmp_path, "fp": f, "size": 0}
            fh = self._alloc_fh(name)
            return fh

    def write(self, path, data, offset, fh):
        if self.read_only:
            raise FuseOSError(errno.EROFS)
        name = path.lstrip('/')
        p = self.pending.get(name)
        if p is None:
            # writing to non-pending file not supported yet
            raise FuseOSError(errno.EACCES)
        f = p["fp"]
        f.seek(offset)
        f.write(data)
        new_size = max(p["size"], offset + len(data))
        p["size"] = new_size
        return len(data)

    def truncate(self, path, length, fh=None):
        if self.read_only:
            raise FuseOSError(errno.EROFS)
        name = path.lstrip('/')
        p = self.pending.get(name)
        if p is None:
            # Start a pending file if truncating an existing one
            if name in self.files:
                return 0
            raise FuseOSError(errno.ENOENT)
        f = p["fp"]
        f.truncate(length)
        p["size"] = length
        return 0

    def flush(self, path, fh):
        name = path.lstrip('/')
        p = self.pending.get(name)
        if p is not None:
            p["fp"].flush()
        return 0

    def release(self, path, fh):
        name = path.lstrip('/')
        p = self.pending.get(name)
        if p is None:
            return 0
        # Close temp file, compile to IPROG, append into blob
        f = p["fp"]
        f.flush()
        f.seek(0)
        data = f.read()
        f.close()
        try:
            # Palette mode stub: fall back to append for now; future: synthesize via ARITH
            if getattr(self, 'mode', 'append') != 'append':
                # TODO: implement palette compiler (no-write; BREF+ARITH over deterministic patterns)
                pass
            segs = self.blobfs.write_bytes(data)
            iprog = build_iprog_for_file_bytes(data, name, self.fp, segs, window_size=self.window_size, include_pvrt=self.embed_pvrt)
            iprog.setdefault('policy', {})['mode'] = getattr(self, 'mode', 'append')
            out_path = os.path.join(self.iprog_dir, name + ".iprog.json")
            with open(out_path, 'w', encoding='utf-8') as outf:
                json.dump(iprog, outf, separators=(",", ":"))
                outf.write("\n")
            # Update index
            self.files[name] = iprog
        finally:
            try:
                os.remove(p["tmp"])
            except Exception:
                pass
            self.pending.pop(name, None)
        return 0

    def unlink(self, path):
        if self.read_only:
            raise FuseOSError(errno.EROFS)
        name = path.lstrip('/')
        if name in self.pending:
            try:
                p = self.pending.pop(name)
                try:
                    p["fp"].close()
                except Exception:
                    pass
                try:
                    os.remove(p.get("tmp", ""))
                except Exception:
                    pass
            except Exception:
                pass
            return 0
        ip = self.files.pop(name, None)
        if ip is None:
            raise FuseOSError(errno.ENOENT)
        out_path = os.path.join(self.iprog_dir, name + ".iprog.json")
        try:
            os.remove(out_path)
        except FileNotFoundError:
            pass
        return 0

    def rename(self, old, new):
        if self.read_only:
            raise FuseOSError(errno.EROFS)
        oldn = old.lstrip('/')
        newn = new.lstrip('/')
        if oldn in self.pending:
            self.pending[newn] = self.pending.pop(oldn)
            return 0
        ip = self.files.get(oldn)
        if ip is None:
            raise FuseOSError(errno.ENOENT)
        oldp = os.path.join(self.iprog_dir, oldn + ".iprog.json")
        newp = os.path.join(self.iprog_dir, newn + ".iprog.json")
        try:
            with open(oldp, 'r', encoding='utf-8') as f:
                iprog = json.load(f)
            iprog['file'] = newn
            with open(newp, 'w', encoding='utf-8') as f:
                json.dump(iprog, f, separators=(",", ":"))
                f.write("\n")
            os.remove(oldp)
            self.files.pop(oldn, None)
            self.files[newn] = iprog
        except Exception:
            raise FuseOSError(errno.EIO)
        return 0

    def read(self, path, size, offset, fh):
        name = path.lstrip('/')
        # If pending, read from temp file
        p = self.pending.get(name)
        if p is not None:
            f = p["fp"]
            f.flush()
            f.seek(offset)
            return f.read(size)
        ip = self.files.get(name)
        if ip is None:
            raise FuseOSError(errno.ENOENT)
        total = int(ip.get('size', 0))
        if offset >= total:
            return b''
        end = min(offset + size, total)
        window_size = int(ip.get('window_size', 65536))
        out = bytearray()
        cur = offset
        while cur < end:
            widx = cur // window_size
            wstart = widx * window_size
            wend = min(wstart + window_size, total)
            w = ip['windows'][widx]
            # reconstruct window bytes
            data = reconstruct_window_from_iprog_entry(w, self.vb) or b''
            # slice desired portion
            s = max(0, cur - wstart)
            e = min(len(data), s + (end - cur))
            out += data[s:e]
            cur += (e - s)
            if e - s <= 0:
                break
        return bytes(out)

    # Optional: statfs for df-like info
    def statfs(self, path):
        # Expose blob size as total blocks, simplistic view
        bsize = 4096
        blocks = self.vb.size // bsize
        # advertise ample free space
        return dict(f_bsize=bsize, f_blocks=blocks, f_bfree=blocks*8, f_bavail=blocks*8)

    # Utility
    def _alloc_fh(self, name: str) -> int:
        with self._lock:
            fh = self._fh_counter
            self._fh_counter += 1
            self._fh_map[fh] = name
            return fh


def main():
    import argparse
    import sys

    p = argparse.ArgumentParser(description='PacketFS FUSE mount (read-write: compile-on-close to IPROG over VirtualBlob)')
    p.add_argument('--iprog-dir', required=True)
    p.add_argument('--mount', required=True)
    p.add_argument('--blob-name', required=True)
    p.add_argument('--blob-size', type=int, default=1<<30)
    p.add_argument('--blob-seed', type=int, default=1337)
    p.add_argument('--meta-dir', default='./pfsmeta')
    p.add_argument('--window', type=int, default=65536)
    p.add_argument('--embed-pvrt', action='store_true')
    p.add_argument('--mode', choices=['append','palette'], default='append')
    p.add_argument('--read-only', action='store_true')
    p.add_argument('--foreground', action='store_true')
    args = p.parse_args()

    os.makedirs(args.mount, exist_ok=True)
    fs = PacketFSFuse(args.iprog_dir, args.blob_name, int(args.blob_size), int(args.blob_seed), meta_dir=args.meta_dir, window_size=int(args.window), embed_pvrt=bool(args.embed_pvrt), read_only=bool(args.read_only))
    fs.mode = args.mode  # type: ignore[attr-defined]
    try:
        FUSE(fs, args.mount, nothreads=True, foreground=args.foreground, ro=bool(args.read_only))
    except RuntimeError as e:
        print(f"FUSE error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
