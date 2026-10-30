---
name: setup-execution-node
description: Coordinate end-to-end setup of a headless coding execution node by selecting and sequencing focused provisioning, runtime, Git, agent installation, and shared-config skills. Use when asked to set up a complete agent node or resume a multi-stage setup. Ask for missing important inputs and approve the selected plan first. Not for automatic VM destruction, migration, or an individual app-only install.
---

# Set up an execution node

Coordinate the focused skills; do not duplicate their installation procedures.
Read [the execution-node contract](../provision-execution-node/references/node-contract.md).
Loading this skill is not permission to provision a node or run every stage.

## Select scope and collect inputs once

1. Extract decisions already supplied in the conversation and node guidance.
   Establish whether this is a new node, setup on an existing node, or a resumed
   plan. Confirm the exact target and execution user; do not infer that a named
   existing VM should be replaced or destroyed.
2. Ask which stages, hosts (Maple/T3), and providers (Codex/Claude) are wanted.
   There is no default application bundle. An individual app-only request belongs
   to its own skill, not this full workflow. A setup request alone does not select
   provider authentication, live paid tests, or public exposure.
3. Load each selected child skill using the current harness's skill loader. If it
   is not discoverable, read its canonical `SKILL.md` via the relative links below.
   Stop if a required skill/reference is unavailable; do not invent its workflow.
   Collect the selected skills' required inputs into one resolved plan. Batch
   missing questions without asking again for clear answers already given.
4. For provisioning, get actual CPU/RAM/disk/swap sizes, provider/location/ID,
   storage and OS choices, Btrfs scope/layout, and private/admin access. For other
   stages collect runtime/cache limits, Git identity/signing, exact releases or
   release policy, app paths/services/access, provider-home sharing/isolation,
   and reviewed shared-config source/revision as applicable. Ask only about
   selected stages. Btrfs is the agreed new-filesystem default, not a disk layout
   or a sizing decision. “More RAM/disk” is not a numerical allocation.

## Present and approve the plan

Show the target, selected stages in order, resolved inputs, missing prerequisites,
expected privileged/network changes, and required user login/pairing actions.
Perform read-only inventory/capacity checks before presenting resource promises.
Get approval before mutation. Recommendations remain unselected until accepted.

The user can approve the selected plan end-to-end or choose one-stage-at-a-time
testing. In the latter mode, pause after every stage for permission to continue.
Never treat creation of these skills as approval to execute them. Destruction,
reformatting existing storage, migration, and unselected stages are outside the
plan; request separate exact-resource authorization if the user wants them.

## Execute the selected dependency order

| Stage | Focused skill | Dependency / boundary |
| --- | --- | --- |
| New infrastructure, if selected | [provision-execution-node](../provision-execution-node/SKILL.md) | Capacity and approved storage/access plan; skip for an existing node |
| Build tools and storage policy, if selected | [configure-node-runtime](../configure-node-runtime/SKILL.md) | Reachable node and approved execution user; no implicit tool bundle |
| Repository identity/access, if selected | [configure-node-git](../configure-node-git/SKILL.md) | Reachable node; user-controlled authentication/signing |
| Selected providers | [install-codex](../install-codex/SKILL.md), [install-claude-code](../install-claude-code/SKILL.md) | Approved release/home/auth policies; install only selected providers |
| Selected hosts | [install-maple-agent](../install-maple-agent/SKILL.md), [install-t3code](../install-t3code/SKILL.md) | Host installation can precede providers, but provider execution tests cannot |
| Shared instructions, if selected | [deploy-agent-config](../deploy-agent-config/SKILL.md) | Reviewed source revision and actual selected consumer homes |

Dependencies can already exist; inspect them rather than reinstalling them.
Missing prerequisites are questions or blockers, not authority to add stages.
Git hosting access is not needed just to install public release artifacts. Don't
require Maple for T3 or vice versa. Keep task worktrees and app state separate;
shared provider homes are a deliberate choice, not security isolation.

Follow each selected skill in the current session; this is not automatic
subagent delegation or a tool/function call graph. At each stage:

- Check current target state and conflicts, perform the approved work, then run
  that skill's acceptance checks. Return control here after its stage boundary.
- Record a concise checkpoint in the conversation: target/user, resolved inputs,
  exact versions/config revision, changes, verification evidence, unresolved user
  actions, and next stage. Never record credentials or pairing links. Write a
  persistent non-secret handoff only if requested, at an agreed location.
- Stop on failure, changed scope/capacity, or a prerequisite requiring a new
  decision. Do not roll back by deleting resources or retry destructively.
- If waiting for user authentication or pairing, say so and pause dependent
  checks. Report independent filesystem/service checks without calling the whole
  stage fully verified. Continue only within the approved continuation mode.

## Resume and finish

On resume, read the checkpoint, confirm the target and remaining scope, and
revalidate completed stages against current state before skipping them. Check
identity, ownership, versions, service state and recorded acceptance evidence;
don't trust a stale “done” label or replay installation blindly. Reapprove changed
choices and interruptions. Do not expand the original authorization on resume.

Finish with a per-stage status: verified, installed/configured but awaiting a named
check, blocked, or not selected. Separate static checks, healthy services, and
actual authenticated tool execution. Run final integration checks only for the
selected hosts/providers in approved disposable workspaces, including explicit
working directories and fresh-session shared/node instruction discovery. No
unrequested repositories, commits, pushes, timers, or additional apps.
