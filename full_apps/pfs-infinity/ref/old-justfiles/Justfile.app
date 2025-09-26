# App (podman) bring-up and dependencies sync for pfs-infinity
# Follows repo rules: Podman > Docker, central venv, categorized targets, help by default

# Imports
import "./justfile.vars"
import "../../Justfile.vars"


# Default help
app-default: app-help

app-help:
    @echo "pfs-infinity app (podman) targets:"
    @echo "  app-build           Build backend image (containers/backend/Containerfile)"
    @echo "  app-up              Run backend container (TLS by default)"
    @echo "  app-down            Stop and remove backend container"
    @echo "  app-logs            Tail backend logs"
    @echo "  app-rebuild         Clean rebuild image (no cache) then up"
    @echo "  deps-sync           Copy app dependencies into dependencies/"
    @echo "Env: WS_PORT={{WS_PORT}} QUIC_PORT={{QUIC_PORT}} BIND=0.0.0.0 PFS_WS_PSK=<psk> PFS_META_DIR=var/pfsmeta"

# Image/tag names
APP_IMAGE := "packetfs/pfs-infinity-backend:latest"
APP_NAME  := "pfs-infinity-backend"

# Build backend image from containers/backend/Containerfile (context = repo root)
app-build:
    @echo "[*] Building {{APP_IMAGE}} (Podman)"
    podman build -t {{APP_IMAGE}} \
      -f containers/backend/Containerfile \
      ../..
    @echo "[+] Built {{APP_IMAGE}}"

# Clean rebuild
app-rebuild:
    @echo "[*] Clean building {{APP_IMAGE}} (no cache)"
    podman build --no-cache -t {{APP_IMAGE}} \
      -f containers/backend/Containerfile \
      ../..
    just app-up

# Run backend container (TLS by default)
# Mount meta dir for BlobFS persistence and expose 8811
app-up psk="" meta_dir="var/pfsmeta" bind="0.0.0.0" port="":
    @echo "[*] Starting {{APP_NAME}} on :${PORT:-{{WS_PORT}}} (TLS=on)"
    mkdir -p "{{meta_dir}}"
    # Stop existing
    podman rm -f {{APP_NAME}} 2>/dev/null || true
    # Resolve params with defaults
    PORT="{{port}}"; PORT=${PORT:-{{WS_PORT}}}
    BIND_ADDR="{{bind}}"
    # Run
    podman run -d --name {{APP_NAME}} \
      -e WS_PORT="$PORT" \
      -e BIND="$BIND_ADDR" \
      -e PFS_WS_PSK="{{psk}}" \
      -e PFS_META_DIR=/app/meta \
      -p "$PORT":"$PORT" \
      -v $(pwd)/{{meta_dir}}:/app/meta:Z \
      {{APP_IMAGE}}
    @echo "[+] Up: https://127.0.0.1:${PORT}/static/transfer-v2.html"

app-down:
    @echo "[*] Stopping {{APP_NAME}}"
    podman rm -f {{APP_NAME}} 2>/dev/null || true
    @echo "[+] Stopped"

app-logs lines="200":
    @echo "[*] Tail logs (last {{lines}})"
    podman logs --tail {{lines}} -f {{APP_NAME}}

# Dependencies sync — copies key runtime helper scripts and container defs into dependencies/
# This is a convenience mirror; source of truth remains in-tree.
deps-sync dest="dependencies":
    @echo "[*] Syncing dependencies into {{dest}}/"
    mkdir -p "{{dest}}/scripts" "{{dest}}/containers/backend"
    # Copy CLI helpers (pfs*, pfcp*) from this app
    shopt -s nullglob; \
    for f in scripts/pfs* scripts/pfcp*; do \
      [ -f "$f" ] && install -m 0755 -D "$f" "{{dest}}/scripts/$(basename "$f")" || true; \
    done
    # Copy selected support scripts used at runtime
    for f in scripts/monitor/pfs_pktop.py scripts/pfsfs_mount_host.sh; do \
      [ -f "$f" ] && install -m 0644 -D "$f" "{{dest}}/$f" || true; \
    done
    # Container definitions for backend
    install -m 0644 -D containers/backend/Containerfile "{{dest}}/containers/backend/Containerfile"
    install -m 0644 -D containers/backend/requirements.txt "{{dest}}/containers/backend/requirements.txt"
    install -m 0755 -D containers/backend/start-backend.sh "{{dest}}/containers/backend/start-backend.sh"
    @echo "[+] Dependencies synced to {{dest}}/"
