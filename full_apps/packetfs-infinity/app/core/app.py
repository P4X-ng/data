from __future__ import annotations

import asyncio
import os
import secrets
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.state import APP_STATE, CURRENT_BLOB



def _debug(msg: str):
    if os.environ.get("PFS_DEBUG", "0") in ("1", "true", "TRUE", "True"):
        try:
            print(f"[pfs-debug] {msg}", flush=True)
        except Exception:
            pass


def _startup_tasks(app: FastAPI) -> None:
    @app.on_event("startup")
    async def _auto_attach_blob() -> None:  # noqa: N802
        # Best-effort attach a blob
        try:
            auto = os.environ.get("PFS_BLOB_AUTO", "1")
            if auto not in ("1", "true", "TRUE", "True"):
                return
            if CURRENT_BLOB:
                return
            name = os.environ.get("PFS_BLOB_NAME", "pfs_vblob")
            raw_size = int(os.environ.get("PFS_BLOB_SIZE_BYTES", str(1 << 30)))  # 1 GiB default
            # Clamp to avoid host SIGBUS if backing store cannot allocate; allow override
            # Default clamp now matches 1 GiB so code defaults remain 1 GiB unless explicitly reduced
            max_size = int(os.environ.get("PFS_BLOB_MAX_SIZE", str(1 << 30)))  # 1 GiB safety by default
            if raw_size > max_size:
                _debug(f"Requested blob size {raw_size} > max {max_size}, clamping")
            size = min(raw_size, max_size)
            seed = int(os.environ.get("PFS_BLOB_SEED", "1337"))
            from packetfs.filesystem.virtual_blob import VirtualBlob  # type: ignore

            vb = VirtualBlob(name=name, size_bytes=size, seed=seed)
            vb.create_or_attach(create=True)
            skip_fill = os.environ.get("PFS_BLOB_SKIP_FILL", "0") in ("1", "true", "TRUE", "True")
            progressive = os.environ.get("PFS_BLOB_PROGRESSIVE_FILL", "1") in ("1", "true", "TRUE", "True")
            if skip_fill:
                _debug("Skipping blob fill per PFS_BLOB_SKIP_FILL=1")
            elif progressive and size > (32 * 1024 * 1024):
                # Launch progressive fill task (chunked) so UX can show progress
                APP_STATE["BLOB_FILL"] = {"status": "running", "filled": 0, "size": size, "pct": 0.0}
                async def _progressive_fill():
                    try:
                        mv = vb.buffer
                        header_len = 32
                        # Write header then chunk fill using existing deterministic generator
                        vb.ensure_filled()  # quick header+maybe fill sentinel. We'll overwrite body progressively.
                        # Re-generate body deterministically: use internal block generator for repeatability
                        block_size = 1 << 20
                        from math import ceil
                        total_body = size - header_len
                        blocks = ceil(total_body / block_size)
                        filled = 0
                        # simple local generator replicating _fill_block semantics
                        # (importing private isn't ideal; we reuse method to avoid divergence)
                        for b in range(blocks):
                            want = min(block_size, total_body - filled)
                            if want <= 0:
                                break
                            mv[header_len + filled: header_len + filled + want] = vb._fill_block(want)  # type: ignore[attr-defined]
                            filled += want
                            pct = filled / max(1, total_body)
                            APP_STATE["BLOB_FILL"].update({"filled": filled, "pct": pct})  # type: ignore[index]
                            await asyncio.sleep(0)  # yield
                        APP_STATE["BLOB_FILL"].update({"status": "done", "filled": total_body, "pct": 1.0})  # type: ignore[index]
                    except Exception as e:  # pragma: no cover
                        APP_STATE["BLOB_FILL"] = {"status": "error", "error": str(e), "size": size}
                asyncio.create_task(_progressive_fill())
            else:
                vb.ensure_filled()
            CURRENT_BLOB.clear()
            CURRENT_BLOB.update(
                {
                    "name": name,
                    "size": size,
                    "seed": seed,
                    "id": vb.id,
                    "vb": vb,
                }
            )
            APP_STATE.pop("BLOB_INIT_ERROR", None)
            _debug(f"VirtualBlob attached id={vb.id} size={size} seed={seed}")
        except Exception as e:  # Capture and expose error for status endpoint
            APP_STATE["BLOB_INIT_ERROR"] = str(e)
            _debug(f"VirtualBlob attach failed: {e}")

        # QUIC server startup
        try:
            enable = os.environ.get("PFS_QUIC_ENABLE", "1")
            if enable in ("1", "true", "TRUE", "True"):
                host = os.environ.get("PFS_QUIC_HOST", "0.0.0.0")
                port = int(os.environ.get("PFS_QUIC_PORT", "8853"))
                cert = os.environ.get("PFS_QUIC_CERT", "/tmp/pfs_quic_cert.pem")
                key = os.environ.get("PFS_QUIC_KEY", "/tmp/pfs_quic_key.pem")
                if not (os.path.isfile(cert) and os.path.isfile(key)):
                    try:
                        from cryptography import x509  # type: ignore
                        from cryptography.x509.oid import NameOID  # type: ignore
                        from cryptography.hazmat.primitives import hashes, serialization  # type: ignore
                        from cryptography.hazmat.primitives.asymmetric import rsa  # type: ignore
                        import datetime

                        key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                        subject = issuer = x509.Name(
                            [
                                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pfs-infinity"),
                                x509.NameAttribute(NameOID.COMMON_NAME, "pfs-infinity"),
                            ]
                        )
                        cert_obj = (
                            x509.CertificateBuilder()
                            .subject_name(subject)
                            .issuer_name(issuer)
                            .public_key(key_obj.public_key())
                            .serial_number(x509.random_serial_number())
                            .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
                            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
                            .add_extension(
                                x509.SubjectAlternativeName([x509.DNSName("localhost")]),
                                critical=False,
                            )
                            .sign(key_obj, hashes.SHA256())
                        )
                        with open(cert, "wb") as f:
                            f.write(cert_obj.public_bytes(serialization.Encoding.PEM))
                        with open(key, "wb") as f:
                            f.write(
                                key_obj.private_bytes(
                                    encoding=serialization.Encoding.PEM,
                                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                                    encryption_algorithm=serialization.NoEncryption(),
                                )
                            )
                    except Exception:
                        pass
                APP_STATE["CURRENT_BLOB"] = CURRENT_BLOB
                from app.services.transports.quic_server import run_quic_server

                asyncio.create_task(run_quic_server(host, port, cert, key, APP_STATE))
        except Exception:
            pass


