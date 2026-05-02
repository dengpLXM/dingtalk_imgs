"""Render HTML to image using Playwright headless browser."""
import asyncio
import base64
import hashlib
import os
import sys
from pathlib import Path

_browser = None
_playwright = None
_browser_lock = asyncio.Lock()
# Serialize screenshots: concurrent new_page/screenshot on the singleton browser
# produces blank JPEGs or "browser has been closed" when many cron tasks fire together.
_render_lock = asyncio.Lock()


def _headless_shell_folder_priority() -> list[str]:
    """Subdir names under chromium_headless_shell-* — prefer OS/arch matching Python process."""
    import platform

    machine = platform.machine().lower()
    if sys.platform == "darwin":
        if machine == "arm64":
            return [
                "chrome-headless-shell-mac-arm64",
                "chrome-headless-shell-mac-x64",
            ]
        return [
            "chrome-headless-shell-mac-x64",
            "chrome-headless-shell-mac-arm64",
        ]
    if sys.platform.startswith("linux"):
        if machine in ("aarch64", "arm64"):
            return [
                "chrome-headless-shell-linux-arm64",
                "chrome-headless-shell-linux64",
            ]
        return [
            "chrome-headless-shell-linux64",
            "chrome-headless-shell-linux-arm64",
        ]
    if sys.platform == "win32":
        return ["chrome-headless-shell-win64", "chrome-headless-shell-win32"]
    return []


def _headless_shell_binary_name() -> str:
    return "chrome-headless-shell.exe" if sys.platform == "win32" else "chrome-headless-shell"


def find_installed_headless_shell_executable() -> str | None:
    """Locate bundled headless shell binary; avoids Playwright picking wrong CPU arch on Apple Silicon/Rosetta mixes."""
    explicit = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "").strip()
    if explicit and os.path.isfile(explicit):
        return explicit

    base = (os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "").strip()
    if not base:
        if sys.platform == "darwin":
            base = str(Path.home() / "Library/Caches/ms-playwright")
        else:
            base = str(Path.home() / ".cache" / "ms-playwright")
    root = Path(base)
    if not root.is_dir():
        return None

    shells = sorted(root.glob("chromium_headless_shell-*"), key=lambda p: p.name, reverse=True)
    bin_name = _headless_shell_binary_name()
    for folder_name in _headless_shell_folder_priority():
        for shell_root in shells:
            candidate = shell_root / folder_name / bin_name
            if candidate.is_file():
                return str(candidate)
    for shell_root in shells:
        for sub in sorted(shell_root.glob("chrome-headless-shell-*")):
            candidate = sub / bin_name
            if candidate.is_file():
                return str(candidate)
    return None


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


async def _close_browser_unlocked() -> None:
    """Close browser and stop Playwright driver. Caller must hold _browser_lock."""
    global _browser, _playwright
    if _browser is not None:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright is not None:
        try:
            await _playwright.stop()
        except Exception:
            pass
        _playwright = None


async def _get_browser():
    """Singleton browser; keeps Playwright alive (dropping the driver closes the browser)."""
    global _browser, _playwright
    if _browser is not None and _browser.is_connected:
        return _browser

    async with _browser_lock:
        if _browser is not None and _browser.is_connected:
            return _browser
        await _close_browser_unlocked()
        _ensure_browsers_path()
        from playwright.async_api import async_playwright

        _playwright = await async_playwright().start()
        exe = find_installed_headless_shell_executable()
        opts: dict = {"headless": True}
        if exe:
            opts["executable_path"] = exe
        _browser = await _playwright.chromium.launch(**opts)
    return _browser


async def render_html_to_image(html_content: str, width: int = 900) -> tuple[bytes, str, str]:
    """Render HTML to JPEG image. Returns (jpeg_bytes, base64_str, md5_hex)."""
    async with _render_lock:
        browser = await _get_browser()
        page = await browser.new_page(viewport={"width": width, "height": 1200})
        try:
            await page.set_content(html_content, wait_until="networkidle")
            try:
                await page.evaluate("document.fonts.ready")
            except Exception:
                pass
            # Wait two frames so layout/paint completes before capture (reduces blank screenshots).
            await page.evaluate(
                """() => new Promise((resolve) => {
                  requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
                })"""
            )
            png_bytes = await page.screenshot(full_page=True, type="jpeg", quality=92)
        finally:
            await page.close()

    img_b64 = base64.b64encode(png_bytes).decode()
    img_md5 = hashlib.md5(png_bytes).hexdigest()
    return png_bytes, img_b64, img_md5


async def shutdown():
    async with _browser_lock:
        await _close_browser_unlocked()
