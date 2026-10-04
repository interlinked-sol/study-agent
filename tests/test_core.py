"""核心逻辑单元测试。

为什么只测这几个
----------------
项目里有些模块**改坏了不会报错，只会让输出悄悄变差**：
  - `verify_spans` / `verify_reasons` —— 防幻觉的唯一程序保障，坏了等于放行编造
  - `chunk.split_by_heading` —— 分块边界错会切断概念，静默丢失
  - `Cache` —— key 逻辑错会导致该重跑的没重跑
  - `merge_util.sort_blocks` —— 排序错会让句子读不通，进而拖垮 span 校验
这些正是最该被测的类型。其余模块（LLM 调用、渲染格式）靠端到端验证即可。

运行：
    uv run pytest -q
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from study_agent.cache import Cache
from study_agent.extract.merge_util import Block, merge_to_text, sort_blocks
from study_agent.model import (
    Concept,
    ExamPoint,
    KnowledgeModel,
    verify_reasons,
    verify_spans,
)
from study_agent.understand.chunk import split_by_heading


# ---------- verify_spans：防幻觉的核心 ----------

def _model_with(concepts=None, points=None) -> KnowledgeModel:
    m = KnowledgeModel(mode="exam", source={}, course="t", chapter="t")
    m.concepts = concepts or []
    m.exam_points = points or []
    return m


def test_verify_spans_keeps_verbatim_quote():
    m = _model_with(concepts=[Concept(name="A", definition="d", source_span="短期记忆像便签纸")])
    dropped = verify_spans(m, "前面的话。短期记忆像便签纸，临时记录当前任务。")
    assert dropped == 0
    assert len(m.concepts) == 1


def test_verify_spans_ignores_whitespace_difference():
    """摘录与原文只差空白，应当视为通过（PDF 提取常带硬换行）。"""
    m = _model_with(concepts=[Concept(name="A", definition="d", source_span="短期记忆\n像便签纸")])
    verify_spans(m, "短期记忆像便签纸，临时记录。")
    assert len(m.concepts) == 1


def test_verify_spans_drops_fabricated():
    """原文里没有的摘录必须被丢弃 —— 这是防幻觉的底线。"""
    m = _model_with(concepts=[Concept(name="编造", definition="d", source_span="原文根本不存在这句话")])
    dropped = verify_spans(m, "短期记忆像便签纸。")
    assert dropped == 1
    assert m.concepts == []


def test_verify_spans_drops_empty_span():
    m = _model_with(concepts=[Concept(name="无证据", definition="d", source_span="")])
    verify_spans(m, "任意原文")
    assert m.concepts == []


# ---------- verify_reasons：compensate verify_spans 的盲区 ----------

@pytest.mark.parametrize("reason", [
    "老师反复强调",        # 材料里没有"老师"这回事
    "定义类高频考点",      # 含"高频"
    "历年常考",
    "这段我觉得很重要",    # 自由发挥，不在白名单
])
def test_verify_reasons_clears_unverifiable(reason):
    m = _model_with(points=[ExamPoint(point="p", reason=reason, source_span="x")])
    assert verify_reasons(m) == 1
    assert m.exam_points[0].reason == ""
    # 关键：只清 reason，考点本身要留住（它有 source_span 背书）
    assert m.exam_points[0].point == "p"


@pytest.mark.parametrize("reason", [
    "原文明确列举", "原文对比结构", "原文含数值", "原文含术语定义", "原文陈述",
])
def test_verify_reasons_keeps_allowed(reason):
    m = _model_with(points=[ExamPoint(point="p", reason=reason, source_span="x")])
    assert verify_reasons(m) == 0
    assert m.exam_points[0].reason == reason


# ---------- chunk ----------

def test_chunk_splits_by_heading():
    # 注意 chunk 的语义是「按标题切分，但小块会累积到接近 max_chars」——
    # 所以样本必须足够大，两块才会真被分开（第一版给太小，被合并成一块）
    md = "## A\n" + "a" * 60 + "\n## B\n" + "b" * 60
    blocks = split_by_heading(md, max_chars=100)
    assert len(blocks) == 2
    assert blocks[0].startswith("## A")
    assert blocks[1].startswith("## B")


def test_chunk_accumulates_small_sections():
    """小块会被累积到接近上限 —— 这是设计意图（避免产生大量碎片块）。"""
    md = "## A\nshort\n## B\nalso short"
    blocks = split_by_heading(md, max_chars=1000)
    assert len(blocks) == 1


def test_chunk_hard_splits_oversized():
    blocks = split_by_heading("x" * 250, max_chars=100)
    assert len(blocks) == 3
    assert all(len(b) <= 100 for b in blocks)


def test_chunk_empty_input():
    assert split_by_heading("") == []


# ---------- cache ----------

def test_cache_miss_then_hit(tmp_path):
    c = Cache(tmp_path)
    assert c.get("ns", "key1") is None
    c.set("ns", "key1", {"v": 1})
    assert c.get("ns", "key1") == {"v": 1}


def test_cache_distinguishes_different_keys(tmp_path):
    c = Cache(tmp_path)
    c.set("ns", "甲", {"v": 1})
    c.set("ns", "乙", {"v": 2})
    assert c.get("ns", "甲") == {"v": 1}
    assert c.get("ns", "乙") == {"v": 2}


# ---------- merge_util：坐标排序 ----------

def test_sort_blocks_reading_order():
    blocks = [
        Block("右下", x=300, y=200, h=20),
        Block("左上", x=50, y=50, h=20),
        Block("右上", x=300, y=50, h=20),
        Block("左下", x=50, y=200, h=20),
    ]
    assert [b.text for b in sort_blocks(blocks)] == ["左上", "右上", "左下", "右下"]


def test_sort_blocks_same_line_by_x():
    blocks = [Block("后", x=200, y=50, h=20), Block("前", x=10, y=52, h=20)]
    assert [b.text for b in sort_blocks(blocks)] == ["前", "后"]


def test_merge_marks_low_confidence():
    blocks = [Block("清晰的话", x=10, y=10, h=20, score=0.95),
              Block("糊掉的话", x=10, y=40, h=20, score=0.4)]
    out = merge_to_text(blocks, mark_low_confidence=0.7)
    assert "低置信度" in out
    assert "清晰的话" in out


def test_merge_empty():
    assert merge_to_text([]) == ""
