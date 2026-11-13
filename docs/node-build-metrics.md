# Agent-node build metrics and storage history

Setup reference, verified 2026-11-12. This guide is also installed as
`~/.local/state/node-cleanup/history/README.md` on `agent-node`. Read it before
changing build instrumentation or reclaiming build space. Actual code, config
and current reports take precedence over dated observations.

## What is installed

Two independent tools run as `w3irdrobot`, without root:

- **Cargo metrics:** ordinary `cargo` commands record elapsed time, CPU, peak
  RSS, exit outcome, and limited build context. The wrapper changes neither
  Cargo's arguments nor build profiles and does not capture output. It does not
  install or configure Kache.
- **Node cleanup report:** inventories workspaces/build outputs and records
  storage observations. Despite its name, it has **no deletion mode**. It does
  not stop services, retire worktrees, prune Git, or authorize cleanup.

No automatic retention, cleanup, report timer or remote upload is configured by
these tools. Historical storage observations start with the saved reports; they
cannot be reconstructed for earlier days from Cargo timings alone.

## Where everything lives on the node

| Path | Purpose |
| --- | --- |
| `~/.cache/build-metrics/cargo/YYYY-MM-DD/<uuid>.jsonl` | Historical Cargo start/finish records |
| `~/.local/state/node-cleanup/history/YYYY-MM-DD/<uuid>.json` | Historical storage/workspace reports |
| `~/.local/state/node-cleanup/history/README.md` | This guide |
| `~/.local/state/node-cleanup/backups/` | Script/config copies from reviewed deployment |
| `~/.config/node-cleanup/config.json` | Inventory root, Paseo/MDE configuration, reporting budget, history and tracked caches |
| `~/.local/bin/node-cleanup` | Installed report executable |
| `~/.local/libexec/cargo-metrics/cargo_metrics.py` | Installed Cargo/Nix launcher implementation |
| `~/.local/bin/cargo`, `~/.local/bin/nix` | Symlinks to the launcher |
| `~/.local/libexec/cargo-metrics/bin/` | Shims restored after Nix assembles PATH |
| `~/.local/libexec/cargo-metrics/bashrc.before` | Original node Bash startup file, preserved before PATH activation |

Build outputs are **not** historical measurements. Agent currently shares
intermediates under `~/.cache/cargo-build/maple-agent/<host>/rust-<version>/`,
while final outputs remain in each checkout's `target/`. Other projects may
retain checkout-local targets. These large directories are distinct from
`~/.cache/build-metrics/`; do not confuse the names.

The node's projects, `.cache`, `.cargo` and `/nix` are on its data Btrfs filesystem.
Cleanup history is in the user's state directory, outside those build caches.
Private history/metrics are not checked into Git. Keep files mode 0600 and their
private storage directories mode 0700; do not share reports without reviewing
their private project paths and metadata.

## Taking storage snapshots

```bash
ssh agent-node 'node-cleanup --dry-run'
ssh agent-node 'node-cleanup --dry-run --json'
```

The node config enables `save_history`, so each normal report saves a new JSON
file automatically. With that enabled, **dry run means no cleanup, not zero
writes**. Use `--no-history` for an inspection that does not save a report, or
`--save-history` to explicitly enable it. `--apply` is rejected before scanning.

Reports include host/time/report ID/collector hash, filesystem used/free/total,
workspace protection reasons and artifact-size estimates, and configured shared
cache sizes. `usage_paths` currently tracks Agent's shared cache, incremental
state and dependency outputs for Rust 1.98.0. Update this explicit configuration
when paths/toolchains change; unrelated caches are not discovered automatically.

An exit code of **1** means checks were incomplete or history could not be saved.
Partial reports are still saved when possible: inspect `checks_complete`,
`warnings` and `history.saved`. The first verified report hit an existing
discovery-depth limit; that is not permission to delete undiscovered work.

