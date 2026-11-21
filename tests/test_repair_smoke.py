"""Deterministic tool-chain smoke; this is not a model score."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codetools import AgentTools, CodeGraphBuilder


def test_reproduce_locate_repair_and_submit(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "examples/mini_repo/shopping_cart", repo / "shopping_cart",
                    ignore=shutil.ignore_patterns("__pycache__"))
    pricing = repo / "shopping_cart/pricing.py"
    pricing.write_text(pricing.read_text().replace("1 - percent", "1 + percent"))
    (repo / "test_discount.py").write_text(
        "from shopping_cart.models import Product\n"
        "from shopping_cart.pricing import apply_discount\n"
        "def test_discount():\n"
        "    assert apply_discount(Product('x', 100), 10).price == 90\n"
    )
    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    git("init", "-q")
    git("add", ".")
    git("-c", "user.name=test", "-c", "user.email=test@local", "commit", "-qm", "buggy base")
    tools = AgentTools(str(repo), graph=CodeGraphBuilder(str(repo)).build())
    command = f'"{Path(sys.executable).as_posix()}" -m pytest test_discount.py -q -p no:cacheprovider'
    before = tools.run_command(command)
    assert before.startswith("exit_code=1\n") and "1 failed" in before, before
    assert "apply_discount" in tools.localize_code("apply_discount percent price", top=3, files=2)
    edit = tools.edit_file("shopping_cart/pricing.py", "1 + percent", "1 - percent")
    assert not edit.startswith("error:"), edit
    after = tools.run_command(command)
    assert after.startswith("exit_code=0\n") and "1 passed" in after, after
    patch = tools.submit_patch()
    assert "shopping_cart/pricing.py" in patch and "test_discount.py" not in patch
    git("restore", ".")
    subprocess.run(["git", "apply", "-"], input=patch, cwd=repo, text=True, check=True, capture_output=True)
    assert "1 - percent" in pricing.read_text()
