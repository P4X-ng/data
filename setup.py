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
    install_requires=[
        "websockets>=12,<13",
        "fusepy>=3,<4",
        "aioquic>=0.9,<1.0",
    ],
    entry_points={
        "console_scripts": [
            "pfs-arith-encode=packetfs.tools.arith_encode:main",
            "pfs-translate-daemon=packetfs.tools.translate_daemon:main",
            "pfs-arith-send=packetfs.tools.arith_send:main",
            "pfs-arith-send-quic=packetfs.tools.arith_send_quic:main",
            "pfsfs-mount=packetfs.filesystem.pfsfs_mount:main",
        ]
    },
)

