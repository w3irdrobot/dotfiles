# AGENTS PLAYBOOK
## Mission Profile
- These dotfiles bootstrap macOS and Arch/Hyprland machines via `chezmoi`, so edits must stay idempotent and cross-platform aware.
- Treat every change as infrastructure code; prefer observing current behavior before rewriting defaults.
- Keep the Dracula-inspired visual identity (terminal, Waybar, Ghostty, VSCodium, prompt) intact unless the user explicitly requests otherwise.
- Assume contributors launch commands from the repository root (run `pwd` if unsure) unless a section states otherwise.
- Goal: high-signal diffs agents can execute quickly without guesswork.
## Layout Cheat Sheet
- `.chezmoi.toml.tmpl` defines Go template prompts (`data.email`, `install_*` toggles) and switches git diffing to `difft`.
- `.chezmoiscripts/*` holds OS-gated provisioning scripts; prefixes `run_once` vs `run_onchange` indicate execution semantics.
- `.chezmoitemplates/` stores reusable Go templates (Brewfile, VSCodium settings, bitcoin.conf) that are imported from files ending in `.tmpl`.
- `dot_*` files mirror home-directory assets: shells, prompt, aliases, git config, tmux, vim, Ghostty, etc.
- `dot_config/` contains app configs (Hyprland, Waybar, Ghostty, K9s, Lazygit, VSCodium, etc.) already arranged per XDG spec.
- `dot_local/bin` is for helper scripts referenced by Hyprland autostart commands (e.g., `wofi-launch`).
- `system/` holds raw systemd or seatd assets (e.g., autologin units) intentionally ignored by `.chezmoiignore` and applied manually.
- `.github/workflows/deploy-install-script.yml` regenerates a `docs/install.sh` artifact for GitHub Pages whenever `install.sh` changes.
- `.gitignore` keeps generated secrets (e.g., `machine_export`, VSCodium caches) out of version control; match these patterns in new files.
- `.gitconfig.tmpl` enforces `pull.rebase=true`, `difft` diffs, `zdiff3` merges, and includes `.gitconfig_local` for overrides.
- `.cursor`/`.cursorrules` do not exist; `.github/copilot-instructions.md` is also absent as of this snapshot.
- `dot_config/opencode/skills/skill-creator/` ships the `SKILL.md` authoring guide plus helper scripts for packaging skills.
## Build + Lint + Test Commands
- **Dry-run dotfiles**: `chezmoi diff` previews template renders; add `--refresh-externals` when Git/Hushlogin templates change.
- **Apply changes**: `chezmoi apply` (or `chezmoi apply --verbose --use-git` while debugging template merges).
- **Doctor**: `chezmoi doctor` validates dependencies/path assumptions; run this before reporting provisioning bugs.
- **Single script lint**: `shellcheck install.sh` or `shellcheck .chezmoiscripts/linux/run_onchange_before_20-install-packages.sh.tmpl` (render first if template logic matters) to vet Bash.
- **Format JSON/JSONC**: `jq --indent 4 . dot_config/waybar/config.jsonc` (or `yq` for YAML); this repo expects 4 spaces and trailing newline.
- **Test Hyprland config**: `hyprctl --config ~/.config/hypr/hyprland.conf reload` on a Hypr session, or `hyprctl keyword source /path/to/hyprland.conf` for staged files.
- **Validate Waybar**: `waybar -l trace -c dot_config/waybar/config.jsonc -s dot_config/waybar/style.css` to catch JSONC mistakes before reloading the session.
- **Reload Ghostty locally**: restart the terminal window after editing config once it exists; no remote control helper is available yet.
- **Check prompt**: `bash -n dot_prompt` plus `shellcheck dot_prompt` to keep the multi-line PS1 logic healthy.
- **Deploy workflow**: `gh workflow run deploy-install-script.yml` (needs `gh auth login`) to republish `install.sh` assets.
- **Git hygiene**: prefer `git cz` (Commitizen) for curated messages; `lazygit` already binds `C` to it per `dot_config/lazygit/config.yml`.
- **Secret scan**: `git status --short --ignored` to ensure sensitive exports listed in `.gitignore` stay untracked before submitting diffs.
## Workflow Expectations
- Always edit the `.tmpl` source (not generated dotfiles) when Go templating is involved, then run `chezmoi apply --dry-run` to inspect the render.
- OS checks use `{{ if eq .chezmoi.os "darwin" }}` or `"linux"`; mirror that pattern for any new platform-dependent blocks.
- Use `run_once_*` scripts for bootstrap operations (e.g., installing extensions) and `run_onchange_*` for tasks tied to tracked files.
- Keep provisioning commands idempotent (`yay -Syu --needed --noconfirm`, `brew bundle --file ...`, `cargo binstall -y ...`).
- Store long-lived secrets or host-specific overrides in `.gitconfig_local`, `.config/bash/.variables`, or other ignored files; never bake them into templates.
- When touching Git settings remember diffs run through `difft` (Rust-based), so avoid adding features incompatible with that workflow.
- Document new binaries inside Brewfile templates (macOS) or `.chezmoiscripts/linux/*` (Arch) instead of ad-hoc commands elsewhere.
- Keep Dracula color constants synchronized across CSS, Hyprland, Ghostty, and Waybar; reuse `dot_config/waybar/colors.css` values when adding modules.
- Respect the repo’s 100-column editing preference (see VSCodium template) for JSON, YAML, and CSS modifications.
- Use `chezmoi cd` to enter the managed worktree if you need to inspect rendered files relative to `$HOME` paths.
## Shell & Script Style
- Target Bash 5+; every tracked script begins with `#!/bin/bash` or `#!/usr/bin/env bash` plus `set -euo pipefail` when mutations happen.
- Export helper functions (prompt, gshell, homebrew installers) with `local` variables, double-quoted expansions, and short guard clauses.
- Prefer POSIX-compatible constructs in templates because they may run on busybox during bootstrap.
- Keep logs human-friendly: use the `log_info/log_success/log_error` helpers in `install.sh` and color-coded `printf` sequences instead of echo chains.
- Add `# shellcheck shell=bash` pragmas and `# shellcheck source=...` annotations like in `dot_bashrc.tmpl` when sourcing dynamic paths.
- When curling remote installers (`rustup`, `nvm`, `gcloud`), pin protocols (`--proto '=https' --tlsv1.2`) and clean temp artifacts afterward, matching `.chezmoiscripts/linux/run_onchange_before_20-install-packages.sh.tmpl`.
- Keep loops small; prefer multi-line package installs (grouped by category) with line continuations and alignment exactly as seen in the Linux package script.
- Guard optional sections with template booleans (e.g., `.install_nvm`, `.install_kubernetes_tools`) so headless machines can skip them cleanly.
- When writing new helper functions (see `dot_functions.tmpl`), document behavior with comments and ensure `set -o pipefail` is applied before pipelines.
- Use `trap` for cleanup (temp dirs, background daemons) as showcased in the `gshell` helper.
## Template & Config Style
- Go template helpers live in `.chezmoitemplates`; expose reusable snippets with `{{- template "name" . -}}` and keep logic-free data files (Brewfile, VSCodium JSON).
- Always close template conditionals with `{{ end -}}` to avoid stray whitespace that might break INI or YAML consumers.
- JSON/JSONC files (Waybar, VSCodium, Opencode TUI) use double quotes, 4-space indent, trailing newline, and inline comments only where the format supports them (Waybar uses JSONC, so `//` comments are fine).
- YAML/Git config entries align with 2-space indent per level; follow `dot_config/lazygit/config.yml` for hex color quoting.
- CSS keeps `Dracula` palette centralized through `@define-color` tokens; new selectors should reference `@background`, `@foreground`, etc., rather than raw hex codes.
- Hyprland configs favor block sections (`monitorv2 { ... }`) with lowercase keywords and inline comments referencing the official docs; keep autostart commands grouped by function.
- tmux settings stay minimalistic: prefer descriptive comments and align binds (`bind-key -T copy-mode-vi ...`) with the style already present.
- Lazygit custom commands live under `customCommands`; bind new hotkeys with the same uppercase single-letter notation and provide `loadingText` copy.
- VSCodium settings and keybindings are templated via `{{ template "vscodium-settings.json" . }}` and `vscodium-keybindings.json`—extend templates first, then reference them through `.tmpl` wrappers.
## Desktop Stack Specifics
- Hyprland variables ($terminal, $menu, $browser) feed Waybar modules and autostart entries; update them in `hyprland.conf` and propagate to Waybar if the binary name changes.
- Special workspaces `terminal` and `notes` are triggered via `bind = $mainMod, S/N`; do not repurpose these names without updating binds and docs.
- Clamshell behavior uses the Hyprland clamshell helper under `${HOME}/.local/bin`; ensure any edits preserve the lid switch binds at lines 258-259.
- Waybar custom modules execute curl/jq pipelines; test them in isolation and use `interval` values tuned for rate limits (weather: 1200s, block height: 420s).
- CSS animations like `@keyframes blink` must remain lightweight to avoid GPU spikes on laptops; add new animations sparingly.
- Terminal font stack is JetBrainsMono Nerd Font; if you modify fonts, update both Ghostty (once configured) and the VSCodium `editor.fontFamily` array to prevent mismatched glyphs.
- Prompt (`dot_prompt`) shows Git, AWS, GCloud, and Kubernetes info; keep new environment indicators optional and behind quick exit checks to avoid blocking the shell.
- K9s and Lazygit share the Dracula palette; use the same hex codes defined in `waybar/colors.css` when theming other CLI tools to maintain consistency.
- tmux copy bindings rely on `xclip`; if adding macOS-specific overrides, gate them with template conditionals so Linux clipboard commands stay intact.
- Opencode `tui.json` fixes the Dracula theme; if the CLI adds theme selection later, expose it as a template toggle consistent with other `install_*` prompts.
- Hypridle, Hyprlock, Hyprpaper, and Hyprsunset configs live beside `hyprland.conf`; keep power-management bindings synchronized (idle inhibitors rely on these files).
- Waybar module names follow `custom/<id>` conventions mirrored in `style.css`; keep class names synced when adding CSS selectors.
- Wallpapers and branding assets reside under `dot_local/share/wallpapers`; reference them with `${HOME}` paths so symlinks survive `chezmoi apply`.
- Wofi launchers are expected under `.local/bin`; update Hyprland exec lines and `.chezmoiscripts` together if you rename binaries.
- Hyprland monitor blocks use `monitorv2`; duplicate that structure for new displays instead of mixing legacy syntax.
## Tooling & Dependencies
- macOS installs rely on Homebrew Bundle (`brew bundle --file=dot_config/brewfile/Brewfile`); ensure new taps/casks go through `.chezmoitemplates/Brewfile`.
- Arch/Hypr setups expect `yay`; keep aur helpers consistent and avoid mixing in `paru` or direct `pacman` calls unless necessary for base packages.
- Rust tooling uses `cargo binstall` for speed—when adding CLIs, prefer `cargo binstall -y crate` to keep bootstrap time reasonable.
- Node tooling enters through `nvm` only when `.install_nvm` is true; respect that flag before invoking npm or corepack.
- Docker, Kubernetes, Mullvad, and Tor packages already install via `yay`; reference those names when writing docs so users know prerequisites.
- `mprocs`, `just`, `hugo`, and `gh` are part of the baseline CLI stack; feel free to script against them without additional checks.
- `difft` must stay installed because `.gitconfig` calls it; if you add languages requiring other diff drivers, ensure `difft` remains the default.
- Keep `fzf`, `zoxide`, `bat`, and `eza` usage consistent with the alias definitions in `dot_aliases.tmpl`.
- Prompt helpers assume `git`, `kubectl`, and `gcloud` exist; guard new commands the same way (short-circuit when binaries are missing).
- `gshell` depends on `gcloud`, `fzf`, and `gmktemp` (macOS) or `mktemp` (Linux); document those dependencies if you extend the helper.
## Documentation & Communication
- Reference this `CLAUDE.md` whenever clarifying expectations; link to relevant sections rather than restating them in comments.
- Keep commit messages action-oriented (present tense, why over what); when possible, run `git cz` so commitizen enforces format.
- Mention impacted OS or desktop stack in PR descriptions (e.g., "linux hypr" or "darwin bash").
- Inline comments are rare; only add them for non-obvious logic (complex template conditionals, perf-sensitive shell loops).
- Cross-file changes should call out dependency order (e.g., "update `.chezmoitemplates/Brewfile` + `dot_config/brewfile/Brewfile.tmpl`").
- Prefer referencing file paths with repository-relative notation (`dot_config/waybar/style.css:42`) when handing off work between agents.
- Document new commands or entrypoints either in this guide or in `README`-style comments inside the touched script.
- When editing GitHub workflows, summarize the trigger (`push to master` etc.) so reviewers understand blast radius.
- Capture manual steps (e.g., applying files under `system/`) inside commit notes or PR bodies so humans can finish the process.
- Agent replies should include verification instructions (tests run, commands pending) just like the developer directives demand.
## Troubleshooting Tips
- Hyprland issues: run `hyprctl logs` plus `hyprctl reload` to observe failures; syntax errors show line numbers, so keep configs small.
- Waybar glitches: launch with `WAYBAR_OUTPUT=stderr WAYBAR_HEIGHT=40 waybar -l trace ...` to capture logs before reloading Hyprland.
- Ghostty config changes require reopening windows; plan edits so you can restart terminals without disrupting running sessions.
- Prompt bugs: temporarily set `PS1` to a static string, then source `dot_prompt` with `set -x` to trace functions.
- `chezmoi apply` stuck? run `chezmoi -v2 apply --debug` and check `~/.local/share/chezmoi/.chezmoilog` for template errors.
- Provisioning failures: rerun a single script with `chezmoi apply --include-scripts --verbose --exact=.chezmoiscripts/linux/<name>` to isolate.
- `yay` downtime: fall back to `sudo pacman -S` only for core packages, then restore `yay` usage when possible.
- Workflow deploy issues: use `gh run watch` after `gh workflow run deploy-install-script.yml` to ensure Pages artifacts finish publishing.
- Missing fonts/themes: the repo never bundles proprietary assets; document manual download links inside commit descriptions instead.
- Template rendering errors: `chezmoi cat --template=path/to/file` shows the fully rendered output without touching the filesystem.
## Data & Mocking Guidelines
- Template prompts rely on `chezmoi` data keys (`data.email`, `bitcoin_datadir`); provide safe defaults in tests but never commit personal info.
- When mocking installation commands, guard them with `command -v` checks like the existing scripts to avoid re-install loops during CI.
- `install.sh` expects to run via `curl | bash`; test modifications locally with `bash install.sh` and capture logs for regression notes.
- Custom API endpoints (weather, Mullvad, mempool) should be parameterized via environment variables or script flags before adding secrets.
- For previewing CSS/JSON changes without hardware (e.g., on macOS editing Hyprland files), mention the limitation and list the commands you could not run.
- Avoid fabricating blockchain heights or network info when testing Waybar modules; stub command output via `printf 'value'` piped into modules instead.
## System & Secrets
- `.chezmoiignore` purposefully skips `system/` and certain configs depending on OS; mention these exclusions in PR descriptions if you change them.
- The Bitcoin datadir prompt uses mounted volumes discovered via `df`; preserve that logic (lines 7-9 in `.chezmoi.toml.tmpl`) when editing prompts.
- Secrets such as `machine_export`, `dracula-pro`, or `become_pass` must never leave the ignore list; double-check before committing assets referencing them.
- Use `.gitconfig_local` for user-specific overrides, `.config/bash/.variables` for environment secrets, and `.config/bash/.aliases` for personal tweaks.
- When editing `.local/bin` scripts referenced in configs, ensure file paths remain `${HOME}`-relative (Hyprland autostart uses explicit absolute paths).
- Any new systemd unit templates should live under `system/linux` or `system/darwin` (if added) and carry clear comments on manual application steps.
- Keep domain references (`dotfiles.w3ird.tech`) accurate in install scripts and workflow outputs.
- Avoid macOS-only binaries inside Linux scripts (and vice versa); leverage template guards or separate files to keep surfaces clean.
- For DRMed fonts/themes, store download instructions, not binaries; `.gitignore` already blocks `dracula-pro` archives.
- Use `chezmoi secrets` or external vaults instead of embedding credential material.
## Verification Checklist
- Run `chezmoi diff` and `chezmoi apply --dry-run` after template edits to confirm renders.
- `shellcheck` every Bash file you touched (`shellcheck path/to/file`); fix or comment intentional quirks with `# shellcheck disable=SCXXXX`.
- Validate JSON/JSONC/YAML via `jq`, `yq`, or the consumer binary (`waybar -l trace`, `hyprctl reload`).
- On macOS, run `brew bundle --file=dot_config/brewfile/Brewfile --no-lock --verbose` to ensure new entries are typo-free.
- On Arch, dry-run `yay -S --print` with the package list to ensure availability before committing scripts.
- Exercise Git helpers (`git config user.name`, `git cz`) after touching `dot_gitconfig.tmpl` or `dot_functions.tmpl` to catch regressions.
- For workflow edits, run `act -W .github/workflows/deploy-install-script.yml` or trigger `gh workflow run` to confirm Pages artifacts build.
- Reload Waybar/Hyprland locally if you adjusted visuals; share screenshots when practical to document UI intent.
- Re-run `.chezmoiscripts/*` snippets with `chezmoi apply --verbose --force --include-scripts` if you modified provisioning commands.
- Scan `git status` to ensure no ignored secrets slipped in before opening a PR.
## Cursor/Copilot Rules
- No Cursor `.cursorrules` or GitHub Copilot instruction files are present; follow this CLAUDE guide plus in-repo templates as the authoritative source.
## Final Notes
- Keep responses terse but specific, cite file paths like `dot_config/waybar/style.css`, and include verification steps in the handoff.
- When uncertain, prefer adding context to this playbook rather than guessing—agents downstream will thank you.
