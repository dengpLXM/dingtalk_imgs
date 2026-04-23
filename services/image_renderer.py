import re
import io
import math
import random
import hashlib
import base64
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

W, H = 900, 660
BG_TOP = (150, 8, 8)
BG_BOT = (40, 2, 2)
GOLD = (255, 215, 0)
GOLD_DIM = (180, 140, 0)
WHITE = (255, 255, 255)
WHITE_DIM = (200, 200, 200)
CARD_BG = (90, 6, 6)
CARD_ACCENT = (220, 30, 0)
FONT_PATH = "/System/Library/Fonts/PingFang.ttc"
FONT_BOLD_IDX = 4   # PingFang SC Semibold
FONT_REG_IDX = 0    # PingFang SC Regular


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size, index=FONT_BOLD_IDX if bold else FONT_REG_IDX)
    except Exception:
        try:
            return ImageFont.truetype(FONT_PATH, size, index=0)
        except Exception:
            return ImageFont.load_default()


def _gradient_bg(draw: ImageDraw.ImageDraw) -> None:
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _draw_noise_stars(draw: ImageDraw.ImageDraw) -> None:
    rng = random.Random(7)
    for _ in range(40):
        x = rng.randint(10, W - 10)
        y = rng.randint(80, H - 70)
        r = rng.randint(1, 3)
        br = rng.randint(100, 200)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(br, int(br * 0.8), 0))


def _draw_flame_strip(draw: ImageDraw.ImageDraw, base_y: int = 72) -> None:
    for x in range(0, W, 2):
        fh = int(18 + 14 * math.sin(x * 0.045) + 8 * math.sin(x * 0.12))
        for dy in range(fh):
            t = dy / fh
            r = 255
            g = int(220 * (1 - t) ** 1.5)
            b = 0
            draw.point((x, base_y - dy), fill=(r, g, b))
            if x + 1 < W:
                draw.point((x + 1, base_y - dy), fill=(r, g, b))


def _draw_gold_frame(draw: ImageDraw.ImageDraw) -> None:
    for i in range(6):
        alpha = 1.0 - i * 0.15
        c = tuple(int(v * alpha) for v in GOLD)
        draw.rectangle([i, i, W - 1 - i, H - 1 - i], outline=c)


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _text_h(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int,
                   font: ImageFont.FreeTypeFont, color: tuple,
                   shadow_color: tuple | None = None) -> int:
    tw = _text_w(draw, text, font)
    tx = (W - tw) // 2
    if shadow_color:
        draw.text((tx + 2, y + 2), text, font=font, fill=shadow_color)
    draw.text((tx, y), text, font=font, fill=color)
    return _text_h(draw, text, font)


def _draw_divider(draw: ImageDraw.ImageDraw, y: int, margin: int = 55) -> None:
    mid = W // 2
    draw.line([(margin, y), (mid - 30, y)], fill=GOLD_DIM, width=1)
    draw.ellipse([mid - 5, y - 4, mid + 5, y + 4], fill=GOLD_DIM)
    draw.line([(mid + 30, y), (W - margin, y)], fill=GOLD_DIM, width=1)


def _draw_bottom_strip(draw: ImageDraw.ImageDraw, text: str, strip_y: int) -> None:
    for y in range(strip_y, H):
        t = (y - strip_y) / (H - strip_y)
        r = int(160 * (1 - t) + 80 * t)
        g = int(60 * (1 - t))
        b = 0
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    font = _font(23, bold=True)
    _draw_centered(draw, text, strip_y + 10, font, (255, 240, 180),
                   shadow_color=(100, 50, 0))


def _strip_md(text: str) -> str:
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'^#+\s*', '', text)
    text = re.sub(r'`', '', text)
    return text.strip()


