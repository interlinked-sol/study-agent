"""理解层主流程：分块 → LLM 抽取（带缓存）→ 合并去重 → source_span 校验 → KnowledgeModel。"""
from __future__ import annotations

import json
from pathlib import Path

from ..cache import Cache
from ..model import Concept, ExamPoint, KnowledgeModel, QuizItem, verify_reasons, verify_spans
from . import chunk, llm

SYSTEM = "你是课程内容分析器，只输出严格 JSON，不输出任何其他文字。"

_CONCEPT_KEYS = ("name", "definition", "example", "importance", "source_page", "source_span")
_POINT_KEYS = ("point", "reason", "linked_concepts", "source_page", "source_span")
_QUIZ_KEYS = ("q", "a", "type")


def _merge(partials: list[dict], *, mode: str, source: dict, course: str, chapter: str) -> KnowledgeModel:
    km = KnowledgeModel(mode=mode, source=source, course=course, chapter=chapter)
    seen_concepts: set[str] = set()
    seen_points: set[str] = set()
    for p in partials:
        for c in p.get("concepts", []):
            if c.get("name") and c["name"] not in seen_concepts:
                seen_concepts.add(c["name"])
                km.concepts.append(Concept(**{k: c[k] for k in _CONCEPT_KEYS if k in c}))
        for ep in p.get("exam_points", []):
            if ep.get("point") and ep["point"] not in seen_points:
                seen_points.add(ep["point"])
                km.exam_points.append(ExamPoint(**{k: ep[k] for k in _POINT_KEYS if k in ep}))
        km.pitfalls.extend(x for x in p.get("pitfalls", []) if x not in km.pitfalls)
        for q in p.get("quiz", []):
            if q.get("q"):
                km.quiz.append(QuizItem(**{k: q[k] for k in _QUIZ_KEYS if k in q}))
    return km


def build_model(
    md_text: str,
    *,
    mode: str,
    source: dict,
    course: str,
    chapter: str,
    prompt_path: Path,
    cache: Cache,
) -> tuple[KnowledgeModel, dict]:
    """返回 (知识模型, manifest)。manifest 记录块数、缓存命中、span 校验丢弃数。"""
    prompt_tpl = prompt_path.read_text(encoding="utf-8")
    blocks = chunk.split_by_heading(md_text)

    partials: list[dict] = []
    rolling = ""
    hits = 0
    for b in blocks:
        cache_key = rolling + "\n" + b
        hit = cache.get("understand", cache_key)
        if hit is None:
            user = prompt_tpl.replace("{rolling_summary}", rolling or "（首轮，无）")
            user = user.replace("{content}", b)
            hit = json.loads(llm.chat(SYSTEM, user))
            cache.set("understand", cache_key, hit)
        else:
            hits += 1
        partials.append(hit)
        rolling = f"{rolling} {hit.get('summary', '')}".strip()[-800:]

    model = _merge(partials, mode=mode, source=source, course=course, chapter=chapter)
    dropped = verify_spans(model, md_text)
    # reason 字段的独立校验（verify_spans 只覆盖 source_span，不覆盖 reason）
    reason_cleaned = verify_reasons(model)

    manifest = {
        "chapter": chapter,
        "mode": mode,
        "blocks": len(blocks),
        "cache_hits": hits,
        "span_dropped": dropped,
        "reason_cleaned": reason_cleaned,
        "concepts": len(model.concepts),
        "exam_points": len(model.exam_points),
        "quiz": len(model.quiz),
    }
    return model, manifest
