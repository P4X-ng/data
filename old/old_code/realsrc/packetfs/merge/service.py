#!/usr/bin/env python3
import os
import threading
import time
from typing import Optional
from .transport import Transport, TLSConfig, send_json, recv_json, DEFAULT_PORT

DEFAULT_ROOT = os.getenv("PFS_MERGE_ROOT", "/data/local")

class MergeService:
    def __init__(self, bind_host: str = "0.0.0.0", port: int = DEFAULT_PORT, root: str = DEFAULT_ROOT):
        self.bind_host = bind_host
        self.port = port
        self.root = os.path.abspath(root)
        self._stop = threading.Event()

    def serve_forever(self):
        os.makedirs(self.root, exist_ok=True)
        t = Transport(self.bind_host, self.port, server=True)
        ls = t.listen()
        print(f"[pfs-merge] listening on {self.bind_host}:{self.port}, root={self.root}")
        try:
            while not self._stop.is_set():
                ls.settimeout(1.0)
                try:
                    c, addr = t.accept(ls)
                except TimeoutError:
                    continue
                except Exception:
                    continue
                threading.Thread(target=self._handle_client, args=(c,addr), daemon=True).start()
        finally:
            ls.close()

    def _handle_client(self, sock, addr):
        try:
            hello = recv_json(sock)
            if hello.get("type") != "hello":
                sock.close(); return
            send_json(sock, {"type":"hello","root": self.root})
            # TODO: exchange directory metadata incrementally
        except Exception as e:
            pass
        finally:
            try: sock.close()
            except: pass

    def stop(self):
        self._stop.set()


def main():
    import argparse
    p = argparse.ArgumentParser(description="PacketFS Merge Service")
    p.add_argument("--bind", default="0.0.0.0")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--root", default=DEFAULT_ROOT)
    args = p.parse_args()
    svc = MergeService(args.bind, args.port, args.root)
    try:
        svc.serve_forever()
    except KeyboardInterrupt:
        svc.stop()

if __name__ == "__main__":
    main()
