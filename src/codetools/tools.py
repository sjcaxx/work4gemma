"""复现 Gemma 4 Developer Agent 竞赛的 9 个预定义 agent 工具。

9 个工具 (对照官方):
  1. run_command(command: str) -> str
  2. submit_patch() -> str
  3. get_status() -> str
  4. read_file(filepath, start_line=None, end_line=None) -> str
  5. edit_file(filepath, old_string, new_string, allow_multiple=False) -> str
  6. write_file(filepath, content) -> str
  7. get_code_neighbors(node, edge_type=None, max_neighbors=50) -> str
  8. search_similar_code(query, k=10) -> str
  9. get_code_subgraph(nodes) -> str

所有工具的输出都是字符串 (供 LLM 读取), 与官方一致。
这个类假定它作用于一个"工作目录" (/workspace 在竞赛里等价)。
文件工具默认只允许在 repo_root 内部操作 (沙箱限制)。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .graph_builder import CodeGraph
from .localize import format_result as _format_result
from .localize import localize as _localize_repo


class AgentTools:
    """在给定仓库根目录上运行这 9 个工具。"""

    def __init__(
        self,
        repo_root: str,
        graph: Optional[CodeGraph] = None,
        embeddings: Optional[Dict[str, "object"]] = None,
        cwd_outside_repo: bool = True,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.graph = graph
        self.embeddings = embeddings  # node_id -> embedding (np.ndarray or list), 可选
        # 运行 run_command 时初始的工作目录 (竞赛里是 /workspace 根)
        self.run_cwd = Path(repo_root).resolve() if cwd_outside_repo else Path(repo_root).resolve()
        self.budget_used = 0.0  # 供 get_status 展示的预算, 可选
        self.patch_status = "no patch yet"

    # ---- 官方 embedding 加载 (embeddings/<instance_id>.npz) ----

    @staticmethod
    def load_official_embeddings(npz_path: str) -> Dict[str, "object"]:
        """加载官方 embeddings/<instance_id>.npz。

        官方格式: 每个 <node_id>.npy 是一个长度 256 的 float32 向量。
        numpy 会把 .npz 里的文件名当作键 (去掉了 .npy 后缀),
        正好就是 node_id -> 256-dim array。
        """
        import numpy as np

        data = np.load(npz_path)
        return {key: data[key] for key in data.files}

    @classmethod
    def from_official(
        cls,
        repo_root: str,
        graph_json: Optional[str] = None,
        embedding_npz: Optional[str] = None,
    ) -> "AgentTools":
        """从官方数据文件构建 AgentTools (graphs/<id>.json + embeddings/<id>.npz)。"""
        graph = None
        if graph_json:
            graph = CodeGraph.load_official_graph(graph_json)
        embeddings = None
        if embedding_npz:
            embeddings = cls.load_official_embeddings(embedding_npz)
        return cls(repo_root, graph=graph, embeddings=embeddings)

    # ---- 工具 1: run_command ----
    def run_command(self, command: str) -> str:
        """在仓库根目录里执行一条 shell 命令 (/bin/bash -c)。

        设置 PYTHONDONTWRITEBYTECODE=1, 避免 pytest 等生成 __pycache__/*.pyc
        污染 git 状态 (否则 submit_patch 会把二进制 .pyc 也当补丁提交)。
        """
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            bash = "/bin/bash"
            if os.name == "nt":
                git = shutil.which("git")
                git_bash = Path(git).resolve().parent.parent / "bin" / "bash.exe" if git else None
                bash = str(git_bash) if git_bash and git_bash.is_file() else shutil.which("bash")
                if not bash:
                    return "error: Bash is required; install Git for Windows or add bash to PATH."
            proc = subprocess.run(
                [bash, "-c", command],
                capture_output=True,
                text=True,
                cwd=self.run_cwd,
                timeout=180,
                env=env,
            )
            out = proc.stdout
            err = proc.stderr
            code = proc.returncode
            snippet = (out + err).strip()
            if len(snippet) > 6000:
                snippet = snippet[:6000] + f"\n... [truncated {len(snippet)} chars]"
            return f"exit_code={code}\n{snippet}"
        except subprocess.TimeoutExpired:
            return "exit_code=-1\nCommand timed out after 180s"
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"

    # ---- 工具 2: submit_patch ----
    def submit_patch(self) -> str:
        """对 /workspace (repo_root) 做 git add -N 并 capture git diff HEAD。

        注意: 官方就是 `git add -N .` + `git diff HEAD`, 这里保持同样语义;
        但会过滤掉 __pycache__/*.pyc 等构建产物, 避免把二进制垃圾写进补丁。
        """
        try:
            subprocess.run(
                ["git", "add", "-N", "--", "."],
                capture_output=True,
                text=True,
                cwd=self.run_cwd,
            )
            proc = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.run_cwd,
            )
            patch = self._filter_patch(proc.stdout)
            if not patch.strip():
                return "NO_PATCH: no differences from HEAD."
            self.patch_status = "patch ready"
            return patch
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"

    _PATCH_EXCLUDE_MARKERS = (
        "__pycache__/",
        ".pyc",
        ".pyo",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".egg-info/",
        ".venv/",
        "node_modules/",
    )

    @classmethod
    def _filter_patch(cls, patch: str) -> str:
        """按 diff 块过滤掉构建产物/缓存文件, 保留纯源码修改。"""
        if not patch.strip():
            return patch
        chunks = patch.split("\ndiff --git ")
        kept = []
        for i, chunk in enumerate(chunks):
            head = chunk if i == 0 else "diff --git " + chunk
            # 取首行判断路径
            first = head.splitlines()[0] if head.splitlines() else ""
            if any(m in first for m in cls._PATCH_EXCLUDE_MARKERS):
                continue
            kept.append(head)
        return "\n".join(kept)

    # ---- 工具 3: get_status ----
    def get_status(self) -> str:
        """返回实时预算消耗和补丁状态。"""
        return (
            f"budget_used_seconds={self.budget_used:.1f}\n"
            f"patch_status={self.patch_status}\n"
            f"repo_root={self.repo_root}"
        )

    # ---- 工具 4: read_file ----
    def read_file(self, filepath: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """读取文件, 1-indexed 行切片 (含起始行)。文件必须在 repo_root 内。"""
        path = self._resolve_within_root(filepath)
        if path is None:
            return f"error: path '{filepath}' is outside the workspace root."
        if not path.exists():
            return f"error: file not found: {filepath}"
        if path.is_dir():
            return f"error: {filepath} is a directory, not a file."
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            return f"error: {e}"
        if start_line is None and end_line is None:
            content = "\n".join(lines)
            return f"File: {filepath}\n```\n{content}\n```"
        start = start_line if start_line is not None else 1
        end = end_line if end_line is not None else len(lines)
        # 1-indexed inclusive
        if start < 1:
            start = 1
        if end > len(lines):
            end = len(lines)
        selected = lines[start - 1 : end]
        body = "\n".join(selected)
        header = f"File: {filepath} (lines {start}-{end} of {len(lines)})"
        return f"{header}\n```\n{body}\n```"

    # ---- 工具 5: edit_file ----
    def edit_file(
        self,
        filepath: str,
        old_string: str,
        new_string: str,
        allow_multiple: bool = False,
    ) -> str:
        """把文件里第一个 (或全部) 出现的 old_string 替换成 new_string。"""
        path = self._resolve_within_root(filepath)
        if path is None:
            return f"error: path '{filepath}' is outside the workspace root."
        if not path.exists():
            return f"error: file not found: {filepath}"
        if not path.is_file():
            return f"error: {filepath} is not a file."
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            return f"error: {e}"
        count = content.count(old_string)
        if count == 0:
            return f"error: old_string not found in {filepath}."
        if count > 1 and not allow_multiple:
            return f"error: old_string found {count} times; set allow_multiple=True or provide more context."
        new_content = content.replace(old_string, new_string) if allow_multiple else content.replace(
            old_string, new_string, 1
        )
        try:
            path.write_text(new_content, encoding="utf-8")
        except OSError as e:
            return f"error: {e}"
        self.patch_status = "workspace modified"
        return f"OK: replaced {count if allow_multiple else 1} occurrence(s) in {filepath}."

    # ---- 工具 6: write_file ----
    def write_file(self, filepath: str, content: str) -> str:
        """创建或覆盖文件, 自动建父目录。"""
        path = self._resolve_within_root(filepath)
        if path is None:
            return f"error: path '{filepath}' is outside the workspace root."
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as e:
            return f"error: {e}"
        self.patch_status = "workspace modified"
        return f"OK: wrote {len(content)} chars to {filepath}."

    # ---- 工具 7: get_code_neighbors ----
    def get_code_neighbors(self, node: str, edge_type: Optional[str] = None, max_neighbors: int = 50) -> str:
        """查询调用/依赖图里某符号的邻居 (入边/出边)。"""
        if self.graph is None:
            return "error: code graph not provided."
        if node not in self.graph.g:
            return f"error: node '{node}' not found in graph."
        nbrs = self.graph.neighbors(node, edge_type)
        shown = nbrs[:max_neighbors]
        lines = [f"Neighbors of {node} ({len(nbrs)} total, showing {len(shown)}):"]
        for nbr, etype in shown:
            lines.append(f"  {etype:12s} {nbr}")
        return "\n".join(lines) if len(lines) > 1 else f"No neighbors for {node}."

    # ---- 工具 8: search_similar_code ----
    def search_similar_code(self, query: str, k: int = 10) -> str:
        """在预计算 embedding 里按余弦相似度找 top-k 相似图节点 (语义检索)。

        # 注意: 本复现默认用基于字符 n-gram 的轻量词袋向量代替真实 embedding,
        # 因为本地不加载大模型。将 `embeddings` dict 传入后可用真实 embedding。
        """
        if self.embeddings:
            import numpy as np

            ids = list(self.embeddings.keys())
            qv = self._embed_text(query, dim=len(self.embeddings[ids[0]]))
            scored = []
            for nid in ids:
                v = np.asarray(self.embeddings[nid], dtype=float)
                sim = self._cosine(qv, v)
                scored.append((sim, nid))
            scored.sort(key=lambda x: -x[0])
            top = scored[:k]
            lines = [f"Top {len(top)} similar nodes to query:"]
            for sim, nid in top:
                lines.append(f"  {sim:.3f}  {nid}")
            return "\n".join(lines)
        # fallback: 基于文本的词频/ngram 检索 (近似)
        return self._text_based_search(query, k)

    def _text_based_search(self, query: str, k: int) -> str:
        if self.graph is None:
            return "error: no embeddings and no graph for semantic search."
        scores = []
        import re

        q_tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", query.lower()))
        for nid, attrs in self.graph.g.nodes(data=True):
            text = (attrs.get("text", "") or "").lower()
            n_tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text))
            if not q_tokens:
                continue
            inter = len(q_tokens & n_tokens)
            union = len(q_tokens | n_tokens)
            scores.append((inter / union if union else 0.0, nid))
        scores.sort(key=lambda x: -x[0])
        top = [nid for _, nid in scores[:k] if _ > 0]
        if not top:
            return "No similar nodes found."
        return "Top similar nodes:\n" + "\n".join(f"  {nid}" for nid in top)

    # ---- 能力: localize_code (BM25 代码定位) ----
    def localize_code(self, query: str, top: int = 15, files: int = 5, max_chars: int = 4000) -> str:
        """用 BM25 对当前仓库做代码定位, 返回候选文件与函数/类。

        不是官方 9 个工具之一, 而是我们从审计数据中得到的"超能力":
        审计数据显示整段 issue 直接喂给官方 search_similar_code 命中率 0%,
        而 BM25 over AST 的 hit@10=51, 远优于官方工具。
        """
        result = _localize_repo(str(self.repo_root), query, top=top, files=files)
        return _format_result(result, max_chars=max_chars)

    # ---- 工具 9: get_code_subgraph ----
    def get_code_subgraph(self, nodes: List[str]) -> str:
        """提取给定符号集合的诱导子图 (所有节点 + 相互边)。"""
        if self.graph is None:
            return "error: code graph not provided."
        wanted = [n for n in nodes if n in self.graph.g]
        missing = [n for n in nodes if n not in self.graph.g]
        sg = self.graph.subgraph(wanted)
        lines = []
        if missing:
            lines.append(f"note: {len(missing)} node(s) not found: {missing[:10]}")
        lines.append(f"Subgraph with {sg.g.number_of_nodes()} nodes and {sg.g.number_of_edges()} edges:")
        for nid in wanted:
            lines.append(f"  NODE {nid}")
        for src, tgt, data in sg.g.edges(data=True):
            lines.append(f"  {src} --[{data.get('type', 'calls')}]--> {tgt}")
        return "\n".join(lines)

    # ---- 内部辅助 ----

    def _resolve_within_root(self, filepath: str) -> Optional[Path]:
        p = Path(filepath)
        if not p.is_absolute():
            p = self.repo_root / p
        try:
            p = p.resolve()
        except OSError:
            return None
        try:
            p.relative_to(self.repo_root)
            return p
        except ValueError:
            return None

    @staticmethod
    def _cosine(a, b) -> float:
        import numpy as np

        denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
        return float(np.dot(a, b) / denom)

    @staticmethod
    def _embed_text(text: str, dim: int):
        """轻量占位 embedding: 基于字符 n-gram 的确定性向量。仅用于无真实 embedding 时的示意。"""
        import hashlib

        import numpy as np

        vec = np.zeros(dim, dtype=float)
        lower = text.lower()
        for i in range(len(lower) - 2):
            tri = lower[i : i + 3]
            h = int(hashlib.md5(tri.encode()).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec
