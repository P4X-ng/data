from __future__ import annotations
import os
from typing import Dict, Optional
from authlib.integrations.starlette_client import OAuth

# Central OAuth registry using Authlib. We register providers only when they are configured.
# Supported providers:
# - google (OIDC discovery)
# - github (OAuth2; userinfo via API)
# - microsoft (OIDC discovery; tenant from PFS_MS_TENANT_ID, default "common")
# - oidc (generic OIDC discovery via PFS_GENERIC_OIDC_DISCOVERY_URL or issuer)

_oauth: Optional[OAuth] = None
_registered: Dict[str, Dict[str, str]] = {}


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v in ("1", "true", "TRUE", "True")


def _register_google(oauth: OAuth) -> None:
    cid = os.getenv("PFS_GOOGLE_CLIENT_ID")
    secret = os.getenv("PFS_GOOGLE_CLIENT_SECRET")
    if not (cid and secret):
        return
    oauth.register(
        name="google",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_id=cid,
        client_secret=secret,
        client_kwargs={"scope": "openid email profile"},
    )
    _registered["google"] = {"display": "Google", "kind": "oidc"}


def _register_github(oauth: OAuth) -> None:
    cid = os.getenv("PFS_GITHUB_CLIENT_ID")
    secret = os.getenv("PFS_GITHUB_CLIENT_SECRET")
    if not (cid and secret):
        return
    oauth.register(
        name="github",
        client_id=cid,
        client_secret=secret,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )
    _registered["github"] = {"display": "GitHub", "kind": "oauth2"}


def _register_microsoft(oauth: OAuth) -> None:
    tenant = os.getenv("PFS_MS_TENANT_ID", "common")
    cid = os.getenv("PFS_MS_CLIENT_ID")
    secret = os.getenv("PFS_MS_CLIENT_SECRET")
    if not (cid and secret):
        return
    discovery = f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration"
    oauth.register(
        name="microsoft",
        server_metadata_url=discovery,
        client_id=cid,
        client_secret=secret,
        client_kwargs={"scope": "openid email profile"},
    )
    _registered["microsoft"] = {"display": "Microsoft", "kind": "oidc"}


def _register_generic_oidc(oauth: OAuth) -> None:
    discovery = os.getenv("PFS_GENERIC_OIDC_DISCOVERY_URL")
    issuer = os.getenv("PFS_GENERIC_OIDC_ISSUER")
    cid = os.getenv("PFS_GENERIC_OIDC_CLIENT_ID")
    secret = os.getenv("PFS_GENERIC_OIDC_CLIENT_SECRET")
    if not (cid and secret):
        return
    if not discovery and issuer:
        discovery = issuer.rstrip("/") + "/.well-known/openid-configuration"
    if not discovery:
        return
    display = os.getenv("PFS_GENERIC_OIDC_DISPLAY", "OIDC")
    scopes = os.getenv("PFS_GENERIC_OIDC_SCOPES", "openid email profile").split()
    oauth.register(
        name="oidc",
        server_metadata_url=discovery,
        client_id=cid,
        client_secret=secret,
        client_kwargs={"scope": " ".join(scopes)},
    )
    _registered["oidc"] = {"display": display, "kind": "oidc"}


def get_oauth() -> OAuth:
    global _oauth
    if _oauth is not None:
        return _oauth
    _oauth = OAuth()
    # Allow filtering via PFS_OAUTH_PROVIDERS (comma-separated names)
    requested = os.getenv("PFS_OAUTH_PROVIDERS")
    requested_list = None
    if requested:
        requested_list = [x.strip().lower() for x in requested.split(',') if x.strip()]

    # Register known providers (only if configured)
    def want(name: str) -> bool:
        if requested_list is None:
            return True
        return name in requested_list

    if want("google"):
        _register_google(_oauth)
    if want("github"):
        _register_github(_oauth)
    if want("microsoft"):
        _register_microsoft(_oauth)
    if want("oidc"):
        _register_generic_oidc(_oauth)

    return _oauth


def get_registered_providers() -> Dict[str, Dict[str, str]]:
    # Ensure registration attempted
    get_oauth()
    return dict(_registered)


def default_callback_url() -> str:
    # Compute a reasonable default callback URL
    tls = _bool_env("PFS_TLS", True)
    scheme = "https" if tls else "http"
    host = os.getenv("PFS_PUBLIC_HOST", "localhost")
    port = os.getenv("WS_PORT") or os.getenv("PORT") or "8811"
    return f"{scheme}://{host}:{port}/auth/callback"