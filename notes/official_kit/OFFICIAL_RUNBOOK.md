# Official Kaggle Runbook

目标：只使用 Kaggle 官方 Linux、官方 harness、官方模型运行；本地只负责准备提交包和保存版本记录。

## 运行前

```bash
cd /Users/jiamingwei/gitCode/kaggle/notes/official_kit
bash scripts/package.sh
shasum -a 256 submission.zip > submission.zip.sha256
```

记录以下内容：

- Git commit：`git -C /Users/jiamingwei/gitCode/kaggle rev-parse HEAD`
- submission 包 SHA-256：`submission.zip.sha256`
- 运行时间和 Kaggle Notebook 版本
- 使用的任务数据集版本
- 使用的官方 wheelhouse 数据集版本

`submission.zip` 和校验文件只作为本次运行的输入，不直接修改。

## 官方提交要求（以官方 harness 文档为准）

官方提交包必须是一个 ZIP，且 `agent.yaml` 位于 ZIP 根目录。配置中的 `!include` 路径相对于包含它的 YAML 文件解析，不能通过路径遍历访问提交包之外的文件。

`agent.yaml` 及 `sub_agents/*.yaml` 中的 Agent 必须使用官方允许的模型；当前配置使用：

```yaml
model: gemma-4-31b-it-qat-w4a16-ct
```

工具只能是官方 harness 工具或通过 `agent_tool` 引用的自定义子 Agent。当前多 Agent 设计使用的是 `agent_tool`：

```yaml
tools:
  - agent_tool:
      config_path: sub_agents/architect.yaml
```

这与 ADK 原生 `sub_agents:` 层级转交不同；本项目刻意让 Project Manager 通过工具返回值控制调度。`agent_tool` 的返回值是正式 Agent 交接，临时文件不是正式交接渠道。

官方工具的路径边界：

```text
read_file / write_file / edit_file  -> /workspace 内的仓库路径
run_command                         -> 在 sandbox 中执行 shell，可读写 /tmp
```

因此不能用 `write_file` 或 `read_file` 访问 `/tmp`。临时记录只能由 `run_command` 使用 shell/Python 写入 `/tmp`，不能放进 `/workspace`，否则可能被 `submit_patch` 收集进补丁。

参考：

- `notes/official_kit/docs/harness-notes.md`
- `notes/competition_overview_main.md`
- `notes/adk_config.md`

## 本地打包步骤

本地只准备提交包，不运行官方模型或官方评分。执行：

```bash
cd /Users/jiamingwei/gitCode/kaggle/notes/official_kit
bash scripts/package.sh
shasum -a 256 submission.zip > submission.zip.sha256
unzip -t submission.zip
unzip -l submission.zip | head -30
```

脚本 `scripts/package.sh` 会删除旧包，并把 `submission/` 的内容直接压缩到 ZIP 根目录，因此必须确认以下文件位于包根目录：

```text
submission.zip
├── agent.yaml
├── prompts/
├── skills/
├── sub_agents/
└── configs/
```

打包前检查：

```bash
unzip -p submission.zip agent.yaml >/dev/null
unzip -t submission.zip
```

正式运行必须在 Kaggle 官方 Linux 环境完成：上传 `submission.zip`，安装官方 wheelhouse 中的依赖，先运行单题 smoke test，再扩大到多题回归。不要在 macOS 上直接安装或运行 wheelhouse 中的 Linux wheels。


在 Kaggle Notebook 中添加：

1. `gemma-4-developer-agent` 官方比赛数据；
2. `gemma-4-developer-agent-wheelhouse` 官方依赖数据；
3. 本次生成的 `submission.zip`，或将 submission 目录上传为 Notebook 输入。

Notebook 内完成：

```bash
unzip -q /kaggle/input/<submission-input>/submission.zip -d /kaggle/working/submission
mkdir -p /kaggle/working/wheelhouse
cp /kaggle/input/<wheelhouse-input>/*.whl /kaggle/working/wheelhouse/

pip install --no-index --find-links /kaggle/working/wheelhouse \
  swegemma adk-submission adk-eval-core google-adk
```

先只运行一题：

```bash
swegemma eval \
  --tasks /kaggle/input/<official-data>/tasks.jsonl \
  --snapshots-dir /kaggle/input/<official-data>/snapshots \
  --submission-dir /kaggle/working/submission \
  --results-dir /kaggle/working/results/<run-id> \
  --sandbox docker \
  --task-id rich_3063
```

## 必须保存的回溯材料

将以下内容保存到 Kaggle Notebook 输出或独立 Kaggle Dataset 版本：

```text
run_metadata.json
submission.zip.sha256
任务 ID 和数据集版本
完整命令
安装包列表：pip freeze
results/<run-id>/
  task_results.jsonl
  summary.json
  traces/
  patches/
```

`run_metadata.json` 至少包含：

```json
{
  "run_id": "2025-...",
  "git_commit": "...",
  "submission_sha256": "...",
  "task_ids": ["rich_3063"],
  "harness": "official Kaggle environment",
  "data_version": "...",
  "wheelhouse_version": "..."
}
```

## 运行顺序

```text
本地提交包
→ SHA-256 和 Git 记录
→ Kaggle 官方 Notebook
→ 1 题验证加载和运行
→ 保存完整结果和 trace
→ 5 题回归
→ 再决定是否扩大到完整任务集
```

本机下载的 wheelhouse 不作为 macOS 本地运行依赖；保留作下载缓存，但正式安装和运行都在 Kaggle 官方 Linux 环境完成。
