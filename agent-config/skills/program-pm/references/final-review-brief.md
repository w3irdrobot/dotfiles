# Final-review brief

The final reviewer is a fresh agent that has seen none of the work, on a model
the slice team did not use. Give it the code and the specification, not the
team's conclusions. A reviewer handed a verdict tends to return it confirmed.

```markdown
# Final review: <slice ID and name>

You have seen none of this work. Assume things were missed. Your job is to find
out whether this slice does what its specification says, using your own checks.

## What to review

- Workspace, branch, base commit, and head commit: <values>.
- The specification: <slice file path>. Its acceptance criteria are what you
  are checking.
- The design and decisions, read-only: <paths>.
- The team's report exists at <path>. Read the diff cold before you read it,
  and treat everything in it as a claim to verify.

## How to review

- Verify with your own probes. Write and run your own tests in a disposable
  copy; do not rely on the team's tests passing.
- Run real things: the real artifact at <path, with its real size>, the real
  pinned tool, the real consumer. Look specifically for hand-built look-alike
  fixtures standing in for real producer output.
- Check every name, path, and identifier against where it is supposed to come
  from.
- Confirm the checks hold: for each rule in the specification, show an input
  that should be rejected is rejected and one that should pass does.
- For each finding, say whether it can happen with our real inputs, and whether
  the wrong thing is accepted or it only fails. Report fail-closed behavior on
  impossible input in one line; do not chase it.
- Give a readability verdict next to the correctness one: would a maintainer be
  glad to merge and own this? Name specifics. Check that the commit history is
  reviewable. Load `de-slop` when it is available.
- <Known-failing checks on this machine, and how to tell them from new ones: run
  the same selection on the base commit and compare.>

## Limits

- Read-only on the workspace and on <other sources>. Work in your own scratch
  copy at <path the reviewer may write to without prompting>.
- <The slice's gates: no push, no publishing, no network writes, and so on.>
- Leave `TMPDIR` alone; point big build output at <where>. Run commands in the
  foreground and do not end your turn before the report is written.
- When you finish, delete your scratch by full literal path, then write the
  cleanup line in the report. Describe only what has already happened.

## Report

Write `<evidence path>/FINAL-REVIEW.md`:

- Verdict: PASS or FAIL, first line.
- Findings, most serious first, each with how to reproduce it.
- What held up under your own probes.
- What you ran versus what you only read, and what you did not check.
- Exact commands to reproduce, and your probe tests as a patch.

Then send the PM a few lines pointing at the report.
```
