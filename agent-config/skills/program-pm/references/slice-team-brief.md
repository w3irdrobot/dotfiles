# Slice-team brief

One brief per slice, or one shared brief for sibling slices built in parallel.
The manager, implementer, and reviewer all read it fully before doing anything.
Fill in every section with real paths and values; delete a section only when it
truly does not apply. Where a project keeps planning documents private, say so
at the top and name what must never be quoted in anything committed.

```markdown
# <Slice ID and name>: brief

<Who wrote this and when. Any confidentiality rule for these documents.>

## What this is

<Two or three sentences: what exists today, what this slice adds, and the one
thing it must never do.>

<Workspace path, branch, and base commit. One pull request's worth of work.
Stay out of other teams' workspaces.>

## Read first

- The slice file: <path>. Its plan and acceptance criteria are the
  specification. Do not edit slice files.
- The design and decisions, read-only: <paths, with the sections that matter>.
- The repository's own instruction files inside the workspace.
- Machine guidance: `~/.config/agent-config/node.md`, when present.
- The `de-slop` skill, and for outside projects `upstream-contribution`.

## Inputs that already exist

<Real artifacts to build and test against, each with its path or URL, its
provenance, and its real size or count in numbers. Mark read-only sources.>

## Scope of this pass

<What to build. Then what is not possible yet and why. For each thing left out,
say so in the report; do not fake it.>

## Already decided, do not reopen

<Settled choices with one line of reason each. Rules that sibling slices must
share, and the one file siblings use to coordinate names.>

## How to write the code

<Load `de-slop`. Add project-specific style here. Name anything that needs a
decision before it is built, such as a hand-written parser.>

## What to test, and what not to chase

- Tests run real things: real producer output through the real consumer, the
  real pinned tool, real-sized input. The reviewer looks for hand-built
  look-alike fixtures specifically.
- Before calling anything tested, run the real code on real-sized input once and
  state the sizes in the report. A fake of an external tool goes in the
  "not checked" list for whatever it did not exercise.
- Fix anything where bad input is accepted or valid input is rejected. For
  input that cannot occur and only fails closed, write one line in the report
  and move on. Do not add checks for hypotheticals.
- The reviewer checks every name, path, and identifier against the place it is
  supposed to come from.

## Team and rounds

- Implementer and reviewer come from different providers, picked at random from
  the roster the PM supplies: <roster>.
- The reviewer gives a readability verdict alongside correctness.
- At most <three> review rounds. If the reviewer still fails it after that,
  stop and report where it stands.
- Review briefs for security code ask for defensive verification of our own
  code: "confirm this check holds when X". If a provider refuses, switch
  reviewer in this order: <fallback order>. Do not reword to get past a filter.

## Gates

- Local commits only. No push, pull request, issue, or comment anywhere. Do not
  change Git identity or signing; if a commit fails for a configuration reason,
  stop and report.
- <Project gates: no signing runs, no writes to public services, no publishing,
  no workflow dispatch, no credential lookups, whatever applies.>
- Never log secrets, tokens, or decrypted content, in code or in evidence.
- If something outside this slice needs to change, stop and write it in the
  questions file.

## Machine rules

- Leave `TMPDIR` alone. Point only big build output at real disk: <where>.
- Keep test scratch out of the workspace and the repository.
- When you finish, delete your own scratch by full literal path and say in the
  report what you removed. Never delete another task's files.
- Use the repository's pinned environment; one long-lived shell, not one per
  command. No sudo, no global installs.
- At most <N> heavy jobs at once across the machine.
- Run commands in the foreground and wait for them. Do not end a turn with an
  interim status.
- <Reviewers that prompt before writing outside their workspace get a
  git-ignored scratch directory inside it: <path>.>

## Reporting

- Evidence directory: <path>.
- `REPORT.md`: what was built, the commit list, each acceptance criterion with
  its proof (a file, a test name, or a command result) or the reason it is
  open, models used, review rounds, what was run versus only read, what was not
  checked, and the exact commands to reproduce.
- `QUESTIONS.md`: anything that needs Alex, batched. Keep working on what is not
  blocked.
- When finished or truly blocked, the manager sends the PM a few lines pointing
  at the report. Nothing else goes to the PM.
```
