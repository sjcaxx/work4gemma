"""在真实仓库 (rich) 上构建代码图, 检查规模和性能。"""

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent / "repos" / "rich"
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from codetools import CodeGraphBuilder, AgentTools  # noqa: E402


def main():
    print(f"仓库: {REPO}")
    t0 = time.time()
    builder = CodeGraphBuilder(str(REPO))
    graph = builder.build()
    dt = time.time() - t0
    print(f"构建耗时: {dt:.2f}s")
    print(f"节点数: {graph.g.number_of_nodes()}")
    print(f"边数: {graph.g.number_of_edges()}")

    # 类型分布
    kinds = {}
    for _, attrs in graph.g.nodes(data=True):
        k = attrs.get("kind", "?")
        kinds[k] = kinds.get(k, 0) + 1
    print(f"节点类型: {kinds}")

    # 抽查一些节点是否合理
    print("\n真实符号示例 (含 text 的非模块节点):")
    shown = 0
    for nid, attrs in graph.g.nodes(data=True):
        if attrs.get("kind") in ("function", "method") and attrs.get("text"):
            print(f"  {nid}  (text {len(attrs['text'])} chars)")
            shown += 1
            if shown >= 8:
                break

    # 抽一个有邻居的节点
    tools = AgentTools(str(REPO), graph=graph)
    print("\n邻居示例:")
    for nid, attrs in graph.g.nodes(data=True):
        if attrs.get("kind") == "function" and len(list(graph.g.out_edges(nid))) >= 2:
            print(f"\n-- get_code_neighbors({nid}) --")
            print(tools.get_code_neighbors(nid, max_neighbors=10))
            break

    # 保存图, 检查 node_link 输出大小
    out = Path(__file__).resolve().parent / "rich_graph.json"
    graph.save_json(str(out))
    print(f"\n图已保存: {out} ({out.stat().st_size/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
