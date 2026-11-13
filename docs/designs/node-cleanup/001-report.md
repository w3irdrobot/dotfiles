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

# Save a usage snapshot, or override a node's history-enabled configuration:
node-cleanup --dry-run --save-history
node-cleanup --dry-run --no-history
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
Explicit `usage_paths` now add bounded size measurements of selected external
caches; they do not make those directories cleanup candidates.

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

## Usage history and metrics preservation — 2026-11-12

Report runs can retain private, immutable JSON documents under
`$XDG_STATE_HOME/node-cleanup/history/YYYY-MM-DD/<report-id>.json` (default
`~/.local/state/node-cleanup/history/`). History is opt-in in generic invocations;
the agent-node configuration enables it by default. `--save-history` and
`--no-history` override configuration; `--history-dir` overrides the destination.
With history enabled, `--dry-run` means **no cleanup**, not zero writes: the only
intended persistent output is its history file. There is no automatic pruning,
upload, timer, or deletion mode. `--apply` still fails before any side effects.

Each report retains filesystem used/free/total bytes, per-workspace artifact
estimates and protection reasons, timestamps, host, collector SHA-256, unique
report ID, and explicit configured cache-size observations. `usage_paths` accepts
up to 32 absolute directory paths. Every size has an observation time and status;
missing directories record zero, failed checks record unknown rather than zero.
Measurements share the existing runtime budget and are not an atomic snapshot.
Independent `du` totals can overlap through hardlinks/reflinks: don't sum them.

All history events say `inventory_not_cleanup`: they are neither cleanup markers
nor evidence that space was reclaimed. Run reports before and after an approved
cleanup for comparable usage observations; a future deletion implementation must
record actual cleanup start/results separately, including failures or interruption.
Partial inventories are retained with `checks_complete: false` and their warnings.
History-write failures are visible, never claim success, and cause exit 1.

The report's `preserved_data` explicitly protects:

- `~/.cache/build-metrics/`, including existing Cargo JSONL and validation data;
- a custom `CARGO_METRICS_DIR`, when exported;
- the selected history destination and default node-cleanup state directory;
- `~/.local/libexec/cargo-metrics/`, containing the installed collector.

Protected trees aren't traversed for workspace discovery. A workspace or possible
output containing preserved data is explicitly protected. Any future cleanup/apply
path must honor these protections, including ancestors and symlink aliases.
This report-only tool cannot prevent deletion by unrelated tools or manual commands.
It does not move or duplicate the existing Cargo records; historical timings remain
readable even if their referenced worktrees or compiler outputs are later removed.

Files are mode 0600, history directories 0700. Publication is atomic and refuses
overwriting an existing report; public/foreign/symlinked destinations are refused.
Reports contain private paths and Git/size metadata but no file contents, raw
provider responses, command output, credentials or task transcripts. They remain
node-local, outside Git and build-cache cleanup areas. Saved size observations
start when this feature is enabled; past storage usage cannot be reconstructed.

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

### History extension verification — 2026-11-12

All 31 cleanup-specific tests passed locally and against a byte-identical copy of
the installed node script in disposable fixtures. All 17 Cargo collector tests
also passed locally; Python parsing and `git diff --check` passed. The old node
script/config were SHA-256 checked before replacement and preserved under the
private default node-cleanup state's `backups/` directory. The node's shared
dotfiles checkout was not updated.

A real `node-cleanup --dry-run --json` saved its first immutable history file at
`~/.local/state/node-cleanup/history/2026-11-12/3be9d40d-b7e5-4b00-b788-6a232473a20b.json`.
Its parsed JSON matches stdout and its mode is 0600. The report includes 69
workspace rows and successful shared-cache/incremental/dependency size readings.
Paseo activity was known, but discovery hit the existing depth limit, so the
report correctly retained `checks_complete: false` and exited 1. This incomplete
inventory is useful history, not authorization to clean anything.

All 7,178 pre-existing Cargo metric files remained present with their prior
contents unchanged. No build artifacts, workspaces or services were cleaned,
removed or restarted. No scheduling or actual cleanup markers were added.
