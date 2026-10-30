---
name: configure-node-git
description: Configure an execution user's Git identity, GitHub CLI authentication, Git transport, and optional SSH commit signing on a coding node. Use when preparing repository access and signed commits for agents. Does not copy workstation credentials, create repositories, push commits, or provision a node.
---

# Configure Git on an execution node

Read [the execution-node contract](../provision-execution-node/references/node-contract.md).

## Resolve inputs

Ask for missing target/user, Git hosting account/host, exact author name/email,
Git transport (HTTPS/SSH), and commit-signing policy. If SSH signing is wanted,
ask whether to create a node-local key or use an already configured signer, its
path, and passphrase/unlock expectations for unattended agents. Do not infer
identity from the workstation or confuse SSH Git authentication with signing.

## Setup

1. Inspect installed Git/gh, effective configuration origins, and existing auth
   status without printing credentials or private config contents. Preserve local
   overrides. Obtain approval to install missing packages and change config.
2. Have the user authenticate through `gh auth login` or the host's supported
   interactive workflow. Configure the agreed HTTPS credential helper or SSH
   access; do not import browser stores, copy keys, or pass tokens as arguments.
3. Set only the agreed identity/transport settings. For SSH signing, use
   `gpg.format=ssh`, the approved signing key, and `commit.gpgsign=true`. Generate
   a new key only when authorized, using exclusive/conflict-safe paths. Let the
   user register its public key as a signing key with the hosting account. Do not
   upload keys, change account settings, or disable signing to bypass failures.
4. Keep node-private keys and authentication stores outside source checkouts with
   restrictive permissions. Do not forward workstation credentials as a shortcut.

## Acceptance

Check account/host authentication without exposing tokens, and use an agreed
repository for a read-only remote-access test. Test a signed commit only in an
approved disposable local repository, including local signature verification
with an appropriate public-key allowed-signers entry. Distinguish local validity
from the hosting service's Verified badge. Do not push test commits without
authorization. Report identity/signing configuration and remaining user actions,
never private key material.
