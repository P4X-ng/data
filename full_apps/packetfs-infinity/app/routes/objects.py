"""Router shim - use core implementation.

We import lazily to play nice with static analyzers that may not track the
package path correctly during partial loads.
"""
try:
	from app.core.routes.objects import router  # type: ignore
except Exception:  # pragma: no cover - dev env import quirk
	# Fallback import path (should not be needed at runtime)
	import importlib
	_mod = importlib.import_module("app.core.routes.objects")
	router = getattr(_mod, "router")
