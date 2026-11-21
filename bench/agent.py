"""Gemma 4 编码 agent 循环（本地 Ollama 驱动，复刻官方工具集）。

设计约束来自公开审计数据（见 notes/官方harness情报汇总.md）:
  1. 整段 issue 直接喂检索 -> gold 命中 0%。提示词强制"先提取标识符再检索"。
  2. 上下文溢出会崩。输出 token 限制 + 工具输出截断。
  3. 官方边类型只有 calls，别指望 edge_type 过滤。

对外接口（run_eval.py 依赖）:
  make_agent(repo_root).solve(problem_statement) -> patch_text
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codetools import AgentTools, CodeGraphBuilder  # noqa: E402
from codetools.context_budget import prepare_messages  # noqa: E402

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "gemma4:e4b"
MAX_STEPS = 24
NUM_CTX = 32768
# thinking 会生成上千 token 的推理内容(单步可达 70s), 但对工具调用决策无帮助;
# 关闭后同一任务快 2~9 倍且工具调用正常。实测见 bench/README.md。
USE_THINKING = False
MAX_OUTPUT_TOKENS = 4096
MAX_TOOL_OUTPUT = 6000

SYSTEM_PROMPT = """You are an autonomous software engineer fixing a bug in a Python repository.

## Mandatory workflow
1. EXTRACT identifiers from the issue: function names, class names, error messages,
   file paths, backticked code. Quote them exactly.
2. LOCATE code: use `search_similar_code` with a query built from those identifiers
   (NOT the whole issue text).
3. READ the most relevant files before changing anything.
4. Make the MINIMAL fix. Small patches win: the median real fix is 1 file, ~8 lines.
5. RUN the most relevant tests with run_command (e.g. `python -m pytest tests/test_x.py -q`).
6. If tests fail, read the error and fix again.
7. Call submit_patch when the tests pass. This ends the task.

## Rules
- Never rewrite whole files. Use edit_file with a small unique old_string.
- Do not modify test files; they are the grading oracle.
- If search_similar_code returns nothing useful, fall back to `run_command("grep -rn ...")`.
- Keep tool outputs short; do not dump entire large files.

