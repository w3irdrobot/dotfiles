---
name: install-codex
description: Install and verify the complete OpenAI Codex CLI runtime on an existing coding node, including matching helper binaries, interactive authentication, and a bounded tool-use smoke test. Use specifically for Codex installation or an incomplete Codex runtime. Does not install Maple, T3, Claude, or shared agent configuration.
---

# Install Codex

Read [the execution-node contract](../provision-execution-node/references/node-contract.md).

## Resolve inputs

Confirm target/user/home, OS/architecture, exact version or latest-stable policy,
installation path, and supported installation method. Ask whether to use the
normal provider home or an isolated `CODEX_HOME`, and which authentication method
the user intends. Do not assume that cohosted apps should share accounts. Explain
that a custom home needs its own auth/config and may not work with the current
shared-config linker. API-backed checks may incur cost; get approval.

## Install the complete runtime

1. Read first-party installation and release guidance at
   <https://github.com/openai/codex> and <https://developers.openai.com/codex>.
   Resolve the requested release for the actual OS/libc/architecture. Inspect
   existing binaries, package managers, PATH precedence, homes and running tasks.
2. Prefer a supported native package when avoiding a global Node toolchain. Review
   published checksums/signature metadata and verify before execution. Inspect
   the package manifest/layout instead of extracting only a binary named `codex`.
3. Verify required sibling executables are installed in the expected locations.
   Codex 0.164.0 needed a separately distributed `codex-code-mode-host` alongside
   a standalone CLI; omitting it allowed startup/version checks but broke terminal
   tools. This is historical evidence, not a version pin or an assertion that
   every future release has the same layout. Inspect the chosen release for all
   required helpers (including sandbox components where applicable), matching
   versions/target triples and verified artifacts. Don't mix arbitrary releases.
4. Refuse conflicts and preserve existing auth/config. Retain artifact provenance.
   If an app launches Codex, verify its effective service PATH and provider-home
   environment; an interactive shell's PATH is not proof of service discovery.
5. Let the user authenticate in their terminal using this release's supported
   flow (for example `codex login --device-auth` when available). Never capture
   device codes, tokens, or auth-store content. No permission bypass flags.

## Acceptance

Verify exact CLI version, helper startup, permissions, and effective launcher
paths. After login, run an approved minimal task in a disposable directory that
actually invokes a terminal tool (`pwd` or an equivalent harmless bounded command)
and confirms its working directory. A version check or app-server skills list is
not sufficient. Test through the intended Maple/T3 integration separately if
present; do not restart live hosts automatically. Shared instruction/skill setup
belongs to `deploy-agent-config`. Report which checks remain unverified.
