"""Render HTML to image using Playwright headless browser."""
import asyncio
import base64
import hashlib
import logging
import os
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

_browser = None
_playwright = None
_browser_lock = asyncio.Lock()
# Serialize screenshots: concurrent new_page/screenshot on the singleton browser
# produces blank JPEGs or "browser has been closed" when many cron tasks fire together.
_render_lock = asyncio.Lock()


def _playwright_cache_root() -> Path | None:
    base = (os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "").strip()
    if not base:
        if sys.platform == "darwin":
            base = str(Path.home() / "Library/Caches/ms-playwright")
        else:
            base = str(Path.home() / ".cache" / "ms-playwright")
    root = Path(base)
    return root if root.is_dir() else None


def _full_chromium_folder_priority() -> list[str]:
    """Subdirs under chromium-* (full browser), OS/arch ordered."""
    import platform

    machine = platform.machine().lower()
    if sys.platform == "darwin":
        if machine == "arm64":
            return ["chrome-mac-arm64", "chrome-mac-x64", "chrome-mac"]
        return ["chrome-mac-x64", "chrome-mac-arm64", "chrome-mac"]
    if sys.platform.startswith("linux"):
        if machine in ("aarch64", "arm64"):
            return ["chrome-linux-arm64", "chrome-linux64", "chrome-linux"]
        return ["chrome-linux64", "chrome-linux-arm64", "chrome-linux"]
    if sys.platform == "win32":
        return ["chrome-win64", "chrome-win32"]
    return []


def find_full_chromium_executable() -> str | None:
    """Full Chromium renders templates reliably; headless-shell often yields blank JPEGs for CSS/gradient/canvas."""
    if os.environ.get("PLAYWRIGHT_USE_HEADLESS_SHELL", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return None
    root = _playwright_cache_root()
    if root is None:
        return None
    builds = sorted(
        (
            p
            for p in root.iterdir()
            if p.is_dir()
            and p.name.startswith("chromium-")
            and "headless_shell" not in p.name
        ),
        key=lambda p: p.name,
        reverse=True,
    )
    for build in builds:
        for folder in _full_chromium_folder_priority():
            if folder.startswith("chrome-mac"):
                mac = (
                    build
                    / folder
                    / "Chromium.app"
                    / "Contents"
                    / "MacOS"
                    / "Chromium"
                )
                if mac.is_file():
                    return str(mac)
            exe_name = "chrome.exe" if sys.platform == "win32" else "chrome"
            cand = build / folder / exe_name
            if cand.is_file():
                return str(cand)
    return None


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
    """Locate headless-shell fallback when full Chromium is not installed."""
    root = _playwright_cache_root()
    if root is None:
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


def _launch_arg_merges(exe_kind: str, exe_path: str | None) -> list[str]:
    """Extra Chromium flags. headless_shell on darwin often crashes (SIGSEGV); GPU off can help."""
    merged: list[str] = []
    if sys.platform == "darwin" and (
        exe_kind == "headless-shell"
        or (exe_path and "headless_shell" in exe_path.replace("\\", "/"))
        or (exe_path and "headless-shell" in exe_path.replace("\\", "/"))
    ):
        merged.extend(["--disable-gpu", "--disable-software-rasterizer"])
    return merged


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
        explicit = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "").strip()
        full = (
            find_full_chromium_executable()
            if not (explicit and os.path.isfile(explicit))
            else None
        )
        shell = find_installed_headless_shell_executable()

        linux_shm = ["--disable-dev-shm-usage"] if sys.platform.startswith("linux") else []

        strategies: list[tuple[str, dict]] = []
        if explicit and os.path.isfile(explicit):
            extra = _launch_arg_merges("explicit", explicit) + linux_shm
            strategies.append(
                (
                    "explicit",
                    {"headless": True, "executable_path": explicit, **({"args": extra} if extra else {})},
                )
            )
        if full:
            extra = _launch_arg_merges("full", full) + linux_shm
            strategies.append(
                ("full", {"headless": True, "executable_path": full, **({"args": extra} if extra else {})})
            )
        # headless_shell SIGSEGV on some macOS ARM builds; prefer full Chromium install or system Chrome first.
        if sys.platform == "darwin" and os.environ.get(
            "PLAYWRIGHT_SKIP_CHANNEL_CHROME", ""
        ).strip().lower() not in ("1", "true", "yes"):
            strategies.append(
                ("channel-chrome", {"headless": True, "channel": "chrome", **({"args": linux_shm} if linux_shm else {})}),
            )
        if shell:
            extra = _launch_arg_merges("headless-shell", shell) + linux_shm
            strategies.append(
                (
                    "headless-shell",
                    {"headless": True, "executable_path": shell, **({"args": extra} if extra else {})},
                )
            )
        strategies.append(
            (
                "bundled-default",
                {"headless": True, **({"args": linux_shm} if linux_shm else {})},
            )
        )

        last_err: Exception | None = None
        for exe_kind, opts in strategies:
            try:
                if exe_kind == "channel-chrome":
                    _log.info("Playwright Chromium [%s]", exe_kind)
                elif opts.get("executable_path"):
                    _log.info("Playwright Chromium [%s]: %s", exe_kind, opts["executable_path"])
                elif exe_kind == "bundled-default":
                    _log.warning(
                        "Playwright Chromium [bundled-default]: no cached executable; "
                        "install with: playwright install chromium (avoid --only-shell on macOS)."
                    )
                _browser = await _playwright.chromium.launch(**opts)
                break
            except Exception as e:
                last_err = e
                _log.warning("Playwright launch failed [%s]: %s", exe_kind, e)
        else:
            if last_err:
                raise last_err
            raise RuntimeError("Playwright chromium.launch: no strategy succeeded")
    return _browser


