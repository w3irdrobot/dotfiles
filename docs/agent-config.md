# One agent configuration, multiple tools

`agent-config/` is the source of truth for personal instructions and skills.
OpenCode, Codex, Claude Code, and Maple consume the same files through symlinks.
Use the same checkout and deployment command on a local workstation or on the
remote computer executing tasks. No agent software or credentials are installed.

```text
agent-config/
├── instructions/AGENTS.md       # Portable shared rules
├── instructions/legacy-opencode.md # Previous rules, for migration review only
├── skills/                     # All seven personal skills and supporting files
└── agents/opencode/             # Existing OpenCode-format specialist definitions
```

The old Stow instruction, skill, and agent entries now link back here;
they are adapters, not separate editable copies. OpenCode provider/MCP settings,
terminal preferences, themes, and sandbox integration remain tool-specific.

## Deploy to a node

An agent can follow [SETUP.md](../agent-config/SETUP.md) to pull a reviewed
revision from GitHub and deploy it. Give it the node/user, selected tools, and
checkout path (or let it ask). It uses this same helper, not another installer.

## New local workstation

The normal `ai` group now selects the configuration-only `agent-config` module.
`dotfiles install`, `dotfiles link`, and config/all updates with that selection
preflight and deploy shared links for all four tools as part of the normal flow.
The preflight runs before package transactions and reports existing instructions
or foreign links as conflicts. Dry-runs never create links. Python 3 must be
available for preflight and is also declared as a module dependency.

This installs configuration, not the Codex, Claude Code, or Maple applications.
OpenCode installation remains owned by its existing module. Selecting groups
without `ai` skips shared configuration unless `--modules agent-config` is added.
That explicit module can configure links without selecting workstation OpenCode
settings or its application. For a subset of tools, use the standalone command
below rather than selecting this all-tool workstation module.

## Standalone local or remote deployment

Use a stable clone of these dotfiles on the execution computer. It can live
anywhere; do not run workstation provisioning to configure an agent server.
Python 3 and Linux symlinks are enough for this standalone helper:

```bash
# Local workstation using all four tools:
python3 scripts/link-agent-config.py --tools maple,codex,claude,opencode --dry-run
python3 scripts/link-agent-config.py --tools maple,codex,claude,opencode

# Remote node running Maple and Codex:
python3 scripts/link-agent-config.py --tools maple,codex --dry-run
python3 scripts/link-agent-config.py --tools maple,codex
```

Run as the OS user that executes the tasks. `--home /existing/test-home` supports
disposable rehearsal. Tool selection is explicit and is not saved. Custom
`CODEX_HOME`, `CLAUDE_CONFIG_DIR`, and `XDG_CONFIG_HOME` layouts are currently
refused rather than silently installing into a path the tool will not read.

| Consumer | Global instructions | Skills |
| --- | --- | --- |
| Maple | `~/.agents/AGENTS.md` | `~/.agents/skills/<name>` |
| Codex | `~/.codex/AGENTS.md` | `~/.agents/skills/<name>` |
| Claude Code | `~/.claude/CLAUDE.md` | `~/.claude/skills/<name>` |
| OpenCode | `~/.config/opencode/AGENTS.md` | `~/.config/opencode/skills/<name>` plus shared discovery |

Every deployment creates the shared `.agents` locations. Selected tools receive
their adapters. OpenCode keeps explicit skill links for launches that disable
external discovery; all links resolve to the same canonical content. Claude Code
supports symlinked skill folders and instruction files for ordinary CLI sessions.
Cowork and cloud sessions have different discovery restrictions; this setup does
not claim support for them. Codex's `AGENTS.override.md` shadows `AGENTS.md`, so
the helper refuses a deployment with that override present.

For T3 Code, select the underlying execution tool (for example `--tools codex`)
on its execution computer. This assumes it launches that tool with the same OS
home and normal discovery. Isolated homes, containers, or custom prompts require
configuration in T3 itself. There is no unverified T3-specific adapter here.

## Migrating existing configuration

Start with the dry-run and review any reported conflicts. The helper never
replaces regular files, foreign links, or dangling links, even when their contents
match. Back up and reconcile those files manually before removing a conflicting
destination. Exact canonical links, including this checkout's Stow adapters, are
reused. Symlinked parent directories are otherwise refused. The helper does not
write missing files through an allowed Stow link into the source checkout.
If an earlier PR revision installed whole-directory `skills` or `agents` links,
review and unlink those exact home-level directory links before migrating to the
individual-link layout. The helper and workstation preflight intentionally refuse
to replace them automatically. Existing unrelated entries must be preserved.

