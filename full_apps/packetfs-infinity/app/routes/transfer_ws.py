"""Router shim - use core implementation."""
try:
    from app.core.routes.transfer_ws import router  # type: ignore
except Exception:  # pragma: no cover
    import importlib
    _mod = importlib.import_module("app.core.routes.transfer_ws")
    router = getattr(_mod, "router")