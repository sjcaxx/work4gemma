import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codetools import AgentTools
from codetools.graph_builder import CodeGraph


def test_official_edges_round_trip():
    graph = CodeGraph()
    graph.g.add_edge("caller", "callee", type="calls")
    data = graph.to_node_link()
    assert "edges" in data and "links" not in data
    assert CodeGraph.from_node_link(data).neighbors("caller") == [("callee", "calls")]


def test_load_official_edges():
    data = {
        "directed": True, "multigraph": True, "graph": {},
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"source": "a", "target": "b", "key": 0, "type": "calls"}],
    }
    assert CodeGraph.from_node_link(data).neighbors("a") == [("b", "calls")]


def test_run_command_uses_available_bash(tmp_path):
    result = AgentTools(str(tmp_path)).run_command("printf 'codearch-smoke'")
    assert result == "exit_code=0\ncodearch-smoke"


def test_filter_patch_preserves_multiple_file_boundaries(tmp_path):
    import subprocess

    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True)

    git("init", "-q")
    for name in ["a.py", "b.py"]:
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    git("add", ".")
    git("-c", "user.name=test", "-c", "user.email=test@local", "commit", "-qm", "base")
    for name in ["a.py", "b.py"]:
        (tmp_path / name).write_text("x = 2\n", encoding="utf-8")
    patch = AgentTools(str(tmp_path)).submit_patch()
    git("restore", ".")
    result = subprocess.run(["git", "apply", "--check", "-"], input=patch, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    subprocess.run(["git", "apply", "-"], input=patch, cwd=tmp_path, capture_output=True, text=True, check=True)
    for name in ["a.py", "b.py"]:
        assert (tmp_path / name).read_text(encoding="utf-8") == "x = 2\n"
