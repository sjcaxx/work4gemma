"""Bound local request history without destroying the full audit transcript.

The byte estimate is intentionally conservative. It is NOT Gemma tokenization.
Keep a template margin and record the server's prompt_eval_count when available.
"""
import copy
import json


def request_units(messages, tools):
    return len(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False).encode("utf-8")) + 64 * len(messages)


def prepare_messages(messages, tools, limit, archive):
    outgoing = copy.deepcopy(messages)
    before = request_units(outgoing, tools)
    stats = {"measurement": "conservative_utf8_bytes_plus_message_overhead",
             "before_units": before, "limit_units": limit,
             "compacted": False, "redacted_outputs": 0, "dropped_turns": 0}
    if before <= limit:
        return outgoing, {**stats, "after_units": before}

    # Preserve system instructions and the original issue. Group tool replies with
    # their assistant call so eviction cannot leave invalid tool-call history.
    split = next((i for i, m in enumerate(outgoing) if m["role"] == "assistant"), len(outgoing))
    pinned = outgoing[:split]
    rounds = []
    for message in outgoing[split:]:
        if message["role"] == "assistant":
            rounds.append([])
        rounds[-1].append(message)
    note = {"role": "system", "content": (
        f"Older tool outputs may be shortened or whole completed rounds omitted. "
        f"Full records: {archive}. Omission does not mean a hypothesis was disproved. "
        "Re-read relevant source or tests before editing; keep replies concise.")}

    def flatten():
        return pinned + [note] + [m for group in rounds for m in group]

    def shorten(group):
        for message in group:
            if message["role"] == "tool" and len(message.get("content", "")) > 640:
                content = message["content"]
                message["content"] = content[:320] + f"\n[shortened; full transcript: {archive}]\n" + content[-320:]
                stats["redacted_outputs"] += 1

    for group in rounds[:-2]:
        shorten(group)
    while len(rounds) > 2 and request_units(flatten(), tools) > limit:
        rounds.pop(0)
        stats["dropped_turns"] += 1
    # A single unusually large recent result must not bypass the check.
    if request_units(flatten(), tools) > limit:
        for group in rounds:
            shorten(group)
    outgoing = flatten()
    after = request_units(outgoing, tools)
    if after > limit:
        raise ValueError(f"context budget exceeded by pinned issue, tool schemas or recent call arguments: {after} > {limit}; narrow the task before retrying")
    return outgoing, {**stats, "compacted": True, "after_units": after}
