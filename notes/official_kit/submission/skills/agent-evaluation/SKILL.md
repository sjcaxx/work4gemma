---
name: agent-evaluation
description: Evaluate multi-agent bug-fixing quality, efficiency, failure modes, and opportunities for controlled improvement.
---

# Skill: Agent Evaluation

## When to use

Use after an issue reaches a meaningful outcome, after a significant process failure, or periodically across a set of tasks to identify recurring system weaknesses.

Do not use this skill as a substitute for reviewing the current patch.

## Required inputs

- Task assignments, dependencies, and status history.
- Architect diagnosis and model revisions.
- Worker investigation and repair reports.
- Checker findings and their resolution history.
- Test outcomes and final issue status.
- Timing, token, tool-call, and rework data where available.

If a metric was not recorded, mark it unavailable rather than estimating it.

## Procedure

### 1. Reconstruct the process timeline

Record major events:
- issue intake;
- first useful reproduction;
- initial diagnosis;
- task assignments and changes;
- decisive evidence;
- diagnosis revisions;
- repair authorization and patch;
- Checker findings;
- validation and final outcome.

Identify waiting time, repeated work, and rework separately from active investigation time when data permits.

### 2. Assess outcome and process separately

Outcome questions:
- Was the expected behavior restored?
- Did the patch pass the required tests?
- What limitations remain?

Process questions:
- Did the system reach the result with sound reasoning?
- Were important assumptions challenged?
- Was the result lucky, reproducible, and evidence-backed?
- Did the process waste effort or omit necessary checks?

A successful patch does not prove the process was good. An unresolved issue does not automatically prove the process was poor.

### 3. Locate the failure or strength

Assess:
- **Architect**: model accuracy, hypothesis quality, ranking, and responsiveness to new evidence.
- **Worker**: reproduction quality, depth of investigation, scope discipline, and validation.
- **Checker**: independence, coverage, ability to detect unsupported claims and defects.
- **Project Manager**: decomposition, dependencies, parallelism, assignment fit, and blocker handling.
- **Shared contract**: terminology consistency, evidence traceability, and handoff quality.
- **Skills**: whether instructions led to useful actions or caused unnecessary ceremony.

Trace an observed failure to the earliest process point where it could reasonably have been prevented.

### 4. Analyze efficiency with context

When available, compare:
- elapsed time;
- tool calls and tool failures;
- token usage;
- number of hypotheses explored;
- number of task reassignments;
- patch iterations and review cycles;
- duplicated investigation;
- time spent waiting on dependencies.

Do not optimize for fewer tokens or calls at the expense of correctness. Compare similar task classes where possible.

### 5. Identify systemic patterns

Separate:
- one-off mistake;
- unclear role boundary;
- missing skill capability;
- poor skill execution;
- missing evidence or instrumentation;
- orchestration issue;
- environment or benchmark limitation.

A single example can motivate a hypothesis for process improvement, but recurring claims need multiple observations.

### 6. Recommend a controlled change

For each recommendation, state:
- observed failure mode;
- supporting examples;
- proposed change and where it belongs (role, skill, contract, orchestration, instrumentation);
- expected benefit;
- possible downside;
- how a later task will test whether it helped.

Prefer one small, measurable change over rewriting every prompt after one failure.

### 7. Feed improvements back

Submit proposed edits to the relevant owner. Preserve the previous version or record the change so later evaluations can compare outcomes. Do not silently change shared definitions or role authority.

## Required output

Produce an evaluation report with:
- issue outcome and validation scope;
- process timeline;
- role-by-role findings;
- evidence for strengths and failures;
- cost/latency observations where available;
- systemic failure modes;
- prioritized recommendations and validation plan.

## Stop / escalate

If the evidence is insufficient to distinguish agent failure from missing environment, incomplete issue specification, or benchmark limitation, report the uncertainty. Do not assign blame based on outcome alone.