def parse_content(text: str) -> dict:
    title = ""
    metrics: list[tuple[str, str]] = []
    footer_lines: list[str] = []

    for raw in text.strip().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#'):
            candidate = _strip_md(line)
            if candidate and not title:
                title = candidate
            continue
        m = re.match(r'\*{0,2}(.+?)\*{0,2}\s*[：:]\s*(.+)', line)
        if m:
            metrics.append((_strip_md(m.group(1)), _strip_md(m.group(2))))
            continue
        footer_lines.append(_strip_md(line))

    return {
        "title": title or "销售战报",
        "metrics": metrics[:6],
        "footer_lines": footer_lines[:5],
    }


def render_sales_image(rendered_text: str) -> tuple[bytes, str, str]:
    """Generate sales report image. Returns (jpeg_bytes, base64_str, md5_hex)."""
    data = parse_content(rendered_text)
    title = data["title"]
    metrics = data["metrics"]
    footer_lines = data["footer_lines"]

    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _gradient_bg(draw)
    _draw_noise_stars(draw)
    _draw_flame_strip(draw, base_y=68)
    _draw_gold_frame(draw)

    # ── title ─────────────────────────────────────────────────
    y = 82
    f_title = _font(52, bold=True)
    th = _draw_centered(draw, title, y, f_title, GOLD, shadow_color=(80, 5, 5))
    y += th + 8

    # date
    f_date = _font(22)
    date_str = datetime.now().strftime("%Y年%m月%d日  %H:%M 播报")
    _draw_centered(draw, date_str, y, f_date, WHITE_DIM)
    y += 30

    _draw_divider(draw, y)
    y += 20

    # ── metric cards ──────────────────────────────────────────
    if metrics:
        cols = min(len(metrics), 3)
        pad = 45
        gap = 14
        card_w = (W - 2 * pad - (cols - 1) * gap) // cols
        card_h = 100
        f_value = _font(34, bold=True)
        f_label = _font(19)

        rows = math.ceil(len(metrics) / cols)
        for i, (label, value) in enumerate(metrics):
            row_i = i // cols
            col_i = i % cols
            cx = pad + col_i * (card_w + gap)
            cy = y + row_i * (card_h + gap)

            # card body
            draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h],
                                    radius=10, fill=CARD_BG)
            # top accent bar
            draw.rounded_rectangle([cx, cy, cx + card_w, cy + 5],
                                    radius=3, fill=CARD_ACCENT)

            # value
            vw = _text_w(draw, value, f_value)
            vx = cx + (card_w - vw) // 2
            draw.text((vx + 1, cy + 16 + 1), value, font=f_value, fill=(60, 0, 0))
            draw.text((vx, cy + 16), value, font=f_value, fill=GOLD)

            # label
            lw = _text_w(draw, label, f_label)
            lx = cx + (card_w - lw) // 2
            draw.text((lx, cy + card_h - 30), label, font=f_label, fill=WHITE_DIM)

        y += rows * (card_h + gap) + 6

    _draw_divider(draw, y, margin=80)
    y += 18

    # ── footer / highlight lines ───────────────────────────────
    f_body = _font(26, bold=True)
    f_body_reg = _font(24)
    for idx, line in enumerate(footer_lines):
        fnt = f_body if idx == 0 else f_body_reg
        color = GOLD if idx == 0 else WHITE
        shadow = (80, 50, 0) if idx == 0 else None
        lh = _draw_centered(draw, line, y, fnt, color, shadow_color=shadow)
        y += lh + 10
        if y > H - 90:
            break

    # ── bottom strip ──────────────────────────────────────────
    bottom_y = H - 52
    slogans = ["冲冲冲！超越自我，创造辉煌！", "加油！今天的努力成就明天的卓越！",
               "干就完了！业绩才是硬道理！"]
    slogan = slogans[datetime.now().day % len(slogans)]
    _draw_bottom_strip(draw, slogan, bottom_y)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    img_bytes = buf.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    img_md5 = hashlib.md5(img_bytes).hexdigest()
    return img_bytes, img_b64, img_md5


# ── Compact flat image (fits DingTalk 20KB base64 limit) ──────────────────

