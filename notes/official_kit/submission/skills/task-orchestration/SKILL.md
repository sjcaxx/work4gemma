---
name: task-orchestration
description: Intake, decompose, assign, coordinate, and close issue-driven bug-fixing work across multiple agents.
---

# Skill: Task Orchestration

## When to use

Use when a new issue enters the system, an existing investigation needs reassignment or reprioritization, a blocker needs coordination, or repair/review work must be scheduled.

## Required inputs

- Issue statement and available expected-behavior source.
- Repository/base commit and environment constraints.
- Available agents and their current workload/capabilities.
- Current Architect diagnosis, if available.
- Time, tool, token, or execution constraints, if known.

If critical context is missing, request it or create a bounded intake task. Do not invent repository facts.

## Procedure

### 1. Establish the task envelope without technical investigation

Create the minimal canonical task board and assign the next stable task/run identifiers before dispatch. Record only the raw issue, expected-behavior source if supplied, repository/base revision, environment constraints, edit restrictions, and stage completion criteria. Do not inspect source, search symbols/call graphs, run a reproduction, infer causes, or choose technical work packages at intake. Repository context is metadata for Architect, not permission for PM investigation.

Immediately call Architect for initial reproduction or characterization and semantic diagnosis. If the Architect handoff is empty, malformed, or fails, record the failure and retry with the same task number; do not investigate or assign Workers as a substitute.

### 2. Obtain technical decomposition from Architect

Ask Architect for:
- the current bug-centric model;
- leading hypotheses and alternatives;
- likely investigation boundaries;
- cross-entity dependencies;
- checks that distinguish competing explanations;
- which work can safely proceed in parallel.

Do not independently invent technical partitions from file names alone.

### 3. Create work packages and register assignments

A useful task has a stable task ID and run ID, one objective, bounded scope, named owner, explicit input artifacts and deliverables, dependencies, constraints, acceptance criteria, and completion condition.

Register each assignment in the canonical board before dispatch. Track at minimum: `task_id`, `run_id`, `issue`, `owner`, `type`, `objective`, `scope`, `status`, `priority`, `dependencies`, `blocked_by`, `acceptance_criteria`, `input_artifacts`, `deliverable`, `evidence`, `next_action`, and `updated_at`. Add fields when real work requires them; do not force every communication to carry every field.

Partition by meaningful behavior, Entity, execution path, or hypothesis—not automatically by file or directory.

Avoid:
- two Workers unknowingly changing the same code;
- separate tasks that require incompatible interpretations of one Relationship;
- tasks so broad that no one can report a decisive result;
- tasks so small that coordination costs exceed the work.

### 4. Decide parallelism

Parallelize when tasks have sufficiently independent evidence paths or code areas.

Keep work sequential when:
- one result determines the next useful investigation;
- shared mutable code creates collision risk;
- multiple tasks depend on one unresolved semantic definition;
- a discriminating experiment should be run before broader exploration.

Architect recommends technical dependencies; Project Manager makes the actual allocation decision.

### 5. Assign review deliberately

For important diagnosis and repair claims, assign a Checker with:
- the original issue and relevant revision;
- the claim or artifact to review;
- access to underlying evidence;
- an explicit request for independent inspection;
- expected review output and deadline.

Do not ask Checker merely to “confirm” the Worker.

### 6. Manage progress and changes

On each update, compare the report with its deliverable and acceptance criteria; register the delivery, sender, recipient, artifact type/revision, evidence location, status, and next action; identify blockers; decide whether to continue, narrow, expand, split, or cancel; append status, scope, model, authorization, review, and rework changes to history; and notify affected agents.

When Worker evidence invalidates Architect's model, route it to Architect for reconciliation. Do not suppress it to preserve the original plan.

### 7. Authorize repair

Authorize implementation only when:
- the target behavior and acceptance criteria are explicit;
- the technical basis is adequate for the risk of the change;
- the allowed scope is clear;
- the Worker knows whether experiments or edits are permitted.

If diagnosis remains uncertain, authorize a narrow diagnostic change or experiment only when that is the intended objective.

### 8. Preserve provenance and close the coordination loop

For every execution, preserve Git and submission/config revisions, task/data version, model/harness when known, exact commands, timing, tool usage, results, traces, and patches. Store the canonical task board, delivery register, history, and reports under `/workspace/.agent_state/<run-id>/` using `run_command`, not `/tmp`. Ensure `.agent_state/` is excluded through `/workspace/.git/info/exclude` before writing so it cannot enter the patch. Mark unavailable provenance explicitly.

Close only after required Worker deliverables are registered; Checker findings are resolved or accepted as limitations; tests and skipped checks are recorded; patch reference and changed files are known; risks, provenance, and handoff history are preserved; and Evaluator can access process records when evaluation is required.

### Phase gates

Use these phases explicitly: `intake` (PM records and delegates only), `architect_diagnosis` (Architect performs initial reproduction/characterization and model building), `worker_investigation` (Worker performs bounded experiments or authorized repair), `independent_review` (Checker reviews independently), and `coordination_close` (PM records outcome; Evaluator assesses process when assigned). Do not enter Worker investigation until a valid Architect report defines the relevant questions, hypotheses, evidence gaps, and dependencies.


- **Blocked**: a concrete dependency or missing input prevents progress. Assign an unblock action.
- **Needs revision**: the deliverable exists but fails its stated acceptance criteria. Return specific findings.
- **Completed**: the task deliverable is supplied; this does not imply the issue is fixed.
- **Issue resolved**: only use when the technical acceptance criteria are met within the stated validation scope.

## Run-record storage

Store the canonical task board, delivery register, append-only history, and agent reports under `/workspace/.agent_state/<run-id>/` so records persist and can be inspected after the run. Use `run_command` to create, read, and append these records. Do not use `read_file`, `write_file`, or `edit_file` for paths outside `/workspace`.

Before writing run records, use `run_command` to add `.agent_state/` to `/workspace/.git/info/exclude` if it is not already ignored, then verify with `git -C /workspace check-ignore -q .agent_state/<run-id>/task_board.yaml`. Never add run records to the repository or patch. Ordinary scratch/reproduction files may use `/tmp`; they are not canonical run records.

The `agent_tool` return value remains the primary Agent-to-Agent handoff. Do not rely on filesystem sharing across separate `agent_tool` calls unless verified in the runtime.



Maintain one canonical, inspectable task board and delivery register per issue/run, plus append-only status and handoff history. Use YAML, JSON, Markdown table, or another format readable by available agents. Keep core fields stable and extend the record when real work exposes a need. Preserve it where subsequent agents and Evaluator can read it. Keep technical diagnosis in Architect's model rather than duplicating it as managerial prose.

## Stop / escalate

Escalate to Architect for unresolved technical-model conflicts; to Checker for independent verification; and to the appropriate competition/operator authority for missing permissions, unavailable infrastructure, or policy constraints. Do not resolve technical uncertainty by managerial fiat.
