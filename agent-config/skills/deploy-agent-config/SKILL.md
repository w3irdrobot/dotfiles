---
name: deploy-agent-config
description: Deploy reviewed shared agent instructions and skills onto an existing execution node using the dotfiles link helper, with explicit tool selection and non-secret node guidance. Use for Maple, Codex, Claude, or OpenCode configuration deployment, not application installation, provider authentication, or workstation provisioning.
---

# Deploy shared agent configuration

Read [the execution-node contract](../provision-execution-node/references/node-contract.md).
Use the repository's existing workflow, not a new deployment implementation.

## Resolve inputs

Confirm target/user/home, selected tools, canonical dotfiles repository, stable
checkout path, and reviewed revision. Ask for missing choices rather than selecting
all tools or a moving branch. For T3 select its actual Codex/Claude providers;
there is no `t3` linker adapter. Confirm checkout/worktree conventions and knowledge
access for node guidance. Knowledge remains disabled unless explicitly enabled
with a verified local path and permitted use; never copy a workstation knowledge
checkout or its access policy.

## Deploy and verify

1. Read `agent-config/SETUP.md` and `docs/agent-config.md` from the selected dotfiles
   checkout. They own link destinations and conflict handling. Inspect origin,
   revision, status and current links before fetching or switching revisions;
   changing linked source is itself deployment. Do not discard local changes.
2. Check Python, Git, selected apps and actual provider-home variables. The helper
   refuses unsupported custom homes; report that constraint instead of linking
   configuration into an unverified directory. Never run `install.sh` or
   `bin/dotfiles install` to prepare a headless execution node.
3. As the execution user, run `python3 scripts/link-agent-config.py --tools <selection> --dry-run`.
   Reconcile any conflicts with the user. If authorized and clean, rerun without
   `--dry-run`. Do not force links, prune unrelated skills, or deploy credentials.
4. Create or reconcile `~/.config/agent-config/node.md` using
   `agent-config/examples/agent-node.md` and actual approved facts: execution user,
   checkout root, config revision, worktree conventions, runtime/resource limits,
   credential boundaries and knowledge policy. Do not copy historical VM values.
5. Verify all selected links and repeat the preview for idempotence. In a fresh
   session of each selected app, verify discovery and that shared instructions
   cause node guidance to be read without explicitly prompting it to read that
   file. Asking about execution-environment conventions is a useful check.
   For T3 verify its actual provider process uses the intended home and config.

Report path/revision, selected consumers, conflicts, and filesystem versus runtime
checks separately. Keep the source checkout; live links depend on it. New skills
are discovered by the helper from direct child skill directories, but new home
links require rerunning deployment. Do not deploy onto another node unless asked.
