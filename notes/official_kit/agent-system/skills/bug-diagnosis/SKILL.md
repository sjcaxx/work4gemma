---
name: bug-diagnosis
description: Build an evidence-grounded, bug-centric semantic model and rank plausible root-cause hypotheses.
---

# Skill: Bug Diagnosis

## When to use

Use when an issue has been reported and the system needs a technical explanation of where and why the behavior may be wrong. Use again when new Worker or Checker evidence materially changes the model.

## Required inputs

- Issue description and expected behavior, if available.
- Actual symptom, reproduction, failing test, or observed output.
- Repository revision and relevant source/test access.
- Existing findings and constraints.

If expected behavior is unclear, identify competing interpretations and the source needed to resolve them.

## Initial diagnosis ownership

Architect owns initial technical investigation, including reproducing or characterizing the issue when feasible. PM supplies the raw issue, repository/base revision, and environment constraints; PM must not inspect source, search symbols, run reproduction commands, or form technical hypotheses before Architect reports. Architect establishes the first local semantic model and root-cause hypotheses before recommending bounded Worker tasks.

Attempt a minimal reproduction or inspect available failure evidence. If reproduction is infeasible, state the blocker and proceed with the strongest available static/specification evidence, clearly labeled. Do not present an issue description as reproduced fact.


### 1. Normalize the symptom

Write a compact expected-versus-actual statement:
- What operation or scenario is involved?
- What was expected, and why?
- What actually happened?
- Under what version, configuration, and conditions?
- What evidence establishes the observation?

Do not translate the symptom directly into a root-cause label.

### 2. Establish the behavioral boundary

Identify the externally visible boundary or likely Action:
- API/request, command, event, callback, background job, transaction, or internal operation;
- relevant inputs and preconditions;
- expected output or state transition;
- error or side effect.

If the Action is not yet known, mark it unresolved and identify how to locate it.

### 3. Build the local semantic model

Identify only the relevant:
- Entities and their identities;
- Properties and invariants;
- Relationships and their direction/constraints;
- Functions participating in the behavior;
- Action and its execution path.

For each element, distinguish definition, implementation, and invocation evidence. Label model status.

### 4. Trace the causal path

Use both directions where useful:

- **Backward from symptom**: which output, state, or assertion is wrong; which operation produced it; which inputs and prior state influenced it?
- **Forward from inputs/state**: where are values selected, transformed, validated, stored, and consumed?

Follow the path across Entity boundaries when evidence requires it. Do not assume the nearest function is the cause.

### 5. Generate competing hypotheses

Consider the relevant fault classes without forcing every issue into all of them:

- Entity/Property definition is incorrect.
- Entity/Property implementation violates the intended definition.
- Relationship definition or constraints are wrong.
- Relationship implementation is wrong.
- Relationship usage/traversal/update is wrong.
- Function computation, assumptions, inputs, or side effects are wrong.
- Action orchestration, invocation, ordering, or state transition is wrong.
- Cross-component interaction, configuration, concurrency, lifecycle, or environment is responsible.

For each hypothesis, record:
- what it explains;
- evidence supporting it;
- counter-evidence;
- what observation would distinguish it from alternatives;
- confidence and unresolved assumptions.

### 6. Rank and delegate investigation

Rank by explanatory power and evidence, not by code proximity alone.

Recommend tasks that answer specific questions, such as:
- reproduce a suspected state transition;
- inspect a Relationship definition versus its traversal;
- verify a caller's argument/order;
- test whether an invariant is violated before or after a Function;
- inspect a cross-Entity lifecycle path.

State dependencies and which tasks can run in parallel. Project Manager decides actual assignments.

### 7. Update the model

When evidence arrives:
- compare it with the original claim;
- accept, weaken, reject, or split hypotheses;
- add missing elements/edges;
- record the evidence and affected tasks;
- publish a revised diagnosis.

A Worker finding outside the initial scope is a reason to expand the model, not to force the finding into the old one.

## Required output

Provide:
1. symptom and expected/actual statement;
2. current local semantic model;
3. leading hypotheses and alternatives;
4. evidence and counter-evidence;
5. confidence and unresolved questions;
6. discriminating checks;
7. recommended investigation tasks and dependencies.

Use the communication contract's `diagnosis_update` format where practical.

## Stop / escalate

Do not declare a root cause when multiple explanations remain observationally equivalent. Request a discriminating test or more evidence. Escalate specification ambiguity to the issue owner/operator; escalate conflicting model interpretations through explicit evidence comparison.

## Completion condition

Diagnosis is complete for the current stage when it provides a sufficiently grounded and bounded explanation—or clearly states why the cause remains unresolved—and gives Workers actionable next checks. Diagnosis may be reopened by later evidence.
