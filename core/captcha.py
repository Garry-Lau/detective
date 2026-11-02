"""图形验证码 + 每设备查证次数限流。

- 设备标识由服务端下发 Cookie（wb_device），换浏览器/设备自动重新计数。
- 每设备查证满 CAPTCHA_THRESHOLD 次后，必须通过图形验证码才能继续，通过即重置计数。
- 验证码答案只存内存（10 分钟有效），不落库。
"""
from __future__ import annotations

import io
import random
import secrets
import threading
import time

from . import config

_lock = threading.Lock()
_store: dict[str, tuple[str, float]] = {}          # captcha_id -> (答案小写, 过期时间)
_counts: dict[str, int] = {}                        # device_id -> 已查证次数

CHARS = "23456789abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ"


# ---------------- 限流计数 ----------------
def used(device: str) -> int:
    with _lock:
        return _counts.get(device, 0)


def bump(device: str) -> None:
    with _lock:
        _counts[device] = _counts.get(device, 0) + 1


def reset(device: str) -> None:
    with _lock:
        _counts.pop(device, None)


def needs_captcha(device: str) -> bool:
    return used(device) >= config.CAPTCHA_THRESHOLD


# ---------------- 验证码 ----------------
def new_challenge() -> tuple[str, str, str]:
    """返回 (captcha_id, 明文答案, dataURL 图片)。明文答案仅 CAPTCHA_DEBUG 时下发。"""
    code = "".join(random.choice(CHARS) for _ in range(4))
    cid = secrets.token_urlsafe(16)
    now = time.time()
    with _lock:
        for k in [k for k, v in _store.items() if v[1] < now]:
            _store.pop(k, None)
        if len(_store) > 1000:
            _store.clear()
        _store[cid] = (code.lower(), now + 600)
    return cid, code, _render(code)


def check(cid: str | None, text: str | None) -> bool:
    if not cid or not text:
        return False
    with _lock:
        item = _store.pop(cid, None)
    if not item:
        return False
    code, exp = item
    if exp < time.time():
        return False
    return text.strip().lower() == code


def _render(code: str) -> str:
    """画一张带噪点的验证码图，返回 dataURL。PIL 不可用时退化为纯色块图。"""
    w, h = 168, 56
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (w, h), (250, 247, 239))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default(size=34)
        except TypeError:
            font = ImageFont.load_default()
        inks = [(34, 31, 25), (28, 95, 88), (140, 60, 30), (60, 70, 120)]
        for i, ch in enumerate(code):
            d.text((16 + i * 36 + random.randint(-3, 3), random.randint(4, 14)),
                   ch, font=font, fill=random.choice(inks))
        for _ in range(4):
            x1, y1 = random.randint(0, w // 2), random.randint(0, h)
            x2, y2 = random.randint(w // 2, w), random.randint(0, h)
            d.line((x1, y1, x2, y2), fill=(210, 200, 180), width=2)
        for _ in range(60):
            d.point((random.randint(0, w - 1), random.randint(0, h - 1)),
                    fill=(200, 190, 170))
        img = img.rotate(random.uniform(-4, 4), resample=Image.BILINEAR,
                         fillcolor=(250, 247, 239))
        buf = io.BytesIO()
        img.save(buf, "PNG")
    except Exception:
        from PIL import Image  # 理论上不会走到；再兜一层底
        img = Image.new("RGB", (w, h), (240, 236, 226))
        buf = io.BytesIO()
        img.save(buf, "PNG")
    import base64

    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
