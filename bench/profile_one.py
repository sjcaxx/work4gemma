"""单任务计时剖析：每步 LLM / 工具耗时 + 上下文规模。

只做观测，不改 agent.py / run_eval.py。
用法: python bench/profile_one.py [instance_id] [max_steps]
"""

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(ROOT / "src"))

import agent as A  # noqa: E402


def main():
    tasks = [json.loads(l) for l in open(ROOT / "bench/tasks/tasks.jsonl", encoding="utf-8") if l.strip()]
    tid = sys.argv[1] if len(sys.argv) > 1 else tasks[0]["instance_id"]
    max_steps = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    task = next(t for t in tasks if t["instance_id"] == tid)

    repo = ROOT / "examples" / "repos" / "rich"
    tmp = Path(tempfile.mkdtemp())
    wt = tmp / "wt"
    subprocess.run(
        ["git", "worktree", "add", "--force", "--detach", str(wt), task["base_commit"]],
        cwd=repo, check=True, capture_output=True,
    )

    print(f"任务: {tid}")
    print(f"issue: {task['problem_statement'][:100]}")
    print("=" * 70)

    T0 = time.time()
    t_build = time.time()
    ag = A.GemmaAgent(str(wt))
    print(f"[setup] 建图+工具: {time.time()-t_build:.1f}s  "
          f"nodes={ag.tools.graph.g.number_of_nodes()} edges={ag.tools.graph.g.number_of_edges()}")
    print("-" * 70)

    ag.messages.append({
        "role": "user",
        "content": "Fix this issue in the repository. Follow the mandatory workflow.\n\n"
                   f"<issue>\n{task['problem_statement']}\n</issue>",
    })

    patch = ""
    no_tool_streak = 0
    for step in range(1, max_steps + 1):
        # ---- LLM ----
        t0 = time.time()
        try:
            data = ag._chat()
        except Exception as e:  # noqa: BLE001
            print(f"[step {step}] LLM ERROR: {e}")
            break
        t_llm = time.time() - t0

        msg = data.get("message", {})
        calls = msg.get("tool_calls") or []
        content = (msg.get("content") or "").strip()
        think = (msg.get("thinking") or "")

        gen = data.get("eval_count") or 0
        prm = data.get("prompt_eval_count") or 0
        print(f"[step {step}] LLM {t_llm:6.1f}s | gen={gen:4} tok | "
              f"prompt={prm:6} tok | "
              f"think={len(think)}c | tools={[c['function']['name'] for c in calls]}")

        am = {"role": "assistant", "content": content}
        if calls:
            am["tool_calls"] = calls
        ag.messages.append(am)

        if not calls:
            no_tool_streak += 1
            print(f"          ↳ 无工具调用 (连续 {no_tool_streak} 次)")
            if no_tool_streak >= 2:
                print("          ↳ 强制结束")
                break
            ag.messages.append({
                "role": "user",
                "content": "If the fix is complete, call submit_patch. Otherwise continue with a tool call.",
            })
            continue

        no_tool_streak = 0

        # ---- 工具 ----
        for call in calls:
            f = call.get("function", {})
            name = f.get("name", "")
            raw = f.get("arguments", {})
            args = raw if isinstance(raw, dict) else A._safe_json(raw)

            if name == "submit_patch":
                t0 = time.time()
                patch = ag.tools.submit_patch()
                print(f"          ↳ submit_patch {time.time()-t0:.1f}s -> {len(patch)}c")
                break

            t0 = time.time()
            res = ag._run_tool(name, args)
            t_tool = time.time() - t0
            ctx = sum(len(str(m.get("content", ""))) for m in ag.messages)
            print(f"          ↳ {name}({A._short(args, 50)}) {t_tool:5.1f}s "
                  f"-> {len(res)}c | ctx={ctx}c")
            ag.messages.append({"role": "tool", "tool_name": name, "content": res})

        if patch:
            break

    total = time.time() - T0
    print("=" * 70)
    print(f"总耗时: {total:.1f}s | LLM 调用 {ag.n_llm_calls} | 工具调用 {ag.n_tool_calls}")
    print(f"补丁: {patch.count(chr(10))} 行")
    if patch:
        print("-" * 70)
        print(patch[:1500])

    shutil.rmtree(tmp, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=repo, capture_output=True)


if __name__ == "__main__":
    main()