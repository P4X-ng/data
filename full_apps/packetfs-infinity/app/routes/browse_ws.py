"""Shim registrar - use core implementation."""
try:
    from app.core.routes.browse_ws import register_browse_ws  # type: ignore
except Exception:  # pragma: no cover
    import importlib
    _mod = importlib.import_module("app.core.routes.browse_ws")
    register_browse_ws = getattr(_mod, "register_browse_ws")
