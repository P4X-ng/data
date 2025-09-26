from __future__ import annotations
"""OAuth provider registry (Google, PayPal, Generic OIDC, TikTok joke, Apple stub)."""
from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional
import os

@dataclass
class Provider:
    name: str
    display: str
    auth_url: str
    token_url: str | None
    userinfo_url: str | None
    scopes: list[str]
    client_id: str | None = None
    client_secret: str | None = None
    kind: str = "oidc"  # oidc | joke | custom
    enabled: bool = True
    extra: Dict[str, Any] | None = None

    def is_configured(self) -> bool:
        if self.kind == "joke":
            return True
        return bool(self.client_id and self.client_secret and self.auth_url and self.token_url)


def _google() -> Provider:
    return Provider(
        name="google",
        display="Google",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scopes=["openid","email","profile"],
        client_id=os.getenv("PFS_GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("PFS_GOOGLE_CLIENT_SECRET"),
    )

def _paypal() -> Provider:
    mode = os.getenv("PFS_PAYPAL_MODE","sandbox").lower()
    base = "https://api-m.sandbox.paypal.com" if mode != "live" else "https://api-m.paypal.com"
    return Provider(
        name="paypal",
        display="PayPal",
        auth_url=f"{base}/v1/oauth2/authorize",
        token_url=f"{base}/v1/oauth2/token",
        userinfo_url=None,  # PayPal's classic userinfo flow differs; simplified placeholder
        scopes=["openid","email","profile"],
        client_id=os.getenv("PFS_PAYPAL_CLIENT_ID"),
        client_secret=os.getenv("PFS_PAYPAL_CLIENT_SECRET"),
        extra={"mode": mode},
    )

def _generic_oidc() -> Optional[Provider]:
    issuer = os.getenv("PFS_GENERIC_OIDC_ISSUER")
    if not issuer:
        return None
    # Discovery would be nicer; keep static minimal for now
    auth_url = os.getenv("PFS_GENERIC_OIDC_AUTH") or issuer.rstrip('/') + "/authorize"
    token_url = os.getenv("PFS_GENERIC_OIDC_TOKEN") or issuer.rstrip('/') + "/token"
    userinfo_url = os.getenv("PFS_GENERIC_OIDC_USERINFO") or issuer.rstrip('/') + "/userinfo"
    return Provider(
        name="oidc",
        display=os.getenv("PFS_GENERIC_OIDC_DISPLAY","OIDC"),
        auth_url=auth_url,
        token_url=token_url,
        userinfo_url=userinfo_url,
        scopes=[s for s in (os.getenv("PFS_GENERIC_OIDC_SCOPES") or "openid email profile").split() if s],
        client_id=os.getenv("PFS_GENERIC_OIDC_CLIENT_ID"),
        client_secret=os.getenv("PFS_GENERIC_OIDC_CLIENT_SECRET"),
    )

def _tiktok_joke() -> Provider:
    return Provider(
        name="tiktok",
        display="TikTok (lol)",
        auth_url="",
        token_url=None,
        userinfo_url=None,
        scopes=[],
        kind="joke",
    )

def _apple_stub() -> Provider:
    return Provider(
        name="apple",
        display="Apple (coming soon)",
        auth_url="",
        token_url=None,
        userinfo_url=None,
        scopes=[],
        kind="custom",
        enabled=False,
    )

def _microsoft() -> Provider:
    # Azure AD v2 common tenant or specific tenant
    tenant = os.getenv("PFS_MS_TENANT_ID", "common")
    base = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
    return Provider(
        name="microsoft",
        display="Microsoft",
        auth_url=f"{base}/authorize",
        token_url=f"{base}/token",
        userinfo_url="https://graph.microsoft.com/oidc/userinfo",
        scopes=["openid","email","profile"],
        client_id=os.getenv("PFS_MS_CLIENT_ID"),
        client_secret=os.getenv("PFS_MS_CLIENT_SECRET"),
    )

ALL_BUILDERS: Dict[str, Callable[[], Optional[Provider]]] = {
    "google": _google,
    "paypal": _paypal,
    "oidc": _generic_oidc,
    "tiktok": _tiktok_joke,
    "apple": _apple_stub,
    "microsoft": _microsoft,
}

def load_providers() -> Dict[str, Provider]:
    requested = os.getenv("PFS_OAUTH_PROVIDERS", "google,paypal,tiktok").split(',')
    out: Dict[str, Provider] = {}
    for name in [r.strip().lower() for r in requested if r.strip()]:
        builder = ALL_BUILDERS.get(name)
        if not builder:
            continue
        p = builder()
        if not p:
            continue
        if not p.enabled:
            continue
        if p.is_configured() or p.kind == "joke":
            out[p.name] = p
    return out
