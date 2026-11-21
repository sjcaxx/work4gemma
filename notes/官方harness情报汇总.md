# 官方 harness 情报汇总（来自 GitHub 开源审计仓库）

来源：
- `Yuxiang-Ren-HUB/gemma4-graph-toolkit-audit`（图工具审计，129 公开任务）
- `bsw0610/gemma4-swe-harness-audit`（harness 审计 + localize-code skill）
- `JGM-droid/Gemma-coding-agent`（真实端到端跑通的工程记录）
> 均已 clone 到 `examples/refs/`

---

## 1. 官方库/组件名（wheelhouse）

Kaggle 数据集 `metric/gemma-4-developer-agent-wheelhouse` 提供：
- `swegemma`（**0.2.7** 与 **0.2.11** 两个版本；0.2.11 于 2026-10-12 发布）
- `adk_submission-0.2.11`
- `adk_eval_core-0.1.0`
- `google_adk-1.36.1`
- `google_genai-2.11.0`

官方图工具真实实现：`swegemma.graph.{graph_utils, embedding_utils, retrieval_utils}`
- `graph_utils.get_graph(repo, graph_dir=, embeddings_dir=, base_commit=)`
- `graph_utils.resolve_node_name(name, graph)`
- `graph_utils.get_neighbor(node, graph=, edge_type=)`
- `retrieval_utils.get_similar_nodes(query, repo_name=, k=, graph_dir=, embeddings_dir=, base_commit=)` -> list of {"node_name": ...}
- `embedding_utils.embed(node_id, repo, embeddings_dir=, base_commit=)`

---

## 2. 数据集真相（129 公开任务）

| 项 | 值 |
|---|---|
| 仓库分布 | fastapi 67 / rich 48 / requests 13 / httpx 1 |
| gold patch 中位改动 | **1 个文件，+8/-2 行**（很小！） |
| 含可提取标识符的 issue | 120/129 (93%) |
| 含反引号代码 | 76/129 (58.9%) |
| hints_text 非空 | **0/129**（全空） |
| 中位 issue 长度 | 58 词 |

图 & embedding：
- 127 个图；**367,985 节点 / 452,588 边**
- 边类型**只有 `calls`**
- **38.3% 节点孤立**（无边）
- **100% 节点有 256 维 embedding**
- 11.3% 节点 body text 缺失

gold symbol 覆盖：
- 115/129 (89.1%) 任务的 gold 函数/类出现在图里
- 522 个 gold 符号

---

## 3. 官方图工具的真实表现（关键！）

**hit@k（能否命中 gold symbol，分母 115 个有 gold 在图里的任务）：**

| 策略 | hit@10 | hit@50 | hit@100 |
|---|---|---|---|
| 0.2.7 工具（issue 标识符作种子） | 2 | 2 | 2 |
| 0.2.11 resolver + 1-hop 邻居 | 30 | 35 | 35 |
| 0.2.11 resolver + 语义搜索（含词法回退） | 42 | 55 | 62 |
| 0.2.11 search_similar_code（整段 issue，仅词法回退） | 32 | 64 | 84 |
| **自建 BM25 over AST span** | **51** | **83** | **98** |

**按 query 形态（表 D）：**
| Query 形态 | 解析命中 gold | Top-10 命中 |
|---|---|---|
| 完整 issue（NL） | **0%** | 32.2% |
| issue 首行 | 0% | 35.7% |
| gold patch 代码片段 | 0% | 37.4% |
| top-5 关键词 | 6.1% | 31.3% |
| 提取的标识符（shim） | 27.0% | 35.7% |
| gold 裸名字（oracle） | 100% | 41.7% |

**核心教训：**
1. **整段 issue 直接丢给 search_similar_code → 解析 gold 命中 0%**（只有 top-10 32%）
2. **必须先提取标识符（函数名/类名/代码片段）当查询**，命中率 27%/47%
3. `edge_type` 过滤无效：`calls` == `CALLS` == 无过滤（1866）；文档里的 `DEFINED_IN`/`IMPORTS` **返回 0**（静默失败）
4. 官方工具的 embedding 经常是"词法回退"（lexical fallback），质量差
5. **自建 BM25 检索大幅优于官方工具**

---

## 4. 上下文溢出是头号杀手

- 默认 `max_output_tokens=16384`：120 任务里 **26 个 run 因 ContextWindowExceededError 崩溃**
- 减半后崩溃全消失，resolved 从 29→34/80（+6.2pp）
- 实例：`rich_4079` 请求 34,722 tokens > 32,768 context → 失败
- 0.2.11 在溢出时会提交"半成品"patch

---

## 5. 官方 CLI 与预算

```bash
swegemma eval --tasks tasks.jsonl --snapshots-dir snapshots \
  --submission-dir sample_submission --results-dir results \
  --image swebench-sandbox:latest --sandbox docker \
  --models-yaml dev_models.yaml \
  --task-id <id> --max-tool-calls 30 --max-time-minutes 20 --concurrency 1 \
  --display single --verbose
```
- **官方 CLI 不读 `eval_config.yaml`**（只有 Kaggle 推理脚本读）；CLI 用 flags 设预算
- 沙箱：`subprocess` 或 `docker`（`swebench-sandbox:latest`）
- `--skip-agent-patch` 可只验证 test_patch 基线

**dev models.yaml 映射**（本地小模型冒充官方名）：
```yaml
models:
  gemma-4-31b-it-qat-w4a16-ct: {path: openai/gemma-4-e4b-it, api_base: http://127.0.0.1:8080/v1}
  main_lora:                   {path: openai/gemma-4-e4b-it, api_base: http://127.0.0.1:8080/v1}
  tool_lora:                   {path: openai/gemma-4-e4b-it, api_base: http://127.0.0.1:8080/v1}
```

---

## 6. 模型与硬件

- 官方 31B 权重需 **~16-18 GB VRAM**；E4B Q4_0 GGUF 约 5.15 GB，可 32K context 跑
- 本地 dev 用 `google/gemma-4-E4B-it-qat-q4_0-gguf`（Apache-2.0，不需要 gated 权限！）
- 推理：llama.cpp server (OpenAI 兼容) 或 vLLM
- 官方 parser 是 vLLM `gemma4` parser，llama.cpp 的模板解析**不完全一致**

## 7. 数据体积
- 完整数据集 **524 文件 / 22.42 GB**
- 最小子集（1 个任务）约 45 MB：`HARNESS_README.md`, `tasks.jsonl`, `docker/`, `sandbox/setup.py`, `sample_submission/`, 1 个 snapshot + graph + embedding, 4 个 wheel

---

## 8. 可直接复用的资源
- `bsw0610/.../skill/localize-code/`：**纯标准库 BM25 代码定位**，默认 top-15 命中 51.3%
- `bsw0610/.../analysis/gold_core.py`：diff 行 → 所在函数/类
- `bsw0610/.../analysis/trace_metrics.py`：分析 harness trace
- `bsw0610/.../results/c3_run_rows.csv`：320 次参考跑分基线
