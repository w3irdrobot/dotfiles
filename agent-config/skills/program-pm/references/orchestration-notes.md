# Orchestration notes

Practical details for running slice teams. The roster and the tool notes
describe Alex's setup as of November 2026. Check what the current node and
orchestration tool actually offer before relying on any of it.

## Roster

Pick the implementer and reviewer at random; do not default to one provider.
They must come from different providers.

| Role | Models |
| --- | --- |
| Program PM | The strongest available model, one long-lived session |
| Slice manager | A cheap model, such as Claude Sonnet |
| Implementer and reviewer | Claude Opus, Codex Sol, `maple/inkling-2-small`, `maple/kimi-k3-1-pro` |
| Final reviewer | A model the slice team did not use |

Confirm on first use that a model can drive the tools the role needs.

## Security-sensitive review

Phrase the brief as defensive verification of our own code: "confirm this check
holds when X". A brief that reads as an attack request can end a provider
session outright and lose the round.

If a provider refuses anyway, switch reviewer instead of rewording. The fallback
that keeps a second provider in the loop is
`maple/deepseek-v4-1-flash-1017-uncensored`. It is a small model whose review
quality has not been measured, so pair it with a stronger reviewer on anything
that matters.

## Working with sub-agents

- **An agent that ends its turn does not come back on its own.** "I'll report
  when my runs finish" means it sits idle. Briefs say to run long jobs in the
  foreground, and the PM checks for idle agents whenever it is waiting on one.
- **A denial reason may not reach the agent.** Some providers show only
  "rejected by user". If a denied command should be redone differently, send
  that as a separate message.
- **Some providers prompt before every write outside their workspace.** A
  reviewer told to keep build output elsewhere can raise dozens of prompts, each
  waking the PM. Give it a git-ignored scratch directory inside its workspace,
  or have Alex set its permission mode before it starts. The PM cannot and
  should not raise a sub-agent's permissions itself.
- **Read a command before approving it.** Turn down a recursive delete written
  through a shell variable and ask for the full literal path.
- **Reports can describe work that has not happened yet.** Check cleanup and
  restore claims against the disk.

## Workspaces and worktrees

- Archiving a worktree-backed workspace can delete the worktree. Confirm
  everything is pushed and repoint references before archiving.
- A workspace pointed at a checkout that another tool manages may be registered
  as a worktree workspace. Tear those down through the tool that owns them.
- After pushing several branches at once, list the CI runs and start any that
  did not trigger.

## Disk and scratch

- Leave `TMPDIR` alone. Moving it to fix a full temp directory broke tests that
  build throwaway projects there, because the tool under test read instruction
  files from the new parent directories.
- Put only large build output on real disk, and never put test scratch inside a
  workspace or repository.
- Each development-shell invocation can leave a directory in the temp
  directory. Prefer one long-lived shell, and have every agent delete its own
  scratch when it finishes. The manager checks that it did.
- Respect the node's limit on concurrent heavy builds across all teams.
