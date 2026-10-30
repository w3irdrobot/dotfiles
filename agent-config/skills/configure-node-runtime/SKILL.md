---
name: configure-node-runtime
description: Configure a headless coding node's project build runtime, Nix, optional rootless Podman, cache placement, and resource limits. Use after provisioning when development tools and build storage need setup. Does not install agent apps, configure Git credentials, or repartition disks.
---

# Configure a node's build runtime

Read [the execution-node contract](../provision-execution-node/references/node-contract.md).
This skill works on an existing node; it does not provision one.

## Resolve inputs

Confirm target/user, OS, checkout root, representative project requirements, and
whether Nix and rootless containers are wanted. Ask for missing build concurrency,
per-build compiler jobs, cache locations/budget, minimum free-space reserve, and
cleanup/retention choices. Ask which tools beyond project environments are needed
(for example Git, Python, ripgrep, just, ShellCheck, or shfmt). Do not install a
blanket package list or reuse the former VM's two-build/four-job settings.

Inspect actual CPU/RAM, disk and Btrfs usage, mounts/subvolumes, existing tools,
configs, Nix distribution, and container state before proposing changes.

## Configure the selected components

1. Use supported packages for the selected OS where suitable. On Fedora use its
   repository Nix/nix-daemon workflow; do not mix it with upstream installations.
   For other OSes choose one supported Nix distribution and review its installer.
   Make the daemon, flake configuration, allowed users, and experimental features
   explicit. Keep execution users untrusted Nix clients, not daemon administrators.
2. Use repositories' pinned Nix development environments for Rust/Node/etc. Do
   not substitute global Rustup/NVM. Verify a representative project's declared
   workflow rather than assuming all repositories use the same flake attributes.
3. Apply agreed Nix build concurrency/core limits and free-space controls. If
   requested, set Cargo jobs and cache paths without overwriting existing config.
   Explain that build limits across multiple agent apps are not automatically a
   single global semaphore. Do not claim an instruction alone enforces them.
4. Account for Nix store, Cargo caches/targets, worktrees, container storage, app
   artifacts, and logs in the capacity plan. On Btrfs check both data and metadata
   usage; `df` alone is insufficient. Explain that snapshots can retain deleted
   caches. Do not enable NOCOW, quotas, timers, or destructive pruning implicitly.
5. If containers were selected, configure rootless Podman and the chosen Compose
   provider using supported subordinate-ID/user-namespace setup. Verify normal-user
   operation. Do not add Docker-group privileges or install a rootful daemon.
6. Keep node-specific resource and checkout conventions in non-secret node guidance,
   not in portable shared instructions. Reconcile an existing node file with the
   user; shared agent-config deployment is a separate skill.

## Acceptance

Verify selected tools as the execution user, Nix daemon access without privileged
trust, effective build settings, cache filesystem/free space, and rootless Podman
when selected. Run a small approved project build from its explicit checkout;
bound the test and report disk growth. Verify settings persist in a fresh login.
Report omitted components and pending real-project checks. Do not launch agent
services, garbage collection, or unattended upgrades as part of this skill.
