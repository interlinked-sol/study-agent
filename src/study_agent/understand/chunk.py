"""分块策略：按 Markdown 标题分块，超长块按页锚点硬切。

课件文本常无标题层级，此时整块硬切；块间靠滚动摘要携带上下文，
不做全文一次性喂入（防爆上下文）。
"""
from __future__ import annotations

import re


def split_by_heading(md: str, max_chars: int = 4000) -> list[str]:
    parts = re.split(r"(?m)(?=^#{1,3} )", md)

    blocks, buf = [], ""
    for part in parts:
        if len(buf) + len(part) <= max_chars:
            buf += part
        else:
            if buf:
                blocks.append(buf)
            buf = part
    if buf:
        blocks.append(buf)

    out: list[str] = []
    for b in blocks:
        while len(b) > max_chars:
            out.append(b[:max_chars])
            b = b[max_chars:]
        if b.strip():
            out.append(b)
    return out
