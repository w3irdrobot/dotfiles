---
name: provision-execution-node
description: Plan and provision a fresh headless coding execution node on Proxmox, another hypervisor, or a cloud provider. Use for creating an agent VM or server, including resource sizing, Btrfs storage, execution user, and private access. Does not install agent applications, destroy existing nodes, or migrate their state.
---

# Provision an execution node

Read [the shared execution-node contract](references/node-contract.md). Apply it
throughout this skill; it also governs the independently runnable setup skills.
This is orchestration guidance, not a tested cross-provider provisioner.

## Resolve inputs before provisioning

Ask for missing consequential choices together. Do not reuse an old node's values:

- Provider/hypervisor, account/project or cluster/node, region where applicable,
  and new node name/identifier. Discover available IDs rather than guessing one.
- OS/release/image and CPU architecture; vCPU count, RAM, swap size or no swap.
- Disk sizes, backing storage/pool, thin provisioning or reservations, and any
  separate data disks. Ask what “a lot more” means in actual GiB.
- Btrfs is the accepted filesystem default. Confirm its scope (root and/or data),
  subvolume/mount layout, encryption choice, and any snapshot/retention policy.
  Explain that EFI/boot partitions may require other filesystems. Do not silently
  accept an ext4 cloud root and call a Btrfs data disk a Btrfs root installation.
- Execution username, home and checkout root; administrative access method,
  authorized public keys, network/bridge/IP policy, and private access choice.
  Ask whether Tailscale and an exit node are wanted, and which exit node.

Existing context may answer these questions. Present the resolved plan and get
approval before resource creation, formatting, or network changes. No resource
sizes are implicit defaults. A request to create a replacement is not permission
to destroy the original or reuse its attached volumes.

## Check capacity and choose the installation method

1. Inspect live host/account inventory, allocations, storage reservations, and
   quotas. Separate physical free disk from thin-provisioned logical commitments;
   separate currently available RAM from assigned VM RAM. Leave measured host
   headroom and explain overcommit. Stop if the requested plan does not fit.
2. Verify the OS image and its published checksum/signature. Inspect the actual
   image partition/filesystem layout. Standard cloud images may not support a
   Btrfs root; propose a supported installer or image-building path instead of
   formatting an attached disk and hoping it boots. Do not install image-building
   or VM software on the operator's machine without approval.
3. For Proxmox, discover available tools and their schemas; inspect the selected
   node, pools, bridges, existing VM IDs, and image inventory. Build an explicit
   VM/disk/boot plan, avoid passthrough or unrelated devices, await each task, and
   check its exit status. Never delete an existing VM to free its ID or capacity.
   For another provider, use its supported workflow with equivalent checks.
4. If implementing IaC, load `opentofu-conventions` and use the project's reviewed
   plan/apply workflow. Do not create an IaC repository/backend without agreement.

## Configure only the approved baseline

- Install the selected OS onto the approved new disks with the resolved Btrfs
  layout. Keep snapshots, build caches, and application state deliberately placed;
  snapshots share the disk and are not backups. Compression, quotas, automatic
  snapshots, and cleanup schedules must be explicit choices, not hidden tuning.
- Create the normal execution user without unrestricted sudo. Keep administration
  separate. Place only approved public SSH keys on the node; never copy workstation
  private keys or forward an authentication agent as a provisioning shortcut.
- Establish approved private access before tightening access rules. Verify the
  new route while preserving administrative reachability. Tailscale enrollment is
  interactive or uses approved secret injection; do not print enrollment secrets.
  An exit node is optional and requires explicit selection and an egress check.
- Check Btrfs/swap compatibility before creating swap; use the OS-supported
  Btrfs swapfile procedure or approved separate swap. Do not create an ordinary
  copy-on-write swapfile or snapshot an active swap subvolume.

## Acceptance and handoff

Verify OS/architecture, assigned CPU/RAM/disks, `findmnt` filesystem/subvolume
layout, `btrfs filesystem usage`, swap, normal-user SSH and separate admin access.
Report actual usable capacity, including Btrfs data/metadata headroom. Test reboot
and reconnect only with approval. Record non-secret node facts outside Git.

Stop here. Run `configure-node-runtime`, `configure-node-git`, individual app
installation skills, and `deploy-agent-config` only when separately selected.
Report any pending reboot/network acceptance checks; do not claim completion from
VM creation alone.
