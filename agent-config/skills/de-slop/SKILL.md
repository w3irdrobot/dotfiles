---
name: de-slop
description: Hold code, tests, docs, and commit history to the standard of something a human maintainer would be glad to read, merge, and own. Load when implementing or reviewing code that Alex or an outside maintainer will read, when briefing an implementer or reviewer sub-agent, or when asked to polish, clean up, or "de-slop" a branch. It covers readability and craftsmanship, not correctness or security review, and it does not replace the project's own formatter, linter, or language conventions.
---

# De-slop

Code that passes its tests can still read like a machine wrote it: dense
one-liners, positional flags, pasted expressions, magic values, tests generated
by loops, and "fixed in round 2" commits. Reviews aimed at correctness and
security do not catch this, and reviewer agents are generous about it. The cost
shows up later as a whole extra polish pass, or as Alex rejecting work two
reviewers had passed.

The standard is a question: would a maintainer who has never seen this change be
glad to merge and maintain it? Apply it from the first commit, as implementer
and as reviewer.

Match the surrounding code first. The project's formatter, linter, naming,
idioms, and test layout are the rule, even where its style is not what you would
choose. Write new files in the cleanest version of the same idiom.

## Writing the code

- One idea per line. Compute a condition or intermediate value into a well-named
  constant on its own line, then use it. Keep long expressions out of
  conditionals, call arguments, and `throw` or `return` statements.
- Use `if` statements or a small helper where a nested or multi-line ternary
  would go.
- Name magic numbers, strings, dates, and identifiers such as OIDs or numeric
  codes, including when they are table keys.
- Use named options where a positional boolean or "mode" parameter would go.
- Security checks should be the easiest lines in the file to read. A reader
  should see what is checked without unpacking a chain.
- An expression pasted three times wants a helper. A helper used once that hides
  more than it explains wants inlining.
- Leave out options, abstractions, error variants, and defensive branches that
  nothing uses.
- Comments say why, in plain words. They never mention review rounds, findings,
  or how the change came to be. Add one where the code does something deliberate
  that looks like a mistake.
- Flag a hand-rolled parser or similar custom machinery for a decision before
  building it. Alex is wary of them; prefer the smallest thing that does the job
  with a library the project already trusts.

The difference in practice:

```ts
// Before
if (!(entry.kind === "hashedrekord" && entry.logIndex >= 0 && KEYS[entry.keyId]?.curve === "1.3.132.0.34")) throw new Error(entry.kind !== "hashedrekord" ? "bad kind" : entry.logIndex < 0 ? "bad index" : "bad key");
```

```ts
// After
const P384_CURVE_OID = "1.3.132.0.34";

const isHashedRekord = entry.kind === "hashedrekord";
if (!isHashedRekord) {
  throw new Error("unsupported log entry kind");
}

const hasLogIndex = entry.logIndex >= 0;
if (!hasLogIndex) {
  throw new Error("log entry has no index");
}

const signingKey = KEYS[entry.keyId];
const isP384Key = signingKey?.curve === P384_CURVE_OID;
if (!isP384Key) {
  throw new Error("log entry key is not P-384");
}
```

## Tests, docs, and history

- Tests: one behavior per test, a name that says what breaks, grouped by
  scenario, set up through a readable fixture, and parameterized the way the
  project already does it. Loops that generate tests are a smell where the
  project has a table or parameterized idiom.
- When restructuring a test, show it still fails when the thing it guards is
  broken. Restructuring is welcome; weakening is not.
- Docs: short and specific, with no report-style structure and no selling.
  Change a README only as much as the change needs.
- Commits: one concern each, in an order someone can review, with a message that
  describes the change. Squash fix-ups into the commit they fix before calling
  the work done.
- Keep work bound for an upstream project separate from our own plumbing from
  the first commit, so the pull-request branch does not have to be carved out
  later. See `upstream-contribution` when it is available.

## Reviewing

Read the diff cold, the way the project's maintainer would, before reading
anyone's report. Readability is a first-class verdict next to correctness, and a
change does not pass on correctness alone. Go through production code first,
then tests, docs, fixtures, tooling, and commit messages. Name specifics: file,
line, what is hard to read, and what would fix it.

Pay particular attention to names that are vague or disagree with the codebase's
own vocabulary, functions doing several jobs, error messages out of step with
the project's tone, and files that do not belong in the change at all.

A polish pass on accepted code preserves behavior. If something looks wrong or
badly named in a public API, write it up as a finding instead of changing it.

## Acceptance criteria for code-producing work

Add these to the plan for any slice or task that produces code:

- [ ] The project's formatter and linter are clean with no new warnings.
- [ ] A reviewer who has not seen the work says the code and tests read as
      maintainable, with specifics.
- [ ] The branch history is one concern per commit with no fix-up commits.
- [ ] Anything bound for an upstream project is on its own branch with none of
      our plumbing in it.

Agent reviews are not the final gate for readability. Get code in front of Alex
early and in small pieces instead of after several review rounds.
