"""eval 回归：拿金标准对账一次新的产出，算召回率并记入 history。

配合 `eval/README.md` 的流程使用：
    ① 改 prompt
    ② 删 build/.cache/（缓存 key 不含 prompt，不清会命中旧结果）
    ③ 重跑管线拿到新产物
    ④ uv run python scripts/eval_run.py 项目1
    ⑤ 看召回率涨跌，记入 eval/history.md

为什么用「关键词覆盖率」而不是文本相似度
------------------------------------------
金标准条目里用 `/` 分隔同义词（如「智能体开发流程 / 创建 / 提示词 / 技能 / 测试 / 发布」）。
只要产物里出现了足够比例的关键词，就算这条被覆盖。
这比编辑距离之类的指标**可控**——你可以靠加同义词来调节松紧，
而不用去猜某个阈值到底代表什么。

用法：
    uv run python scripts/eval_run.py <章节关键字>
    uv run python scripts/eval_run.py 项目1 --threshold 0.6
    uv run python scripts/eval_run.py 项目1 --no-record    # 只看结果，不写 history
"""
from __future__ import annotations

import re
import sys
import argparse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "eval"
BUILD = ROOT / "build"

GOLDEN_LINE = re.compile(r"^\s*-\s*\[(?P<mark>[xX ])\]\s*(?P<text>.+?)\s*$")


def load_golden(path: Path) -> list[str]:
    """只取勾选过的条目 —— 没勾的视为尚未人工确认，不计入分母。"""
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = GOLDEN_LINE.match(line)
        if m and m.group("mark").lower() == "x":
            items.append(m.group("text"))
    return items


def find_latest_output(keyword: str) -> Path | None:
    """找 build 下最新的一份考点清单产物。"""
    cands = sorted(BUILD.glob(f"**/考点清单-*{keyword}*.md"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        cands = sorted(BUILD.glob("**/考点清单-*.md"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def _norm(s: str) -> str:
    """去掉所有空白后比较。

    为什么：中文材料里空格极不稳定 —— OCR 可能输出「智能体与AI应用」，
    而金标准写的是「智能体与 AI 应用」，逐字比较会误判为未覆盖。
    实测踩过：一条明明覆盖了的考点被算成漏检，召回率凭空低了 25%。
    """
    return re.sub(r"\s+", "", s)


def check_coverage(golden: str, output: str, threshold: float) -> tuple[bool, str]:
    """关键词覆盖率判定。返回 (是否覆盖, 说明)。

    规则：**第一个关键词是主标题，必须命中**，否则整条判不覆盖。
    为什么：实测发现「智能体与AI应用的区别 / LUI / GUI」这条，
    主标题完全没出现在产物里，但 LUI 和 GUI 出现了 → 覆盖率 2/3 就通过了。
    这显然不对：同义词只是提高容错，不能替代主标题。
    """
    keys = [k.strip() for k in golden.split("/") if k.strip()]
    if not keys:
        return False, "无关键词"

    out_n = _norm(output)
    hit = [k for k in keys if _norm(k) in out_n]
    missed = [k for k in keys if _norm(k) not in out_n]
    detail = "命中 %d/%d" % (len(hit), len(keys))

    if _norm(keys[0]) not in out_n:
        return False, "主标题未命中（" + keys[0][:20] + "）"
    if missed:
        detail += "，缺：" + "、".join(missed[:3])
    return len(hit) / len(keys) >= threshold, detail


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword", help="章节关键字，如 项目1")
    ap.add_argument("--threshold", type=float, default=0.6,
                    help="关键词覆盖率阈值（默认 0.6）")
    ap.add_argument("--no-record", action="store_true", help="不写入 history.md")
    ap.add_argument("--prompt-version", default="v1", help="本次 prompt 版本号")
    args = ap.parse_args()

    goldens = sorted(EVAL.glob(f"*{args.keyword}*golden*.md"))
    if not goldens:
        print("没找到金标准文件（eval/*%s*golden*.md）" % args.keyword)
        print("提示：先按 eval/项目1-候选池-待核对.md 完成人工核对")
        return
    golden_path = goldens[0]

    items = load_golden(golden_path)
    if not items:
        print("金标准里没有勾选([x])的条目：%s" % golden_path.name)
        print("请先人工核对，把确认的条目改成 - [x]")
        return

    out_path = find_latest_output(args.keyword)
    if not out_path:
        print("build/ 下没找到对应的考点清单产物，先跑一次管线")
        return

    output = out_path.read_text(encoding="utf-8")
    print("金标准：%s（%d 条已确认）" % (golden_path.name, len(items)))
    print("对账产物：%s" % out_path.relative_to(ROOT))
    print("阈值：关键词覆盖率 ≥ %.0f%%\n" % (args.threshold * 100))

    covered = 0
    for i, item in enumerate(items, 1):
        ok, detail = check_coverage(item, output, args.threshold)
        covered += ok
        print("  %s %-46s %s" % ("✅" if ok else "❌", item[:44], detail))

    recall = covered / len(items)
    print()
    print("=" * 60)
    print("召回率：%d/%d = %.1f%%" % (covered, len(items), recall * 100))
    print("=" * 60)

    if not args.no_record:
        hist = EVAL / "history.md"
        if not hist.exists():
            hist.write_text(
                "# eval 回归记录\n\n"
                "| 日期 | 章节 | prompt 版本 | 召回率 | 覆盖率阈值 | 备注 |\n"
                "|---|---|---|---|---|---|\n",
                encoding="utf-8")
        with hist.open("a", encoding="utf-8") as fh:
            fh.write("| %s | %s | %s | %.1f%% (%d/%d) | %.0f%% | 产物 %s |\n" % (
                date.today().isoformat(), args.keyword, args.prompt_version,
                recall * 100, covered, len(items), args.threshold * 100,
                out_path.name))
        print("已记入 %s" % hist.relative_to(ROOT))


if __name__ == "__main__":
    main()
