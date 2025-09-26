from __future__ import annotations
"""Session handling (in-memory) and helpers (core copy)."""
import os, secrets, time
from typing import Dict, Any, Optional
from itsdangerous import URLSafeSerializer, BadSignature

SESSION_SECRET = os.getenv("PFS_SESSION_SECRET", secrets.token_hex(32))
SESSION_TTL = int(os.getenv("PFS_SESSION_TTL_SECONDS", "86400"))
serializer = URLSafeSerializer(SESSION_SECRET, salt="pfs-session")

SESSIONS: Dict[str, Dict[str, Any]] = {}

def _now() -> int:
    return int(time.time())

def create_session(user: Dict[str, Any]) -> str:
    sid = secrets.token_urlsafe(24)
    exp = _now() + SESSION_TTL
    SESSIONS[sid] = {"user": user, "created": _now(), "expires": exp}
    return serializer.dumps({"sid": sid, "exp": exp})

def decode_cookie(cookie: str) -> Optional[Dict[str, Any]]:
    try:
        data = serializer.loads(cookie)
        sid = data.get("sid")
        exp = int(data.get("exp", 0))
        if exp < _now():
            if sid in SESSIONS: del SESSIONS[sid]
            return None
        sess = SESSIONS.get(sid)
        if not sess:
            return None
        if sess["expires"] < _now():
            del SESSIONS[sid]
            return None
        return {"sid": sid, **sess}
    except BadSignature:
        return None
    except Exception:
        return None

def destroy_session(cookie: str) -> None:
    d = decode_cookie(cookie)
    if d and d.get("sid") in SESSIONS:
        try: del SESSIONS[d["sid"]]
        except Exception: pass

def get_user_from_request(request) -> Optional[Dict[str, Any]]:
    c = request.cookies.get("pfs_session") if hasattr(request, 'cookies') else None
    if not c: return None
    d = decode_cookie(c)
    if not d: return None
    return d.get("user")
