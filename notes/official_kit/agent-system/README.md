# Agent System

A role-based, issue-driven bug diagnosis and repair system.

## Design

This repository separates three concerns:

1. **Shared communication contract** — the common vocabulary, semantic model, evidence rules, and message protocol used by every agent.
2. **Role definitions** — responsibility, authority, boundaries, and collaboration expectations for each agent.
3. **Skills** — reusable procedures that tell agents how to perform concrete work.

A role is not a skill. A role defines *who is responsible for what*; a skill defines *how to perform a kind of work*. The current layout maps one primary skill to each role for clarity, but this is not a requirement that every future role have exactly one skill.

## Directory

```text
agent-system/
├── README.md
├── shared-agent-communication-contract/
│   ├── SKILL.md
│   ├── vocabulary.md
│   ├── semantic-model.md
│   ├── evidence-convention.md
│   └── communication-protocol.md
├── roles/
│   ├── project-manager.md
│   ├── architect.md
│   ├── worker.md
│   ├── checker.md
│   └── evaluator.md
└── skills/
    ├── task-orchestration/
    │   └── SKILL.md
    ├── bug-diagnosis/
    │   └── SKILL.md
    ├── bug-investigation/
    │   └── SKILL.md
    ├── independent-review/
    │   └── SKILL.md
    └── agent-evaluation/
        └── SKILL.md
```

## Operating principles

- Start from the reported symptom and the available evidence; do not assume the issue description already identifies the cause.
- Build a local model around the bug. Expand it only when evidence requires expansion.
- Keep semantic definitions, implementation details, and runtime invocation paths distinct.
- Treat Architect hypotheses as testable proposals, not authoritative truth.
- Workers may discover entities, relationships, functions, actions, or execution paths omitted by the initial diagnosis.
- Checker review should be independent enough to detect shared assumptions and missed evidence.
- Project Manager coordinates people, task boundaries, and resources; it does not decide technical root cause.
- Evaluator assesses the quality of the overall agent process, not merely whether one patch passes tests.
- No agent may report a hypothesis as a verified conclusion.
- A repair is not complete merely because code was changed; the relevant behavior and regression risk must be checked.

## Suggested initial execution

1. Project Manager receives the issue and prepares the task context.
2. Architect performs diagnosis and proposes likely fault locations, alternatives, and investigation tasks.
3. Project Manager assigns bounded investigation tasks to Workers and corresponding review tasks to Checkers.
4. Workers reproduce, investigate, and report evidence. A Worker may challenge or extend the Architect's model.
5. Checkers independently inspect the claims and evidence, then return specific review findings.
6. Architect updates the shared diagnosis when the evidence changes the model or ranking of hypotheses.
7. Project Manager authorizes and coordinates repair work once the responsible path is sufficiently established.
8. Worker implements the authorized repair; Checker reviews the patch and validation.
9. Evaluator assesses the process and recommends changes to the agent system.

This is a coordination pattern, not a mandatory linear sequence. Reproduction, diagnosis, investigation, and review may overlap or repeat.
