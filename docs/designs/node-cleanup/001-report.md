---
id: "001"
status: ready for review
depends_on: []
blockers: []
---

# 001 — Read-only node cleanup report

`node-cleanup --dry-run` inventories the execution node's workspaces and possible
build outputs before we choose retirement and retention rules. The first slice is
a report, not a deletion engine. Its source is `scripts/node-cleanup.py`; the node
gets an explicitly deployed executable and private, node-local configuration.

```bash
# On the execution node after deployment:
node-cleanup --dry-run
node-cleanup --dry-run --json

# From the workstation (noninteractive SSH need not include ~/.local/bin):
ssh agent-node '~/.local/bin/node-cleanup --dry-run'

# Disposable/local inspection, with activity unknown and therefore protected:
python3 scripts/node-cleanup.py --root /explicit/project/root --dry-run
```

## Scope agreed on 2026-11-10

Preserve active work, dirty/untracked files, unpushed/local-only commits, unknown
state, persistent container data, and credentials. Start by examining reports;
do not introduce emergency pruning or unattended workspace deletion. Keep the
200 GiB free-space target advisory. Git/Paseo operations in this slice only read
metadata, and Git checks disable optional index locking and fsmonitor hooks.

The current node has Paseo-managed worktrees and MDE workspace directories whose
state, environment, logs, and secrets live beside source. Paseo exposes workspace
listing/archive commands; MDE retirement behavior has not been qualified. Active
Paseo workspace/agent references and all configured MDE workspace roots are
protected. Unknown provider schemas or unavailable activity checks protect all
rows. No raw task transcripts, credentials, source contents, or remote URLs enter
the report.

## Report behavior

Discovery stays inside the explicit project root, skips symlinked directories and
common cache/state/secret directories, and reads registered Git worktrees without
pruning them. A bounded directory scan and per-command timeouts limit load.
`target`, `node_modules`, `dist`, `build`, and `.next` directories are *possible*
outputs, not verified disposable content. Their `du` allocated sizes do not
establish Btrfs exclusive/reclaimable space and must not be summed across overlap.
Directory mtime is only a hint, not workspace last-use time. The report does not
inspect shared Nix/Cargo caches, container volumes, or external target directories.

Clean work with no known owner reference can be marked `retirement_review_only`.
Every row still has `deletion_permitted: false`: local remote-tracking refs may be
stale, Maple task/process/open-file census is not integrated, and no retirement
decision has been made. Unknown Git/activity/discovery state is protected.
`--apply` is explicitly refused before scanning or side effects.

## Acceptance and verification

- Test discovery of real disposable Git worktrees, dirty/untracked protection,
  local-only commits, missing remotes, activity failure, unknown agent statuses,
  MDE protection, symlink avoidance, budgets, and artifact reporting.
- Test that report invocation leaves fixture source/metadata unchanged and that
  `--apply` cannot mutate anything.
- Run the scoped Python tests, syntax checks, and `git diff --check`.
- Deploy only the report executable/config after conflict checks, run it on the
  actual node without root, and record runtime checks separately from mocks.

## Follow-up decisions

Review actual candidates before choosing grace periods, explicit retirement
markers, artifact eligibility, owner-mediated workspace removal, and a weekly
report timer/output location. Apply-mode and scheduling are subsequent work;
this slice installs neither a deletion mode nor a timer.

## Results

The report-only executable is installed at `~/.local/bin/node-cleanup` on the
execution node. Its private `~/.config/node-cleanup/config.json` selects the
project root, Paseo executable, MDE root, and a 180-second reporting budget. The
canonical source is local and uncommitted; deployment copied the reviewed script
without updating the node's shared-config checkout.

All 20 cleanup-specific tests pass, along with Python syntax checks and
`git diff --check`. The initial full-suite run (before the extra path-format
regression test) ran 470 tests and reported 21 failures in existing installer
tests. Those same 21 failures reproduce in the five affected test modules from
an unmodified `HEAD` archive; those files are not changed by this slice.

The first real-node report discovered 55 Git workspace rows and reported
build-output estimates up to 43 GiB. Its activity adapter rejected Paseo's `~/...`
agent paths, correctly protecting all work; the adapter now expands only this
user's home abbreviation, with a regression test. The verification rerun confirms
Paseo activity is known. It inventories 55 Git workspace rows; all are protected
because some non-Git subdirectories exceed the discovery depth limit. Two output
size checks were incomplete. The report exits 1 and explicitly reports those
gaps rather than presenting a complete/deletable inventory. These are observed
limits of this bounded report, not completed reclamation checks.

The rerun observed 939 GiB free on the project filesystem. Largest measured
output: `github.com/w3irdrobot/theboatingaccident/target`, about 43 GiB allocated;
other measured Rust targets were roughly 7–11 GiB each. Shared/exclusive Btrfs
accounting remains unverified. No workspace data or services were changed.
