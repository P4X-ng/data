#!/usr/bin/env python3
"""
VMKit Setup Script
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="vmkit",
    version="0.1.0",
    description="Simple Python abstraction for libvirt/KVM with Secure Boot support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="VMKit Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0",
        "libvirt-python>=8.0",
        "psutil>=5.8",
        "PyYAML>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black>=22.0",
            "flake8>=4.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "vmkit=vmkit.cli:vmkit",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Systems Administration",
        "Topic :: System :: Emulators",
    ],
)