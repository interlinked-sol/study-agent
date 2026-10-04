# study-agent 迭代执行清单

> 用法：每版按顺序打勾；每版开工前先跑 eval 回归确认无回退，收尾打 git tag。
> 全程纪律：改 prompt 必删 `build/.cache/`；金标准冻结后不许改；新增产物 = 新增渲染器，不动理解层。

## 0. 收尾欠账（开工 v0.2 前完成）

- [ ] **先配 `DEEPSEEK_API_KEY` 并用本课程材料跑一次真实链路** —— 这是 v0.1 验收的前提
- [ ] 首个 commit：`git add -A && git commit -m "v0.1: pipeline + stubbed run (no API key yet)"`
      （原拟 message 是 "first real run"，但实际是 `demo_run.py` 打桩跑的，真实 API 未调用过）
- [ ] 冻结金标准：**用本课程材料**（《数据采集与挖掘》第 1 章 / 《智能体技能入门》任一项目）——
      **不要用 IQ 材料**，尺子必须量目标对象
- [x] 处理 `reason` 字段：**已完成 2026-09-24**（prompt 限五取值 + verify_reasons 程序兜底）——当前会写出"老师反复强调"这类无从验证的推测，而
      `verify_spans()` 只校验 `source_span`、不校验 `reason`，是防幻觉盲区。三选一：
      (a) prompt 禁止此类推测 (b) 删掉该字段 (c) 保留但明确标注"未经验证"
- [ ] 跑首次回归记基线：召回率记入 `eval/history.md`（这就是 v1 prompt 的基线分）
- [ ] 删除工作区过时副本 `WorkBuddy\2026-09-23-11-44-33\study-agent`
      ⚠️ 删前先 diff：该副本 `build/` 里有第一次运行的产物（缓存 JSON + 考点清单），
      是"跑通过"的原始证据；确认新位置已包含再删

---

## v0.2 图片型 PDF + PPTX（提取层扩展）

**目标**：图片型课件全链路跑通。
**参考资产**：`C:\Users\john\WorkBuddy\2026-09-17-19-04-04\courseware-notes\extract_text.py`（RapidOCR 实战实现）、`merge_pages.py`（坐标排序）。

- [ ] 装依赖：`C:\Users\john\.local\bin\uv.exe add pymupdf python-pptx rapidocr-onnxruntime`
- [ ] 写 `extract/merge_util.py`：文本块按坐标排序合成（移植 merge_pages 思路，**根治拼句丢弃**）
- [ ] 写 `extract/pdf_ocr.py`：PyMuPDF 逐页渲染 300dpi → RapidOCR 本地推理（零成本）→ 带 `<!-- pN -->` 锚点输出
- [ ] 低置信页处理：置信度 < 阈值写入 `build/review-needed.md`；**仅这些页**走腾讯云 OCR 双引擎交叉校验（P1，不一致字符标红）
- [ ] 写 `extract/pptx_text.py`：python-pptx 提取文字+备注；纯图 slide 导出 → OCR
- [ ] `router.py` 接通两个 `NotImplementedError`；雨课堂切片（images/ 目录）支持直接喂入，跳过 PDF 抽图
- [ ] 验证：一份图片型课件跑通，manifest 的 `span_dropped` 应显著低于 v0.1（坐标排序生效的证据）
- [ ] eval 回归：第 2 章召回率不低于基线
- [ ] `git tag v0.2`

**验收**：图片型 PDF 和 PPTX 各跑通一份，低置信页有清单，回归无回退。

---

## v0.3 记忆卡片 + 复习闭环

**目标**：卡片进 Obsidian，SR 插件能调度。
**参考资产**：`courseware-notes/PROMPT.md`（5 铁律口径）、`normalize_cards.py`、`output/` 510 张样板。

- [ ] 写 `render/flashcards.py`：concepts + quiz → `问题::答案<!-- P页码 -->`（单向卡，格式已定案，不许改）
- [ ] prompt 加**原子卡片规则**：一卡只考一点，★★★ 拆多卡，★ 合并（P1）
- [ ] 移植 `normalize_cards.py` 为 `render/normalize.py`：归一 `:::`→`::`、`<--`→`<!--`，自检每卡带页码，**必跑**（LLM 自查不可信）
- [ ] CLI 加 `--vault <Obsidian路径>`：卡片直接写入 vault 对应课程目录
- [ ] 验证：SR 插件（v1.15.4）里看到新卡进入复习队列
- [ ] 选做：移植 `to_apkg.py`，CLI 加 `--anki` 导出 apkg
- [ ] eval 回归 + `git tag v0.3`

