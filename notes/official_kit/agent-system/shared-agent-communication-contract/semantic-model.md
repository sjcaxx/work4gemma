# Shared Semantic Model

## Purpose

Describe the smallest useful semantic model that explains the issue and supports investigation. The model should help agents reason about meaning, implementation, and execution without turning the entire repository into one giant graph.

## Model elements

Represent relevant elements using these categories:

- `Entity`
- `Property`
- `Relationship`
- `Function`
- `Action`

Each element should have a stable local identifier, a concise meaning, and evidence or an explicit uncertainty status.

## Relationship patterns

The following are common patterns, not an exhaustive ontology:

| Connection | Meaning |
|---|---|
| Entity — Property | Property belongs to or describes an Entity |
| Entity — Relationship — Entity | A meaningful association between two Entities |
| Function — Entity | Function reads, creates, updates, deletes, validates, or otherwise uses an Entity |
| Function — Property | Function reads, derives, validates, or changes a Property |
| Function — Relationship | Function creates, traverses, checks, or changes a Relationship |
| Action — Function | Function participates in the Action's execution |
| Action — Entity | Action operates on or changes an Entity |
| Action — Relationship | Action creates, removes, traverses, or relies on a Relationship |

Use explicit edge labels such as `reads`, `writes`, `validates`, `creates`, `deletes`, `traverses`, `invokes`, `guards`, or `derives`. Avoid an unlabeled generic “connected to” edge when the meaning matters.

## Keep three views distinct

### 1. Definition view

What does the system say the concepts and constraints mean?

Examples:
- Entity identity and ownership.
- Property meaning, type, nullability, and invariant.
- Relationship direction, cardinality, and lifecycle.
- Action's intended purpose and preconditions.

### 2. Implementation view

How is the definition realized in code?

Examples:
- Data structures and storage layout.
- Functions that implement validation or updates.
- Relationship indexes, pointers, foreign keys, or traversal logic.
- Error handling and synchronization.

### 3. Invocation view

How is the implementation reached and used?

Examples:
- Entry point, event handler, API, callback, or command.
- Caller/callee sequence.
- Arguments, configuration, permissions, and execution context.
- Ordering, retries, concurrency, and transaction boundaries.

Do not infer one view automatically from another. A schema can be correct while the code violates it; code can be correct while a caller uses it incorrectly.

## Bug-centric modeling procedure

1. Write down the observed symptom and expected behavior.
2. Identify the directly involved Entity, Property, Action, Function, or observable boundary, if known.
3. Trace backward from the incorrect result to the operations and values that produced it.
4. Trace forward from relevant inputs and state to see where they are transformed or consumed.
5. Identify Relationships needed to explain the path, including their definition and their actual usage.
6. Add alternative explanations and missing links rather than forcing an early single-cause model.
7. Expand the model only when evidence crosses its current boundary.
8. Update element status and links when new evidence changes the explanation.

The process may start at an Action, a failed assertion, a corrupted Property, or a suspicious Relationship. It is not required to follow a fixed order.

## Model status

Every important element or claim should carry one of:

- `observed`: directly located or observed in code, tests, or runtime.
- `inferred`: derived from evidence but not directly established.
- `hypothesized`: proposed explanation awaiting investigation.
- `unresolved`: relevant but currently unknown or disputed.
- `verified`: established within an explicitly stated scope.

Do not mark an entire model “verified” merely because one path or test was verified.

## Suggested compact representation

```yaml
issue: "short issue identifier"
symptom:
  expected: "expected behavior"
  actual: "observed behavior"
  evidence:
    - "test or reproduction reference"

elements:
  - id: E1
    kind: Entity
    name: "Relevant entity"
    meaning: "What this entity represents"
    status: observed
    evidence: ["path/to/file:line or test reference"]

  - id: P1
    kind: Property
    owner: E1
    name: "Relevant property"
    meaning: "What the value means"
    status: unresolved

  - id: F1
    kind: Function
    name: "Relevant function"
    responsibility: "What it computes or changes"
    status: observed

  - id: A1
    kind: Action
    name: "Relevant operation"
    intent: "Why this operation occurs"
    status: inferred

relationships:
  - from: A1
    to: F1
    type: invokes
    status: observed
    evidence: ["call-site reference"]

hypotheses:
  - id: H1
    claim: "Possible explanation"
    supporting_evidence: []
    counter_evidence: []
    discriminating_check: "What would distinguish this from alternatives"
    status: hypothesized

open_questions:
  - "Unresolved question"
```

## Model change discipline

When changing the model, state:
- the element or relationship being added, removed, or reinterpreted;
- the previous understanding;
- the new understanding;
- the evidence causing the change;
- which existing hypotheses or tasks are affected.

Architect maintains the coherent issue-level model, but any agent may propose a correction. No agent owns the truth independently of evidence.
