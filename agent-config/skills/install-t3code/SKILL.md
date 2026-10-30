---
name: install-t3code
description: Install and verify T3 Code on an existing execution node, optionally as a user service, with explicit private access and per-device pairing. Use specifically for T3 Code host setup. Does not provision a VM, install Maple or provider CLIs, migrate state, or expose a public server automatically.
---

# Install T3 Code

Read [the execution-node contract](../provision-execution-node/references/node-contract.md).

## Resolve inputs

Confirm target/user, OS/architecture, release policy, install/data paths, and
foreground versus persistent service. Ask which access method is wanted:
desktop-managed SSH, direct private-network pairing, Tailscale HTTPS, or T3
Connect. Ask for the exact bind address/port for direct access. Do not default to
`0.0.0.0`, copy an old Tailscale IP, enable Serve/Funnel, or sign into T3 Connect
without agreement. HTTPS/T3 Connect can require additional user/account actions.

Ask which already installed providers to use and whether provider homes/auth
should be shared or isolated. Distinct T3 app data does not isolate Codex/Claude
history/auth. Isolated homes require separate login and configuration deployment;
the current shared-config linker may refuse custom homes. Do not improvise around
that refusal. No provider installation or update is implicit in T3 setup.

## Install and configure

1. Read current first-party [installation](https://github.com/pingdotgg/t3code/blob/main/docs/user/install.md),
   [service](https://github.com/pingdotgg/t3code/blob/main/docs/user/background-service.md),
   and [remote access](https://github.com/pingdotgg/t3code/blob/main/docs/user/remote-access.md)
   instructions; check the chosen release's CLI help where it differs from main.
   Inspect existing `t3`, `t3code`, data/runtime paths and services for conflicts.
2. Prefer the official self-contained CLI where supported; it does not require a
   global Node/npm installation. Review <https://t3.codes/install.sh> before use;
   pin the resolved version, verify published artifact checksums/metadata, and
   refuse overwrite/pruning behavior against unmanaged paths. Retain provenance.
3. Follow the release's runtime/launcher layout. For a service, configure the
   approved host/port through private `service.env` (literal values, no shell
   expansion), then use `t3 service install`. Do not print captured startup logs
   blindly: they can contain pairing secrets.
4. Inspect the generated unit. Ensure its effective PATH can resolve the selected
   provider CLIs under the intended user, not just in an SSH shell. Put needed
   PATH and `UMask=0077` settings in a conflict-safe systemd drop-in. Enable
   lingering only if selected. Keep T3 state separate from Maple state; default
   T3 paths are normally `~/.t3` with application data under `userdata`.
5. Verify listening sockets match only the agreed interfaces. A plain HTTP server
   at `http://<private-ip>:<port>` is not `https://<private-ip>/`; include scheme
   and port when connecting. The hosted web app needs HTTPS. Tailscale Serve HTTPS
   is a separate network change, not something to auto-enable after a failed URL.

## Pair and verify

Have the user run `t3 pair` interactively on the host. Use a fresh one-time link
for each device. In desktop use its `t3code://pair` link or Settings → Environments
→ Add environment. Sharing & access shares the currently selected environment;
sharing the desktop's Local environment does not pair a client to the VM.

Verify exact version, service health, bind address, endpoint response, selected
provider paths, and a user-approved disposable provider task. A running HTTP
endpoint doesn't prove provider login or tool execution. Confirm instructions and
skills through the actual provider session after separate config deployment.
Recommend distinct task worktrees/threads when cohosting apps; do not silently
change their accounts or shared limits. Report remaining pairing/auth checks.
