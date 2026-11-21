# Shared Vocabulary

This file defines the terms agents use when discussing the code system and a reported bug. These are working abstractions for diagnosis, not claims that every codebase literally contains objects with these names.

## Core semantic concepts

### Entity

A unit with a distinguishable identity in the system's domain or internal logic. An Entity may be represented by a data structure, database row, object, module-owned record, or another identifiable unit.

An Entity definition describes what the entity means and what invariants it is expected to maintain. An implementation describes how that entity is represented and manipulated in code.

### Property

A value or characteristic associated with an Entity. A Property may represent data, configuration, identity, derived state, or an invariant-bearing attribute.

A Property error is a symptom category, not a root-cause category. The wrong value may originate in an incorrect Entity definition, faulty implementation, incorrect Relationship, Function, Action, or execution path.

### Relationship

A meaningful association between Entities. A Relationship has semantics and may have direction, cardinality, ownership, lifecycle rules, ordering, or other constraints.

Distinguish:
- **Relationship definition**: what association exists and what its semantics and constraints are.
- **Relationship implementation**: how the association is represented or maintained.
- **Relationship usage**: how code traverses, constructs, updates, or interprets it.

A wrong traversal does not by itself prove that the Relationship definition is wrong.

### Function

A code unit that performs computation or processing. A Function may read data, derive values, call other functions, and may or may not change state.

Function is a semantic role in the diagnosis model; it does not require a language-level function declaration. A method, callback, procedure, handler, or multi-step code unit may serve this role.

### Action

A purposeful operation that the system performs in response to a request, event, command, or internal trigger. An Action describes the operation in terms of its intent, execution flow, and relevant state changes. It may be implemented by one or more Functions.

Do not assume one Action equals one function, endpoint, transaction, or source file. Identify the Action from behavior and execution context.

## Execution and behavior terms

### Bug Symptom

The externally observed incorrect behavior or failed expectation. A symptom is the starting point for diagnosis, not proof of a particular cause.

### Expected Behavior

The behavior supported by an issue specification, test, documented contract, established invariant, or other defensible source.

### Actual Behavior

The behavior observed in a reproduction, test, runtime trace, or other concrete observation.

### Execution Path

The ordered or branching sequence of calls, handlers, callbacks, or operations through which an Action is carried out.

### Data Flow

The movement, transformation, selection, or propagation of values through the system.

### State Transition

A change from one relevant system state to another. Describe the precondition, operation, and resulting state when they matter to the bug.

### Invariant

A condition that must remain true across relevant operations or states.

### Root Cause

A defect in a definition, implementation, relationship, function, action, or execution interaction that explains the symptom and is supported by evidence. A plausible location is not yet a root cause.

### Counter-evidence

Evidence that weakens, contradicts, or limits a claim or hypothesis.

## Knowledge-status terms

- **Fact**: directly observed or explicitly specified, with evidence and scope.
- **Hypothesis**: a possible explanation that has not been established.
- **Inference**: a reasoned conclusion drawn from facts, but not directly observed.
- **Verified Conclusion**: a claim tested against relevant evidence and alternatives within a stated scope.
- **Unknown**: information not yet established.
- **Evidence**: inspectable material that supports or challenges a claim.

## Diagnostic dimensions

Use these dimensions to avoid collapsing different failure modes:

| Dimension | Question |
|---|---|
| Definition | Is the intended meaning, identity, property, relationship, or invariant wrong? |
| Implementation | Does the code correctly realize the intended definition and behavior? |
| Invocation | Is the correct code called with the correct arguments, order, context, and conditions? |
| Data flow | Is the right value selected, transformed, and propagated? |
| State transition | Does the operation produce the intended state change? |

These dimensions are lenses, not mandatory sequential steps.

## Common distinctions

- Symptom is not root cause.
- Property error is not necessarily a Property-definition error.
- Relationship-definition error is not the same as Relationship-implementation or Relationship-usage error.
- Function failure is not necessarily a local Function defect; its inputs, caller, state, or assumptions may be wrong.
- Action failure may originate in its execution path, orchestration, authorization, sequencing, or a participating Function or Relationship.
- A test passing is evidence for the tested scope, not proof that all related behavior is correct.
