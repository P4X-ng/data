from setuptools import setup, Extension
from pathlib import Path

this_dir = Path(__file__).parent

bitpack_ext = Extension(
    name="packetfs._bitpack",
    sources=[
        str(this_dir / "src" / "native" / "bitpack.c"),
        str(this_dir / "src" / "native" / "prp.c"),
    ],
    extra_compile_args=["-O3", "-std=c11", "-Wall", "-Wextra"],
)

setup(
    name="packetfs",
    version="0.1.0",
    description="Ultra-minimal raw-Ethernet offset streaming",
    packages=["packetfs"],
    package_dir={"": "src"},
    ext_modules=[bitpack_ext],
    python_requires=">=3.10",
)

