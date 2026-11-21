---
name: independent-review
description: Independently challenge diagnosis, evidence, semantic-model claims, and bug-fix patches.
---

# Skill: Independent Review

## When to use

Use when a diagnosis, investigation report, model revision, or repair patch needs independent technical scrutiny.

## Required inputs

- Review assignment and requested verdict.
- Issue statement and expected-behavior source.
- Relevant repository revision.
- Original source/tests/runtime evidence.
- Worker report, diagnosis model, patch, and validation results.

If original evidence is unavailable, state that the review is limited; do not present a report-only review as fully independent.

## Procedure

### 1. Define review claims

Extract the material claims:
- expected behavior;
- actual symptom;
- main root-cause explanation;
- key Entity/Property/Relationship/Function/Action model claims;
- causal link between defect and symptom;
- patch behavior and test coverage.

Do not spend equal effort on incidental wording and causal claims.

### 2. Reconstruct critical evidence independently

Inspect original code and tests. Re-run the reproducer or relevant commands when feasible. Verify that cited lines and test results correspond to the reviewed revision.

Ask:
- Does the evidence show what the report says it shows?
- Does the test exercise the claimed path?
- Is the relevant input/state actually present?
- Could another path produce the same symptom?

### 3. Challenge the semantic model

Check:
- Entity identity and boundaries;
- Property meaning and invariants;
- Relationship direction, cardinality, and lifecycle;
- Relationship definition versus implementation versus usage;
- Function responsibility, inputs, outputs, and side effects;
- Action purpose, invocation, ordering, and state transition.

Look especially for cross-Entity assumptions hidden by Worker task boundaries.

### 4. Challenge the causal explanation

Try to falsify the leading hypothesis:
- identify a counterexample;
- inspect an alternative path;
- check whether the proposed cause is necessary and sufficient for the observed failure;
- determine whether the patch merely masks the symptom;
- identify missing discriminating evidence.

If the diagnosis is plausible but not established, request the specific experiment that would establish it.

### 5. Review the patch

Inspect:
- whether the change addresses the supported cause;
- whether scope is minimal and intentional;
- whether existing invariants and interfaces remain valid;
- boundary cases, error paths, concurrency, lifecycle, and compatibility where relevant;
- whether tests fail before and pass after the patch;
- whether test assertions actually detect the original defect.

Do not demand unrelated cleanup or speculative tests with no connection to the issue.

### 6. Issue a verdict

Use one:
- `accept`: material claims and patch are adequately supported within the stated scope;
- `reject`: a material defect or unsupported causal claim blocks acceptance;
- `needs_more_evidence`: no decisive defect is established, but key claims remain unverified;
- `partially_accept`: some claims or patch areas are sound while others need work.

For every blocker/major finding, include exact location or claim, evidence, impact, and required resolution. State what was not checked.

### 7. Follow through

When a finding is addressed, review the changed claim or code and the evidence relevant to it. Do not automatically reopen every unrelated part of the review.

## Required output

Use the communication contract's `review_feedback` structure:
- verdict;
- findings and severity;
- independent evidence;
- coverage and limitations;
- new hypotheses/model-change proposals;
- concrete resolution criteria.

## Stop / escalate

Escalate unresolved semantic conflicts to Architect with the competing evidence. Escalate missing specification authority to the issue owner/operator. If review cannot be independent because the required source or environment is unavailable, report the limitation and do not imply full approval.
