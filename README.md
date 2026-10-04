# study-agent 使用指南

个性化学习系统 v0.1：文字型课件 PDF → 统一知识模型 → 考点清单。
架构设计与迭代路线见 `../coursework-agent-architecture.md`，构建与调试细节见 `../study-agent-build-guide.md`。

## 安装（一次性）

```bash
cd study-agent
C:\Users\john\.local\bin\uv.exe sync
```

配置密钥（二选一，本机禁 cmd 改注册表）：
- 系统设置 → 高级 → 环境变量 → 用户变量新增 `DEEPSEEK_API_KEY`（设完**重开终端**生效）
- 或 PyCharm Run Configuration → Environment variables

## 命令

```bash
C:\Users\john\.local\bin\uv.exe run study-agent run <文件> [选项]
```

| 选项 | 默认 | 说明 |
|---|---|---|
| `--course` | 未命名课程 | 课程名，写入产物标题 |
| `--chapter` | 文件名 | 章节名 |
| `--mode` | exam | `exam` 考频加权 / `selfstudy` 概念中心性（v0.5 完整启用） |
| `--out` | build | 产物目录 |

示例：

```bash
C:\Users\john\.local\bin\uv.exe run study-agent run "第1章课件.pdf" --course "数据采集与挖掘"
```

## 输出（`build/` 目录）

| 文件 | 内容 | 用途 |
|---|---|---|
| `<章节>.md` | 提取的文本，带 `<!-- pN -->` 页码锚点 | 中间产物，**可人工修正后重跑** |
| `<章节>.concepts.json` | 统一知识模型（概念/考点/易错点/自测题） | 三种产物的单一事实源 |
| `考点清单-<章节>.md` | 最终产物（自测题答案折叠，先答后看） | 直接入库 Obsidian |
| `manifest.json` | 块数 / 缓存命中 / span 丢弃数 / 条目统计 | 质量监控 |

## 典型工作流

**1. 日常处理一章课件**：跑命令 → 看 `考点清单-*.md` → 扫一眼 `manifest.json` 的 `span_dropped`（丢弃多说明 LLM 在编证据，要调 prompt）。

**2. 调 prompt 迭代**：改 `prompts/extract_concepts.md` → **删掉 `build/.cache/`**（缓存 key 不含 prompt，不清会命中旧结果）→ 重跑 → 对照 `eval/` 金标准看召回率。

**3. 提取有乱码/错字**：手改 `build/<章节>.md` → 临时注释 `cli.py` 中 `extract_markdown` 一行 → 重跑（只走下游，缓存未命中部分才调 LLM）。

**4. 查看 LLM 原始返回**：`build/.cache/understand/*.json` 就是每个分块的原始 JSON，调 prompt 时直接看。

## 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| `未设置 DEEPSEEK_API_KEY` | 环境变量没配或没重开终端 | GUI 配好后**重开终端/PyCharm** |
| `NotImplementedError: 无文本层` | 图片型 PDF | v0.1 不支持，换文字型课件（v0.2 接 OCR） |
| `uv: command not found` | uv 不在 PATH | 用绝对路径 `C:\Users\john\.local\bin\uv.exe` |
| 考点清单条目很少 | span 校验大量丢弃 | 看 `manifest.json` 的 `span_dropped`；查 `.cache/understand/` 原始返回 |
| `JSONDecodeError` | LLM 返回非 JSON | 重跑一次；频繁发生则在 prompt 里加强「只输出 JSON」 |
| 第二次跑同一文件秒回 | 缓存全命中 | 正常现象，不是没跑 |

## 目录结构

```
study-agent/
├── pyproject.toml          # 项目与依赖（pypdf + httpx）
├── prompts/                # LLM prompt（版本化管理）
│   └── extract_concepts.md
├── eval/                   # 金标准考点清单 + 回归记录
└── src/study_agent/
    ├── cli.py              # 入口
    ├── model.py            # 知识模型 + verify_spans 防幻觉
    ├── cache.py            # 内容哈希缓存
    ├── extract/            # 提取层（adapter 模式）
    ├── understand/         # 理解层（分块 → LLM → 合并 → 校验）
    └── render/             # 产出层（渲染器模式）
```
