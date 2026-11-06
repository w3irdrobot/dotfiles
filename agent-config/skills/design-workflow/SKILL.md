---
name: design-workflow
description: Collaboratively design new projects or scoped features in existing systems, including new API endpoints. Interview Alex, create or iterate on conversational technical proposals, record significant accepted choices, and plan testable implementation slices. Continue using this workflow for follow-up design revisions and, when requested, selected-slice implementation or GitHub issue publication. Reuse existing project docs and conventions; a new project-wide design doc is not required. Do not use for every code edit, routine README work, or standalone code review; planning does not authorize implementation or issue creation.
---

# Design workflow

Help turn an idea into an understandable design and a sequence of reviewable
changes. This is a collaborative workflow, not a document-generation checklist.
Enter at the stage the user requested; do not repeat an interview or regenerate
an accepted plan just because the skill was loaded.

Continue applying this workflow while the user iterates on the same design,
feature, or slice plan; follow-up questions do not require another explicit
invocation. Keep the discussion at the current stage rather than restarting the
process. On a fresh session, recover state from the relevant documents instead
of assuming earlier conversation or approvals are available. This guidance does
not make skill selection persistent across sessions or override a task change.

Read [the writing guide](references/writing.md) before drafting or revising prose.
Read [the templates](references/templates.md) when creating design, decision, or
slice documents. Adapt them to the project rather than filling every heading.

## 1. Establish context and interview

- Read relevant repository instructions, design docs, decisions, and actual code.
  Identify what is implemented, accepted, proposed, and unverified. Existing
  project conventions take precedence over the default paths below.
- Establish the unit of design: a new project, a change to an existing design, or
  a scoped feature in an existing system. For brownfield work, investigate the
  affected code paths and representative existing features before proposing a
  solution. Document the current behavior and proposed delta, not a redesign of
  the whole system. Raise doc/code discrepancies instead of silently choosing
  whichever is more convenient.
- Interview first for new or materially unclear designs. Ask a few focused
  questions at a time, use the answers, and avoid asking for information already
  available. For a clear revision request, ask only about consequential gaps.
- Establish the problem, intended users and concrete use cases, desired outcome,
  scope/non-goals, constraints, and important tradeoffs. Ask about operational,
  security, compatibility, or migration concerns when they affect this project;
  do not impose a security-library questionnaire on every idea.
- Challenge unnecessary complexity and weak assumptions constructively. Prefer
  the smallest useful concrete solution over speculative frameworks. Explain
  alternatives and costs instead of simply accumulating prohibitions.
- Summarize the direction and consequential open questions before drafting. Do
  not endlessly interview: draft when there is enough context, explicitly leaving
  unresolved choices open rather than making decisions on the user's behalf.

## 2. Write the design and capture decisions

Default layout for a new project, creating supporting files only when needed:

```text
docs/DESIGN.md               problem, use cases, approach, examples, tradeoffs
docs/specs/<topic>.md         detailed contracts that would interrupt the story
docs/decisions.md             one lightweight, append-oriented decision log
docs/slices/README.md         ordered slice index, dependencies, status, links
docs/slices/001-<outcome>.md   implementation brief and eventual results
```

Keep newly created design documents under `docs/`, including the project-wide
`docs/DESIGN.md`; do not default to a repository-root design document. Respect
existing project locations, and do not move existing docs without approval.

For a feature in an existing project, first reuse its proposal/RFC, ADR, spec,
and work-tracking conventions. Extend an existing relevant proposal when that
fits; otherwise use a scoped document such as `docs/designs/<feature>.md`.
Do not create a project-wide `docs/DESIGN.md`, reorganize existing documentation, or
introduce a competing decision log merely to use this workflow. If the project
has no suitable structure, a feature-local directory is a reasonable fallback:

```text
docs/designs/<feature>/
  design.md                  current behavior, proposed change, examples, tradeoffs
  decisions.md               significant accepted feature choices, when needed
  slices/README.md            ordered feature slice index
  slices/001-<outcome>.md     brief and results
```

Keep documentation proportional: for a small one-slice feature, the design and
implementation brief may share a document. Separate them when the detail warrants
it. Link existing architecture and contracts rather than copying them. Update
shared design/API docs only where the accepted feature changes them.

For example, designing new endpoints in an existing API server should examine
nearby routes, authentication/authorization, validation/error conventions,
service/data access, API specs, and integration tests. Discuss new contracts,
compatibility, data migrations, and rollout only as relevant. Prefer extending
the current architecture; keep unrelated cleanup out of the feature. A useful
slice might deliver one endpoint through routing, authorization, business logic,
persistence, and tests, rather than implementing all routes before any behavior.

Keep the main design readable as a narrative. Link to exact specifications,
decision rationale, and implementation work rather than copying them into it.
Extract dense wire formats or persistence contracts when useful; do not create
empty specs or an elaborate documentation hierarchy preemptively.

