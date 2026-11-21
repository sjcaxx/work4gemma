"""验证 codetools: 在 mini_repo 上构建代码图, 检查官方 schema, 测试 9 个工具。"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent / "mini_repo"
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from codetools import CodeGraphBuilder, AgentTools  # noqa: E402
from codetools.graph_builder import CodeGraph  # noqa: E402


def main():
    print("=" * 60)
    print("1) 构建代码图 (scope-aware AST)")
    print("=" * 60)
    builder = CodeGraphBuilder(str(REPO))
    graph = builder.build()
    tools = AgentTools(str(REPO), graph=graph)

    print(f"\n节点数: {graph.g.number_of_nodes()}")
    for nid, attrs in graph.g.nodes(data=True):
        print(f"  {nid}  [{attrs.get('kind')}]")

    print(f"\n边数: {graph.g.number_of_edges()}")
    for src, tgt, data in graph.g.edges(data=True):
        print(f"  {src} --[{data.get('type')}]--> {tgt}")

    print("\n" + "=" * 60)
    print("2) 官方 schema (node_link_data) 兼容性检查")
    print("=" * 60)
    data = graph.to_node_link()
    print("顶层键:", sorted(data.keys()))
    print("directed:", data["directed"], " multigraph:", data["multigraph"])
    print("示例 node:", json.dumps(data["nodes"][1], ensure_ascii=False)[:200])
    print("示例 edge:", json.dumps(data["edges"][0], ensure_ascii=False)[:200])

    # 保存 + 重新加载 (模拟官方 graphs/*.json 的读写往返)
    out_json = Path(__file__).resolve().parent / "mini_graph.json"
    graph.save_json(str(out_json))
    reloaded = CodeGraph.load_official_graph(str(out_json))
    assert reloaded.g.number_of_nodes() == graph.g.number_of_nodes()
    assert reloaded.g.number_of_edges() == graph.g.number_of_edges()
    print(f"\n[OK] node_link 往返一致 -> {out_json}")

    # 检查官方要求的字段是否齐全
    assert all(k in data for k in ("directed", "multigraph", "graph", "nodes", "edges"))
    for n in data["nodes"]:
        assert "id" in n and "name" in n and "text" in n
    for e in data["edges"]:
        assert "source" in e and "target" in e and "type" in e and "key" in e
    print("[OK] nodes 含 id/name/text, edges 含 source/target/type/key -> 与官方 schema 1:1")

    print("\n" + "=" * 60)
    print("3) 工具测试")
    print("=" * 60)

    print("\n-- get_code_neighbors(shopping_cart.main.checkout) --")
    print(tools.get_code_neighbors("shopping_cart.main.checkout"))

    print("\n-- get_code_subgraph([checkout, bulk_price]) --")
    print(tools.get_code_subgraph([
        "shopping_cart.main.checkout",
        "shopping_cart.pricing.bulk_price",
    ]))

    print("\n-- search_similar_code('discount percent price', k=5) --")
    print(tools.search_similar_code("discount percent price", k=5))

    print("\n-- read_file(shopping_cart/pricing.py, 1, 6) --")
    print(tools.read_file("shopping_cart/pricing.py", 1, 6))

    print("\n-- edit_file (0.9 -> 0.8) --")
    print(tools.edit_file("shopping_cart/pricing.py", "        total *= 0.9", "        total *= 0.8"))

    print("\n-- write_file --")
    print(tools.write_file("note.txt", "hello\n"))

    print("\n-- submit_patch --")
    print(tools.submit_patch()[:400])

    print("\n-- get_status --")
    print(tools.get_status())

    print("\n-- run_command --")
    print(tools.run_command('python3 -c "print(1+1)"'))


if __name__ == "__main__":
    main()
