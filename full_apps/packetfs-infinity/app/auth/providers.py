"""Compatibility shim: re-export auth providers from core."""
from app.core.auth.providers import *  # noqa: F401,F403
from app.core.auth.providers import Provider, load_providers  # explicit for type-checkers
