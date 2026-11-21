"""从 Python 仓库构建 Abstract Syntax Tree (AST) 调用/依赖图。

目标: 与官方数据集 graphs/<instance_id>.json **schema 1:1 对齐**。

官方图就是 NetworkX 的 `node_link_data` 序列化格式:
    {
      "directed": true,
      "multigraph": true,
      "graph": {},
      "nodes": [{"id": "<fq symbol>", "name": ..., "text": ...}, ...],
      "edges": [{"source": ..., "target": ..., "type": "calls", "key": 0}, ...]
    }
  官方 nodes[*].id     -> 完全限定符号路径, 如 "fastapi.routing._prepare_response_content"
  官方 nodes[*].name   -> 人类可读的符号名
  官方 nodes[*].text   -> 该函数/方法/类的源码定义
  官方 edges[*].source -> 源符号 id
  官方 edges[*].target -> 目标符号 id
  官方 edges[*].type   -> 结构关系类别 (如 "calls")
  官方 edges[*].key    -> 多边图中的并行边索引

因此本模块:
  - 内部用 networkx.MultiDiGraph 表示图;
  - `to_node_link()` / `from_node_link()` 与官方 json 完全兼容;
  - `load_official_graph(path)` 可直接读官方 graphs/*.json;
  - 构建时用 scope-aware AST visitor 尽量正确地解析 calls/imports。
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx


class CodeGraph:
    """包装 networkx.MultiDiGraph, 提供图查询与官方 schema 序列化。

    与官方 schema 1:1:
      - nodes: id / name / text (以及额外 kind)
      - edges: source / target / type / key
    """

    def __init__(self, graph: Optional[nx.MultiDiGraph] = None):
        self.g: nx.MultiDiGraph = graph if graph is not None else nx.MultiDiGraph()

    # ---------- 查询接口 ----------

    def node(self, symbol_id: str):
        return self.g.nodes.get(symbol_id)

    def node_text(self, symbol_id: str) -> str:
        return self.g.nodes.get(symbol_id, {}).get("text", "")

    def neighbors(self, symbol_id: str, edge_type: Optional[str] = None) -> List[Tuple[str, str]]:
        """返回 (neighbor_id, edge_type), 含出边和入边。与官方"incoming and outgoing neighbors"一致。"""
        if symbol_id not in self.g:
            return []
        result: List[Tuple[str, str]] = []
        # 出边
        for _, tgt, data in self.g.out_edges(symbol_id, data=True):
            etype = data.get("type", "calls")
            if edge_type is None or etype == edge_type:
                result.append((tgt, etype))
        # 入边
        for src, _, data in self.g.in_edges(symbol_id, data=True):
            etype = data.get("type", "calls")
            if edge_type is None or etype == edge_type:
                result.append((src, etype))
        return result

    def subgraph(self, symbol_ids: List[str]) -> "CodeGraph":
        """诱导子图 (all nodes and interconnecting edges)。"""
        present = [s for s in symbol_ids if s in self.g]
        return CodeGraph(self.g.subgraph(present).copy())

    def all_nodes(self) -> List[str]:
        return list(self.g.nodes())

    def __len__(self) -> int:
        return self.g.number_of_nodes()

    # ---------- 官方 schema 序列化 ----------

    def to_node_link(self) -> Dict:
        """输出与官方 graphs/*.json 完全一致的 dict。"""
        return nx.readwrite.json_graph.node_link_data(self.g, edges="edges")

    def save_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_node_link(), f)

    @classmethod
    def from_node_link(cls, data: Dict) -> "CodeGraph":
        g = nx.readwrite.json_graph.node_link_graph(
            data, directed=data.get("directed", True), multigraph=data.get("multigraph", True),
            edges="edges" if "edges" in data else "links",
        )
        return cls(g)

    @classmethod
    def load_official_graph(cls, path: str) -> "CodeGraph":
        """直接加载官方 graphs/<instance_id>.json。"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_node_link(data)


class CodeGraphBuilder:
    """从仓库目录构建 CodeGraph (scope-aware AST call graph)。"""

    DEFAULT_SKIP_DIRS = {
        "venv", ".venv", "node_modules", ".git", "__pycache__",
        "build", "dist", "env", "site-packages", "tests", "test", ".tox", ".mypy_cache",
        ".eggs", "docs", "examples",
    }

    def __init__(self, repo_root: str, skip_dirs: Optional[Set[str]] = None):
        self.repo_root = Path(repo_root)
        self.skip_dirs = set(skip_dirs) if skip_dirs else set(self.DEFAULT_SKIP_DIRS)
        self.graph = nx.MultiDiGraph()
        # 全局: 完全限定符号 id -> node attrs
        self._nodes: Dict[str, Dict] = {}
        # 每个文件(相对路径) 定义的 顶层名字 -> 完全限定 id (用于跨文件解析)
        self._file_exports: Dict[str, Dict[str, str]] = {}
        # import 别名解析: 文件 -> {local_name: fq_symbol}
        self._file_imports: Dict[str, Dict[str, str]] = {}

    # ---------- 主入口 ----------

    def build(self) -> CodeGraph:
        py_files = self._collect_py_files()

        # 第一遍: 收集所有定义 & 每个文件的导出名
        for py_file in py_files:
            self._collect_definitions(py_file)

        # 第二遍: 解析 import (先把所有文件的 import 表建好)
        for py_file in py_files:
            self._collect_imports(py_file)

        # 第三遍: 解析调用, 加边
        for py_file in py_files:
            self._collect_calls(py_file)

        # 汇总到 networkx 图
        for nid, attrs in self._nodes.items():
            self.graph.add_node(nid, **attrs)
        # (edges 在 _collect_calls 里直接 add)

        return CodeGraph(self.graph)

    # ---------- 文件收集 ----------

    def _collect_py_files(self) -> List[Path]:
        files: List[Path] = []
        for root, dirs, filenames in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]
            for fn in filenames:
                if fn.endswith(".py"):
                    files.append(Path(root) / fn)
        files.sort()
        return files

    def _rel(self, path: Path) -> str:
        return str(path.relative_to(self.repo_root))

    def _module_id_from_path(self, path: Path) -> str:
        rel = path.relative_to(self.repo_root)
        parts = list(rel.parts)
        if parts[-1].startswith("__init__"):
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
        if not parts:
            return "__root__"
        return ".".join(parts)

    # ---------- 第一遍: 定义 ----------

    def _collect_definitions(self, path: Path) -> None:
        text = self._safe_read(path)
        if not text:
            return
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return

        module_id = self._module_id_from_path(path)
        rel = self._rel(path)
        exports: Dict[str, str] = {}

        # module 节点
        if module_id not in self._nodes:
            self._nodes[module_id] = {"name": module_id.split(".")[-1], "text": "", "kind": "module"}

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_id = f"{module_id}.{node.name}"
                class_text = ast.get_source_segment(text, node) or ""
                self._nodes[class_id] = {
                    "name": node.name, "text": class_text, "kind": "class",
                }
                exports[node.name] = class_id
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_id = f"{class_id}.{sub.name}"
                        mtext = ast.get_source_segment(text, sub) or ""
                        self._nodes[method_id] = {
                            "name": sub.name, "text": mtext, "kind": "method",
                        }
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = f"{module_id}.{node.name}"
                ftext = ast.get_source_segment(text, node) or ""
                if func_id not in self._nodes:
                    self._nodes[func_id] = {
                        "name": node.name, "text": ftext, "kind": "function",
                    }
                exports[node.name] = func_id

        self._file_exports[rel] = exports

    # ---------- 第二遍: import ----------

    def _collect_imports(self, path: Path) -> None:
        text = self._safe_read(path)
        if not text:
            return
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return
        rel = self._rel(path)
        module_id = self._module_id_from_path(path)
        imports: Dict[str, str] = {}

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".")[0]
                    imports[local] = alias.name
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                # 相对导入: 处理 . / .. 前缀
                if node.level and node.level > 0:
                    base = self._resolve_relative_import(module_id, node.level, node.module)
                for alias in node.names:
                    local = alias.asname or alias.name
                    full = f"{base}.{alias.name}" if base else alias.name
                    imports[local] = full
        self._file_imports[rel] = imports

    def _resolve_relative_import(self, module_id: str, level: int, module: Optional[str]) -> str:
        parts = module_id.split(".")
        # level=1 表示当前包; 去掉最后 1 级 (当前模块) 的 level-1 级
        base_parts = parts[: len(parts) - level] if level <= len(parts) else []
        if module:
            base_parts = base_parts + module.split(".")
        return ".".join(base_parts)

    # ---------- 第三遍: 调用 ----------

    def _collect_calls(self, path: Path) -> None:
        text = self._safe_read(path)
        if not text:
            return
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return
        rel = self._rel(path)
        module_id = self._module_id_from_path(path)
        imports = self._file_imports.get(rel, {})

        # 建立父指针
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child._parent = node  # type: ignore[attr-defined]

        # 遍历所有函数/方法, 解析其函数体中的调用
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                owner_id = self._owner_id(node, module_id)
                func_id = f"{owner_id}.{node.name}" if not owner_id.endswith(node.name) else owner_id
                if func_id not in self._nodes:
                    continue
                self._resolve_calls_in_func(func_id, node, imports)

    def _owner_id(self, func_node: ast.AST, module_id: str) -> str:
        cur = getattr(func_node, "_parent", None)
        while cur is not None:
            if isinstance(cur, ast.ClassDef):
                return f"{module_id}.{cur.name}"
            if isinstance(cur, ast.Module):
                break
            cur = getattr(cur, "_parent", None)
        return module_id

    def _resolve_calls_in_func(self, func_id: str, func_node: ast.AST, imports: Dict[str, str]) -> None:
        local_names = self._collect_local_names(func_node)
        seen: Set[Tuple[str, str]] = set()

        # 只处理 Call 节点, 避免与内部 Name/Attribute 重复解析;
        # 同时记录 (target, etype) 去重, 同一函数对同一目标的单次调用只留一条边。
        for sub in ast.walk(func_node):
            if isinstance(sub, ast.Call):
                target_fq = self._resolve_call(sub, func_id, imports, local_names)
                if target_fq and target_fq in self._nodes and target_fq != func_id:
                    key = (target_fq, "calls")
                    if key not in seen:
                        seen.add(key)
                        self._add_edge(func_id, target_fq, "calls")

    def _collect_local_names(self, func_node: ast.AST) -> Set[str]:
        """收集函数内定义的局部变量/参数名 (这些不应解析成全局符号)。"""
        names: Set[str] = set()
        for sub in ast.walk(func_node):
            if isinstance(sub, ast.arg):
                names.add(sub.arg)
            elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                names.add(sub.id)
            elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(sub.name)
        return names

    def _resolve_call(self, call: ast.Call, func_id: str, imports: Dict[str, str], local_names: Set[str]) -> Optional[str]:
        func = call.func
        if isinstance(func, ast.Name):
            return self._resolve_name(func.id, imports, local_names)
        if isinstance(func, ast.Attribute):
            # self.method() / cls.method() / obj.method()
            base = self._attr_root_name(func)
            if base in ("self", "cls"):
                # 解析到当前类的 method
                class_id = func_id.rsplit(".", 1)[0]
                candidate = f"{class_id}.{func.attr}"
                if candidate in self._nodes:
                    return candidate
                return None
            # module.func() / alias.func()
            if isinstance(func.value, ast.Name):
                root = func.value.id
                if root in imports:
                    fq = f"{imports[root]}.{func.attr}"
                    if fq in self._nodes:
                        return fq
                    # import 的是 module, 属性是模块内函数
                # 尝试全局类方法: ClassName.method
                cls_id = self._resolve_name(root, imports, local_names)
                if cls_id:
                    cand = f"{cls_id}.{func.attr}"
                    if cand in self._nodes:
                        return cand
            return None
        return None

    def _resolve_ref(self, node: ast.AST, imports: Dict[str, str], local_names: Set[str]) -> Optional[str]:
        if isinstance(node, ast.Name):
            return self._resolve_name(node.id, imports, local_names)
        if isinstance(node, ast.Attribute):
            base = self._attr_root_name(node)
            if isinstance(node.value, ast.Name):
                root = node.value.id
                if root in imports:
                    fq = f"{imports[root]}.{node.attr}"
                    if fq in self._nodes:
                        return fq
            return None
        return None

    def _resolve_name(self, name: str, imports: Dict[str, str], local_names: Set[str]) -> Optional[str]:
        if name in local_names:
            return None
        # import 别名
        if name in imports:
            fq = imports[name]
            if fq in self._nodes:
                return fq
        # 直接同名定义
        if name in self._nodes:
            return name
        # 在各文件 exports 里找同名 (不区分模块)
        for _rel, exports in self._file_exports.items():
            if name in exports and exports[name] in self._nodes:
                return exports[name]
        return None

    @staticmethod
    def _attr_root_name(node: ast.Attribute) -> Optional[str]:
        cur = node
        while isinstance(cur, ast.Attribute):
            cur = cur.value
        if isinstance(cur, ast.Name):
            return cur.id
        return None

    def _add_edge(self, source: str, target: str, etype: str = "calls") -> None:
        # MultiDiGraph 自动分配 key; 官方用整数 key 区分并行边
        self.graph.add_edge(source, target, type=etype)

    # ---------- 工具 ----------

    def _safe_read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
