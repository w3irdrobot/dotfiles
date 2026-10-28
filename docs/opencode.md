# OpenCode workstation configuration

`stow/opencode/.config/opencode/` owns the workstation's tool configuration,
terminal preferences, and themes. Its instruction, skill, and agent paths link
to the canonical [shared agent configuration](agent-config.md).

The tracked MCP set is Exa, GitHub, and optional Proxmox; Linear was removed to
match the local setup. Exa and GitHub refer to `EXA_API_KEY` and `GITHUB_TOKEN`.
The local Maple provider uses `MAPLE_API_KEY` and includes the uncensored
DeepSeek V4.1 Flash model alongside the existing models. Configuration references
environment variables, never credential values.

## Optional Proxmox MCP

The tracked server preserves the local Docker command but is **disabled by
default**. It needs Docker, reviewed access to its daemon, a locally available
`proxmox-mcp:1.4.4` image, connectivity to the selected Proxmox endpoint, and an
appropriately scoped API token. Docker installation, image builds/downloads,
network access, Docker-group membership, and token provisioning are not managed
by this configuration. The image tag records the local setup; it is not a
verified registry source or immutable digest. Review/provide the image separately
before enabling the server. Docker's host network mode is retained from the local
setup and is not a network isolation boundary.

Supply these variables on the execution computer through your private credential
injection or machine-environment setup, not the public dotfiles checkout:

- `PROXMOX_HOST`: endpoint hostname, without a URL scheme.
- `PROXMOX_USER`: Proxmox account identity.
- `PROXMOX_TOKEN_NAME`: token name for that account.
- `PROXMOX_API_KEY`: token secret; mapped to the container's `PROXMOX_TOKEN_VALUE`.

The default port is `443` and TLS verification remains enabled. Optional
`PROXMOX_TIMEOUT`, `TOOL_ROUTING`, `ROUTER_TOP_K`, `PROXMOX_READ_ONLY`, and
`PROXMOX_DISABLE_RAW_API` values are forwarded from the process environment when
set. No read-only mode is imposed by the tracked config; enforce least privilege
in the token's Proxmox permissions and review the server's controls separately.

For managed Bash, machine environment overrides belong in
`~/.config/bash/variables.sh`, outside this checkout. Exported secrets may still
be inherited by AI processes; prefer narrowly scoped credential injection. Never
paste values into chat or print them for validation.

Enable Proxmox only in your reviewed local configuration. OpenCode reloads config
on save; `/reload` forces a reload. Check connection state with `opencode mcp list`
or `/mcps`. Configuration syntax checks do not prove authenticated access or tool
authorization. No live Proxmox actions are needed to validate these dotfiles.

### Workstation-only overrides

For projects under your home directory, `~/.opencode/opencode.jsonc` can hold a
non-secret machine override without editing the tracked global defaults. Keep the
Proxmox server disabled in Stow. In the private override, declare the **complete**
server definition with `disabled: false`, its local command, and environment map.
MCP servers replace earlier definitions by name; a fragment containing only
`disabled` and environment values is not a valid local server definition.

Keep authentication as an environment reference such as `{env:PROXMOX_API_KEY}`.
Do not copy resolved credentials into the override. This home-level configuration
does not apply to workspaces outside your home, and closer `.opencode` configs
can override it. OpenCode skips project discovery when the current location is
its global configuration directory, so verify this override from a repository,
not from `~/.config/opencode`. If a newly created configuration is not discovered
by an already loaded location, use `/reload`; do not restart the background service
just to apply settings.

## Keep local fixes in source control

Compare the live `~/.config/opencode` directory with the Stow source, including
symlink targets. Preserve machine-local values as environment references rather
than publishing hostnames, usernames, tokens, or service state. `service.json`
belongs to OpenCode's local runtime; never copy it into Stow.

The `nono-sandbox` plugin and skill are symlinks into nono's installed OpenCode
package. Their owner is the pinned nono package setup, not a second vendored copy
under `stow/opencode`. Do not copy them merely because they appear only in the
live directory. Configuration changes do not authorize changing sandbox grants.
