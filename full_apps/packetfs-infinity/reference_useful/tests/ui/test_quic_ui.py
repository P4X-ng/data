import os, time, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_quic_transfer_ui():
    # Prepare a small file
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(b"hello packetfs quic")
    tmp.flush(); tmp.close()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8811")
        # Select Mode: quic
        page.select_option("#mode", "quic")
        # Set receiver host and ports (defaults ok)
        page.fill("#receiver", "127.0.0.1")
        page.fill("#wsport", "8811")
        page.fill("#quicport", "8853")
        # Attach file via Uppy Dashboard input
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(tmp.name)
        # Click start
        page.click('#start')
        # Wait and read log for status
        for _ in range(15):
            log = page.inner_text('#log')
            if 'status' in log and ('success' in log or 'failed' in log):
                break
            time.sleep(1)
        browser.close()
        Path(tmp.name).unlink(missing_ok=True)