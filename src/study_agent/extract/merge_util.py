"""文本块坐标排序：把 OCR / 提取得到的散落文本块还原成阅读顺序。

为什么需要
----------
OCR 返回的是「一堆带坐标的文本块」，顺序是检测顺序，不等于阅读顺序。
直接拼接会得到读不通的句子，进而让 LLM 抽错概念、让 source_span 校验失败
（因为模型引用的"连续摘录"在拼接结果里并不连续）。

算法
----
1. 用块高估一个行高，按 y 分桶变成"行"（容差取行高的一半，避免上下行粘连）
2. 行内按 x 排序
3. 行间按 y 排序 —— 即标准的「先上后下、先左后右」

实测来源：`courseware-notes/merge_pages.py` 在 8 份课件 325 页上验证过。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Block:
    """一个文本块及其在页面上的位置（坐标单位为像素，原点在左上）。"""

    text: str
    x: float
    y: float
    w: float = 0.0
    h: float = 0.0
    score: float = 1.0  # OCR 置信度；非 OCR 来源固定为 1.0


def _estimate_line_height(blocks: list[Block]) -> float:
    heights = [b.h for b in blocks if b.h > 0]
    if heights:
        return sum(heights) / len(heights)
    # 没有高度信息时用中位数字号经验值兜底
    return 20.0


def sort_blocks(blocks: list[Block], y_tolerance: float | None = None) -> list[Block]:
    """按版面位置还原阅读顺序。"""
    if not blocks:
        return []

    line_h = _estimate_line_height(blocks)
    tol = y_tolerance if y_tolerance is not None else max(line_h * 0.6, 8.0)

    ordered = sorted(blocks, key=lambda b: b.y)
    lines: list[list[Block]] = []
    for b in ordered:
        if lines and abs(b.y - lines[-1][0].y) <= tol:
            lines[-1].append(b)
        else:
            lines.append([b])

    out: list[Block] = []
    for line in lines:
        out.extend(sorted(line, key=lambda b: b.x))
    return out


def merge_to_text(blocks: list[Block], *, mark_low_confidence: float | None = 0.7) -> str:
    """把文本块合并成 Markdown 文本（一行一块）。

    mark_low_confidence 非 None 时，低于该置信度的块会被标注出来 ——
    这些正是需要人工抽查的地方，标记保留给下游写 review-needed.md。
    """
    lines: list[str] = []
    for b in sort_blocks(blocks):
        t = (b.text or "").strip()
        if not t:
            continue
        if mark_low_confidence is not None and b.score < mark_low_confidence:
            lines.append(f"{t}  ⟪低置信度{b.score:.2f}⟫")
        else:
            lines.append(t)
    return "\n".join(lines)


def low_confidence_blocks(blocks: list[Block], threshold: float = 0.7) -> list[Block]:
    """挑出低置信度块（供 review-needed.md 使用）。"""
    return [b for b in sort_blocks(blocks) if b.score < threshold]
