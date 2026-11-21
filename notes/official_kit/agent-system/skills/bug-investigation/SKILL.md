---
name: bug-investigation
description: Reproduce, inspect, test hypotheses, collect evidence, and implement an explicitly authorized bug fix.
---

# Skill: Bug Investigation

## When to use

Use for concrete technical investigation of an assigned issue or hypothesis. Continue into repair only when the assignment explicitly authorizes code changes.

## Required inputs

- Task assignment with objective and scope.
- Issue context and current diagnosis.
- Repository revision, build/test instructions, and environment.
- Edit permission and acceptance criteria, if repair is requested.

If the task does not say whether edits are allowed, assume diagnosis-only and ask before changing code.

## Procedure

### 1. Verify context

Record:
- repository and base commit;
- current branch/worktree state;
- relevant build configuration;
- exact task scope and edit restrictions.

Do not overwrite unrelated user or agent changes.

### 2. Reproduce or characterize

Attempt the smallest reliable reproduction:
- run the failing test or exact command;
- capture relevant output and exit status;
- record environment/configuration;
- reduce the reproduction if doing so preserves the failure.

If reproduction is impossible, state the blocker and establish the strongest available static or test-based characterization.

### 3. Inspect the real path

Inspect source definitions and call sites. Trace:
- inputs and argument values;
- relevant Entity and Property state;
- Relationship creation, traversal, and update;
- participating Functions;
- Action entry point and sequencing;
- error handling, retries, synchronization, and transaction boundaries where relevant.

Do not stop at the assigned file if evidence shows the cause crosses its boundary. Report material scope expansion.

### 4. Test hypotheses

For each assigned or newly discovered hypothesis:
- identify the claim being tested;
- choose an observation that would distinguish it from alternatives;
- run the smallest useful inspection or experiment;
- record both positive and negative results;
- update the diagnosis when evidence contradicts it.

Do not modify production code merely to see whether a guess works unless the task explicitly authorizes a diagnostic experiment.

### 5. Report diagnosis findings

Separate:
- direct observations;
- inferences;
- supported hypotheses;
- rejected hypotheses;
- unresolved questions.

Propose semantic-model changes with evidence. Do not silently reinterpret shared Entities or Relationships.

### 6. Implement only when authorized

Before editing, confirm:
- target behavior;
- accepted root-cause position;
- allowed files/behavior;
- out-of-scope changes;
- acceptance criteria.

Then:
- make the smallest coherent fix;
- preserve existing interfaces and invariants unless the task authorizes changing them;
- add or update a regression test that fails before the fix where feasible;
- avoid unrelated refactoring;
- inspect the final diff for accidental changes.

### 7. Validate

Run, as applicable:
- the new regression test;
- the previously failing test;
- directly related tests;
- relevant broader test subset;
- build, static checks, or formatting required by the repository.

Record exact commands and outcomes. Distinguish not-run, failed, skipped, and passed. Do not claim broad coverage from a narrow test.

### 8. Handoff

Provide:
- concise result;
- evidence and code references;
- exact reproduction/test commands and results;
- model changes proposed;
- patch reference and changed files, if any;
- known limitations and unresolved risks;
- recommended next action for Architect, Checker, or Project Manager.

## Completion condition

The assigned deliverable is complete when another agent can inspect the evidence and continue without guessing. A repair task additionally requires a coherent patch and an honest validation report. Independent approval belongs to Checker.