**验收**：一份课件 → 卡片文件 normalize 零报错 → Obsidian SR 可复习。

---

## v0.4 速查表 + 覆盖率自测 + 成本计量

**目标**：三件套齐了，且有质量自查和成本数据。

- [ ] 写 `render/cheatsheet.py`：concepts + pitfalls 压缩成单页（对照表/参数/流程步骤，查不背）
- [ ] 写覆盖率自测：LLM 对照原文逐节查漏，输出 `build/coverage-report.md`（哪些原文段落未覆盖到任何考点）
- [ ] manifest 加成本计量（P1）：每章 token 数、估算金额、耗时——「单章成本 ¥0.X」进简历
- [ ] 选做：理解层 asyncio 并发（块间无依赖部分）
- [ ] eval 回归 + `git tag v0.4`

**验收**：一份课件出齐三件套；coverage-report 能定位遗漏段落；manifest 有 token/金额。

---

## v0.5 自学模式（双模式成形）

**目标**：一篇陌生领域文章 → 概念清单 + 自测题。

- [ ] 写 `extract/web_text.py`：URL → 正文提取（readability）→ 带锚点 Markdown
- [ ] 写 `extract/epub_text.py`：EPUB 章节 → Markdown（`uv add ebooklib`）
- [ ] 理解层按 `mode=selfstudy` 切换加权：importance = 概念中心性（改 prompt，新版本号）
- [ ] 产出标题切换「核心概念清单」（渲染器已支持）
- [ ] eval：为一篇自学材料建第二份金标准
- [ ] `git tag v0.5`

**验收**：给一个 URL 跑通全流程，输出形态符合 learn-new-domain 四步循环的第 1/3 步。

---

## v1.0 简历形态（DSH 插件 + 交付四件套）

**目标**：对话里一句话调用 + GitHub 可展示。
**参考资产**：`C:\Users\john\WorkBuddy\2026-09-17-19-04-04\dsh-plugin-dev-guide.md`。

- [ ] 包成 DSH 插件：对话输入「处理第 X 章课件」→ 调同一套管线
- [ ] README 四件套：① 架构图（五层+双模式）② eval 迭代表（prompt v1→vN 召回率）③ 成本数据（单章 ¥0.X、二次零成本）④ 3 分钟演示视频（丢课件→三件套→Obsidian 复习）
- [ ] 期末作业叙事定稿：「个性化学习系统」，备考是第一个场景
- [ ] `git tag v1.0`

**验收**：插件可用；README 拿出手；能讲 20 分钟。

---

## v1.5 / v2.0 个性化备考系统（差异化故事线）

- [ ] v1.5 错题回流：导出 SR 答题记录 → 掌握度按章节聚合 → 薄弱点清单 → 自动生成二轮强化材料（回流理解层）
- [ ] v1.5 音频速览（借鉴 NotebookLM Audio Overview）：考点清单 → TTS 播客式音频，通勤场景
- [ ] v2.0 备考编排：输入考试日期 + 各章掌握度 → 动态生成每日复习计划
- [ ] v2.0 彩蛋·风格画像：喂历年题/作业 → 考点排序加权（无历年题数据则不做，明确写进局限）
- [ ] v2.0+ 多源引用问答（借鉴 NotebookLM）：**仅当**出现跨课程问答真实需求时再做；单课程场景维持不上 RAG 的决策

> 竞品对照备忘（2026-10-02）：与 NotebookLM 表面功能重叠，但三个差异立身——① 国内直连+数据不出本机（NotebookLM 需翻墙+传 Google）；② SR 间隔重复+错题回流闭环（NotebookLM 卡片一次性无排程）；③ eval/防幻觉/成本可验证（NotebookLM 黑盒）。答辩被问「和 NotebookLM 区别」就按这三条答。

---

## 每版通用检查单（复制到每版开工时）

- [ ] 跑 eval 回归，确认基线无回退
- [ ] 本版改动不碰已冻结的金标准
- [ ] 新功能对应 manifest 有新指标（可观测）
- [ ] 收尾：回归通过 → commit → `git tag vX.X` → 更新 `eval/history.md`
