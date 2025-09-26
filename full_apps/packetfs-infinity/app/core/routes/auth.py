from __future__ import annotations
import os, secrets, time, json
from fastapi import APIRouter, Request, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse, JSONResponse
from urllib.parse import urlencode
import httpx
# Authlib-backed OAuth/OIDC integration
from app.core.auth.oauth_client import get_oauth, get_registered_providers, default_callback_url
from app.core.auth.sessions import create_session, destroy_session, get_user_from_request
from app.core.state import get_tenant_ctx

router = APIRouter(prefix="/auth", tags=["auth"])

STATE_CACHE: dict[str, dict] = {}
STATE_TTL = 600

def _gen_state(redirect: str, provider: str) -> str:
    s = secrets.token_urlsafe(24)
    STATE_CACHE[s] = {"redirect": redirect, "provider": provider, "ts": time.time()}
    return s

def _pop_state(s: str) -> dict | None:
    d = STATE_CACHE.pop(s, None)
    if not d:
        return None
    if time.time() - d.get("ts", 0) > STATE_TTL:
        return None
    return d

@router.get("/providers")
async def list_providers():
    providers = get_registered_providers()
    # Normalize shape expected by UI
    return [
        {"id": name, "name": name, "display": meta.get("display", name.title()), "kind": meta.get("kind", "oauth2")}
        for name, meta in providers.items()
    ]

@router.get("/login")
async def login(provider: str, request: Request, redirect: str = "/"):
    oauth = get_oauth()
    client = getattr(oauth, provider, None)
    if client is None:
        raise HTTPException(status_code=400, detail="unknown provider")
    # Track post-auth redirect using our own state cache; pass state through to provider
    state = _gen_state(redirect, provider)
    callback_url = os.getenv("PFS_OAUTH_CALLBACK_URL", default_callback_url())
    try:
        return await client.authorize_redirect(request, redirect_uri=callback_url, state=state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"authorize_redirect failed: {e}")

@router.get("/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None, provider: str | None = None):
    if not state:
        raise HTTPException(status_code=400, detail="missing state")
    meta = _pop_state(state)
    if not meta:
        raise HTTPException(status_code=400, detail="invalid state")
    prov_name = provider or meta.get("provider")
    oauth = get_oauth()
    client = getattr(oauth, prov_name, None)
    if client is None:
        raise HTTPException(status_code=400, detail="unknown provider")
    # Exchange code for token using Authlib (handles PKCE/state)
    try:
        token = await client.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"token exchange failed: {e}")

    userinfo = {}
    sub = None
    email = None
    display = None

    try:
        # Try OIDC userinfo first
        userinfo = await client.userinfo(token=token)
    except Exception:
        userinfo = {}

    # If provider is GitHub, fetch via API
    if prov_name == "github":
        try:
            resp = await client.get("user", token=token)
            if resp.status_code == 200:
                gh = resp.json()
                sub = str(gh.get("id") or gh.get("node_id"))
                display = gh.get("name") or gh.get("login")
            # Best-effort primary email
            try:
                r2 = await client.get("user/emails", token=token)
                if r2.status_code == 200:
                    emails = r2.json()
                    prim = next((e for e in emails if e.get("primary")), None)
                    email = (prim or {}).get("email") or email
            except Exception:
                pass
        except Exception:
            pass

    # Normalize from OIDC if available
    sub = sub or userinfo.get("sub") or "user" + secrets.token_hex(4)
    email = email or userinfo.get("email") or None
    display = display or userinfo.get("name") or userinfo.get("preferred_username") or (email.split('@')[0] if email else sub)

    # tenant id extraction
    tenant_id = (email.split('@')[0].lower() if email and '@' in email else (display or sub)[:32].lower())
    get_tenant_ctx(tenant_id)  # ensure tenant context exists

    user_profile = {
        "provider": prov_name,
        "user_id": f"{prov_name}:{sub}",
        "display": display,
        "email": email,
        "tenant_id": tenant_id,
    }
    cookie = create_session(user_profile)
    redirect_target = meta.get("redirect") or "/"
    secure_cookie = os.getenv("PFS_TLS", "1") in ("1","true","TRUE","True")
    resp = RedirectResponse(url=redirect_target)
    resp.set_cookie("pfs_session", cookie, httponly=True, secure=secure_cookie, samesite="lax", max_age=86400)
    return resp

@router.post("/logout")
async def logout(request: Request):
    c = request.cookies.get("pfs_session")
    if c:
        destroy_session(c)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("pfs_session")
    return resp

@router.get("/whoami")
async def whoami(request: Request):
    u = get_user_from_request(request)
    if not u:
        return {"authenticated": False}
    return {"authenticated": True, "user": {k: u.get(k) for k in ("provider","user_id","display","email")}, "tenant_id": u.get("tenant_id")}

@router.post("/enable")
async def enable_auth(request: Request):
    token = request.headers.get("X-Admin-Token") or request.query_params.get("token")
    expected = os.environ.get("PFS_ADMIN_TOKEN")
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")
    request.app.state.auth_enabled = True
    return {"ok": True, "auth_enabled": True}

@router.post("/disable")
async def disable_auth(request: Request):
    token = request.headers.get("X-Admin-Token") or request.query_params.get("token")
    expected = os.environ.get("PFS_ADMIN_TOKEN")
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")
    request.app.state.auth_enabled = False
    return {"ok": True, "auth_enabled": False}

@router.get("/status")
async def auth_status(request: Request):
    u = get_user_from_request(request)
    return {
        "auth_enabled": bool(getattr(request.app.state, "auth_enabled", False)),
        "authenticated": bool(u),
        "tenant_id": (u or {}).get("tenant_id") if u else None,
    }
