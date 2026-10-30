---
name: install-claude-code
description: Install and verify Anthropic Claude Code on an existing coding node using a reviewed supported release, interactive authentication, and a bounded tool-use smoke test. Use specifically for Claude Code CLI setup. Does not install Maple, T3, Codex, or shared agent configuration.
---

# Install Claude Code

Read [the execution-node contract](../provision-execution-node/references/node-contract.md).

## Resolve inputs

Confirm target/user/home, OS/architecture, installation path, and exact version or
latest-stable policy. Ask which supported authentication/account method to use,
and whether provider state will use the normal home or an isolated
`CLAUDE_CONFIG_DIR`. Explain the separate-login/config implications and the current
shared-config linker's custom-home restrictions. Obtain approval for a live task
that consumes provider allowance or incurs API cost.

## Install

1. Read current official setup instructions at <https://code.claude.com/docs/en/setup>.
   Inspect existing installations, launchers, package-manager ownership, config
   directories, service PATHs, and running tasks. Do not create competing installs
   or overwrite an app-managed provider binary.
2. Prefer the supported native distribution when avoiding global Node/npm. Review
   its installer, resolve the selected version, and verify platform checksums
   against official metadata before execution. If the installer cannot honor an
   exact pin, stop and choose a supported reproducible method with the user.
3. Preserve existing auth/config and retain non-secret installation provenance.
   Check the chosen distribution's update behavior; explain it and agree on a
   supported update policy before deployment. Do not promise a durable pin if a
   native auto-updater or parent application will replace the CLI.
4. Have the user run the release's supported authentication flow interactively
   (for example `claude auth login` when available). Don't print auth-store
   contents, pass tokens on the command line, or copy workstation sessions.

## Acceptance

Verify version/launcher, ownership, and discovery in the intended execution
user/service environment. After login, run a minimal approved task in a disposable
workspace that actually uses a terminal tool and confirms the intended working
directory. Keep normal permission checks; don't enable permission bypasses for
the test. Test the Maple/T3 integration if present, without interrupting active
work. Deploy shared instructions and skills separately with `deploy-agent-config`,
then check fresh-session loading. Report installed versus authenticated/tested
status honestly.
