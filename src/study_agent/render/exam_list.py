"""考点清单渲染器：KnowledgeModel → Markdown（渲染器模式，新增产物=新增渲染器）。"""
from __future__ import annotations

import re

from ..model import KnowledgeModel


def _one_line(s: str) -> str:
    """把原文摘录里的换行/连续空白压成单空格。

    为什么需要：source_span 是**逐字摘录**，而 PDF 提取出来的文本带硬换行
    （如"《习近平新时代中国特色\n社会主义思想概论》"）。直接塞进引用块会让它断成多段，
    破坏 Markdown 结构。压平只是展示层处理 —— verify_spans() 本来就按去空白归一化比较，
    所以不影响校验逻辑。
    """
    return re.sub(r"\s+", " ", s or "").strip()


def render(model: KnowledgeModel) -> str:
    title = "考点清单" if model.mode == "exam" else "核心概念清单"
    L = [f"# {title} · {model.course} {model.chapter}", ""]

    if model.exam_points:
        L.append("## 考点（按重要性排序）\n")
        imp = {c.name: c.importance for c in model.concepts}
        pts = sorted(
            model.exam_points,
            key=lambda p: -max((imp.get(n, 0) for n in p.linked_concepts), default=0),
        )
        for i, p in enumerate(pts, 1):
            meta = "；".join(x for x in [p.reason, f"p{p.source_page}" if p.source_page else ""] if x)
            L.append(f"{i}. **{p.point}**" + (f"（{meta}）" if meta else ""))
            # 输出原文摘录 —— 这是"可核验"的唯一抓手：
            # source_span 已通过程序校验（确实存在于原文），摆在旁边用户才能快速对照
            if p.source_span:
                L.append(f"   > {_one_line(p.source_span)}")
        L.append("")

    if model.concepts:
        L.append("## 核心概念\n")
        for c in sorted(model.concepts, key=lambda c: -c.importance):
            L.append(f"- **{c.name}**（重要度 {c.importance}/5）：{c.definition}")
            if c.example:
                L.append(f"  - 例：{c.example}")
            if c.source_span:
                L.append(f"  - 原文：{_one_line(c.source_span)}")
        L.append("")

    if model.pitfalls:
        L.append("## 易错点\n")
        L.extend(f"- {x}" for x in model.pitfalls)
        L.append("")

    if model.quiz:
        L.append("## 自测题（先答后看）\n")
        for i, q in enumerate(model.quiz, 1):
            L.append(f"{i}. 【{q.type}】{q.q}")
        L.append("\n<details><summary>答案</summary>\n")
        L.extend(f"{i}. {q.a}" for i, q in enumerate(model.quiz, 1))
        L.append("\n</details>")

    return "\n".join(L) + "\n"
