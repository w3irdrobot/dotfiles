# Set up this agent configuration on an execution node

Use this workflow when asked to install shared instructions and skills on a node.
It is configuration deployment, not workstation provisioning or agent installation.

1. Confirm which OS user/home executes tasks and which tools to configure:
   `maple`, `codex`, `claude`, and/or `opencode`. Ask if unclear. Check Git,
   Python 3, and the selected applications; report missing prerequisites rather
   than installing them without approval.
2. Reuse a matching checkout of `git@github.com:w3irdrobot/dotfiles.git`. If none
   exists, agree on a stable path and clone it there. Before updating an existing
   checkout, verify its origin, status, and revision. Preserve local changes;
   never reset, stash, or overwrite to get deployment through. Use the requested
   reviewed revision; do not deploy an arbitrary branch or unreviewed update.
3. Read `docs/agent-config.md` from that checkout. Do **not** run `install.sh` or
   `bin/dotfiles install` on a remote node. Those provision a Fedora workstation.
4. From the checkout, run the selected tools' preview, for example:

   ```bash
   python3 scripts/link-agent-config.py --tools maple,codex --dry-run
   ```

5. Report conflicts and reconcile them with the user. Do not delete or replace
   existing instructions, skills, or links automatically. If the preview succeeds
   and deployment was requested, repeat without `--dry-run`.
6. If node-specific paths or knowledge access are wanted, create non-secret
   `~/.config/agent-config/node.md` based on `examples/agent-node.md`, only after
   confirming the actual values. Knowledge stays off otherwise. Do not copy
   credentials, personal SSH/Git config, or the workstation knowledge checkout.
7. Verify links and skill discovery in a fresh session of each selected tool.
   Check that the shared instructions and any node guidance are actually read.
   For T3 Code, verify its underlying Codex/Claude process uses this same home;
   do not assume isolated runtimes inherit it.
8. Report the checkout path/revision, selected tools, changed links, conflicts,
   and checks actually performed. Do not claim a filesystem check proves runtime
   loading. Keep the checkout: installed links point into it.

For later updates, repeat the review and preview. Updating linked source files
changes the live configuration immediately. No scheduled pulls or automatic
pruning are configured.