If you tried this PR's original four-skill helper, its `~/.agents/AGENTS.md` link
points at the old `agent-config/AGENTS.md` location. Review and unlink that exact
stale link before running the new helper. The moved skills remain reachable through
the Stow compatibility paths. There is no automatic migration of old instruction links.

For an existing Stow deployment, the old instruction file and skill/agent
directories become links when this revision is deployed. Updating that checkout
therefore changes the live instruction content. Review
`instructions/legacy-opencode.md` against the shared rules first; it is retained
only as migration context and is **not installed or loaded**. Its old workstation
paths and unconditional knowledge-base usage must move to node guidance if wanted.

The shared rules replace those assumptions with optional
`~/.config/agent-config/node.md`. Copy `examples/agent-node.md` manually and fill in
actual checkout paths, worktree conventions, and tools. For the existing workstation,
`~/projects` can remain the checkout root; a remote node can choose another path.
The shared instructions ask the model to read this file. It is not executable
configuration or a native automatic import, so verify that it was read in a fresh task.

All seven personal skills are now shared: Bash, Rust, OpenTofu, frontend design,
project creation, skill creation, and YouTube transcripts. Tool prerequisites are
still checked at use time, not provisioned by deployment. Project creation uses
the node's checkout root; skill creation no longer assumes OpenCode-only tooling.
Supporting scripts, references, and licenses move with the skills. The nono skill
and plugin remain owned by their installed package, not this shared collection.
The helper discovers non-hidden direct child directories containing `SKILL.md`;
there is no separate skill manifest. New skills are automatically included on the
next helper run. Stow has individual compatibility links for existing resources,
not a whole-directory link, so package-managed entries stay outside the checkout.

## Agents are tool-specific

Existing specialist definitions retain their OpenCode format and disabled flags
under `agents/opencode/`. Selecting OpenCode links them into its `agents/` folder.
They are not copied into Claude's or Codex's agent directories: metadata, tool
names, delegation policy, and availability differ. Maple has no equivalent custom
agent adapter in this proposal. The shared skills work without these specialists.
This preserves the prompts for later deliberate conversion without pretending
that symlinking one format makes it valid in every tool.

## Knowledge and machine configuration

Knowledge access is disabled unless node guidance supplies a verified local path
and permitted use. Nothing clones, syncs, or grants access to the personal knowledge
base. A workstation can opt in to its existing checkout; remote nodes can use a
separately reviewed subset or none. Enforce read-only access with OS permissions
if required; instructions are not access controls. The existing OpenCode-specific
`knowledge` reference remains in its config and must be reviewed separately when
deploying that full workstation configuration.

Credentials, Git identity/signing, private hosts, tool auth stores, MCP config,
service state, and sandbox permissions are not part of this helper's deployment.
Node guidance stays non-secret and outside Git. Repo-specific instructions and
skills stay in the relevant repo.

## Updates and verification

Updating a linked checkout **is deployment**, because links see content changes
immediately. Use a dedicated checkout pinned to a reviewed revision to control
rollout. Verify origin and a clean status before fetching/updating; use fast-forward
updates for tracking branches and never reset/stash/discard node edits. Run the
helper's dry-run and deployment again to add newly selected resources. SSH can run
the same commands using each node's own checkout path; no host inventory or
automatic remote updates are included.

There is no pruning: removing a skill directory or deselecting a tool
does not revoke previously installed links. Review and unlink them manually.
Interrupted deployments leave completed links in place and can be rerun safely.
Do not run concurrent deployment or edit link parents during deployment.

Fixture tests cover the filesystem layout, conflicts, Stow compatibility, and
shared content. They do not prove an authenticated agent used the instructions.
After deployment, start a fresh session in each selected tool, verify instruction
sources and skills, and try a harmless relevant skill. In Claude use `/context`
and `/skills`; in OpenCode use `/reload` and skill discovery. Check that the node
file was actually read. Remote Maple and T3 runtime checks remain pending.

References: [Codex instructions](https://developers.openai.com/codex/guides/agents-md),
[Claude memory](https://code.claude.com/docs/en/memory),
[Claude skills](https://code.claude.com/docs/en/skills),
[OpenCode skills](https://opencode.ai/v2/docs/skills).
