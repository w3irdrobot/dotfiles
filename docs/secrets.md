# Moving secrets between machines

Use the globally available per-user `dotfiles` launcher:

```bash
dotfiles secrets export --dry-run
dotfiles secrets export
dotfiles secrets import
dotfiles secrets --help
```

These commands delegate directly to this checkout's existing `secrets_export`
and `secrets_import` scripts. The standalone commands remain available when the
GnuPG module is linked. Neither path runs as part of installation or updates.
Selections and archive locations are interactive; do not pass credentials or
passphrases as command arguments. `--dry-run` describes the operation without
reading keys, wallets, or archives. Help and previews do not check dependencies
or prove that an export/restore will succeed.

The helpers support Linux and macOS; Fedora-only provisioning checks do not run
for secrets migration. On a source machine without the launcher, use
`bash /path/to/checkout/bin/dotfiles secrets export` with Bash 5+ and the helper
dependencies (`gpg`, `fzf`, `tar`, `jq`, and platform discovery tools) installed.
No dependencies are installed automatically. The caller's current directory is
preserved for the existing fallback when no removable media is found. Run from
a private directory outside this checkout, including for dry-run previews.

`dotfiles secrets` suppresses DEBUG/xtrace/verbose tracing before invoking the
helper. Do not separately enable tracing inside the helper or publish its output
without reviewing it for identifying metadata.

Secrets export/import remain a separate, manual migration workflow.
Review the archive selection and test a restore before wiping the source machine.
Keep archives, keys, wallet data, and authentication stores outside this checkout.

## SSH configuration

Imported host definitions belong in `~/.ssh/config.local`. Export follows that
include at the top of the main config and accepts whitespace and `keyword=value`
syntax. For each selected host, it flattens applicable global, wildcard/negated,
repeated-host, and `Match all` settings in their original order, collecting all
explicit identity files. It does not run `ssh -G` or config commands.

Flatten and review these unsupported forms manually before exporting:

- Other, nested, or conditional includes and conditional `Match` blocks.
- Hostname canonicalization.
- Identity paths requiring expansions or ambiguous quoting.

Use absolute or `~/` identity paths. Default identities are not inferred. When
Bitwarden's SSH agent holds the private half, an explicitly referenced private
path whose file is absent is exported from its `.pub` companion instead; the
archive then contains public material only. Export fails only when both the
private file and its public companion are missing. Explicit `.pub` identities
export without adding a `.pub.pub` entry.

Archives use flat key filenames, so basename collisions—including public-key
companions and reserved entries—stop export before staging or changing an
existing archive. Rename colliding keys and update the config yourself.

Import restores names from archived `IdentityFile` entries, including names other
than `id_*`. Agent-only archives are valid: a missing private key is accepted
when its public companion is archived. Import fails when neither half is present.
Private key content is restored as `0600`, even when the filename ends in `.pub`;
public content uses `0644`. Existing differing files are warned about and skipped
rather than overwritten. Review the restore summary and adjust identity paths that
differ on the destination.

## USB selection

USB selection keeps exact mountpoints separate from displayed labels. Failed
discovery or an invalid picker selection aborts instead of choosing another path.
Confirm the selected destination and verify the restored files before retiring
the originals.