_CW, _CH = 560, 420
_BG   = (100, 5, 5)
_GOLD = (255, 215, 0)
_GDIM = (180, 140, 0)
_WHITE = (255, 255, 255)
_WDIM  = (200, 200, 200)
_CBG   = (68, 4, 4)
_CACC  = (210, 25, 0)


def _cf(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size, index=FONT_BOLD_IDX if bold else FONT_REG_IDX)
    except Exception:
        return ImageFont.load_default()


def _cw(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _ch_px(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _cc(draw: ImageDraw.ImageDraw, text: str, y: int,
        font: ImageFont.FreeTypeFont, color: tuple) -> int:
    tw = _cw(draw, text, font)
    draw.text((_CW // 2 - tw // 2, y), text, font=font, fill=color)
    return _ch_px(draw, text, font)


def render_compact_image(rendered_text: str) -> tuple[bytes, str, str]:
    """Flat compact image ≤ 20KB base64 for direct DingTalk image message."""
    data = parse_content(rendered_text)
    title = data["title"]
    metrics = data["metrics"]
    footer_lines = data["footer_lines"]

    img = Image.new("RGB", (_CW, _CH), _BG)
    draw = ImageDraw.Draw(img)

    # gold bars top/bottom
    draw.rectangle([0, 0, _CW, 7], fill=_GDIM)
    draw.rectangle([0, _CH - 7, _CW, _CH], fill=_GDIM)

    # title
    y = 14
    th = _cc(draw, title, y, _cf(36, bold=True), _GOLD)
    y += th + 6

    # date
    date_str = datetime.now().strftime("%Y年%m月%d日  %H:%M")
    th = _cc(draw, date_str, y, _cf(14), _WDIM)
    y += th + 6

    # divider
    draw.line([25, y, _CW - 25, y], fill=_GDIM, width=1)
    y += 8

    # metric cards (up to 3)
    top_metrics = metrics[:3]
    if top_metrics:
        cols = len(top_metrics)
        pad, gap = 22, 10
        cw = (_CW - 2 * pad - (cols - 1) * gap) // cols
        ch = 82
        fl = _cf(14)
        for i, (label, value) in enumerate(top_metrics):
            cx = pad + i * (cw + gap)
            cy = y
            draw.rectangle([cx, cy, cx + cw, cy + ch], fill=_CBG)
            draw.rectangle([cx, cy, cx + cw, cy + 4], fill=_CACC)
            # auto-size value to fit card width
            for vsize in (24, 20, 17, 14):
                fv = _cf(vsize, bold=True)
                if _cw(draw, value, fv) <= cw - 8:
                    break
            vw = _cw(draw, value, fv)
            draw.text((cx + (cw - vw) // 2, cy + 12), value, font=fv, fill=_GOLD)
            lw = _cw(draw, label, fl)
            draw.text((cx + (cw - lw) // 2, cy + ch - 20), label, font=fl, fill=_WDIM)
        y += ch + 8

    # extra metrics as text (metrics 4-6)
    if len(metrics) > 3:
        fe = _cf(15)
        for label, value in metrics[3:6]:
            line = f"{label}：{value}"
            lw = _cw(draw, line, fe)
            draw.text((_CW // 2 - lw // 2, y), line, font=fe, fill=_WDIM)
            y += _ch_px(draw, line, fe) + 4

    # divider
    draw.line([25, y, _CW - 25, y], fill=(120, 10, 10), width=1)
    y += 8

    # footer lines (rankings/motivation)
    f1, f2 = _cf(17, bold=True), _cf(15)
    for idx, line in enumerate(footer_lines[:5]):
        fnt = f1 if idx == 0 else f2
        color = (255, 240, 180) if idx == 0 else _WDIM
        lh = _cc(draw, line, y, fnt, color)
        y += lh + 5
        if y > _CH - 30:
            break

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=30, optimize=True)
    img_bytes = buf.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    img_md5 = hashlib.md5(img_bytes).hexdigest()
    return img_bytes, img_b64, img_md5
