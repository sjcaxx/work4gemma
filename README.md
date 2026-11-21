# CodeArch — Gemma 4 Developer Agent 复现工程

复现 Kaggle **"Google - The Gemma 4 Developer Agent Competition"** 的 SWE-bench 风格编码 agent 环境：
1:1 还原官方 9 个工具 + 代码图/embedding 接口，并搭建本地 mini-benchmark 用于量化评测。

## 快速开始

```bash
bash scripts/bootstrap.sh          # 恢复 venv、依赖、外部仓库
source .venv/bin/activate

python examples/test_tools.py     # 验证 9 个工具
python bench/run_eval.py --oracle # 验证 benchmark 判分器（应 15/15）
```

## 目录结构

```
src/codetools/
├── graph_builder.py   # AST 调用图 → NetworkX MultiDiGraph（与官方 graphs/*.json schema 1:1）
├── tools.py           # AgentTools：官方 9 工具 + localize_code
└── localize.py        # BM25 代码定位（数据证明强于官方 search_similar_code）

bench/
├── build_tasks.py     # 从 git 历史挖 SWE-bench 任务 + Fail-to-Pass/Pass-to-Pass 校验
├── run_eval.py        # 评测 agent，复刻官方 Phase 2 判分
└── tasks/tasks.jsonl  # 15 个 rich 任务

submission_skills/     # 官方 ADK skill 格式（可直接进 submission.zip）
notes/                 # 官方文档抓取 + 情报汇总
examples/              # mini_repo 测试仓库 + 工具验证脚本
```

## 官方 9 个工具

| # | 工具 | 签名 |
|---|---|---|
| 1 | `run_command` | `(command: str) -> str` |
| 2 | `submit_patch` | `() -> str` |
| 3 | `get_status` | `() -> str` |
| 4 | `read_file` | `(filepath, start_line=None, end_line=None) -> str` |
| 5 | `edit_file` | `(filepath, old_string, new_string, allow_multiple=False) -> str` |
| 6 | `write_file` | `(filepath, content) -> str` |
| 7 | `get_code_neighbors` | `(node, edge_type=None, max_neighbors=50) -> str` |
| 8 | `search_similar_code` | `(query, k=10) -> str` |
| 9 | `get_code_subgraph` | `(nodes: list[str]) -> str` |

## 关键情报（来自公开审计仓库）

- 官方 `search_similar_code` 接受整段 issue 时，命中 gold symbol 的比例 **0%**（必须先提取标识符）
- 官方边类型**只有 `calls`**，文档里的 `DEFINED_IN`/`IMPORTS` 过滤返回 0（静默失败）
- 129 公开任务：fastapi 67 / rich 48 / requests 13 / httpx 1；gold patch 中位 **1 文件 +8/-2 行**
- 上下文溢出是头号杀手：默认 `max_output_tokens=16384` 导致 26/120 崩溃；减半后 +6.2pp

## 环境

macOS / Python 3.14 / Ollama `gemma4:e4b`。官方 checkpoint `gemma-4-e4b-it-qat-w4a16-ct` 不可获取，
本地开发用 Ollama MLX 版近似；benchmark 结论不能直接外推到官方隐藏集。

## 上下文保护（2026-11-21）

本地 `bench/agent.py` 在每次 Ollama 请求前检查历史大小，优先缩短旧工具
输出，必要时整组移除旧的调用及其回复，保留原始问题和最近两轮。
无法容纳的原始问题、工具定义或近期调用参数会在请求前明确报错。
完整历史、实际发送内容和服务端返回的 usage 保存在
`dist/context_traces/<run-id>/`；完整工具输出也会保存。最终补丁不截断。

没有部署 Gemma tokenizer 时，预算使用保守的 UTF-8 字节估计加消息开销，
不是实测 token 数。审计文件保留了压缩掉的信息，但模型需要重新读取才能使用；
该策略不保证诊断质量不下降，需要真实任务回归。

运行验证和构建独立的比赛测试包：

```bash
python -m pytest tests --basetemp=.test_tmp_context -q
python scripts/build_context_variant.py
```

独立测试包：`dist/context_variant/submission.zip`。原提交包和原始提交目录
不变。比赛测试版保留相同模型、角色、工具和任务预算，将输出上限从 16384
降为 8192，保留 4096 思考预算但关闭 `include_thoughts`，并约束工具读取和
角色交接的内容。交接长度规则属于提示词约束，不是程序强制截断。

对照结果：`dist/context_guard_ab.json`。该测试使用脚本模拟模型回复并限制
请求字节数，实际执行读文件、编辑、pytest、导出补丁；不是 Gemma 推理或
Kaggle 得分。

## 真实 Gemma 官方环境测试（2026-11-21）

已使用官方 Gemma 4 31B QAT、4 张 L4 完成 3 道题 × 4 组真实推理。
原配置和仅关闭思考历史的配置各发生一次上下文超限；输出上限降至 8192
的两组在这三道题上未观察到超限。但四组均 0/3，12 次都在调查阶段消耗完
5 分钟，补丁均未修改产品源码；Requests 另有验证环境错误。
这验证了输出预算的缓解作用，尚未验证修复能力提升。

结果、逐轮原始证据、实际执行 Notebook、复算脚本和下一步分析均位于
[experiments/context-budget-20261121](experiments/context-budget-20261121)。
先看 [分析与建议](experiments/context-budget-20261121/ANALYSIS.txt)，
复查步骤见 [REPRODUCE.txt](experiments/context-budget-20261121/REPRODUCE.txt)。
本次没有新增比赛提交，测试结果不是 Kaggle 排行榜得分。
