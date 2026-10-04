"""演示驱动：未配置 DEEPSEEK_API_KEY 时跑通真实管线。

除 llm.chat 被 responses.json 打桩外，分块、缓存、合并、span 校验、
渲染、manifest 全部走项目真实代码。用法：

    uv run python scripts/demo_run.py <pdf> <responses.json>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from study_agent.cache import Cache
from study_agent.extract.router import extract_markdown
from study_agent.render.exam_list import render
from study_agent.understand import llm, pipeline


def main() -> None:
    pdf, responses_path = sys.argv[1], Path(sys.argv[2])
    responses = iter(json.loads(responses_path.read_text(encoding="utf-8")))
    llm.chat = lambda system, user, **kw: json.dumps(next(responses), ensure_ascii=False)

    out = ROOT / "build"
    out.mkdir(exist_ok=True)
    chapter = Path(pdf).stem

    md = extract_markdown(pdf)
    (out / f"{chapter}.md").write_text(md, encoding="utf-8")

    model, manifest = pipeline.build_model(
        md,
        mode="exam",
        source={"type": "courseware", "ref": Path(pdf).name},
        course="Information Quality",
        chapter=chapter,
        prompt_path=ROOT / "prompts" / "extract_concepts.md",
        cache=Cache(out / ".cache"),
    )
    model.to_json(out / f"{chapter}.concepts.json")
    target = out / f"考点清单-{chapter}.md"
    target.write_text(render(model), encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))
    print(f"[ok] {target}")


if __name__ == "__main__":
    main()
