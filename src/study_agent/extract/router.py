"""提取层分流：按文件类型 + 文本层探测结果路由到对应 adapter。"""
from __future__ import annotations

from pathlib import Path

from . import pdf_ocr, pdf_text, pptx_text


def extract_markdown(path: str | Path) -> str:
    """只要 Markdown（兼容旧调用）。需要低置信清单时用 extract_with_review。"""
    md, _ = extract_with_review(path)
    return md


def extract_with_review(path: str | Path) -> tuple[str, list[dict]]:
    """提取并返回 (Markdown, 待人工核对清单)。

    分流逻辑：
    - `.pptx`                      → python-pptx（纯图 slide 单独标记）
    - `.pdf` 有 ToUnicode 文本层   → 原生解析（零成本、零识别错误）
    - `.pdf` 无文本层（图片型）     → PyMuPDF 渲染 + RapidOCR
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    suffix = p.suffix.lower()

    if suffix == ".pptx":
        return pptx_text.extract_with_review(p)

    if suffix == ".pdf":
        if pdf_text.has_text_layer(p):
            return pdf_text.extract(p), []
        # 图片型 PDF：走 OCR
        return pdf_ocr.extract_with_review(p)

    raise ValueError(f"暂不支持的文件类型：{suffix}（v0.5 支持 epub/web）")
