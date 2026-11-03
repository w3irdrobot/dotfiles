# GitHub CLI on Debian execution nodes

When `gh` installation or an update is approved on a Debian agent node, use the
official release `.deb` from [cli/cli](https://github.com/cli/cli/releases), rather
than Debian's older repository candidate. Install it through APT as a local package;
do not add GitHub's APT repository or an unattended updater. This policy is for
Debian execution nodes, not the Fedora workstation or arbitrary other operating
systems. Git itself can remain distribution-managed.

## Inspect and select

- Confirm the exact guest, execution user, OS, and `dpkg --print-architecture`.
  Inspect command resolution and `dpkg-query`/`apt-cache policy gh`; preserve PATH
  conflicts and unmanaged binaries instead of overwriting them. Check for running
  `gh` commands before replacing an existing installation.
- Resolve the approved release policy (exact version or latest stable) to an exact
  non-prerelease tag. Do not pin future nodes to a version copied from these notes.
  Use the matching official architecture asset, such as
  `gh_<version>_linux_amd64.deb` or `gh_<version>_linux_arm64.deb`; refuse unsupported
  architectures and downgrades unless explicitly approved.
- Installation is administrator-owned guest work. Keep the execution user without
  sudo, and do not run the workstation bootstrap or modify the hypervisor.

## Verify before privileged installation

1. Fetch the exact release metadata from GitHub's official `cli/cli` repository.
   Download the `.deb` and `gh_<version>_checksums.txt` from that release's HTTPS
   asset URLs into a new staging directory. Do not use third-party repackages or
   a moving download URL as a version pin.
2. Check the downloaded size and SHA-256 against the release asset's API digest
   and the matching published checksum entry. Verify the checksums asset against
   its own API digest when available. Prefer immutable published releases; if
   authoritative digest metadata is missing or disagrees, stop and review the
   release's supported attestation/signature verification rather than skipping it.
   These checks establish agreement with release metadata, not a detached package
   signature. Verify supplied signatures/attestations through supported upstream
   tooling where available; never claim verification that was not performed.
3. Check `dpkg-deb --show` for package `gh`, the selected version, and the guest's
   architecture. Inspect control metadata and any maintainer scripts before
   privileged execution. Keep verified artifacts in an administrator-owned path
   that APT can read; do not install an execution-user-writable artifact as root.
4. As guest administrator, simulate the exact local-package transaction:

   ```bash
   apt-get --simulate install /absolute/verified/path/gh_<version>_linux_<arch>.deb
   ```

   Review dependencies and space requirements. Install that same verified local
   package with `apt-get install --no-remove` after approval. Do not select `gh`
   by bare package name, run a general upgrade, remove unrelated packages, or
   disable package verification. Dependency additions need to fit the approved
   plan; unexpected changes are a blocker.

## Verify and preserve authentication

Run `gh --version` as the execution user in a fresh login and confirm the resolved
executable is the updated package, not a shadowing binary. Check `dpkg --audit`.
When an existing account is expected, make a read-only authenticated check such as
`GH_PROMPT_DISABLED=1 GH_NO_UPDATE_NOTIFIER=1 gh api user --jq .login`; never print
tokens or raw credential files. If authentication fails, report it rather than
running login, changing credential storage, or migrating secrets automatically.
New-account authentication remains the separate `configure-node-git` workflow.

Retain the exact version, asset URL, digest, size, and actual verification evidence
outside Git in non-secret installation provenance. Report that later updates need
another explicit reviewed package installation. No agent-service restart is
required for this CLI update.
