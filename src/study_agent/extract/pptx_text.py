"""PPTX 适配器：python-pptx 提取文字 + 备注；纯图 slide 走 OCR。

调研结论（写在这里免得以后重复踩）
----------------------------------
- python-pptx 只能读**文本框里的文字**，读不到图片里的字
- 所以「纯图 slide」（一张截图铺满）必须导出成图片再 OCR
- 导出需要渲染器（LibreOffice / PowerPoint COM），**Windows 上禁 COM**（本项目环境限制）
  → v0.2 的策略：**纯图 slide 退回 OCR 需要外部渲染，暂标记为待处理**，
    写入 review-needed.md 让人工知道。真实课件里纯图页占比不高，且多为示意图。

slide 顺序即页码顺序，锚点写 `### P<n>`。
"""
from __future__ import annotations

from pathlib import Path

from .merge_util import Block, merge_to_text

# 纯图 slide 的判据：文字字符数低于此值，且图占位面积超过页面一半
MIN_CHARS_FOR_TEXT_SLIDE = 10


def _iter_text_frames(shapes):
    """递归取出所有文本框的文字（含组合形状内的）。"""
    for shape in shapes:
        if shape.shape_type == 6 and hasattr(shape, "shapes"):  # GROUP
            yield from _iter_text_frames(shape.shapes)
            continue
        if getattr(shape, "has_text_frame", False):
            yield shape.text_frame


def _slide_text(slide) -> str:
    lines: list[str] = []
    for tf in _iter_text_frames(slide.shapes):
        for para in tf.paragraphs:
            t = "".join(run.text for run in para.runs).strip()
            if t:
                lines.append(t)
        # 备注常含讲解要点，是考点的重要来源
    if slide.has_notes_slide:
        notes = (slide.notes_slide.notes_text_frame.text or "").strip()
        if notes:
            lines.append(f"[备注] {notes}")
    return "\n".join(lines)


def _image_area_ratio(slide) -> float:
    """粗略估计图片占页面面积的比例，用于判断是否纯图页。"""
    try:
        pw = slide.slide_layout.slide_master.slide_width
        ph = slide.slide_layout.slide_master.slide_height
    except Exception:
        return 0.0
    if not pw or not ph:
        return 0.0
    area = 0
    for shape in slide.shapes:
        if shape.shape_type == 13:  # PICTURE
            area += (shape.width or 0) * (shape.height or 0)
    return area / (pw * ph)


def extract_with_review(path: Path) -> tuple[str, list[dict]]:
    """返回 (Markdown, 待人工处理的 slide 清单)。"""
    from pptx import Presentation

    prs = Presentation(str(path))
    parts: list[str] = []
    review: list[dict] = []

    for i, slide in enumerate(prs.slides, 1):
        text = _slide_text(slide)
        img_ratio = _image_area_ratio(slide)

        if len(text) < MIN_CHARS_FOR_TEXT_SLIDE and img_ratio > 0.5:
            # 纯图页：python-pptx 读不到图里的字
            parts.append(
                f"### P{i}\n\n[本页为纯图片 slide，文字需 OCR；"
                f"图片占页面约 {img_ratio:.0%}]\n"
            )
            review.append({
                "page": i,
                "text": f"纯图 slide（图占 {img_ratio:.0%}），python-pptx 无法读取图中文字",
                "score": 0.0,
            })
            continue

        parts.append(f"### P{i}\n\n{text}\n")

    return "\n".join(parts), review


def extract(path: Path) -> str:
    """Adapter 协议要求的接口。"""
    md, _ = extract_with_review(path)
    return md
