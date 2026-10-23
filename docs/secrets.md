# Moving secrets between machines

`secrets_export` and `secrets_import` are a separate, manual migration workflow.
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

Use absolute or `~/` identity paths. Default and agent-only identities are not
inferred. Archives use flat key filenames, so basename collisions—including
public-key companions and reserved entries—stop export before staging or changing
an existing archive. Rename colliding keys and update the config yourself.

Import restores names from archived `IdentityFile` entries, including names other
than `id_*`. Missing explicitly referenced private keys stop import; public
companions are optional. Explicit private identities use mode `0600` even when
their filename ends in `.pub`; public companions use `0644`. Existing differing
files are warned about and skipped rather than overwritten. Review the restore
summary and adjust identity paths that differ on the destination.

## USB selection

USB selection keeps exact mountpoints separate from displayed labels. Failed
discovery or an invalid picker selection aborts instead of choosing another path.
Confirm the selected destination and verify the restored files before retiring
the originals.
