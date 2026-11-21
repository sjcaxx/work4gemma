"""整合测试: BM25 定位 + 工具集, 演示 "定位 -> 读 -> 改 -> 测 -> 提交" 流程。

在 mini_repo 上注入一个真实 bug, 让 agent 工具链定位并修复它。
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from codetools import AgentTools, CodeGraphBuilder  # noqa: E402

MINI = ROOT / "examples" / "mini_repo"
WORK = ROOT / "examples" / "_work_mini"


def setup_buggy_repo():
    """复制 mini_repo 到临时工作区, 并注入 bug: 折扣率算错。"""
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(MINI, WORK)

    # 注入 bug: apply_discount 用加法而非减法, 折扣变成涨价
    pricing = WORK / "shopping_cart" / "pricing.py"
    text = pricing.read_text()
    text = text.replace(
        "disc = product.price * (1 - percent / 100.0)",
        "disc = product.price * (1 + percent / 100.0)",  # BUG: 应为 1 - percent
    )
    pricing.write_text(text)

    # 加一个会失败的测试, 模拟 task 的 test_patch
    tests = WORK / "test_pricing.py"
    tests.write_text(
        "from shopping_cart.models import Product\n"
        "from shopping_cart.pricing import apply_discount\n\n\n"
        "def test_discount_lowers_price():\n"
        "    p = Product('x', 100)\n"
        "    d = apply_discount(p, 10)\n"
        "    assert d.price == 90.0, f'expected 90.0, got {d.price}'\n"
    )

    # 重新初始化 git, 作为 base_commit
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=WORK, check=True)
    subprocess.run(["git", "add", "-A"], cwd=WORK, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"],
        cwd=WORK, check=True,
    )
    return WORK


def main():
    repo = setup_buggy_repo()
    print(f"工作区: {repo}")

    graph = CodeGraphBuilder(str(repo)).build()
    tools = AgentTools(str(repo), graph=graph)

    issue = (
        "Discounted items are getting MORE expensive. When I apply a 10 percent "
        "discount to a $100 product the price becomes $110 instead of $90. "
        "The discount calculation has the wrong sign."
    )

    print("\n" + "=" * 60)
    print("STEP 1: localize_code (BM25 定位)")
    print("=" * 60)
    loc = tools.localize_code(issue, top=6, files=3)
    print(loc)

    print("\n" + "=" * 60)
    print("STEP 2: 基线测试失败 (复现 bug)")
    print("=" * 60)
    print(tools.run_command("python3 -m pytest test_pricing.py -q 2>&1 | tail -8"))

    print("\n" + "=" * 60)
    print("STEP 3: 用图工具确认符号关系")
    print("=" * 60)
    print(tools.get_code_neighbors("shopping_cart.pricing.apply_discount"))

    print("\n" + "=" * 60)
    print("STEP 4: read_file 看源码")
    print("=" * 60)
    print(tools.read_file("shopping_cart/pricing.py", 1, 10))

    print("\n" + "=" * 60)
    print("STEP 5: edit_file 修复 bug")
    print("=" * 60)
    print(tools.edit_file(
        "shopping_cart/pricing.py",
        "disc = product.price * (1 + percent / 100.0)",
        "disc = product.price * (1 - percent / 100.0)",
    ))

    print("\n" + "=" * 60)
    print("STEP 6: 重跑测试验证修复")
    print("=" * 60)
    print(tools.run_command("python3 -m pytest test_pricing.py -q 2>&1 | tail -5"))

    print("\n" + "=" * 60)
    print("STEP 7: submit_patch")
    print("=" * 60)
    patch = tools.submit_patch()
    print(patch)
    # 只应包含 pricing.py 的修改, 不含 test_pricing.py (那是测试, 不应提交)
    assert "pricing.py" in patch or patch.startswith("diff"), "patch 生成失败"

    print("\n" + "=" * 60)
    print("DONE: 完整 agent 工具链流程跑通")
    print("=" * 60)


if __name__ == "__main__":
    main()
