"""CLI 入口：study-agent run <课件文件> [--course 课程] [--mode exam|selfstudy]"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cache import Cache
from .extract.router import extract_with_review
from .render.exam_list import render
from .understand.pipeline import build_model

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extract_concepts.md"


def main() -> None:
    ap = argparse.ArgumentParser(prog="study-agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="处理一个材料文件，生成考点清单")
    run.add_argument("file")
    run.add_argument("--course", default="未命名课程")
    run.add_argument("--chapter", default=None, help="默认取文件名")
    run.add_argument("--mode", choices=["exam", "selfstudy"], default="exam")
    run.add_argument("--out", default="build")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    chapter = args.chapter or Path(args.file).stem

    # 提取层：中间产物落盘（可人工修正后重跑下游）
    md, review = extract_with_review(args.file)
    (out / f"{chapter}.md").write_text(md, encoding="utf-8")

    # 低置信内容单独列出，供人工抽查 —— 不静默通过
    if review:
        lines = [
            f"# 需要人工核对的内容 · {chapter}",
            "",
            f"共 {len(review)} 处。这些是 OCR 置信度偏低（或无法自动读取）的位置，",
            "建议对照原文件确认后再信任下游产物。",
            "",
            "| 页码 | 置信度 | 内容片段 |",
            "|---|---|---|",
        ]
        for r in review[:200]:
            snippet = str(r["text"]).replace("|", "\\|").replace("\n", " ")[:70]
            lines.append(f"| P{r['page']} | {r['score']} | {snippet} |")
        if len(review) > 200:
            lines.append(f"| … | | 另有 {len(review) - 200} 处未列出 |")
        (out / f"review-needed-{chapter}.md").write_text("\n".join(lines) + "\n",
                                                         encoding="utf-8")

    # 理解层 → 统一知识模型
    model, manifest = build_model(
        md,
        mode=args.mode,
        source={"type": "courseware", "ref": Path(args.file).name},
        course=args.course,
        chapter=chapter,
        prompt_path=PROMPT_PATH,
        cache=Cache(out / ".cache"),
    )
    model.to_json(out / f"{chapter}.concepts.json")

    # 产出层：考点清单
    target = out / f"考点清单-{chapter}.md"
    target.write_text(render(model), encoding="utf-8")

    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[ok] {target}  (块 {manifest['blocks']}，缓存命中 {manifest['cache_hits']}，"
          f"span 校验丢弃 {manifest['span_dropped']})")


if __name__ == "__main__":
    main()