Reports say `event: inventory_not_cleanup`. Take one before and one after an
approved cleanup. Record the actual cleanup time and exact removed paths
separately: a report is not proof a cleanup happened. Compare observations by
their timestamps and paths, not by summing every directory size. `du` estimates
can overlap through ancestors, hardlinks and reflinks and are not guaranteed
reclaimable bytes. Btrfs-exclusive extents/snapshots are not measured here.
Unavailable sizes are null; missing directories are explicitly marked missing
with size zero. Measurements are bounded and not an atomic filesystem snapshot.

## What must survive cleanup

Keep **all of `~/.cache/build-metrics/`**, **all of
`~/.local/state/node-cleanup/`**, and **`~/.local/libexec/cargo-metrics/`**.
Also preserve a custom `CARGO_METRICS_DIR` or history destination if configured.
The report exposes these as `preserved_data` and protects overlapping candidates.
These protections are not a filesystem lock: manual commands and unrelated
cleanup tools must honor them too. There is no off-node backup supplied by this
setup, so preserving local files is not disaster recovery.

Build-output cleanup can leave the historical measurements intact but make later
builds colder. Preserve that distinction when comparing performance. Never run
blanket `cargo clean` in Agent: Cargo's shared build directory can invalidate
other worktrees. Check active owners/builds and approve exact cleanup scope first.
Containers, credentials, workspace state and source work are not disposable
compiler caches.

## Interpreting Cargo records

Each invocation normally has two JSONL records (`event: start` and `finish`)
joined by `invocation_id`. A missing finish is incomplete, not successful; a
partial final line can be ignored while retaining prior complete lines.
Nested calls carry parent IDs and must not be double-counted. Different command
intervals can overlap, so summed elapsed time is not time personally spent waiting.

- Elapsed time includes compilation, linking, waits and any tests/programs run.
  Exclude long-lived `cargo run` services from build-time summaries.
- Exclude tiny `/maple-git-metadata-…/` fixture crates from full-project build
  statistics; they account for many recorded invocations.
- CPU is accumulated process/descendant CPU time; peak RSS is a Linux process
  high-water mark in KiB, not total simultaneous build RAM.
- No artifact-freshness/cache-hit, compiler-stage, lock-wait or per-test counters
  are collected. No complete argv, output or environment dumps are stored.
  Package/feature options are allowlisted and RUSTFLAGS-like values are hashed.
- A matching commit and recorded options do not establish identical inputs:
  dirty source, unrecorded test filters and effective Cargo config can differ.
- The shims preserve Nix-selected Cargo through `nix develop -c …` and
  `nix shell -c …`. Absolute executable paths, interactive Nix shells or tools
  replacing PATH can bypass collection. Direct test-binary execution is invisible.
- `CARGO_METRICS_DISABLE=1` bypasses recording; `CARGO_METRICS_DIR` overrides
  its destination. A logging failure does not fail the build.

For an initial compilation/execution split, run these back-to-back inside the
component's pinned Nix environment, without edits or competing builds:

```bash
RUSTFLAGS="-D warnings" cargo test --workspace --locked --no-run --timings
RUSTFLAGS="-D warnings" cargo test --workspace --locked
```

The first measures remaining compilation/linking without executing tests; the
second should be mostly execution when inputs remain unchanged. Keep flags,
packages, features and toolchain identical. Do not clear the shared cache for
this check. Package-only/headless test commands need their own matching pair.
The wrapper records both but cannot prove the second didn't recompile.

## Canonical source and further detail

The workstation dotfiles checkout is
`/home/alex/projects/github.com/w3irdrobot/dotfiles`:

- `scripts/cargo_metrics.py`, `tests/test_cargo_metrics.py`, `docs/cargo-metrics.md`
- `scripts/node-cleanup.py`, `tests/test_node_cleanup.py`
- `docs/designs/node-cleanup/001-report.md` (contracts and dated validation)
- `docs/node-build-metrics.md` (this guide)

The node uses explicitly deployed copies. Its shared dotfiles checkout is not
necessarily at the workstation revision: do not pull or replace shared agent
configuration just to update these tools. Inspect current changes and compare
installed/source hashes before deployment. No Git commit/push is implied by a
node installation.
