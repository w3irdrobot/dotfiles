### Create a worktree

```bash
# Interactive mode

git wt add

# From a remote branch
git wt add feature origin/feature

# Create a new branch
git wt add -b new-feature new-feature

# Detached, locked, or quiet modes
git wt add --detach hotfix HEAD~5
git wt add --lock -b wip wip-branch
git wt add --quiet -b feature feature
```

### Switch worktrees

```bash
cd "$(git wt switch)"
```

### Remove a worktree and local branch

```bash
git wt remove feature-branch
git wt remove --dry-run feature-branch
```

### Remove a worktree and local + remote branch

```bash
git wt remove feature-branch --delete-remote
```

### Sweep safe cleanup candidates

```bash
git wt remove --sweep

git wt remove --sweep --dry-run
```

### Inspect repository health

```bash
git wt doctor
```

### Show worktree status

```bash
git wt status
```

### List worktrees

```bash
git wt list
git wt list --json
git wt list --porcelain
```

### Update the default branch

```bash
git wt update # or: git wt u
```

## Commands

| Command             | Description                                                |
| ------------------- | ---------------------------------------------------------- |
| `clone <url>`       | Clone a repo with the bare worktree structure              |
| `migrate`           | Convert an existing repo to the bare worktree structure    |
| `add [options] ...` | Create a new worktree                                      |
| `remove` / `rm`     | Remove worktrees directly or by safe cleanup filters       |
| `doctor`            | Run repository diagnostics                                 |
| `status`            | Show a compact dashboard for linked worktrees              |
| `list`              | List worktrees with table, JSON, or passthrough Git output |
| `switch`            | Interactively select a worktree                            |
| `update` / `u`      | Fetch remotes and update the default branch                |

Native `git worktree` commands (`lock`, `unlock`, `move`, `prune`, `repair`)
are also supported as pass-through commands.
