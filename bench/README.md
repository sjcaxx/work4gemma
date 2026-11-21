# 本地 mini-benchmark（复刻官方 SWE-bench 范式）

官方评测 = SWE-bench 范式：给 issue + base_commit 快照 → agent 出补丁 → 应用官方 test_patch → pytest → PASS/FAIL。
本目录在本地用**同款仓库（rich）的真实 git 历史**造同结构任务，用于量化 agent 表现。

## 产物

- `tasks/tasks.jsonl` — **15 个任务**，字段与官方一致：
  `instance_id / repo / base_commit / problem_statement / hints_text / patch / test_patch`
- `results/oracle.json` — 判分器自检结果（15/15）

## 用法

```bash
source .venv/bin/activate

# 1. 造任务（已跑过，产物在 tasks/）
python bench/build_tasks.py --limit 15 --scan 700 --workers 6

# 2. 验证判分器（标准答案应 15/15）
python bench/run_eval.py --oracle

# 3. 跑真实 agent
python bench/run_eval.py --limit 5
```

## 质量校验（与官方一致）

每个任务入池前必须双检：

| 检查 | 要求 | 含义 |
|---|---|---|
| **Fail-to-Pass** | base + test_patch → pytest **FAIL** | bug 真实存在 |
| **Pass-to-Pass** | base + test_patch + patch → pytest **PASS** | 测试与参考修复正确 |

判分器本身三向自检：

| 输入 | 结果 |
|---|---|
| 参考修复（oracle） | 15/15 PASS |
| 无关可应用补丁 | 0/3 PASS |
| 不可应用补丁 | 0/5 PASS |

## 已知环境坑

1. **依赖版本漂移**：rich 的历史测试对 Pygments 颜色码敏感（2.21.0 vs 当时版本）。
   这类任务会以 `test_fails_with_fix` 被自动拒绝——不是我们的 bug。
   `scan=700 → 41 候选 → 15 合格`，拒绝率 ~20%（`test_passes_without_fix` 4 / `test_fails_with_fix` 12）。
2. **必须装齐运行时依赖**：`markdown-it-py`、`pygments`、`attrs`、`pytest-asyncio`，否则大量假失败。
3. **`PYTHONDONTWRITEBYTECODE=1`**：否则 pytest 生成的 `.pyc` 会污染 git 状态。
4. **worktree 用绝对路径**：相对路径会触发 `FileNotFoundError`。

## 当前 15 个任务

| instance_id | 涉及文件 | issue 摘要 |
|---|---|---|
| rich_b17c6169 | console, logging, segment, theme | perf: reduce import time by deferring imports |
| rich_39ee57df | console.py | fix background style with soft wrap |
| rich_95fe8ff5 | prompt.py | Fix raw markup printed on prompt errors |
| rich_0c271d5b | _inspect.py | Handle unusual `__qualname__` in inspect |
| rich_30e5ed61 | panel.py | fix(panel): title missing panel background |
| rich_16b38304 | table.py | fix(table): highlight columns added by add_row |
| rich_be42f1b0 | cells.py | box drawing characters |
| rich_f591471c | highlighter.py | Fix @ breaks highlighting in hyperlink #3327 |
| rich_f021979c | ansi.py | Strip problematic private escape sequences |
| rich_15cc59b1 | prompt.py | refactor to 'case_sensitive' with default True |
| rich_92e71647 | _export_format.py | Fix inline styles in HTML export #3104 |
| rich_d9eff2aa | repr.py | Fixed issue with custom classes #2875 |
| rich_e9c9e434 | style.py | Clear hashed cache when clearing meta |
| rich_1ebf8230 | console.py | avoid FORCE_COLOR implying a terminal in Jupyter |
| rich_aa092929 | segment.py | fix issue splitting segments |

## 与官方的差异（须知）

- 官方 `problem_statement` 是**人工筛选的 issue**，我们用的是 **commit message**（信息量更低、更"内部"）。
  因此本 benchmark 的难度**分布不同**，分数不能直接外推到官方 129 题。
- 官方提供 `snapshots/*.tgz` 和预建图/embedding；这里用 `git worktree` + 现场建图。
- 官方的依赖环境由 Docker 镜像固定；本地是共享 venv，版本漂移会导致部分任务失真。

---

## Baseline v1（2026-11-13）

**`1/15 PASS (6.7%)`** — 结果文件 `results/baseline_v1.json`

| 指标 | 值 |
|---|---|
| PASS 率 | 1/15 (6.7%) |
| 平均耗时 | 164s（中位 153s） |
| 平均补丁行数 | 21.2 |
| 零补丁任务 | 3 |

配置：`USE_THINKING=False`, `MAX_OUTPUT_TOKENS=4096`, `MAX_STEPS=24`, Ollama `gemma4:e4b`。

唯一 PASS：`rich_e9c9e434`（Clear hashed cache when clearing meta，71.9s）。

### 失败归因

| 类别 | 数量 | 说明 |
|---|---|---|
| 逻辑改错（断言不符） | 7 | 改了但没改对，如 `rich_15cc59b1` 改 `case_sensitive` 却没改调用点 → `AttributeError` |
| 语法错误（改坏代码） | 1 | `rich_16b38304` 把 `table.py` 改出语法错误 |
| 未产出补丁 | 3 | 24 步用满仍未 edit，`submit_patch` 返回 `NO_PATCH` |
| 环境/测试无关 | 4 | 如 `rich_b17c6169` 的 `OSError: pytest: reading from stdin`（交互测试） |

### 已修复的判分器 bug

1. **补丁重复应用**：agent 在 worktree 内直接改文件后，`submit_patch` 返回的 diff 是快照；
   原判分器再次 apply 同一 diff → `patch does not apply` → 假失败。
   修复：先 `git status --porcelain` 判断 worktree 是否已脏，脏则跳过 apply。
2. **错误消息当补丁**：`submit_patch` 无改动时返回 `NO_PATCH: ...`，被判分器当 diff 应用。
   修复：识别 `NO_PATCH` / `error:` 前缀，且要求补丁以 `diff --git` 或 `--- ` 开头。

这两处 bug 曾让 3/15 任务被误判为「补丁应用失败」，实际是真实失败。