def create_app() -> FastAPI:
    app = FastAPI(title="pfs-infinity", version="0.2.0")

    # CORS (dev: allow all)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Session middleware required by Authlib (used only for OAuth state)
    tls_on = os.environ.get("PFS_TLS", "1") in ("1","true","TRUE","True")
    session_secret = os.getenv("PFS_SESSION_SECRET", secrets.token_hex(32))
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        same_site="lax",
        https_only=tls_on,
        max_age=int(os.getenv("PFS_SESSION_TTL_SECONDS", "86400")),
    )

    # Static files
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    static_dir = os.path.abspath(static_dir)
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    # Serve web libraries (built TypeScript bundles) for browser import
    try:
        pfs_arith_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web", "pfs-arith", "dist"))
        if os.path.isdir(pfs_arith_dist):
            app.mount("/static/pfs-arith", StaticFiles(directory=pfs_arith_dist), name="pfs-arith")
    except Exception:
        pass

    # Security headers (TLS only)
    if os.environ.get("PFS_TLS", "1") in ("1", "true", "TRUE", "True"):
        @app.middleware("http")
        async def _hsts_header(request, call_next):
            resp = await call_next(request)
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            return resp

    # Routers
    from app.routes.health import router as health_router
    from app.core.routes.objects import router as objects_router
    from app.core.routes.transfers import router as transfers_router
    from app.core.routes.offsets import router as offsets_router
    try:
        from app.routes.gpu import router as gpu_router  # type: ignore
    except Exception:
        gpu_router = None  # type: ignore
    from app.routes.blob import router as blob_router
    from app.routes.debug import router as debug_router
    from app.routes.ingress import router as ingress_router
    from app.routes.iprog import router as iprog_router
    from app.routes.palette_build import router as palette_router
    from app.routes.compute import router as compute_router
    from app.routes.websockets import register_ws_handlers
    from app.routes.browse import router as browse_router
    from app.core.routes.browse_ws import register_browse_ws
    from app.routes.cluster import router as cluster_router
    from app.core.routes.cluster_ws import register_cluster_ws, start_background_tasks
    from app.routes.xfer import router as xfer_router
    from app.routes.fs import router as fs_router
    from app.routes.whoami import router as whoami_router
    try:
        from app.routes.discovery_ws import register_discovery_routes
    except Exception:
        register_discovery_routes = None  # type: ignore
    # Terminal routes now env-guarded
    enable_terminal = os.environ.get("PFS_ENABLE_TERMINAL", "0") in ("1", "true", "TRUE", "True")
    terminal_ui_style = os.environ.get("PFS_TERMINAL_UI", "simple").lower()
    if enable_terminal:
        try:
            from app.routes.terminal_ws import register_terminal_routes
        except Exception:
            register_terminal_routes = None  # type: ignore
    else:
        register_terminal_routes = None  # type: ignore
    from app.core.routes.transfer_ws import router as transfer_ws_router
    from app.routes.files import router as files_router
    # Auth from core
    from app.core.routes.auth import router as auth_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(objects_router)
    app.include_router(transfers_router)
    app.include_router(offsets_router)
    try:
        if gpu_router is not None:  # type: ignore
            app.include_router(gpu_router)  # type: ignore[arg-type]
    except Exception:
        pass
    app.include_router(blob_router)
    app.include_router(debug_router)
    app.include_router(ingress_router)
    app.include_router(iprog_router)
    app.include_router(palette_router)
    app.include_router(compute_router)
    app.include_router(browse_router)
    app.include_router(cluster_router)
    app.include_router(xfer_router)
    app.include_router(fs_router)
    app.include_router(whoami_router)
    app.include_router(files_router)
    register_ws_handlers(app)
    app.include_router(transfer_ws_router)
    try:
        register_browse_ws(app)
    except Exception:
        pass
    try:
        register_cluster_ws(app)
        @app.on_event("startup")
        async def start_cluster_background():
            start_background_tasks()
    except Exception:
        pass
    try:
        if register_discovery_routes is not None:  # type: ignore
            register_discovery_routes(app)  # type: ignore[arg-type]
    except Exception:
        pass
    # Conditionally register terminal
    if enable_terminal and register_terminal_routes:
        try:
            register_terminal_routes(app)  # type: ignore[arg-type]
            _debug("Terminal routes enabled")
        except Exception as e:
            _debug(f"Terminal route registration failed: {e}")

        # Provide a lightweight /terminal redirect to chosen UI style
        try:
            from fastapi.responses import RedirectResponse
            chosen = "/static/terminal-simple.html" if terminal_ui_style.startswith("simple") else "/static/terminal.html"
            @app.get("/terminal", include_in_schema=False)
            async def _terminal_redirect():  # noqa: N802
                return RedirectResponse(url=chosen)
            _debug(f"/terminal -> {chosen} (style={terminal_ui_style})")
        except Exception as e:  # pragma: no cover - non critical
            _debug(f"Terminal redirect setup failed: {e}")

    _startup_tasks(app)

    try:
        @app.get("/", include_in_schema=False)
        async def _home_index():  # noqa: N802
            # Serve the PFS-only transfer page
            static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
            return FileResponse(os.path.join(static_dir, "index.html"))
    except Exception:
        pass

    # Dynamic auth enable/disable
    app.state.auth_enabled = os.environ.get("PFS_AUTH_ENABLED", "1") in ("1","true","TRUE","True")
    from app.core.auth.sessions import get_user_from_request
    # Optional dev toggle: allow anonymous POST /objects while keeping other routes protected
    PUBLIC_UPLOAD = os.environ.get("PFS_PUBLIC_UPLOAD", "0") in ("1","true","TRUE","True")
    PROTECTED_PREFIXES = ["/objects", "/blob/fill", "/tenants"]
    PUBLIC_PATHS = {"/","/auth/login","/auth/callback","/auth/providers","/auth/whoami","/auth/logout","/health","/compression/stats","/blob/status","/auth/enable","/auth/disable"}
    @app.middleware("http")
    async def _auth_guard(request, call_next):  # type: ignore
        if not getattr(app.state, "auth_enabled", False):
            return await call_next(request)
        path = request.url.path
        if path.startswith("/static/") or path in PUBLIC_PATHS:
            return await call_next(request)
        if any(path.startswith(p) for p in PROTECTED_PREFIXES):
            # If public upload is enabled, allow anonymous POST /objects only
            if PUBLIC_UPLOAD and path == "/objects" and request.method.upper() == "POST":
                return await call_next(request)
            if not get_user_from_request(request):
                return JSONResponse({"detail":"authentication required"}, status_code=401)
        return await call_next(request)
    return app
