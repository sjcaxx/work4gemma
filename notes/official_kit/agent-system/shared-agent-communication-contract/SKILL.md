---
name: shared-agent-communication-contract
description: Shared language, semantic-model, evidence, and communication rules for agents collaborating on issue-driven bug diagnosis and repair.
---

# Shared Agent Communication Contract

## Purpose

This contract gives all agents a common way to describe a code system, express findings, reason about possible causes, and exchange work. It does not prescribe one universal debugging algorithm and does not replace role-specific skills.

Every participating agent MUST follow this contract when it:
- describes code-system concepts or execution paths;
- reports a symptom, observation, hypothesis, or conclusion;
- assigns, performs, or reviews investigation work;
- proposes a change to the shared model;
- hands work to another agent.

## Contract modules

The contract consists of four complementary modules:

- `vocabulary.md`: shared meanings and boundaries of terms.
- `semantic-model.md`: how to represent entities, properties, relationships, functions, actions, and their connections.
- `evidence-convention.md`: how to distinguish observations, inferences, hypotheses, and verified conclusions.
- `communication-protocol.md`: how agents package tasks, findings, review feedback, and decisions.

These modules are not four sequential workflow stages. They are shared rules used whenever relevant.

## Run-record storage

Store the canonical task board, delivery register, append-only history, and agent reports under `/workspace/.agent_state/<run-id>/` so records persist and can be inspected after the run. Use `run_command` to create, read, and append these records. Do not use `read_file`, `write_file`, or `edit_file` for paths outside `/workspace`.

Before writing run records, use `run_command` to add `.agent_state/` to `/workspace/.git/info/exclude` if it is not already ignored, then verify with `git -C /workspace check-ignore -q .agent_state/<run-id>/task_board.yaml`. Never add run records to the repository or patch. Ordinary scratch/reproduction files may use `/tmp`; they are not canonical run records.

The `agent_tool` return value remains the primary Agent-to-Agent handoff. Do not rely on filesystem sharing across separate `agent_tool` calls unless verified in the runtime.



1. Use the defined terms consistently. If a term does not fit, explain the mismatch instead of silently redefining it.
2. Separate **definition**, **implementation**, and **invocation**. A correct definition can have a faulty implementation; a correct implementation can be invoked incorrectly.
3. Describe only the part of the system needed to explain the current issue. Expand the model when evidence points outside the current boundary.
4. Label claims as facts, hypotheses, inferences, or verified conclusions.
5. Attach evidence to material claims. Give enough location or reproduction detail for another agent to inspect it.
6. State uncertainty and counter-evidence. Do not hide unresolved alternatives.
7. Make handoffs actionable: identify what was established, what remains unknown, what was tried, and what the recipient is expected to do.
8. Propose changes to shared model definitions explicitly. Do not silently change the meaning of an existing entity or relationship.
9. Preserve disagreements until evidence resolves them. Consensus is not a substitute for verification.
10. Keep messages proportional to the task. Do not repeat the entire model or contract in every message.

## Minimal claim format

For a material claim, communicate:

- **Claim**: what is being asserted.
- **Status**: fact / hypothesis / inference / verified conclusion.
- **Scope**: which entity, relationship, function, action, path, or behavior it concerns.
- **Evidence**: code, test, runtime, or specification evidence.
- **Counter-evidence / uncertainty**: what could make the claim wrong.
- **Next step**: what should be checked or changed, if anything.

## Conflict handling

If agents disagree:
1. identify the exact claim or model element in dispute;
2. compare the evidence and scope behind each position;
3. seek a discriminating test or inspection;
4. record the result and update the model;
5. escalate to Architect for model-level reconciliation or Project Manager for resource/priority decisions.

Neither Architect seniority nor Worker implementation ownership makes a claim true by default.

## Scope

This contract governs collaboration language and information exchange. It does not grant repository permissions, authorize code changes, define benchmark policy, or replace the competition's execution constraints.
