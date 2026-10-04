"""图片型 PDF 适配器：PyMuPDF 渲染 → RapidOCR 识别 → 带页码锚点的 Markdown。

为什么选 RapidOCR（本地 ONNX 推理）
-----------------------------------
- **零成本、离线**：不调云 API，不花钱，不受网络影响
- 325 页课件实测约 4.6 秒/页（本机 CPU）
- 中文识别质量已在一门课的 8 份课件上验证过

已知的代价（写在这里避免以后惊讶）
----------------------------------
- `onnxruntime` 体积数百 MB；**首次运行会下载模型文件**（需联网，约几十 MB）
- 表格会被拍平成单列（行列关系丢失，但文字都在）
- 界面截图/流程图会碎片化（节点关系认不出）→ 靠 review-needed.md 标记出来人工看

OCR 置信度低怎么办
------------------
不静默通过：低置信块在回收结果里单独列出，由 CLI 写入 `build/review-needed.md`。
这是架构文档里「低置信页写入 review-needed.md，供人工抽查」的落点。
"""
from __future__ import annotations

from pathlib import Path

from .merge_util import Block, low_confidence_blocks, merge_to_text

# 渲染分辨率：300dpi 是文字识别的常用下限，再低小字会糊
RENDER_DPI = 300

# 低置信阈值：低于此值的块进入人工抽查清单
LOW_CONFIDENCE = 0.7

_engine = None


def _get_engine():
    """懒加载 RapidOCR（首次会加载/下载模型，耗时较长，所以不在 import 时做）。"""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def _render_pages(path: Path, dpi: int = RENDER_DPI) -> list["object"]:
    """用 PyMuPDF 把每页渲染成 numpy 图像，交给 OCR。

    直接渲染成 ndarray 可以省掉落盘临时文件的往返。
    """
    import numpy as np
    import pymupdf  # PyMuPDF 新包名（旧的 fitz 别名已弃用，会打警告）

    docs = pymupdf.open(str(path))
    try:
        zoom = dpi / 72.0
        mat = pymupdf.Matrix(zoom, zoom)
        pages = []
        for page in docs:
            pix = page.get_pixmap(matrix=mat)
            arr = np.frombuffer(pix.samples, dtype=np.uint8)
            arr = arr.reshape(pix.height, pix.width, pix.n)
            if pix.n >= 3:
                arr = arr[:, :, :3]  # 丢掉 alpha，OCR 只要 RGB
            pages.append(arr)
        return pages
    finally:
        docs.close()


def extract_with_review(path: Path) -> tuple[str, list[dict]]:
    """提取并返回 (Markdown, 低置信清单)。

    低置信清单每项形如 {"page": 3, "text": "...", "score": 0.52}，
    由调用方写入 review-needed.md。
    """
    engine = _get_engine()
    pages = _render_pages(path)

    parts: list[str] = []
    review: list[dict] = []

    for i, img in enumerate(pages, 1):
        try:
            result, _ = engine(img)
        except Exception as e:  # 单页失败不该毁掉整份文档
            parts.append(f"### P{i}\n\n[本页 OCR 失败：{type(e).__name__}]\n")
            review.append({"page": i, "text": f"[整页失败] {e}", "score": 0.0})
            continue

        blocks: list[Block] = []
        for item in (result or []):
            box, text, score = item[0], item[1], item[2]
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            blocks.append(Block(
                text=text,
                x=min(xs), y=min(ys),
                w=max(xs) - min(xs), h=max(ys) - min(ys),
                score=float(score),
            ))

        for b in low_confidence_blocks(blocks, LOW_CONFIDENCE):
            review.append({"page": i, "text": b.text, "score": round(b.score, 3)})

        body = merge_to_text(blocks, mark_low_confidence=LOW_CONFIDENCE)
        parts.append(f"### P{i}\n\n{body}\n")

    return "\n".join(parts), review


def extract(path: Path) -> str:
    """Adapter 协议要求的接口：只要 Markdown。"""
    md, _ = extract_with_review(path)
    return md
