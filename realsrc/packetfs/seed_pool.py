import os
from dataclasses import dataclass
from typing import List


@dataclass
class SeedPool:
    seeds: List[bytes]

    @classmethod
    def from_file(cls, path: str) -> "SeedPool":
        seeds: List[bytes] = []
        with open(path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(b"#"):
                    continue
                # accept hex or raw
                try:
                    if (
                        all(c in b"0123456789abcdefABCDEF" for c in line)
                        and len(line) % 2 == 0
                    ):
                        seeds.append(bytes.fromhex(line.decode()))
                    else:
                        seeds.append(line)
                except Exception:
                    continue
        if not seeds:
            raise ValueError("No seeds loaded from file")
        return cls(seeds)

    def get(self, idx: int) -> bytes:
        return self.seeds[idx % len(self.seeds)]
