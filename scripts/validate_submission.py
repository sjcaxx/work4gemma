"""Compile the agent tree with official ADK; no inference or grading is performed."""
from pathlib import Path
from adk_submission import compile_submission, ModelRegistry

ROOT = Path(__file__).resolve().parents[1]


def run_command(command: str) -> str:
    return "compile-only"


def read_file(filepath: str, start_line: int | None = None, end_line: int | None = None) -> str:
    return "compile-only"


def edit_file(filepath: str, old_string: str, new_string: str, allow_multiple: bool = False) -> str:
    return "compile-only"


def write_file(filepath: str, content: str) -> str:
    return "compile-only"


def get_code_neighbors(node: str, edge_type: str | None = None, max_neighbors: int = 50) -> str:
    return "compile-only"


def search_similar_code(query: str, k: int = 10) -> str:
    return "compile-only"


def get_code_subgraph(nodes: list[str]) -> str:
    return "compile-only"


def get_status() -> str:
    return "compile-only"


def submit_patch() -> str:
    return "compile-only"


if __name__ == "__main__":
    functions = [run_command, read_file, edit_file, write_file, get_code_neighbors,
                 search_similar_code, get_code_subgraph, get_status, submit_patch]
    models = ModelRegistry()
    model = "gemma-4-31b-it-qat-w4a16-ct"
    models.register(model, model)
    agent = compile_submission(ROOT / "notes/official_kit/submission",
                               tool_registry={f.__name__: f for f in functions},
                               model_registry=models)
    print("OFFICIAL_COMPILER_OK:", agent.name)
    print("Compile only: no model request, no benchmark score.")
