"""
Shim module for backward compatibility.
Exports register_cluster_ws and start_background_tasks from core.
"""
try:
    from app.core.routes.cluster_ws import register_cluster_ws, start_background_tasks  # type: ignore
except Exception:  # pragma: no cover - allow import-time fallbacks
    # Provide no-op fallbacks to avoid import errors during static analysis
    def register_cluster_ws(app):  # type: ignore
        return None

    def start_background_tasks():  # type: ignore
        return None