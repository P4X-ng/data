from __future__ import annotations

import asyncio
import os
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.state import APP_STATE, CURRENT_BLOB


def _maybe_mount_spider(app: FastAPI, enable_spider: bool) -> None:
    if not enable_spider:
        return
    try:
        from app.spider.coordinator import router as spider_router  # type: ignore
    except Exception:
        spider_router = None  # type: ignore
    if spider_router is None:
        return
    app.include_router(spider_router)
    try:
        from app.spider import coordinator as _spider_coord  # type: ignore
        if hasattr(_spider_coord, "attach_to_app"):
            _spider_coord.attach_to_app(app)  # type: ignore[attr-defined]
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
            size = int(os.environ.get("PFS_BLOB_SIZE_BYTES", str(1 << 30)))  # 1 GiB default
            seed = int(os.environ.get("PFS_BLOB_SEED", "1337"))
            from packetfs.filesystem.virtual_blob import VirtualBlob  # type: ignore

            vb = VirtualBlob(name=name, size_bytes=size, seed=seed)
            vb.create_or_attach(create=True)
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
        except Exception:
            # Silent failure acceptable; users can call /blob/setup manually
            pass

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


def create_app(enable_spider: Optional[bool] = None) -> FastAPI:
    app = FastAPI(title="pfs-infinity", version="0.2.0")

    # CORS (dev: allow all)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    static_dir = os.path.abspath(static_dir)
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Security headers (TLS only)
    if os.environ.get("PFS_TLS", "1") in ("1", "true", "TRUE", "True"):
        @app.middleware("http")
        async def _hsts_header(request, call_next):
            resp = await call_next(request)
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            return resp

    # Routers
    from app.routes.health import router as health_router
    from app.routes.objects import router as objects_router
    from app.routes.transfers import router as transfers_router
    from app.routes.gpu import router as gpu_router
    from app.routes.blob import router as blob_router
    from app.routes.debug import router as debug_router
    from app.routes.ingress import router as ingress_router
    from app.routes.compute import router as compute_router
    from app.routes.websockets import register_ws_handlers
    from app.routes.browse import router as browse_router
    from app.routes.browse_ws import register_browse_ws
    from app.routes.cluster import router as cluster_router
    from app.routes.cluster_ws import register_cluster_ws, start_background_tasks
    from app.routes.xfer import router as xfer_router
    from app.routes.fs import router as fs_router
    from app.routes.whoami import router as whoami_router
    from app.routes.discovery_ws import register_discovery_routes
    from app.routes.terminal_ws import register_terminal_routes
    from app.routes.transfer_ws import router as transfer_ws_router

    app.include_router(health_router)
    app.include_router(objects_router)
    app.include_router(transfers_router)
    app.include_router(gpu_router)
    app.include_router(blob_router)
    app.include_router(debug_router)
    app.include_router(ingress_router)
    app.include_router(compute_router)
    app.include_router(browse_router)
    app.include_router(cluster_router)
    app.include_router(xfer_router)
    app.include_router(fs_router)
    app.include_router(whoami_router)
    register_ws_handlers(app)
    app.include_router(transfer_ws_router)
    # Register persistent remote browse WS
    try:
        register_browse_ws(app)
    except Exception:
        pass
    # Register cluster WebSocket handler
    try:
        register_cluster_ws(app)
        # Start background tasks on startup
        @app.on_event("startup")
        async def start_cluster_background():
            start_background_tasks()
    except Exception:
        pass
    
    # Register discovery WebSocket handler
    try:
        register_discovery_routes(app)
    except Exception:
        pass
    
    # Register terminal WebSocket handler
    try:
        register_terminal_routes(app)
    except Exception:
        pass

    # Optional spider coordinator (disabled by default)
    if enable_spider is None:
        # Enable only if explicitly set true
        enable_spider = os.environ.get("PFS_ENABLE_SPIDER", "0") in ("1", "true", "TRUE", "True")
    _maybe_mount_spider(app, bool(enable_spider))

    # Startup tasks
    _startup_tasks(app)

    # Home redirect
    try:
        from fastapi.responses import RedirectResponse
        @app.get("/")
        async def _home_redirect():
            return RedirectResponse(url="/static/transfer-v2.html")
    except Exception:
        pass

    return app
