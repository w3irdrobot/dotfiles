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

Each export picker requires explicit marks: press **TAB** to mark/unmark items,
then **Enter** to export those marks. Enter with no marked items, or Escape,
skips that category; the focused row is not implicitly selected. If every category
is empty, export stops without creating an archive. Personal fzf auto-selection
and output-transform options are ignored for these sensitive pickers. Picker
errors abort rather than selecting a fallback, and malformed/empty GPG key IDs
are rejected before GPG is invoked.

## SSH configuration

Git manages only a generic `~/.ssh/config` template: the local include and
shared defaults. Personal host aliases, addresses, usernames, and identity paths
belong outside the checkout. Export the **current, cleaned-up source-machine
config**, not an old copy from Git history; deleted hosts must not be resurrected
by config linking or installation. Import restores selected archived hosts into
`~/.ssh/config.local`, never into the tracked template.

Earlier revisions incorrectly embedded personal host blocks in that template.
They are removed from the current tree, not moved into a new local copy or
recovered from history. On a machine linking to the old template, pulling the
cleanup removes those old blocks; export the correct source config and explicitly
import it on the destination. Existing destination hosts are skipped, not pruned
or overwritten: importing an archive is not an automatic deletion/sync operation.
Historical Git commits still contain the removed entries; erasing history would
be a separate, explicitly approved operation.

Imported host definitions belong in `~/.ssh/config.local`. Export follows that
include at the top of the main config and accepts whitespace and `keyword=value`
syntax. For each selected host, it flattens applicable global, wildcard/negated,
repeated-host, and `Match all` settings in their original order, collecting all
explicit identity files. It does not run `ssh -G` or config commands.
Archive host blocks use two-space indentation and conventional keyword casing
for common options. Values, directive order, and repeated options are preserved;
inherited settings are flattened into each selected host rather than relying on
the destination's global defaults. This is a semantic export, not a byte-for-byte
copy preserving original comments/layout. Existing local fragments are not
automatically reformatted or overwritten when updating the tools.

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
