# Node-local Cargo metrics

Ordinary `cargo` calls record build context and resource usage without capturing
output or changing compilation settings. This is an opt-in execution-node tool,
not part of the workstation installer. It needs Linux and `/usr/bin/python3`.

Install a reviewed copy of `scripts/cargo_metrics.py` at
`~/.local/libexec/cargo-metrics/cargo_metrics.py` (executable, mode 0755). Create
symlinks to that file named `cargo`, `nix` and `cargo-metrics-enter` in its sibling
`bin/` directory. Also link `~/.local/bin/cargo` and `~/.local/bin/nix` to it.
Refuse existing destination conflicts; don't overwrite another tool. Put
`~/.local/bin` before real Cargo/Nix on the execution user's PATH. No services
need restarting if they already search that directory.

On a node whose non-interactive SSH shells omit `~/.local/bin`, prepend the
reviewed block in `examples/cargo-metrics-path.sh` to its existing `.bashrc`,
before the interactive-only return. Preserve the original file and keep a
private backup. The block adds the directory only if missing, emits no output
and doesn't change shell options. This is node-local setup, not deployment of
the workstation's Bash configuration.

The Cargo shim resolves the next non-shim Cargo on PATH, preserving Nix's
toolchain choice. The Nix shim forwards commands unchanged except that
`nix develop -c …` and `nix shell -c …` insert a launcher after Nix assembles its
environment. This restores Cargo interception even when Nix prepends toolchain
directories. `--command` is also supported. No repository or flake changes are
needed, and these shims can be deployed independently of shared agent config.

## Reading the data

Each invocation writes two version-1 JSON objects, one per line, to:

```text
~/.cache/build-metrics/cargo/YYYY-MM-DD/<uuid>.jsonl
```

Files are private (0600), directories 0700. `CARGO_METRICS_DIR` overrides the
destination. There is no automatic retention, upload or deletion. A start record
without a finish means an incomplete observation, not a successful build. A
partial final line is possible after a crash or storage failure; ingestion should
ignore that line and retain earlier complete records.

The start record has UTC time, invocation/parent IDs, cwd, Git worktree/common
directory/commit (when available), Cargo and rustc PATH identities, allowlisted
build options, build-directory/compiler-wrapper environment settings, flag
hashes, CPU count and load average. Nix store executable paths identify pinned
toolchains; no extra Cargo/rustc version command is run. These are observed
environment settings, **not resolved Cargo configuration**: config files, aliases,
command-line `--config` and other overrides can change effective settings.

The finish record has UTC time, elapsed seconds, setup overhead, exit code or
signal, and Linux `wait4` resource counters. CPU counters include the waited
process and descendants whose usage is reaped through it. Peak RSS is the kernel's
reported high-water mark in KiB, **not the sum of concurrent compiler memory**.
Filesystem input/output operation counters are not byte counts. `cargo run`,
`test` and `bench` include executed programs/tests, not just compilation.

Nested invocations have parent IDs; their elapsed time and resource counters can
overlap. Don't sum parent and child measurements. Other simultaneous builds can
also affect timings. Setup (including a bounded, read-only Git lookup) is excluded
from measured Cargo elapsed time and reported separately.

No complete argv, arbitrary environment, compiler output, test filters or
arguments after `--` are stored. RUSTFLAGS-like values are hashed, not logged.
Paths, commit IDs and package/feature names remain private project metadata;
review before sharing. Git status and dirty-file contents are not inspected.

## Coverage and behavior

Stdin/stdout/stderr and the process group are inherited, with no tee or pipes.
Exit codes and fatal child signals are preserved; termination signals sent to
the launcher are forwarded to Cargo. Uncatchable termination can leave an
incomplete record. Telemetry setup/write failures do not fail the build.

Set `CARGO_METRICS_DISABLE=1` to execute the selected tools without telemetry.
Removing the two `~/.local/bin` symlinks disables interception for new calls;
already running builds and recorded data are unaffected.

Coverage is PATH-based. Absolute Cargo/Nix paths, interactive `nix develop`
shells without `-c`, environments that replace PATH again, and shells not
searching `~/.local/bin` can bypass interception. Nix derivation builds aren't
instrumented. Already-running Cargo invocations are unchanged. There are no
artifact freshness, compiler-cache hit, linking-time or lock-wait counters yet.
The same launcher can remain in place when Kache is enabled later; snapshot
Kache counters separately. This tool doesn't install or configure Kache.

Storage measurement is intentionally separate: recursive `du`/Btrfs scans on
every invocation would distort the timings we're trying to collect.

## Validation

```sh
python3 -m unittest discover -s tests -p test_cargo_metrics.py -v
```

Disposable fixtures cover argument/exit/stream/TTY passthrough, signals,
concurrent and nested invocations, privacy, permissions, storage failure,
recursion avoidance, disable mode, missing Cargo, Nix PATH precedence and
unrelated Nix commands. Real-node smoke checks must also verify a pinned Nix
Cargo invocation and its records; fixture success alone doesn't prove that path.

### Agent-node verification, 2026-11-03

- All 17 focused tests passed locally and against the installed node copy,
  including TERM/INT/HUP forwarding,
  foreground terminal Ctrl-C without a duplicate interrupt, and failed final
  record writes without changing Cargo's exit result.
- Real `nix develop --offline --no-update-lock-file … -c …` selected the existing
  Rust 1.98.0 toolchain and recorded Cargo version plus cold/warm checks of an
  isolated dependency-free fixture. A real `nix shell` using that existing store
  output also recorded its Cargo invocation.
- Eight `cargo --version` samples per mode had median launcher elapsed times of
  36 ms disabled and 48 ms enabled (about 12 ms incremental recording cost).
  This is a tiny-command overhead sample, not a build performance benchmark;
  disabled mode still starts the Python launcher.
- Smoke data/artifacts are separate under
  `~/.cache/build-metrics/validation-gscwskox/`, not production measurements.
- Plain non-interactive SSH now resolves the node-local Nix shim and records
  its normal `nix develop … -c cargo --version` call. The guarded startup block
  was prepended to `.bashrc`; its original is preserved mode 0600 at
  `~/.local/libexec/cargo-metrics/bashrc.before`. Existing agent processes already
  had `~/.local/bin` on PATH; no service restarts or Maple edits were needed.
- The full local suite ran 449 tests with 21 failures in existing OpenCode,
  nono and Bitwarden installer tests. No existing installer code was changed.
