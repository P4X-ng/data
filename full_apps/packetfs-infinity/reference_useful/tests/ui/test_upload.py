#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


def run(url: str) -> int:
    # Default URL if not provided
    if not url:
        url = "https://127.0.0.1:8811/static/transfer-v2.html"

    # Some callers may pass "url=https://..."; normalize here
    if url.startswith("url="):
        url = url.split("=", 1)[1]
    print(f"[ui] testing URL: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # Cache-bust to avoid stale static
        bust = f"v={int(time.time())}"
        sep = '&' if ('?' in url) else '?'
        page.goto(f"{url}{sep}{bust}", wait_until="domcontentloaded")

        # Ensure UI is ready
        page.wait_for_selector("#fileInput", state="attached", timeout=10_000)
        page.wait_for_selector("#uploadBtn", timeout=10_000)

        # Create a temporary file to upload
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(os.urandom(64 * 1024))  # 64 KiB
            tf.flush()
            temp_path = tf.name
        print(f"[ui] created temp file: {temp_path} ({Path(temp_path).stat().st_size} bytes)")

        # Add file to queue (directly target hidden input)
        page.set_input_files("#fileInput", temp_path)

        # Start upload
        # Allow button enable to propagate
        page.wait_for_function("() => !document.getElementById('uploadBtn').disabled", timeout=5_000)

        # Wait for the network response while clicking upload
        def is_objects_post(resp):
            try:
                return resp.request.method == "POST" and resp.url.endswith("/objects")
            except Exception:
                return False

        with page.expect_response(is_objects_post, timeout=15_000) as resp_info:
            page.click("#uploadBtn")
        resp = resp_info.value
        status = resp.status
        body = resp.text()[:256]
        print(f"[ui] /objects response: status={status} body={body}")
        if status < 200 or status >= 300:
            print("[ui] FAIL: non-2xx status from /objects")
            return 2

        # Verify success toast appears
        page.wait_for_selector(".toast.toast-success", timeout=5_000)
        toast_text = page.inner_text(".toast.toast-success")
        print(f"[ui] success toast: {toast_text}")

        # Basic assertion on content
        if "Uploaded:" not in toast_text:
            print("[ui] WARN: success toast did not contain expected 'Uploaded:' prefix")

        print("[ui] PASS")
        # Cleanup
        context.close()
        browser.close()
    try:
        os.remove(temp_path)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://127.0.0.1:8811/static/transfer-v2.html"
    sys.exit(run(target_url))
