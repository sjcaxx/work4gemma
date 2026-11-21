"""BM25 代码定位 (code localisation)。

基于 `bsw0610/gemma4-swe-harness-audit` 的 localize-code skill (Apache-2.0)，
重构为可导入的结构化模块。

为什么需要它 (来自 129 任务审计数据):
  - 官方 `search_similar_code` 直接接受整段 issue 时, 解析 gold 命中率 = 0%;
  - 自建 BM25 over AST (函数/类 span) 的 hit@10 = 51, hit@100 = 98,
    明显优于官方工具 (32 / 84)。
  - 因此 agent 应该"先用 BM25 定位候选文件/符号, 再去 read_file"。

纯标准库实现 (ast/collections/math/os/re), 只读, 不写仓库。
"""

from __future__ import annotations

import ast
import collections
import math
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Set, Tuple


SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env",
    "build", "dist", ".tox", ".nox", ".mypy_cache", ".pytest_cache", "site-packages",
    "docs", "doc", "docs_src", "examples", "tests", "test", "testing", "benchmarks",
}
TEST_FILE = re.compile(r"(^test_.*|.*_test)\.py$")
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CAMEL = re.compile(r"_|(?<=[a-z0-9])(?=[A-Z])")
STOP = set(
    """the a an and or of to in for is are be this that with on as it by not if from at we can should when use
using was were has have had but so do does did into than then there their them they you your our its also only
self none true false return def class import""".split()
)
MAX_FILE_BYTES = 1_000_000


@dataclass
class Symbol:
    path: str          # 相对仓库根路径
    line: int
    qualname: str      # 完全限定名 (ClassName.method)


@dataclass
class LocalizeResult:
    files: List[str] = field(default_factory=list)
    symbols: List[Symbol] = field(default_factory=list)
    n_files: int = 0
    n_symbols: int = 0


def tokens(text: str) -> List[str]:
    out: List[str] = []
    for word in TOKEN.findall(text):
        parts = [p for p in CAMEL.split(word) if p]
        for t in [word] + (parts if len(parts) > 1 else []):
            t = t.lower()
            if len(t) > 1 and t not in STOP:
                out.append(t)
    return out


def python_files(root: str) -> Iterator[str]:
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("."))
        for f in sorted(files):
            if f.endswith(".py") and not TEST_FILE.match(f):
                p = os.path.join(d, f)
                try:
                    if os.path.getsize(p) <= MAX_FILE_BYTES:
                        yield p
                except OSError:
                    pass


def units(root: str) -> Iterator[Tuple[str, int, Optional[str], str]]:
    """产出 (rel_path, line, qualname_or_None, text)。qualname=None 表示整个文件。"""
    for path in python_files(root):
        rel = os.path.relpath(path, root)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                src = fh.read()
            tree = ast.parse(src)
        except (SyntaxError, ValueError, OSError):
            continue
        lines = src.splitlines()
        yield rel, 1, None, src
        stack: List[Tuple[ast.AST, str]] = [(tree, "")]
        while stack:
            node, prefix = stack.pop()
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    q = f"{prefix}.{ch.name}" if prefix else ch.name
                    start = min([ch.lineno] + [d.lineno for d in ch.decorator_list])
                    end = getattr(ch, "end_lineno", None) or start
                    yield rel, ch.lineno, q, "\n".join(lines[start - 1 : end])
                    stack.append((ch, q))
                else:
                    stack.append((ch, prefix))


def bm25(query_terms: Set[str], docs: List[str], k1: float = 1.2, b: float = 0.75) -> List[float]:
    tfs = [collections.Counter(tokens(d)) for d in docs]
    n = len(tfs) or 1
    avg = sum(sum(t.values()) for t in tfs) / n or 1.0
    df = collections.Counter(w for t in tfs for w in t)
    scores: List[float] = []
    for t in tfs:
        dl = sum(t.values())
        s = 0.0
        for w in query_terms:
            if w in t:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * t[w] * (k1 + 1) / (t[w] + k1 * (1 - b + b * dl / avg))
        scores.append(s)
    return scores


def localize(root: str, query: str, top: int = 15, files: int = 5) -> LocalizeResult:
    """对仓库按 BM25 排序文件与符号。返回结构化结果。"""
    q = set(tokens(query))
    result = LocalizeResult()
    if not q:
        return result

    file_units: List[Tuple[str, int, str]] = []      # (rel, line, text)
    sym_units: List[Tuple[str, int, str, str]] = []  # (rel, line, qual, text)
    for rel, line, qual, text in units(root):
        if qual is None:
            file_units.append((rel, line, text))
        else:
            sym_units.append((rel, line, qual, text))

    result.n_files = len(file_units)
    result.n_symbols = len(sym_units)
    if not sym_units:
        return result

    fs = bm25(q, [t for _, _, t in file_units])
    ss = bm25(q, [t for _, _, _, t in sym_units])

    file_rank = sorted(range(len(file_units)), key=lambda i: (-fs[i], file_units[i][0]))[:files]
    result.files = [file_units[i][0] for i in file_rank if fs[i] > 0]

    seen: Set[Tuple[str, str]] = set()
    for i in sorted(range(len(sym_units)), key=lambda i: (-ss[i], sym_units[i][0], sym_units[i][1])):
        key = (sym_units[i][0], sym_units[i][2])
        if key not in seen and ss[i] > 0:
            seen.add(key)
            rel, line, qual, _ = sym_units[i]
            result.symbols.append(Symbol(path=rel, line=line, qualname=qual))
        if len(result.symbols) >= top:
            break
    return result


def format_result(result: LocalizeResult, max_chars: int = 4000) -> str:
    """格式化成与官方 skill 一致的文本 (默认 < 4000 字符)。"""
    out = [f"Likely files (BM25 over {result.n_files} non-test files):"]
    out += [f"  {p}" for p in result.files]
    out.append(f"Likely functions/classes (of {result.n_symbols}):")
    out += [f"  {s.path}:{s.line}  {s.qualname}" for s in result.symbols]
    return "\n".join(out)[:max_chars]