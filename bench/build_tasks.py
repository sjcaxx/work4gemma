"""从 rich 仓库的 git 历史中挖掘 SWE-bench 风格的任务。

流程（与官方 Data Generation 管线对齐）:
  1. Commit Mining: 遍历 commit, 筛出"同时修改源码 .py 和测试 test_*.py"的修复性提交
  2. 拆分: base_commit = 该 commit 的父提交
           test_patch   = 测试文件的 diff
           patch        = 源码文件的 diff (参考修复/标准答案)
           problem      = commit message (当 issue 文本)
  3. 校验（关键，Fail-to-Pass / Pass-to-Pass）:
       a) base + test_patch            -> pytest 必须 FAIL
       b) base + test_patch + patch    -> pytest 必须 PASS
     两道都过, 才收进 benchmark。
  4. 输出 tasks.jsonl (与官方同结构) + worktrees/

用法:
  python bench/build_tasks.py --repo examples/repos/rich --limit 15 --workers 4
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------

def git(repo: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, timeout=timeout
    )


def list_commits(repo: Path) -> list[str]:
    """按时间倒序返回非 merge commit 的 SHA。"""
    out = git(repo, "rev-list", "--no-merges", "--all").stdout
    return [s for s in out.splitlines() if s.strip()]


def commit_files(repo: Path, sha: str) -> tuple[list[str], list[str]]:
    """返回 (changed_files, parent_shas)。"""
    parents = git(repo, "rev-list", "--parents", "-n", "1", sha).stdout.split()
    # parents[0] 是 commit 本身, 其余是父
    parent_shas = parents[1:]
    names = git(repo, "show", "--name-only", "--pretty=format:", sha).stdout
    changed = [f for f in names.splitlines() if f.strip()]
    return changed, parent_shas


def commit_message(repo: Path, sha: str) -> str:
    return git(repo, "log", "-1", "--pretty=%B", sha).stdout.strip()


def diff_for_paths(repo: Path, sha: str, paths: list[str]) -> str:
    if not paths:
        return ""
    return git(repo, "show", "--format=", sha, "--", *paths).stdout


# ---------------------------------------------------------------------------
# 任务候选筛选
# ---------------------------------------------------------------------------

SOURCE_PREFIX = "rich/"
TEST_PATTERNS = re.compile(r"(^|/)test_[^/]*\.py$|(^|/)[^/]*_test\.py$")


def is_source_py(f: str) -> bool:
    return f.startswith(SOURCE_PREFIX) and f.endswith(".py") and not TEST_PATTERNS.search(f)


def is_test_py(f: str) -> bool:
    return f.endswith(".py") and bool(TEST_PATTERNS.search(f))


def candidate_from_commit(repo: Path, sha: str) -> dict | None:
    changed, parents = commit_files(repo, sha)
    if len(parents) != 1:  # 跳过 merge 或 root
        return None
    src = [f for f in changed if is_source_py(f)]
    tst = [f for f in changed if is_test_py(f)]
    if not src or not tst:
        return None

    base = parents[0]
    patch = diff_for_paths(repo, sha, src)
    test_patch = diff_for_paths(repo, sha, tst)
    if not patch.strip() or not test_patch.strip():
        return None

    # 过滤：机械性大改 (类似官方排除 LSC)
    total_lines = patch.count("\n") + test_patch.count("\n")
    if total_lines > 400:
        return None

    msg = commit_message(repo, sha)
    if not msg.strip():
        return None

    # issue 文本质量过滤：太短的 commit message 不像 issue，agent 无从下手
    problem = clean_problem(msg, sha)
    if not is_good_problem(problem):
        return None

    repo_short = repo.name
    short_sha = sha[:8]
    return {
        "instance_id": f"{repo_short}_{short_sha}",
        "repo": repo_short,
        "base_commit": base,
        "commit": sha,
        "problem_statement": problem,
        "hints_text": "",
        "patch": patch,
        "test_patch": test_patch,
        "changed_source_files": src,
        "changed_test_files": tst,
    }


BAD_PROBLEM = re.compile(
    r"^(fix(es|ed)?\s+(the\s+)?tests?|test\s*(cases?|fixes?|updates?)?|tests|typo|wip|lint|black|ruff|typing(\s+updates?)?|reformat\w*|cleanup|bump\s+version|merge\b.*)$",
    re.IGNORECASE,
)


def is_good_problem(text: str) -> bool:
    """判断 commit message 是否适合当作 issue 文本。"""
    t = text.strip()
    if len(t) < 25:  # 至少 25 字符
        return False
    if len(t.split()) < 4:  # 至少 4 个词
        return False
    first = t.splitlines()[0].strip()
    if BAD_PROBLEM.match(first):
        return False
    return True


def clean_problem(msg: str, sha: str) -> str:
    """把 commit message 清洗成"像 issue 的描述"（去掉 Signed-off-by 等）。"""
    lines = []
    for ln in msg.splitlines():
        low = ln.lower()
        if low.startswith(("signed-off-by", "co-authored-by", "fixes #", "closes #")):
            continue
        lines.append(ln)
    text = "\n".join(lines).strip()
    if not text:
        text = f"Fix in commit {sha[:8]}"
    return text


# ---------------------------------------------------------------------------
# Fail-to-Pass / Pass-to-Pass 校验
# ---------------------------------------------------------------------------

def _apply_patch(worktree: Path, patch_text: str) -> bool:
    """用 git apply 应用补丁, 尽量容忍上下文。"""
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as fh:
        fh.write(patch_text)
        tmp = fh.name
    try:
        for extra in (["--3way"], []):
            res = git(worktree, "apply", *extra, tmp)
            if res.returncode == 0:
                return True
        return False
    finally:
        os.unlink(tmp)


def _run_pytest(worktree: Path, test_files: list[str], timeout: int = 120) -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", *test_files],
            cwd=worktree,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        out = (res.stdout + res.stderr)[-2500:]
        return res.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "[timeout]"
    except Exception as e:  # noqa: BLE001
        return False, f"[error {e}]"


def validate_task(task: dict, repo: Path, base_dir: Path) -> dict:
    """在独立 worktree 里跑 Fail-to-Pass / Pass-to-Pass。返回带校验结果的任务。"""
    iid = task["instance_id"]
    wt = base_dir / iid
    if wt.exists():
        git(repo, "worktree", "remove", "--force", str(wt))
        shutil.rmtree(wt, ignore_errors=True)

    res = git(repo, "worktree", "add", "--force", "--detach", str(wt), task["base_commit"])
    if res.returncode != 0:
        return {**task, "valid": False, "reason": f"worktree_failed: {res.stderr[:200]}"}

    try:
        # 需要安装依赖吗? rich 有 pyproject; 简单起见只用 pytest 直接跑
        test_files = task["changed_test_files"]

        # a) Fail-to-Pass: 仅 test_patch
        if not _apply_patch(wt, task["test_patch"]):
            return {**task, "valid": False, "reason": "test_patch_apply_failed"}
        ok_a, out_a = _run_pytest(wt, test_files)
        if ok_a:
            # 测试本来就过 -> 不是修复性任务, 丢弃
            return {**task, "valid": False, "reason": "test_passes_without_fix"}

        # 重置测试改动
        git(wt, "checkout", "--", ".")

        # b) Pass-to-Pass: test_patch + patch
        if not _apply_patch(wt, task["test_patch"]):
            return {**task, "valid": False, "reason": "test_patch_apply_failed_2"}
        if not _apply_patch(wt, task["patch"]):
            return {**task, "valid": False, "reason": "source_patch_apply_failed"}
        ok_b, out_b = _run_pytest(wt, test_files)
        if not ok_b:
            return {**task, "valid": False, "reason": "test_fails_with_fix", "output": out_b[-500:]}

        return {**task, "valid": True, "reason": "ok"}
    finally:
        git(repo, "worktree", "remove", "--force", str(wt))
        shutil.rmtree(wt, ignore_errors=True)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="examples/repos/rich")
    ap.add_argument("--limit", type=int, default=15, help="最终要收多少个合格任务")
    ap.add_argument("--scan", type=int, default=400, help="最多扫描多少个候选 commit")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="bench/tasks")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    work_root = out_dir / "_worktrees"
    work_root.mkdir(exist_ok=True)

    print(f"仓库: {repo}")
    sha_list = list_commits(repo)
    print(f"总 commit: {len(sha_list)}，开始扫描候选...")

    # 1) 快速筛选候选（不需要 worktree）
    candidates = []
    scanned = 0
    for sha in sha_list:
        if scanned >= args.scan:
            break
        scanned += 1
        try:
            c = candidate_from_commit(repo, sha)
        except Exception:  # noqa: BLE001
            continue
        if c:
            candidates.append(c)
    print(f"扫描 {scanned} 个 commit，得到 {len(candidates)} 个候选")

    # 越新的越可能依赖新版本；先按时间倒序（sha_list 已是倒序）
    # 2) 并行校验，收够 limit 就停
    valid: list[dict] = []
    rejected = {"test_passes_without_fix": 0, "test_fails_with_fix": 0, "patch_apply": 0, "other": 0}
    t0 = time.time()

    def work(c):
        return validate_task(c, repo, work_root)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, c): c for c in candidates}
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001
                rejected["other"] += 1
                continue
            if r.get("valid"):
                valid.append(r)
                print(f"  [OK] {r['instance_id']}  ({r['reason']})  total={len(valid)}")
                if len(valid) >= args.limit:
                    for f in futs:
                        f.cancel()
                    break
            else:
                reason = r.get("reason", "other")
                if "test_passes_without_fix" in reason:
                    rejected["test_passes_without_fix"] += 1
                elif "test_fails_with_fix" in reason:
                    rejected["test_fails_with_fix"] += 1
                elif "apply" in reason:
                    rejected["patch_apply"] += 1
                else:
                    rejected["other"] += 1

    dt = time.time() - t0
    print(f"\n校验耗时 {dt:.1f}s，合格 {len(valid)} 个，拒绝统计: {rejected}")

    if not valid:
        print("没有造出合格任务，可能需要调整筛选/环境。")
        return 1

    tasks_path = out_dir / "tasks.jsonl"
    with open(tasks_path, "w", encoding="utf-8") as f:
        for t in valid:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"任务已写入: {tasks_path}")

    # 清理工作区
    shutil.rmtree(work_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())