"""CI smoke test: serve ./_site, open it in Chromium, wait for a real review to render.

    python site/smoke_check.py
Fails if the in-browser app does not show a verdict within the timeout or shows a Python exception.
"""
import asyncio
import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.async_api import async_playwright

SITE = Path(__file__).resolve().parents[1] / "_site"
PORT = 8765
TIMEOUT_MS = 300_000


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler).serve_forever()


async def main() -> int:
    threading.Thread(target=serve, daemon=True).start()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1400, "height": 1800})
        logs = []
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        await page.goto(f"http://127.0.0.1:{PORT}/")
        try:
            await page.get_by_text("Do not sign yet").first.wait_for(timeout=TIMEOUT_MS)
        except Exception:
            await page.screenshot(path="smoke_failure.png", full_page=True)
            print("Verdict never rendered. Last console lines:\n" + "\n".join(logs[-40:]))
            return 1
        await page.wait_for_timeout(3000)
        exc = await page.locator('[data-testid="stException"]').count()
        await page.screenshot(path="smoke.png", full_page=True)
        body = await page.inner_text("body")
        await browser.close()
    if exc:
        print("Python exception shown in the app:\n" + body[:3000])
        return 1
    if "Al Noor" not in body:
        print("Expected the Al Noor conflict for the default (Gulf Crown) draft.\n" + body[:3000])
        return 1
    print("Smoke test passed: in-browser app rendered the Gulf Crown review with the Al Noor conflict.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
