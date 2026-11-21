# Evidence Convention

## Purpose

Make every important claim inspectable and prevent plausible explanations from being mistaken for established causes.

## Evidence categories

### Code evidence

Source definitions, call sites, control flow, data structures, comments where relevant, build configuration, and version-specific implementation details.

Record repository revision and file/line or symbol references where possible.

### Test evidence

Existing tests, newly written reproductions, regression tests, test output, and the exact command/environment used.

A test is evidence for what it actually exercises. State its coverage boundary.

### Runtime evidence

Logs, traces, debugger observations, assertions, crash reports, metrics, memory/state inspection, or a minimal runtime experiment.

Include enough context to reproduce or independently inspect the observation.

### Specification evidence

Issue text, documented behavior, API contract, design document, invariant, compatibility requirement, or other authoritative expected-behavior source.

If sources conflict, record the conflict rather than silently choosing one.

## Claim status

- `fact`: directly observed in a named source or experiment.
- `hypothesis`: proposed explanation not yet established.
- `inference`: reasoning from one or more facts.
- `verified_conclusion`: survived relevant checks and alternatives within a stated scope.

A code comment is evidence that a comment exists; it is not automatically proof that runtime behavior matches it.

## Evidence record

Use a compact record:

```yaml
claim: "The caller passes a stale identifier."
status: hypothesis
scope: "Action A -> Function F"
evidence:
  - type: code
    reference: "src/module.c:120-145"
    observation: "The value is read before the refresh call."
  - type: test
    reference: "test_refresh_order"
    observation: "Reordering the calls changes the result."
counter_evidence:
  - "The refresh may update the object through a shared reference."
confidence: medium
next_check: "Inspect aliasing and add a test that asserts the identifier after refresh."
```

## Claim-to-evidence rules

1. Attach evidence to the specific claim it supports.
2. Distinguish direct observation from interpretation.
3. Prefer a minimal reproducer over an unverified narrative.
4. Record negative results when they eliminate a plausible explanation.
5. Record exact commands, relevant configuration, revision, and environment for test/runtime claims.
6. Do not use “the code looks wrong” as a complete explanation. Identify the violated expected behavior or invariant.
7. Do not claim a root cause from proximity alone.
8. If evidence is incomplete, say what is missing.

## Root-cause verification

A root-cause claim should normally satisfy all applicable conditions:

- The issue can be reproduced or the symptom is otherwise reliably established.
- The proposed cause explains the observed behavior and the expected/actual difference.
- The relevant code or runtime path is identified.
- Competing explanations have been tested or explicitly remain unresolved.
- A discriminating experiment, targeted test, or equivalent evidence supports the causal link.
- The proposed repair addresses the cause rather than merely masking the symptom.
- Relevant regression tests pass, or any failure is explained.

Not every repository issue permits full runtime reproduction. In that case, state the limitation and use the strongest available static/specification evidence without overstating certainty.

## Counter-evidence and confidence

For each material hypothesis, ask:
- What observation would make this hypothesis unlikely?
- What alternative cause could produce the same symptom?
- Does the evidence cover the same version, configuration, and execution path?
- Is the test actually exercising the suspected branch?

Use confidence labels only as summaries; they do not replace evidence:
- `low`: plausible, weak or indirect support.
- `medium`: multiple relevant observations, but important alternatives remain.
- `high`: direct, discriminating evidence; remaining uncertainty is bounded.

## Verification scope

Every verified conclusion must state its scope, for example:
- “Verified for this reproducer and configuration.”
- “Verified for the affected call path; concurrency behavior remains untested.”
- “Patch passes the targeted regression test and the relevant existing test subset.”

Avoid unbounded statements such as “the bug is fixed” when only a narrow test has been run.
