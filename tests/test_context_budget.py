"""Exercise the actual Ollama request boundary without requiring a model server."""
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(ROOT / "src"))
import agent as module


class Response(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


def exercise(monkeypatch, tmp_path, messages):
    instance = module.GemmaAgent(str(tmp_path))
    instance.messages = messages
    payloads = []
    def receive(request, timeout):
        payloads.append(json.loads(request.data))
        return Response(b'{"message":{"role":"assistant","content":"ok"}}')
    monkeypatch.setattr(module.urllib.request, "urlopen", receive)
    instance._chat()
    return instance, payloads[0]


def long_history():
    messages = [{"role": "system", "content": "Keep the behavior unchanged."},
                {"role": "user", "content": "BUG-42: percent discount should lower price."}]
    for i in range(24):
        messages.extend([
            {"role": "assistant", "content": f"Inspect candidate {i}.", "tool_calls": [
                {"function": {"name": "read_file", "arguments": {"filepath": f"file_{i}.py"}}}]},
            {"role": "tool", "tool_name": "read_file", "content": f"EVIDENCE-{i}\n" + "x = 1\n" * 950},
        ])
    return messages


def test_long_trajectory_is_bounded_and_archived(monkeypatch, tmp_path):
    original = long_history()
    instance, payload = exercise(monkeypatch, tmp_path, original)
    serialized = json.dumps({"messages": payload["messages"], "tools": payload["tools"]}, ensure_ascii=False).encode()
    # Conservative byte ceiling, deliberately not presented as a real token count.
    allowance = module.NUM_CTX - module.MAX_OUTPUT_TOKENS - 2048
    assert len(serialized) + 64 * len(payload["messages"]) <= allowance
    assert payload["messages"][:2] == original[:2]
    assert any("file_23.py" in json.dumps(m) for m in payload["messages"])
    assert original == long_history(), "Compaction must not destroy the full transcript"
    artifacts = list(instance.trace_dir.glob("request-*.json"))
    assert artifacts
    record = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert record["full_messages"] == original
    assert record["measurement"] == "conservative_utf8_bytes_plus_message_overhead"
    assert record["compacted"] is True
    # Never retain an orphaned tool result or remove the call that explains it.
    pending = 0
    for message in payload["messages"]:
        if message["role"] == "assistant":
            assert pending == 0
            pending = len(message.get("tool_calls", []))
        elif message["role"] == "tool":
            assert pending > 0
            pending -= 1
    assert pending == 0


def test_small_history_unchanged(monkeypatch, tmp_path):
    messages = long_history()[:4]
    _, payload = exercise(monkeypatch, tmp_path, messages)
    assert payload["messages"] == messages


def test_oversized_issue_is_rejected_before_network(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **k: calls.append(a))
    instance = module.GemmaAgent(str(tmp_path))
    instance.messages = [{"role": "system", "content": "system"},
                         {"role": "user", "content": "huge issue " * 10000}]
    with pytest.raises(ValueError, match="context budget"):
        instance._chat()
    assert not calls


def test_submit_patch_is_not_cut_at_tool_output_limit(tmp_path):
    instance = module.GemmaAgent(str(tmp_path))
    patch = "diff --git a/a.py b/a.py\n" + "+line\n" * 2000
    instance.tools.submit_patch = lambda: patch
    assert instance._run_tool("submit_patch", {}) == patch


def test_long_solve_preserves_edit_test_and_patch(monkeypatch, tmp_path):
    import subprocess
    import types
    from urllib.error import HTTPError

    (tmp_path / "pricing.py").write_text("def discount(price):\n    return price * 1.1\n")
    (tmp_path / "test_pricing.py").write_text("from pricing import discount\ndef test_discount():\n    assert discount(100) == 90\n")
    (tmp_path / "reference.txt").write_text("large irrelevant source excerpt\n" * 190)
    for args in [("init", "-q"), ("add", "."), ("-c", "user.name=test", "-c", "user.email=t@t", "commit", "-qm", "base")]:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    sequence = [("read_file", {"filepath": "reference.txt"})] * 18 + [
        ("edit_file", {"filepath": "pricing.py", "old_string": "price * 1.1", "new_string": "price * 0.9"}),
        ("run_command", {"command": f'"{Path(sys.executable).as_posix()}" -m pytest test_pricing.py -q -p no:cacheprovider'}),
        ("submit_patch", {}),
    ]
    sent_sizes = []
    def receive(request, timeout):
        payload = json.loads(request.data)
        # Simulate a bounded backend independently of the guard's implementation.
        size = len(json.dumps({"messages": payload["messages"], "tools": payload["tools"]}, ensure_ascii=False).encode())
        sent_sizes.append(size)
        if size > 30000:
            raise HTTPError(request.full_url, 400, "context length exceeded (scripted byte limit)", {}, None)
        name, args = sequence[len(sent_sizes) - 1]
        return Response(json.dumps({"message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": name, "arguments": args}}]},
            "prompt_eval_count": 123, "eval_count": 20}).encode())
    monkeypatch.setattr(module.urllib.request, "urlopen", receive)
    original = types.ModuleType("codearch_original_agent")
    original.__file__ = module.__file__
    source = subprocess.check_output(["git", "show", "HEAD:bench/agent.py"], cwd=ROOT).decode("utf-8")
    exec(compile(source, "original_agent.py", "exec"), original.__dict__)
    baseline_patch = original.GemmaAgent(str(tmp_path), url="http://scripted-test.invalid/api/chat").solve("A 10 percent discount on price 100 must produce 90, not 110.")
    assert baseline_patch == ""
    assert max(sent_sizes) > 30000
    baseline_sizes = sent_sizes.copy()
    sent_sizes.clear()
    instance = module.GemmaAgent(str(tmp_path), url="http://scripted-test.invalid/api/chat")
    patch = instance.solve("A 10 percent discount on price 100 must produce 90, not 110.")
    assert len(sent_sizes) == len(sequence)
    assert max(sent_sizes) <= 30000
    assert "return price * 0.9" in patch
    assert "reference.txt" not in patch and "test_pricing.py" not in patch
    outputs = [p.read_text(encoding="utf-8") for p in instance.trace_dir.glob("tool-*.txt")]
    assert any("1 passed" in result for result in outputs)
    records = [json.loads(p.read_text(encoding="utf-8")) for p in instance.trace_dir.glob("request-*.json")]
    assert any(record["compacted"] for record in records)
    assert all(record["server_usage"]["prompt_eval_count"] == 123 for record in records)
    report = {"test_type": "scripted_backend_with_30000_byte_input_limit",
              "real_model_inference": False, "real_token_counts": False,
              "baseline_request_bytes": baseline_sizes,
              "patched_request_bytes": sent_sizes,
              "baseline_completed": False, "patched_completed": True,
              "patched_target_test_passed": True,
              "patched_trace_dir": str(instance.trace_dir)}
    (ROOT / "dist/context_guard_ab.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def test_unicode_multicall_history_keeps_complete_rounds():
    from codetools.context_budget import prepare_messages, request_units
    messages = [{"role": "system", "content": "system"}, {"role": "user", "content": "original issue"}]
    for i in range(20):
        messages.append({"role": "assistant", "content": f"round {i}", "tool_calls": [
            {"function": {"name": "read_file", "arguments": {"filepath": "a.py"}}},
            {"function": {"name": "run_command", "arguments": {"command": "pytest"}}},
        ]})
        messages.extend([{"role": "tool", "tool_name": name, "content": "诊断信息\n" * 2000}
                         for name in ["read_file", "run_command"]])
    output, stats = prepare_messages(messages, [], 12000, "evidence.json")
    assert request_units(output, []) <= 12000
    assert stats["dropped_turns"] > 0
    assert output[:2] == messages[:2]
    assert output[-3]["content"] == "round 19"
    pending = 0
    for m in output:
        if m["role"] == "assistant":
            assert pending == 0
            pending = len(m.get("tool_calls", []))
        elif m["role"] == "tool":
            assert pending > 0
            pending -= 1
    assert pending == 0