## Tools
- read_file(filepath, start_line, end_line)
- edit_file(filepath, old_string, new_string)
- write_file(filepath, content)
- run_command(command)
- get_code_neighbors(node, edge_type, max_neighbors)
- search_similar_code(query, k)
- get_code_subgraph(nodes)
- submit_patch()
"""

# 暴露给模型的官方 9 工具 schema
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file with 1-indexed line slice.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace old_string with new_string in filepath. old_string must be unique unless allow_multiple.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                    "allow_multiple": {"type": "boolean"},
                },
                "required": ["filepath", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["filepath", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the repository root. Returns exit_code and output.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_code_neighbors",
            "description": "Show call-graph neighbors of a node.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "edge_type": {"type": "string"},
                    "max_neighbors": {"type": "integer"},
                },
                "required": ["node"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_similar_code",
            "description": "Semantic/lexical search over code nodes. Prefer extracted identifiers over long prose.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_code_subgraph",
            "description": "Show the induced subgraph over a list of node ids/names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nodes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["nodes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "Report budget usage and patch status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_patch",
            "description": "Finalize the task and return the git diff. Call this only when the fix is ready.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class GemmaAgent:
    def __init__(self, repo_root: str, model: str = MODEL, url: str = OLLAMA_URL):
        self.repo_root = repo_root
        self.model = model
        self.url = url
        graph = CodeGraphBuilder(repo_root).build()
        self.tools = AgentTools(repo_root, graph=graph)
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.tool_schemas = TOOL_SCHEMAS
        self.n_llm_calls = 0
        self.n_tool_calls = 0
        self.trace_dir = ROOT / "dist" / "context_traces" / uuid.uuid4().hex
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.request_index = 0
        self.tool_index = 0


    # ---- Ollama 调用 ----
    def _chat(self) -> dict[str, Any]:
        self.request_index += 1
        trace = self.trace_dir / f"request-{self.request_index:04d}.json"
        # Archive BEFORE compaction; even a rejected request remains inspectable.
        record = {"full_messages": self.messages, "model": self.model, "backend_url": self.url}
        trace.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            outgoing, stats = prepare_messages(
                self.messages, self.tool_schemas,
                NUM_CTX - MAX_OUTPUT_TOKENS - 2048, str(trace),
            )
        except ValueError as error:
            record["error"] = str(error)
            trace.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            raise
        record.update(stats)
        record["sent_messages"] = outgoing
        trace.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        payload = {
            "model": self.model,
            "stream": False,
            "messages": outgoing,
            "tools": self.tool_schemas,
            "think": USE_THINKING,
            "options": {
                "num_ctx": NUM_CTX,
                "num_predict": MAX_OUTPUT_TOKENS,
                "temperature": 0.2,
            },
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read())
        record["server_usage"] = {key: result[key] for key in (
            "prompt_eval_count", "eval_count", "prompt_eval_duration", "eval_duration"
        ) if key in result}
        trace.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    # ---- 工具执行 ----
    def _run_tool(self, name: str, args: dict[str, Any]) -> str:
        fn = getattr(self.tools, name, None)
        if fn is None:
            return f"error: unknown tool '{name}'"
        try:
            out = fn(**args) if args else fn()
        except TypeError as e:
            return f"error: bad arguments for {name}: {e}"
        except Exception as e:  # noqa: BLE001
            return f"error: {name} failed: {e}"
        out = "" if out is None else str(out)
        self.tool_index += 1
        artifact = self.trace_dir / f"tool-{self.tool_index:04d}.txt"
        artifact.write_text(out, encoding="utf-8")
        # The patch is the deliverable, not history: never truncate it.
        if name == "submit_patch":
            return out
        if len(out) > MAX_TOOL_OUTPUT:
            out = out[:MAX_TOOL_OUTPUT] + f"\n... [truncated, {len(out)} chars total; full output: {artifact}]"
        return out

    def solve(self, problem_statement: str) -> str:
        self.messages.append(
            {
                "role": "user",
                "content": (
                    "Fix this issue in the repository. Follow the mandatory workflow.\n\n"
                    f"<issue>\n{problem_statement}\n</issue>"
                ),
            }
        )

        for step in range(MAX_STEPS):
            try:
                data = self._chat()
            except Exception as e:  # noqa: BLE001
                print(f"  [llm error] {e}", file=sys.stderr)
                return ""

            self.n_llm_calls += 1
            msg = data.get("message", {})
            calls = msg.get("tool_calls") or []
            content = (msg.get("content") or "").strip()

            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
            if calls:
                assistant_msg["tool_calls"] = calls
            self.messages.append(assistant_msg)

            if not calls:
                # 模型没调工具，直接要 patch
                self.messages.append(
                    {
                        "role": "user",
                        "content": "If the fix is complete, call submit_patch. Otherwise continue with a tool call.",
                    }
                )
                continue

            for call in calls:
                f = call.get("function", {})
                name = f.get("name", "")
                raw = f.get("arguments", {})
                args = raw if isinstance(raw, dict) else _safe_json(raw)

                # submit_patch 是终止信号
                if name == "submit_patch":
                    result = self._run_tool("submit_patch", args)
                    print(f"  [submit after {step+1} steps]", file=sys.stderr)
                    return result if not result.startswith("error") else ""

                self.n_tool_calls += 1
                result = self._run_tool(name, args)
                print(f"  [tool] {name}({_short(args)}) -> {len(result)} chars", file=sys.stderr)
                self.messages.append(
                    {"role": "tool", "tool_name": name, "content": result}
                )

        # 超步数：再要一次 patch
        print(f"  [max steps {MAX_STEPS} reached]", file=sys.stderr)
        return self._run_tool("submit_patch", {})


def _safe_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw or "{}")
        return v if isinstance(v, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _short(args: dict[str, Any], n: int = 60) -> str:
    s = json.dumps(args, ensure_ascii=False)
    return s[:n] + "..." if len(s) > n else s


def make_agent(repo_root: str) -> GemmaAgent:
    return GemmaAgent(repo_root)


if __name__ == "__main__":
    # 手动冒烟：对一个任务跑一次
    task_file = ROOT / "bench" / "tasks" / "tasks.jsonl"
    tasks = [json.loads(l) for l in open(task_file, encoding="utf-8") if l.strip()]
    tid = sys.argv[1] if len(sys.argv) > 1 else tasks[0]["instance_id"]
    task = next(t for t in tasks if t["instance_id"] == tid)

    import subprocess
    import tempfile

    repo = ROOT / "examples" / "repos" / "rich"
    wt = Path(tempfile.mkdtemp()) / "wt"
    subprocess.run(
        ["git", "worktree", "add", "--force", "--detach", str(wt), task["base_commit"]],
        cwd=repo, check=True, capture_output=True,
    )
    print(f"任务 {tid}: {task['problem_statement'][:100]}", file=sys.stderr)
    agent = make_agent(str(wt))
    patch = agent.solve(task["problem_statement"])
    print(f"\n=== 补丁 ({patch.count(chr(10))} 行) ===")
    print(patch)
    print(f"LLM 调用 {agent.n_llm_calls}, 工具调用 {agent.n_tool_calls}")