Use the project's existing ADR system when it has one. Otherwise use a single
decision log, not a directory of individual ADRs by default. Record
significant accepted choices whose rationale would otherwise be lost. Each entry
has a stable `D-001`-style ID, actual acceptance date, choice, why, considered
alternatives, and tradeoff. A few sentences may cover all of those. Record only
known dates; mark an imported decision's acceptance date unknown if necessary.
Do not invent rejected alternatives or historical user approval.

Keep proposals in the design's open questions until accepted. If a choice changes,
add a new entry and mark/link the old one as superseded; preserve the original
rationale. The design explains the current approach; the log preserves why it
was chosen. Avoid logging every minor code detail or duplicating the whole design.

For an existing document, preserve substantive requirements and unresolved risks
when reorganizing or simplifying language. Do not turn editorial changes into
technical changes or retroactive approval. Point out possible contradictions.

Get agreement on the design direction before treating it as accepted and planning
committed work. A provisional slice sketch is fine if clearly labeled. Approval
to write a design is not approval to implement it.

## 3. Plan small, end-to-end slices

Each slice should deliver a small observable outcome with tests, not merely build
a horizontal layer. Prefer the smallest useful walking skeleton, then expand it.
Separate time-boxed research or enabling work when a genuine uncertainty prevents
an end-to-end outcome; specify the evidence or decision it must produce.

Write a slice index and a brief for each agreed slice. Give slices stable numeric
IDs; reorder the index rather than renumbering existing documents. Each brief has:

- Outcome and scope/non-goals.
- Dependencies, relevant design/spec/decision links, and blocking open choices.
- Proposed API changes, likely files/modules, and concrete implementation steps.
  Inspect existing code first. Mark paths and APIs as proposed when they do not
  exist; these are useful guidance, not a frozen implementation prescription.
- Observable acceptance criteria and a validation plan, including important
  failure cases and required environments. Separate proposed commands from checks
  actually run; do not invent existing tooling or test targets.
- Status and, after work, a short results/checks/gaps record.

For new slice briefs, use the YAML frontmatter contract in
[the templates](references/templates.md#slice-metadata). Keep `id`, `status`,
`depends_on`, and `blockers` machine-readable so a workspace tracker can derive
available work without interpreting prose. Scope IDs to the containing slice
directory; keep dependencies and blockers aligned with the brief, and treat
frontmatter as canonical over index summaries. Preserve established project
contracts when they conflict; flag tracker incompatibility rather than silently
converting existing plans. Existing prose-only briefs need migration only when
requested.

Do not hide unresolved architecture inside an implementation task. Identify which
questions block which slice; unrelated questions need not block everything. Avoid
giant first slices, scaffolding-only milestones, speculative future scope, and
invented time estimates. Propose the sequence, get agreement, then offer the next
action: refine the plan, implement one selected slice, or publish selected issues.

## 4. Implement only the selected, authorized slice

When implementation is requested, read its brief and current dependencies first.
For structured briefs, check frontmatter dependencies and blockers as well as the
prose; missing references or dependency cycles need resolution before proceeding.
Resolve blockers with the user, then use repository workflows and applicable
language skills. Do not automatically start the next slice.

Ask before materially changing accepted scope, architecture, public contracts,
trust boundaries, or other consequential decisions. Small implementation details
can evolve within the agreed outcome; update the brief when they do.

Keep the design and specs aligned with actual accepted changes. Update the decision
log only for significant accepted choices. Record checks run and their outcomes,
skipped checks with reasons, and remaining gaps in the slice. Mocks and local tests
are not evidence for environments they did not exercise. Never mark a slice done
with unmet acceptance criteria; distinguish implementation finished, checks
pending, and ready for review.
Update the brief's frontmatter status and blockers as work changes, then synchronize
the slice index summary. Checking acceptance boxes alone does not mark work done.

Stop after the slice with a concise account of changes, validation, and unresolved
issues for review. Do not commit, push, deploy, or close issues without permission.

## 5. Optional GitHub issues

Only publish when explicitly requested; local documents are the default. Confirm
the target repository and selected slices if unclear. Inspect repository issue
templates and existing issues to avoid duplicates, using the available GitHub
tools and their required workflow. No integration or plugin is needed just to plan.

Use each approved slice brief as the issue body, including outcome, scope,
dependencies, implementation guidance, acceptance criteria, and a repository link
to the local source document. If the document is not pushed, do not invent a
working remote link; include its repo-relative path and say it is local. Record
the issue URL in the brief and index. Do not create labels, projects, milestones,
or extra tracking issues unless requested.

Keep the local slice brief as the canonical implementation plan; issues are a
work-queue view. On continuation, reconcile relevant issue discussion explicitly
instead of silently overwriting either version. Summarize agreed changes locally.
Publishing an issue does not authorize implementation, and completing local work
does not authorize closing it.
