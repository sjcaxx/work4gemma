"""在本地 mini-benchmark 上评测 agent：复刻官方 Phase 2 判分。

对每个任务:
  1. git worktree 到 base_commit
  2. 调用 agent_fn(repo_root, problem_statement) -> patch_text
  3. 应用 agent 补丁 + 官方 test_patch
  4. 跑 test_patch 涉及的测试文件
  5. 全过 -> PASS (resolved=True)

用法:
  python bench/run_eval.py --tasks bench/tasks/tasks.jsonl --limit 5
  python bench/run_eval.py --tasks bench/tasks/tasks.jsonl --oracle   # 用标准答案验证判分器
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(ROOT / "src"))

import build_tasks as B  # noqa: E402


def run_pytest(worktree: Path, test_files: list[str], timeout: int = 180) -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *test_files],
            cwd=worktree, capture_output=True, text=True, timeout=timeout, env=env,
        )
        out = (res.stdout + res.stderr)[-3000:]
        return res.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "[timeout]"


def evaluate_one(task: dict, repo: Path, work_root: Path, agent_fn) -> dict:
    iid = task["instance_id"]
    wt = work_root / iid
    shutil.rmtree(wt, ignore_errors=True)
    B.git(repo, "worktree", "prune")
    res = B.git(repo, "worktree", "add", "--force", "--detach", str(wt), task["base_commit"])
    if res.returncode != 0:
        return {"instance_id": iid, "resolved": False, "error": "worktree_failed"}

    try:
        t0 = time.time()
        patch = ""
        err = ""
        try:
            patch = agent_fn(str(wt), task["problem_statement"])
        except Exception as e:  # noqa: BLE001
            err = f"agent_error: {e}"
        agent_secs = time.time() - t0

        # submit_patch 在无改动时返回 "NO_PATCH: ..."，工具出错时返回 "error: ..."。
        # 这些都不是补丁，不能当作 diff 去 apply。
        pstrip = (patch or "").strip()
        if not pstrip:
            return {"instance_id": iid, "resolved": False,
                    "error": err or "empty_patch", "agent_seconds": round(agent_secs, 1)}
        if pstrip.startswith(("NO_PATCH", "error:")):
            return {"instance_id": iid, "resolved": False,
                    "error": f"no_patch: {pstrip[:80]}", "agent_seconds": round(agent_secs, 1)}
        if not pstrip.startswith(("diff --git", "--- ")):
            return {"instance_id": iid, "resolved": False,
                    "error": "patch_not_a_diff", "agent_seconds": round(agent_secs, 1)}

        # agent 有两种可能：
        #   a) 直接在 worktree 里改文件（GemmaAgent 就是这样），补丁只是 diff 快照
        #   b) 只返回补丁文本、未动文件（oracle 模式）
        # 前者再 apply 会重复应用失败，所以先看 worktree 是否已脏。
        dirty = B.git(wt, "status", "--porcelain").stdout.strip()
        if not dirty:
            if not B._apply_patch(wt, patch):
                return {"instance_id": iid, "resolved": False,
                        "error": "agent_patch_apply_failed", "agent_seconds": round(agent_secs, 1)}

        # 应用官方 test_patch（判分测试）
        if not B._apply_patch(wt, task["test_patch"]):
            return {"instance_id": iid, "resolved": False,
                    "error": "test_patch_apply_failed", "agent_seconds": round(agent_secs, 1)}

        ok, out = run_pytest(wt, task["changed_test_files"])
        return {
            "instance_id": iid,
            "resolved": ok,
            "agent_seconds": round(agent_secs, 1),
            "patch_lines": patch.count("\n"),
            "test_output": out[-1200:] if not ok else "",
        }
    finally:
        shutil.rmtree(wt, ignore_errors=True)


def oracle_agent(repo_root: str, problem: str, tasks_by_id: dict, iid_holder: dict) -> str:
    """标准答案 agent：直接返回 patch，用于验证判分器正确。"""
    return tasks_by_id[iid_holder["id"]]["patch"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="bench/tasks/tasks.jsonl")
    ap.add_argument("--repo", default="examples/repos/rich")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--oracle", action="store_true", help="用标准答案跑，验证判分器")
    ap.add_argument("--out", default="bench/results")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    tasks = [json.loads(l) for l in open(args.tasks, encoding="utf-8") if l.strip()]
    if args.limit:
        tasks = tasks[: args.limit]

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    work_root = out_dir / "_worktrees"
    work_root.mkdir(exist_ok=True)

    if args.oracle:
        by_id = {t["instance_id"]: t for t in tasks}

        def agent_fn(root: str, problem: str) -> str:
            return by_id[current["id"]]["patch"]

    else:
        from agent import make_agent  # 延迟导入，oracle 模式不需要

        def agent_fn(root: str, problem: str) -> str:
            return make_agent(root).solve(problem)

    current = {" id": ""}
    rows = []
    print(f"评测 {len(tasks)} 个任务" + ("（oracle 模式）" if args.oracle else ""))
    for t in tasks:
        current["id"] = t["instance_id"]
        r = evaluate_one(t, repo, work_root, agent_fn)
        rows.append(r)
        mark = "PASS" if r.get("resolved") else "FAIL"
        extra = r.get("error", "")
        print(f"  [{mark}] {r['instance_id']:16} {r.get('agent_seconds','-')}s {extra}")

    n = len(rows)
    npass = sum(1 for r in rows if r.get("resolved"))
    print(f"\n结果: {npass}/{n} PASS ({100*npass/n:.1f}%)")

    res_path = out_dir / ("oracle.json" if args.oracle else "agent.json")
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump({"n": n, "passed": npass, "rate": npass / n, "rows": rows}, f,
                  ensure_ascii=False, indent=2)
    print(f"详细结果: {res_path}")
    shutil.rmtree(work_root, ignore_errors=True)
    return 0 if npass == n or not args.oracle else 1


if __name__ == "__main__":
    sys.exit(main())