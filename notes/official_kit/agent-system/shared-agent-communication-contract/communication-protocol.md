# Communication Protocol

## Purpose

Make agent handoffs understandable and actionable. Messages should contain enough information for the recipient to continue without reconstructing the sender's entire reasoning process.

All messages use the shared vocabulary and evidence convention. YAML below is illustrative; agents may use concise structured prose if all relevant fields remain clear.

## 1. Task assignment

The sender identifies the objective, scope, expected output, constraints, and dependencies.

```yaml
type: task_assignment
task_id: "T-001"
issue: "issue identifier"
assigned_to: "Worker or Checker"
objective: "What needs to be established"
scope:
  included: ["known entity/path/symbols"]
  excluded: ["explicit exclusions, if any"]
starting_context:
  symptom: "observed symptom"
  relevant_hypotheses: ["H1"]
required_actions:
  - "reproduce or inspect..."
deliverables:
  - "evidence-backed finding"
constraints:
  - "base commit / environment / no-edit constraint"
dependencies: []
priority: "normal"
```

## 2. Investigation report

A Worker reports observations and conclusions separately.

```yaml
type: investigation_report
task_id: "T-001"
status: completed
summary: "Short result"
observations:
  - claim: "Directly observed fact"
    status: fact
    evidence: ["reference"]
analysis:
  - claim: "Interpretation of observations"
    status: inference
    evidence: ["reference"]
hypotheses:
  - id: H1
    status: supported
    supporting_evidence: ["reference"]
    counter_evidence: []
tests:
  - command: "exact command"
    result: "pass/fail and relevant output"
  - command: "exact command"
    result: "..."
model_changes_proposed: []
unresolved:
  - "What remains unknown"
recommended_next_step: "Specific next action"
```

A Worker may report `blocked`, `needs_revision`, or partial completion. Do not manufacture a conclusion to make a task appear complete.

## 3. Review feedback

A Checker identifies the reviewed claim, its verdict, and the evidence needed to resolve it.

```yaml
type: review_feedback
task_id: "T-001"
reviewed_artifact: "investigation report / patch"
verdict: "accept | reject | needs_more_evidence | partially_accept"
findings:
  - severity: "blocker | major | minor | note"
    claim_or_location: "specific claim, file, or behavior"
    issue: "What is wrong or missing"
    evidence: ["independent reference"]
    required_resolution: "What would resolve it"
coverage:
  checked: ["specific areas"]
  not_checked: ["limitations"]
new_hypotheses: []
model_changes_proposed: []
```

“Looks good” is not a sufficient review. A review should identify what was checked and what was not.

## 4. Model change proposal

Any agent may propose a change; Architect reconciles the issue-level model.

```yaml
type: model_change_proposal
element_or_edge: "E1 -[relationship]-> E2"
change: "add | remove | reinterpret"
previous_model: "Current understanding"
proposed_model: "New understanding"
reason: "Why the model should change"
evidence: ["references"]
affected_hypotheses: ["H1"]
affected_tasks: ["T-002"]
```

## 5. Decision or diagnosis update

Architect records the current technical position. Project Manager separately records scheduling and assignment decisions.

```yaml
type: diagnosis_update
issue: "issue identifier"
model_revision: 3
current_best_explanation:
  claim: "Current explanation"
  status: hypothesis
  evidence: ["references"]
alternatives:
  - claim: "Alternative explanation"
    status: unresolved
required_checks:
  - "Discriminating check"
task_implications:
  - "Task to create, revise, or close"
```

A diagnosis update does not itself authorize a code change.

## 6. Repair handoff

Before implementation, make the repair scope and authority explicit.

```yaml
type: repair_authorization
issue: "issue identifier"
authorized_worker: "Worker"
target_behavior: "Behavior that must change"
root_cause_position: "Evidence-backed diagnosis"
allowed_scope: ["files or behavior"]
out_of_scope: ["unrelated cleanup"]
acceptance_criteria:
  - "Regression test demonstrates expected behavior"
  - "Relevant existing tests pass"
known_risks: []
```

If the cause is still uncertain, authorize only a diagnostic experiment or a narrowly scoped prototype, not an irreversible broad repair.

## 7. Repair result

```yaml
type: repair_report
issue: "issue identifier"
status: "implemented | blocked | needs_revision"
root_cause_addressed: "How the patch addresses the cause"
changed_files: ["path"]
tests:
  - command: "exact command"
    result: "pass/fail"
regressions_considered: ["related behavior"]
known_limitations: []
patch_reference: "commit or diff reference"
```

## 8. Evaluator feedback

Evaluator reports process-level observations, not a substitute technical verdict.

```yaml
type: evaluation_report
issue: "issue identifier"
outcome: "resolved | unresolved | inconclusive"
process_findings:
  - area: "diagnosis | investigation | review | orchestration | validation"
    observation: "What happened"
    evidence: ["trace, task, report, or timing reference"]
    impact: "Effect on quality, time, or cost"
systemic_failure_modes: []
recommended_process_changes: []
metrics:
  elapsed_time: "if available"
  tool_calls: "if available"
  token_usage: "if available"
  rework_count: "if available"
```

## Status vocabulary

Use:
- `not_started`
- `in_progress`
- `blocked`
- `completed`
- `needs_revision`
- `cancelled`

A task is `completed` when its requested deliverable is supplied, not necessarily when the issue is fixed.

## Handoff quality

Every handoff should make clear:
- what is known;
- what is believed but unverified;
- what evidence supports each important claim;
- what has already been tried;
- what remains unknown;
- what the recipient is expected to do next.

Do not pass a long transcript as a substitute for a concise, evidence-backed handoff.
