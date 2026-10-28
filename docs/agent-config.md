# Agent configuration on local and remote nodes

This is an opt-in portable configuration for the computer **executing** a task.
It does not install Maple, provision a server, forward credentials, or change the
existing local OpenCode setup. Nothing is added to default installer groups.

## What gets deployed

- `agent-config/AGENTS.md` becomes `~/.agents/AGENTS.md`: communication, safe Git
  workflow, project-owned environments, and execution-node awareness.
- `agent-config/skills.json` explicitly selects Bash, Rust, OpenTofu, and frontend
  skills. Each complete directory, including references/licenses, is linked from
  its existing source under `stow/opencode/`; there is no second editable copy.
- Optional `~/.config/agent-config/node.md` supplies node-specific paths and
  non-secret operational guidance. The shared instructions tell the model to
  read it; Maple does not natively discover or interpret this file.

The allowlist deliberately omits `create-project` (personal template/setup
assumptions), `skill-creator` (OpenCode-specific workflow), and `youtube-transcript`
(extra download/tool requirements). They can be reviewed and opted in later.
Repo-owned skills stay with their repos, rather than becoming global defaults.

Workstation OpenCode config, agents, MCP servers, nono profiles, personal SSH
configuration, Git identity/signing, credentials, and the knowledge-base checkout
are **not** deployed. Skills do not install their prerequisite tools.

## First deployment

On the execution node, use a stable dotfiles checkout owned by the task's OS user.
Clone over SSH if that user already has GitHub access; otherwise arrange access
separately. Do not run the workstation bootstrap on an agent server. The standalone
linker needs Python 3 and an existing home directory, not DNF or Stow.

From the reviewed checkout:

```bash
python3 scripts/link-agent-config.py --dry-run
python3 scripts/link-agent-config.py
```

For a disposable home, pass `--home /path/to/existing/test-home`. All destinations
are checked before creating any links. Existing files, directories, foreign or
dangling links, and symlinked parent directories stop the operation. Only exact
links owned by this checkout are reused. There is no force/adopt option. Move
conflicts manually after review; don't blindly replace existing agent instructions.
Unrelated skills in a real `~/.agents/skills` directory are left alone.

Create the optional node file separately using `examples/agent-node.md` as a
starting point. Replace its example paths; leave knowledge disabled initially.
Do not store node-specific settings, hosts, or credentials in the public repo.

## Updating and remote deployment

Commit shared changes here and review the diff before deploying. On each node,
check `git remote -v`, `git status --short --branch`, and its current commit. Confirm
the origin is this repository and the checkout is clean; then fetch and inspect
the intended branch/commit. For a tracking branch, use `git pull --ff-only` only
after that review. Never reset/stash/discard a node's edits to get an update through.

Run the dry-run and linker again after updating. Existing symlinks see changes to
their source files immediately, even before rerunning the linker, so **updating
the checkout is deployment**. Use a separate checkout pinned to a reviewed commit
if you need to decouple deployment from ordinary dotfiles updates.

You can run those commands over SSH using a host alias maintained outside Git.
The checkout path is chosen per node; it need not match the workstation. Do not
copy your whole home or use `rsync --delete` against agent directories. This first
version intentionally does not auto-pull, select hosts, or restart remote agents.

Removing an entry from the allowlist does not remove an installed link. Review
and unlink that exact destination manually. A stale link continues to expose the
skill; rerunning the linker is not pruning. If interrupted, completed links remain
and rerunning safely resumes; no transactional rollback is claimed.

## Tool compatibility

Maple reads `~/.agents/AGENTS.md` and `~/.agents/skills` on the execution node.
Codex and OpenCode V2 also discover those **skills**, but their global instruction
files remain `~/.codex/AGENTS.md` and `~/.config/opencode/AGENTS.md`. Claude Code
documents `~/.claude/CLAUDE.md` and `~/.claude/skills`. This linker does not touch
those tool-specific paths. In particular, it does not replace the workstation's
existing OpenCode instructions or change duplicate-skill precedence.

Use a fresh task to verify the effective instructions and skill catalog after
deployment; do not assume live tasks reload resources. Ask the agent to name the
loaded instruction paths and available skills, then verify a harmless skill use.
This proposal has fixture coverage, not an authenticated remote Maple rehearsal.

## Knowledge: opt in, don't replicate by default

The workstation's OpenCode `knowledge` reference is not portable Maple config.
Leave the personal knowledge base off remote nodes until its content has been
reviewed for that machine and its operators. If useful, separately deploy a
read-only curated checkout and name its actual path in `node.md`. Do not claim
read-only prose restricts OS writes: enforce that with filesystem permissions or
the node's execution policy. Do not point at a nonexistent workstation path.

Keep shared engineering rules in skills and repo contracts in repo instructions.
Knowledge notes should explain decisions, not duplicate those contracts. Neither
these links nor the node file set sandbox permissions or protect secrets from
an agent already allowed to read them.
