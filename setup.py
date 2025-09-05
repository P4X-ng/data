from setuptools import setup, Extension, find_packages

ext_modules = [
    Extension(
        "packetfs._bitpack",
        sources=["realsrc/native/bitpack.c"],
        extra_compile_args=[],
        extra_link_args=[],
    ),
]

setup(
    name="packetfs",
    version="0.1.0",
    description="PacketFS production package with native bitstream codec",
    packages=find_packages(where="realsrc"),
    package_dir={"": "realsrc"},
    ext_modules=ext_modules,
    python_requires=">=3.8",
)

