"""Render HTML to image using Playwright headless browser."""
import os
import io
import hashlib
import base64

_browser = None


def _ensure_browsers_path():
    """Read PLAYWRIGHT_BROWSERS_PATH from .env directly, overriding sandbox defaults."""
    from pathlib import Path
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        if line.startswith("PLAYWRIGHT_BROWSERS_PATH="):
            path = line.split("=", 1)[1].strip()
            if os.path.isdir(path):
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = path
            return


async def _get_browser():
    global _browser
    if _browser is None:
        _ensure_browsers_path()
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        _browser = await pw.chromium.launch(headless=True)
    return _browser


async def render_html_to_image(html_content: str, width: int = 900) -> tuple[bytes, str, str]:
    """Render HTML to JPEG image. Returns (jpeg_bytes, base64_str, md5_hex)."""
    browser = await _get_browser()
    page = await browser.new_page(viewport={"width": width, "height": 100})
    await page.set_content(html_content, wait_until="networkidle")
    png_bytes = await page.screenshot(full_page=True, type="jpeg", quality=92)
    await page.close()

    img_b64 = base64.b64encode(png_bytes).decode()
    img_md5 = hashlib.md5(png_bytes).hexdigest()
    return png_bytes, img_b64, img_md5


async def shutdown():
    global _browser
    if _browser:
        await _browser.close()
        _browser = None
