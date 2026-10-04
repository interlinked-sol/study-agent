"""统一知识模型：三种产物（考点清单/卡片/速查表）的单一事实源。"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Concept:
    name: str
    definition: str
    example: str = ""
    importance: int = 3  # 1-5；mode=exam 考频加权，mode=selfstudy 概念中心性
    source_page: int | None = None
    source_span: str = ""  # 原文逐字摘录，程序校验防幻觉


@dataclass
class ExamPoint:
    point: str
    reason: str = ""  # 老师强调 / 历年题 / 高频
    linked_concepts: list[str] = field(default_factory=list)
    source_page: int | None = None
    source_span: str = ""


@dataclass
class QuizItem:
    q: str
    a: str
    type: str = "辨析"  # 辨析 / 应用 / 陷阱


@dataclass
class KnowledgeModel:
    mode: str  # exam | selfstudy
    source: dict  # {"type": "courseware|book|web", "ref": "文件名或URL"}
    course: str
    chapter: str
    concepts: list[Concept] = field(default_factory=list)
    exam_points: list[ExamPoint] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    quiz: list[QuizItem] = field(default_factory=list)

    def to_json(self, path: Path) -> None:
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def verify_spans(model: KnowledgeModel, source_text: str) -> int:
    """防幻觉硬规则（P0）：source_span 逐字匹配不上原文的条目直接丢弃。

    返回被丢弃的条目数（供 run manifest 记录）。
    """
    src = _norm(source_text)

    def keep(span: str) -> bool:
        return bool(span) and _norm(span) in src

    before = len(model.concepts) + len(model.exam_points)
    model.concepts = [c for c in model.concepts if keep(c.source_span)]
    model.exam_points = [p for p in model.exam_points if keep(p.source_span)]
    return before - len(model.concepts) - len(model.exam_points)


# reason 字段中**必须来自外部信息**的词 —— 模型无从得知，写出来即编造。
# 实测教训：prompt 里曾把「老师反复强调」当示例，结果模型对一份《培养意见》材料
# 也照样写「老师反复强调」——而那份材料里没有老师。
FORBIDDEN_IN_REASON = (
    '老师', '教师讲', '课堂', '课上',
    '考频', '历年', '真题', '考试', '常考', '必考', '高频',
    '反复强调', '多次强调', '重点强调',
    '大纲要求', '教学要求',
)

# reason 的合法取值（与 prompts/extract_concepts.md 保持一致）
ALLOWED_REASONS = (
    '原文明确列举', '原文对比结构', '原文含数值', '原文含术语定义', '原文陈述',
)


def verify_reasons(model: KnowledgeModel) -> int:
    """reason 字段的防幻觉校验（补偿 verify_spans 不覆盖该字段的盲区）。

    规则：reason 出现「必须来自外部信息」的词，或不属于允许取值集合时，
    清空该 reason（**保留考点本身** —— 考点有 source_span 背书，是可信的；
    只是"为什么值得考"这个判断不可信）。

    返回被清理的 reason 数量（供 manifest 记录）。
    """
    cleaned = 0
    for p in model.exam_points:
        r = (p.reason or '').strip()
        if not r:
            continue
        bad = any(w in r for w in FORBIDDEN_IN_REASON)
        if not bad and r not in ALLOWED_REASONS:
            # 不在白名单里的自由发挥也算不可信
            bad = True
        if bad:
            p.reason = ''
            cleaned += 1
    return cleaned
