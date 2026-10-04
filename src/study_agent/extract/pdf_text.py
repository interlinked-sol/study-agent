"""文字型 PDF 适配器：先探测 ToUnicode，有文本层才允许走原生解析。

判据来自实测：CID 字体 ≠ 文本层损坏，真正的判据是有没有 ToUnicode CMap。
有 → 纯解析零成本零错误；无 → 交给 OCR 适配器（v0.2）。
"""
from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

# Wingdings/Symbol 字体的项目符号会提取为 PUA 私有区字符（实测 \uf097 等），
# 对 LLM 和 source_span 校验都是噪声，统一替换为「·」。
_PUA_BULLET = re.compile(r"[\uf000-\uf0ff]")


def _obj(o):
    return o.get_object() if hasattr(o, "get_object") else o


def has_text_layer(path: Path) -> bool:
    """抽样检查字体是否带 /ToUnicode CMap（含 CIDFontType 的子字体）。"""
    try:
        reader = PdfReader(str(path))
        n = len(reader.pages)
        idx = sorted(set(list(range(min(5, n))) + list(range(max(0, n - 2), n))))
        for i in idx:
            res = _obj(reader.pages[i].get("/Resources")) or {}
            fonts = _obj(res.get("/Font")) or {}
            for ref in fonts.values():
                font = _obj(ref)
                if "/ToUnicode" in font:
                    return True
                for d in _obj(font.get("/DescendantFonts")) or []:
                    if "/ToUnicode" in _obj(d):
                        return True
    except Exception:
        return False  # 探测失败按无文本层处理，v0.2 起走 OCR
    return False


def extract(path: Path) -> str:
    """逐页提取文本，输出带 <!-- pN --> 锚点的 Markdown。"""
    reader = PdfReader(str(path))
    parts = []
    for i, page in enumerate(reader.pages, 1):
        text = _PUA_BULLET.sub("·", page.extract_text() or "").strip()
        if text:
            parts.append(f"<!-- p{i} -->\n{text}")
    if not parts:
        raise ValueError(f"{path.name} 未提取到任何文本（可能需走 OCR 适配器）")
    return "\n\n".join(parts)
