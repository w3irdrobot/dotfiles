# This execution node

Copy this file to `~/.config/agent-config/node.md` on the execution computer and
replace the examples with real, verified values. Keep it non-secret and outside
the dotfiles checkout. This file is guidance, not executable configuration.

## Paths and tools

- Checkout root: `/srv/work/repos` (example only; replace before use).
- Reuse existing checkout paths. New repositories go under
  `<checkout-root>/<remote-host>/<owner-or-namespace>/<repository>`.
- Use project-owned development environments. Do not assume Fedora, Nix, a
  graphical session, Bitwarden, or an interactive SSH agent is available.
- Follow repository worktree conventions. If none exist, use
  `<primary-checkout>/.worktrees/<task-name>` after checking it is ignored.
- Git identity and authentication are configured separately by the operator.
  Do not change them or copy credentials from another machine.

## Knowledge base

Disabled. Do not look for or clone my personal knowledge base on this node.

To opt in later, replace the paragraph above with the verified local path and
permission, for example: "Read-only reference at `/srv/reference/knowledge`.
Start with README.md, search relevant notes, and verify claims against current
source. Do not edit, commit, push, or sync it." Only place reviewed, appropriate
notes on the node; a path in instructions is not an access-control boundary.
