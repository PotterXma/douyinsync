"""
在上传 YouTube 缩略图前，于封面主标题「豆泡极限求生」等右上大字下方绘制黄色序号
（同 account_mark 下已上传条数 + 1）。与 og.jpg 合成后的 ``*_yt.jpg`` 等路径兼容。
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

from modules.logger import logger


def _pick_bold_font_path() -> str | None:
    if platform.system() != "Windows":
        return None
    for p in (
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
    ):
        if os.path.isfile(p):
            return p
    return None


def stamp_upload_sequence_on_cover(src_path: str, sequence: int) -> str | None:
    """
    仅将序号 **阿拉伯数字**（如 ``5``）以黄色大号字叠在封面 **右上区域**（右对齐、略靠上），
    不包含「第 x 份」等文案——若画面上仍有长句，一般来自抖音源封面图本身。
    返回临时 JPEG 路径；失败返回 ``None``（调用方用原图）。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("cover_stamp: PIL not available, skip sequence stamp.")
        return None

    p = Path(src_path)
    if not p.is_file():
        return None
    if sequence < 1:
        sequence = 1

    try:
        img = Image.open(p).convert("RGB")
        w, h = img.size
        draw = ImageDraw.Draw(img)
        # 仅绘制数字，避免再叠一长串中文（与源封面区分）
        text = str(int(sequence))

        # 略小于主标题；16:9 模板用高度比例定位
        size = max(56, min(int(h * 0.14), w // 8, 200))
        fp = _pick_bold_font_path()
        try:
            font = ImageFont.truetype(fp, size) if fp else ImageFont.load_default()
        except OSError:
            font = ImageFont.load_default()

        # 右边距略小，数字更贴近右缘（「往右」）
        margin = max(10, int(w * 0.012))
        # 主标题约在画面上部；序号顶边从 ~30% 起
        y_top = int(h * 0.30)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        # 严格右对齐：数字右缘距画布右边为 margin（不再用 0.45w 下限，以免被拉到画面中间）
        x = w - margin - tw
        y = y_top
        if x < margin:
            x = margin
        # 避免与右下角台标区重叠：底边不超过 0.88h（台标多在右下）
        if y + th > int(h * 0.88):
            y = max(margin, int(h * 0.88) - th)

        yellow = (255, 230, 40)
        outline = (35, 25, 0)
        for dx, dy in (
            (-4, -4),
            (-4, 0),
            (-4, 4),
            (0, -4),
            (0, 4),
            (4, -4),
            (4, 0),
            (4, 4),
            (-3, -3),
            (3, 3),
        ):
            draw.text((x + dx, y + dy), text, font=font, fill=outline)
        draw.text((x, y), text, font=font, fill=yellow)

        out = p.parent / f"{p.stem}_seq{text}_yt_upload.jpg"
        img.save(out, "JPEG", quality=95)
        return str(out)
    except Exception as e:
        logger.warning("cover_stamp: failed for %s seq=%s: %s", src_path, sequence, e)
        return None
