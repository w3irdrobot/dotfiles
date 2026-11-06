# Adaptable document shapes

The prose sections are starting points; new slice briefs use the metadata contract
below. Omit irrelevant sections, rename headings
to suit the subject, and follow existing repository paths. Replace placeholders
with actual content; do not leave empty ceremonial headings.

## Main design: `docs/DESIGN.md`

New design documents belong under `docs/`, not the repository root. Reuse
established project locations; moving an existing document requires approval.

```markdown
# <Project or feature>

<What we are building and the problem it solves, in a short opening.>

Status: <Draft / accepted direction / partially implemented; only what is known.>

## The problem

<Who needs this, what they do today, and what is missing.>

## What using it looks like

<One or two concrete scenarios, API examples, or user flows. Label pseudocode.>

## Goals and boundaries

<What success means; the important non-goals and relevant constraints.>

## The approach

<Major responsibilities, data/control flow, integration points, and a diagram
if useful. Explain why this shape fits. Use topic-specific subsections.>

## Tradeoffs

<Important alternatives and costs of the proposed approach. Link accepted
decision entries rather than repeating their full history.>

## Open questions

<Unresolved choices, what would resolve them, and affected work.>

## Supporting documents

<Links to existing detailed specs, decision log, and slice index.>
```

Do not wait for every question to be answered to draft. Do not call the design
accepted until the user has agreed to it. A short document may combine sections.

## Brownfield feature proposal

Use the repository's existing proposal location and format first. Otherwise use
`docs/designs/<feature>.md`, or `docs/designs/<feature>/design.md` when supporting
files warrant a directory. Do not require a root `DESIGN.md`.

Adapt the main design shape to focus on the change:

- **Problem and intended experience:** the new capability and concrete examples.
- **Current behavior:** relevant code paths, contracts, and existing architecture
  links. Distinguish observed code behavior from potentially stale documentation.
- **Proposed change:** what changes, what stays as-is, and how the feature fits
  existing patterns. Include contracts or request/response examples where useful.
- **Tradeoffs and compatibility:** alternatives, effects on existing consumers,
  and migrations or rollout concerns where applicable.
- **Open questions and implementation:** unresolved choices and slice links, or
  an inline implementation brief if this is a small single-slice feature.

For new API endpoints, use existing route/auth/error/data-access/test patterns as
the baseline. Describe endpoint behavior and authorization, not just a list of
URLs. Plan regression checks for affected existing behavior alongside new tests.
Avoid a mandatory checklist for concerns the feature does not touch.

The decision-log and slice templates below work for project-wide or feature-local
documents. Adjust relative links and ID scope to match their actual locations;
reuse existing IDs and ADR conventions where present.

## Lightweight ADRs: `docs/decisions.md`

```markdown
# Decisions

Significant accepted choices and the reasons behind them.
<Link to the relevant project or feature design. Proposals stay in its open
questions.>

## D-001 — <Choice>

Accepted: <YYYY-MM-DD, or unknown for an imported historical choice>

**Choice:** <What we decided.>

**Why:** <Problem/context and why this fits better than the alternatives we
actually considered.>

**Tradeoff:** <Costs, limits, or consequences we accept.>

<Relevant design/spec/slice links when useful.>
```

Use the next unused ID. A few sentences can be enough for an entry. When changing
a decision, add a new entry with `Supersedes: D-001`, and annotate the old entry
with `Superseded by: D-00N` links. Do not erase its original context and rationale.

## Slice index: `docs/slices/README.md`

```markdown
# Implementation slices

<Design link and a short explanation of the sequence. State whether this is a
provisional or agreed plan. Planning alone does not authorize implementation.>

1. [001 — <Observable outcome>](001-<slug>.md) — planned; <dependencies, if any>.
2. [002 — <Observable outcome>](002-<slug>.md) — planned; depends on 001.

<Add issue links when published. Update status as work happens; do not duplicate
every acceptance check here.>
```

## Slice metadata

Start each new slice brief with YAML frontmatter containing these four fields:

```yaml
---
id: "002"
status: planned
depends_on: ["001"]
blockers: []
---
```

- `id`: a quoted numeric string matching the filename's numeric prefix and the
  heading ID. Preserve leading zeros. IDs are unique within the containing slice
  directory; separate feature plans may each have a `"001"`.
- `status`: one of `planned`, `blocked`, `in progress`, `checks pending`,
  `ready for review`, or `done`. Use these exact strings, choosing only the states
  the plan needs.
- `depends_on`: an array of quoted IDs from the same slice directory, or `[]`.
  List direct prerequisites; keep references resolvable and unique, with no
  self-dependencies or cycles. Describe their rationale in the brief.
- `blockers`: an array of non-empty strings describing unresolved decisions or
  other impediments beyond those dependencies, or `[]`. Include cross-plan
  prerequisites here with a Markdown path/link until resolved. Remove an entry
  only when its blocker is resolved.

All four fields are required, including empty arrays. The frontmatter is canonical
for tracking; do not add a second `Status:` line to the brief. Keep index summaries
and dependency prose in sync with it. Existing project metadata contracts take
precedence; converting legacy briefs is a separate, requested change.

Availability is derived, not a stored status: a slice is available when its status
is `planned`, `blockers` is empty, and every dependency is `done`. An unfinished
dependency can hold a planned slice without changing its recorded status to
`blocked`. Missing references, duplicate IDs, invalid metadata, and cycles are
plan errors to resolve, not evidence that work is available. A blocked slice must
identify its reason through `depends_on` or `blockers`.

## Slice brief: `docs/slices/001-<outcome>.md`

```markdown
---
id: "001"
status: planned
depends_on: []
blockers: []
---

# 001 — <Observable outcome>

<Issue URL only if one exists.>

## Outcome

<What a user or developer can do after this slice that they cannot do now.>

## Scope

<Included behavior and the specific adjacent work intentionally left out.>

## Dependencies and decisions

<Required earlier slices; design/spec/decision links; unresolved blockers.
Say none if there are none.>

## Implementation plan

<Proposed public API changes and likely files/modules. Distinguish proposed
paths from existing ones.>

1. <Concrete implementation step.>
2. <Next step.>
3. <Integration and tests.>

## Acceptance criteria

- [ ] <Observable behavior that establishes the outcome.>
- [ ] <Relevant failure behavior or boundary condition.>
- [ ] <Required integration or environment-specific evidence, if applicable.>

## Validation plan

<Relevant test cases, actual repository check commands when known, environment
requirements, and manual checks. These are planned, not claimed results.>

## Results

Not started. After implementation, record the meaningful changes, checks actually
run and outcomes, skipped checks with reasons, and remaining gaps or deviations.
```

The metadata statuses are not a mandatory transition sequence. "Ready for review"
means acceptance checks passed, but user review is still pending; "done" follows
the agreed review process. If work is finished but required validation is not,
say checks pending rather than implying completion.
