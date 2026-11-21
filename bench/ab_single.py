"""单任务 A/B 对比：thinking 开/关的 速度 vs 准确率。

跑同一条任务两次（use_thinking=False / True），各自判分（应用补丁+pytest），
输出 耗时 / 补丁行数 / PASS-FAIL 对比表。

用法: python bench/ab_single.py [instance_id]
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
import build_tasks as B  # noqa: E402
import run_eval as R  # noqa: E402


def run_once(task, repo, use_thinking: bool) -> dict:
    A.USE_THINKING = use_thinking
    tmp = Path(tempfile.mkdtemp())
    wt = tmp / "wt"
    subprocess.run(
        ["git", "worktree", "add", "--force", "--detach", str(wt), task["base_commit"]],
        cwd=repo, check=True, capture_output=True,
    )
    try:
        t0 = time.time()
        ag = A.GemmaAgent(str(wt))
        patch = ag.solve(task["problem_statement"])
        elapsed = time.time() - t0

        resolved = False
        note = ""
        if not patch.strip():
            # 无补丁：worktree 可能被 agent 直接改过，仍以 diff 是否为空为准
            note = "empty_patch"
        elif not B._apply_patch(wt, task["test_patch"]):
            # agent 已在 worktree 内直接修改文件，补丁内容即当前状态，无需再应用 agent 补丁
            note = "test_patch_apply_failed"
        else:
            ok, out = R.run_pytest(wt, task["changed_test_files"])
            resolved = ok
            if not ok:
                note = out.strip().splitlines()[-1][:70] if out.strip() else "fail"

        return {
            "thinking": use_thinking,
            "seconds": round(elapsed, 1),
            "patch_lines": patch.count("\n"),
            "resolved": resolved,
            "note": note,
            "llm_calls": ag.n_llm_calls,
            "tool_calls": ag.n_tool_calls,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        subprocess.run(["git", "worktree", "prune"], cwd=repo, capture_output=True)


def main():
    tasks = [json.loads(l) for l in open(ROOT / "bench/tasks/tasks.jsonl", encoding="utf-8") if l.strip()]
    tid = sys.argv[1] if len(sys.argv) > 1 else tasks[0]["instance_id"]
    task = next(t for t in tasks if t["instance_id"] == tid)
    repo = ROOT / "examples" / "repos" / "rich"

    print(f"任务: {tid} — {task['problem_statement'][:80]}")
    print("=" * 78)

    rows = []
    for th in (False, True):
        print(f"\n>>> thinking={th} ...", flush=True)
        rows.append(run_once(task, repo, th))

    print("\n" + "=" * 78)
    print(f"{'thinking':<10}{'耗时(s)':<10}{'补丁行':<8}{'LLM':<6}{'工具':<6}{'结果':<8}备注")
    print("-" * 78)
    for r in rows:
        print(f"{str(r['thinking']):<10}{r['seconds']:<10}{r['patch_lines']:<8}"
              f"{r['llm_calls']:<6}{r['tool_calls']:<6}"
              f"{'PASS' if r['resolved'] else 'FAIL':<8}{r['note']}")

    a, b = rows
    if a["seconds"] and b["seconds"]:
        print(f"\n关闭 thinking 提速 {b['seconds']/max(a['seconds'],0.1):.1f}x")
    print(f"准确率: thinking=False {int(a['resolved'])}/1, thinking=True {int(b['resolved'])}/1")


if __name__ == "__main__":
    main()