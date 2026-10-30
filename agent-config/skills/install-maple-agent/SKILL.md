---
name: install-maple-agent
description: Install and verify the official Maple Agent host on an existing headless execution node, with signed release verification, a user service, and interactive remote pairing. Use specifically for Maple installation. Not for T3 or provider CLI installation, node provisioning, migration, or unattended upgrades.
---

# Install Maple Agent

Read [the execution-node contract](../provision-execution-node/references/node-contract.md).

## Resolve inputs and preflight

Confirm target/user/home, OS/architecture, production or development profile,
release policy, install location, and whether a persistent user service and remote
access are wanted. Ask for missing service working directory, approved PATH/tool
locations, and controller/account pairing expectations. Do not create an account
or select an old release/account from historical node setup.

Check existing binaries, bundles, profiles, services, ownership, and running work.
Existing state makes this an update/reconciliation task: stop and plan it with the
user, rather than run a first-install script over an installation. Installing
Codex/Claude or shared skills is outside this skill.

## Verify the current upstream workflow

Use first-party Maple sources: <https://github.com/MaplePrivacyLabs/Maple>, component
`apps/maple-agent`, its `docs/updates.md`, packaging instructions, and
`scripts/linux-install.py`. Inspect an existing source checkout before cloning;
use the selected release's source where available, not arbitrary current code.
Check the current stable Linux feed at
<https://updates.maple.ai/agent/stable/linux/latest.json> when latest stable was
selected. Other platforms require their supported installation path; do not run
Linux instructions on them.

1. Obtain trusted production signing keys from reviewed upstream source, not from
   the downloaded manifest itself. Verify the exact raw manifest bytes and detached
   Minisign signature, then release channel/product/version/platform identity.
2. Download the authenticated artifact from the expected HTTPS origin. Check its
   signed size and SHA-256 before extraction. Inspect archive paths, types, links,
   permissions, and bounds; extract into a new private staging directory.
3. Validate the bundle inventory and metadata with the reviewed upstream validator
   before executing it. Python's tar data filter can omit directory permissions;
   if necessary restore only authenticated, expected directory modes before
   validation. Do not weaken the validator or chmod everything recursively.
4. Use the reviewed first-install workflow under the execution user. Refuse
   destination/launcher conflicts; retain signed provenance outside Git.

## Service and pairing

If selected, create a user service using the verified launcher and supported
`host serve`/`host stop` commands (confirm against this release). Set an explicit
working directory and PATH including approved provider locations, `UMask=0077`,
restart-on-failure with rate limits, and appropriate stop handling. Review current
upstream delegation/cgroup requirements. Enable lingering through approved narrow
administration if persistence after logout/boot was selected.

Have the user perform login, remote enablement, and pairing interactively. These
may start a host outside systemd; coordinate handoff to the service before any
tasks begin. Never capture passwords, account secrets, or pairing codes in tool
output. An unconfigured host may intentionally exit; do not diagnose that as a
crash solely from an inactive service. Don't repeatedly restart it to force login.

## Acceptance

Verify exact installed identity, launcher, permissions, selected profile, effective
service configuration and stable restart count. After user authentication, verify
remote readiness and ask for a harmless controller task in an explicit disposable
workspace. Report endpoint/pairing and actual tool execution separately. If providers
are not installed, report that limit rather than installing them implicitly.

Do not add an unattended updater. Headless update support must be checked against
the current release; a desktop-only updater does not establish a daemon upgrade
path. Existing-bundle maintenance needs a separately approved stopped-host,
verified backup/locking/activation plan, not a rerun of first installation.
