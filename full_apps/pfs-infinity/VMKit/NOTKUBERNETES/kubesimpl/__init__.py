"""
KubeSimpl - Simplified Kubernetes Implementation
"""

__version__ = "1.0.0"

from .transformer import KubeSimplTransformer
from .cli import main

__all__ = ["KubeSimplTransformer", "main"]
