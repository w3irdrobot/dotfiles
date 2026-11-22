# One agent configuration, multiple tools

`agent-config/` is the source of truth for personal instructions and skills.
OpenCode, Codex, Claude Code, and Maple consume the same files through symlinks.
Use the same checkout and deployment command on a local workstation or on the
remote computer executing tasks. No agent software or credentials are installed.

```text
agent-config/
├── instructions/AGENTS.md  # Portable shared rules
└── skills/                 # Shared personal skills and supporting files
```

Tools link straight to these files; there are no separate editable copies.
OpenCode provider/MCP settings, terminal preferences, and themes stay in
`files/opencode/`.

## Deploy to a node

An agent can follow [SETUP.md](../agent-config/SETUP.md) to pull a reviewed
revision from GitHub and deploy it. Give it the node/user, selected tools, and
checkout path (or let it ask). It uses this same helper, not another installer.

## New local workstation

Home Manager links the shared instructions and every skill for all four tools
on each `home-manager switch` (see `home.nix`). New
skills appear after the next switch. This installs configuration, not the Codex,
Claude Code, or Maple applications.

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
destination. Exact canonical links are
reused. Symlinked parent directories are refused.
Node-specific guidance lives in optional
`~/.config/agent-config/node.md`. Copy `examples/agent-node.md` manually and fill in
actual checkout paths, worktree conventions, and tools. For the existing workstation,
`~/projects` can remain the checkout root; a remote node can choose another path.
The shared instructions ask the model to read this file. It is not executable
configuration or a native automatic import, so verify that it was read in a fresh task.

Personal skills are shared, including Bash, Rust, OpenTofu, frontend design,
design workflow, project creation, skill creation, and YouTube transcripts. Tool
prerequisites are still checked at use time, not provisioned by deployment. Project creation uses
the node's checkout root; skill creation no longer assumes OpenCode-only tooling.
Supporting scripts, references, and licenses move with the skills.
The helper discovers non-hidden direct child directories containing `SKILL.md`;
there is no separate skill manifest. New skills are automatically included on the
next helper run. Links are per skill, not whole directories, so package-managed
entries stay outside the checkout.

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

After deployment, start a fresh session in each selected tool, verify instruction
sources and skills, and try a harmless relevant skill. In Claude use `/context`
and `/skills`; in OpenCode use `/reload` and skill discovery. Check that the node
file was actually read. Remote Maple and T3 runtime checks remain pending.

References: [Codex instructions](https://developers.openai.com/codex/guides/agents-md),
[Claude memory](https://code.claude.com/docs/en/memory),
[Claude skills](https://code.claude.com/docs/en/skills),
[OpenCode skills](https://opencode.ai/v2/docs/skills).
