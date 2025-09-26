from __future__ import annotations
"""Compatibility shim: re-export session helpers from core."""
from app.core.auth.sessions import *  # noqa: F401,F403
from app.core.auth.sessions import (
    create_session,
    decode_cookie,
    destroy_session,
    get_user_from_request,
)