_SCREENSHOT_HEIGHT_JS = """
() => {
  const html = document.documentElement;
  const body = document.body;
  if (!body) return { scrollH: 1200, tightBottom: 1200 };
  const viewportH = html.clientHeight;
  const rawScrollH = Math.max(
    html.scrollHeight,
    body.scrollHeight,
    body.offsetHeight
  );
  // Use content-based scroll height: exclude viewport inflation when content
  // is shorter than the viewport (scrollHeight == clientHeight means no overflow).
  const scrollH = html.scrollHeight > viewportH
    ? rawScrollH
    : Math.max(body.scrollHeight, body.offsetHeight, 1);
  let bottom = 0;
  for (const el of body.querySelectorAll("*")) {
    let cs;
    try {
      cs = getComputedStyle(el);
    } catch (e) {
      continue;
    }
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    const op = parseFloat(cs.opacity);
    if (op === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 0.5 || r.height < 0.5) continue;
    const b = r.bottom + window.pageYOffset;
    if (b > bottom) bottom = b;
  }
  const rectBottom = body.getBoundingClientRect().bottom + window.pageYOffset;
  const tightBottom = Math.max(Math.ceil(bottom), Math.ceil(rectBottom));
  return { scrollH, tightBottom };
}
"""


async def render_html_to_image(html_content: str, width: int = 900) -> tuple[bytes, str, str]:
    """Render HTML to JPEG image. Returns (jpeg_bytes, base64_str, md5_hex)."""
    async with _render_lock:
        browser = await _get_browser()
        page = await browser.new_page(viewport={"width": width, "height": 1200})
        try:
            await page.emulate_media(media="screen")
            await page.set_content(html_content, wait_until="load", timeout=90_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=25_000)
            except Exception:
                pass
            try:
                await page.evaluate("document.fonts.ready")
            except Exception:
                pass
            await page.evaluate(
                """() => new Promise((resolve) => {
                  requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
                })"""
            )
            delay_ms = int(os.getenv("PLAYWRIGHT_RENDER_DELAY_MS", "800"))
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000)
            try:
                await page.evaluate(
                    """() => {
                      window.scrollTo(0, document.body.scrollHeight);
                      window.scrollTo(0, 0);
                    }"""
                )
            except Exception:
                pass
            await asyncio.sleep(0.05)
            full_page = os.getenv(
                "PLAYWRIGHT_SCREENSHOT_FULL_PAGE", ""
            ).strip().lower() in ("1", "true", "yes")
            quality = int(os.getenv("PLAYWRIGHT_JPEG_QUALITY", "92"))
            if quality < 1:
                quality = 92
            if full_page:
                png_bytes = await page.screenshot(
                    full_page=True, type="jpeg", quality=quality
                )
            else:
                dims = await page.evaluate(_SCREENSHOT_HEIGHT_JS)
                sh = max(int(dims.get("scrollH", 1)), 1)
                tb = int(dims.get("tightBottom", sh))
                margin = int(os.getenv("PLAYWRIGHT_CROP_MARGIN_PX", "8"))
                tight = os.getenv("PLAYWRIGHT_TIGHT_CROP", "1").strip().lower() not in (
                    "0",
                    "false",
                    "no",
                )
                if tb <= 0:
                    h = sh
                elif tight:
                    h = min(sh, tb + margin)
                    if h < sh * 0.35:
                        h = sh
                else:
                    h = sh
                max_h = int(os.getenv("PLAYWRIGHT_MAX_IMAGE_HEIGHT", "0") or "0")
                if max_h > 0:
                    h = min(h, max_h)
                h = max(h, 1)
                await page.set_viewport_size({"width": width, "height": h})
                png_bytes = await page.screenshot(
                    full_page=False, type="jpeg", quality=quality
                )
        finally:
            await page.close()

    img_b64 = base64.b64encode(png_bytes).decode()
    img_md5 = hashlib.md5(png_bytes).hexdigest()
    return png_bytes, img_b64, img_md5


async def shutdown():
    async with _browser_lock:
        await _close_browser_unlocked()
