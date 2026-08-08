# AGENTS PLAYBOOK
## Mission Profile
- These dotfiles bootstrap macOS and Pop!_OS 24.04/COSMIC machines via `chezmoi`, so edits must stay idempotent and cross-platform aware.
- Treat every change as infrastructure code; prefer observing current behavior before rewriting defaults.
- Keep the Kestrel visual identity (terminal, shell, Ghostty, VSCodium, prompt) intact unless the user explicitly requests otherwise.
- Assume contributors launch commands from the repository root (run `pwd` if unsure) unless a section states otherwise.
- Goal: high-signal diffs agents can execute quickly without guesswork.
## Layout Cheat Sheet
- `.chezmoi.toml.tmpl` defines Go template prompts (`data.email`, `install_*` toggles) and switches git diffing to `difft`.
- `.chezmoiscripts/*` holds OS-gated provisioning scripts; prefixes `run_once` vs `run_onchange` indicate execution semantics.
- `.chezmoitemplates/` stores reusable Go templates (Brewfile, VSCodium settings, bitcoin.conf) that are imported from files ending in `.tmpl`.
- `dot_*` files mirror home-directory assets: shells, prompt, aliases, git config, vim, Ghostty, etc.
- `dot_config/` contains app configs (Ghostty, K9s, Lazygit, VSCodium, etc.) already arranged per XDG spec.
- `dot_local/bin` contains portable helper scripts such as the runtime-selecting clipboard command.
- `.github/workflows/deploy-install-script.yml` regenerates a `docs/install.sh` artifact for GitHub Pages whenever `install.sh` changes.
- `.gitignore` keeps generated secrets (e.g., `machine_export`, VSCodium caches) out of version control; match these patterns in new files.
- `.gitconfig.tmpl` enforces `pull.rebase=true`, `difft` diffs, `zdiff3` merges, and includes `.gitconfig_local` for overrides.
- `.cursor`/`.cursorrules` do not exist; `.github/copilot-instructions.md` is also absent as of this snapshot.
- `dot_config/opencode/skills/skill-creator/` ships the `SKILL.md` authoring guide plus helper scripts for packaging skills.
## Build + Lint + Test Commands
- **Dry-run dotfiles**: `chezmoi diff` previews template renders; add `--refresh-externals` when Git/Hushlogin templates change.
- **Apply changes**: `chezmoi apply` (or `chezmoi apply --verbose --use-git` while debugging template merges).
- **Doctor**: `chezmoi doctor` validates dependencies/path assumptions; run this before reporting provisioning bugs.
- **Single script lint**: render templates, then run `shellcheck install.sh <rendered-script>` to vet Bash.
- **Format JSON/JSONC**: use `jq --indent 4` where valid; this repo expects 4 spaces and a trailing newline.
- **Reload Ghostty locally**: restart the terminal window after editing config once it exists; no remote control helper is available yet.
- **Check prompt**: `bash -n dot_prompt` plus `shellcheck dot_prompt` to keep the multi-line PS1 logic healthy.
- **Deploy workflow**: `gh workflow run deploy-install-script.yml` (needs `gh auth login`) to republish `install.sh` assets.
- **Git hygiene**: keep commit messages concise, action-oriented, and consistent with recent history.
- **Secret scan**: `git status --short --ignored` to ensure sensitive exports listed in `.gitignore` stay untracked before submitting diffs.
## Workflow Expectations
- Always edit the `.tmpl` source (not generated dotfiles) when Go templating is involved, then run `chezmoi apply --dry-run` to inspect the render.
- OS checks use `{{ if eq .chezmoi.os "darwin" }}` or `"linux"`; mirror that pattern for any new platform-dependent blocks.
- Use `run_once_*` scripts for bootstrap operations (e.g., installing extensions) and `run_onchange_*` for tasks tied to tracked files.
- Keep provisioning commands idempotent (`apt-get install --yes`, `brew bundle --file ...`, and version-aware upstream installers).
- Store long-lived secrets or host-specific overrides in `.gitconfig_local`, `.config/bash/.variables`, or other ignored files; never bake them into templates.
- When touching Git settings remember diffs run through `difft` (Rust-based), so avoid adding features incompatible with that workflow.
- Document new binaries inside Brewfile templates (macOS) or `.chezmoiscripts/linux/*` (Pop!_OS) instead of ad-hoc commands elsewhere.
- Keep Kestrel color constants synchronized across shell and application themes; use the canonical palette in `~/projects/github.com/w3irdrobot/kestreltheme/docs/kestrel-theme-design-system.html` when adding integrations.
- Respect the repo’s 100-column editing preference (see VSCodium template) for JSON, YAML, and CSS modifications.
- Use `chezmoi cd` to enter the managed worktree if you need to inspect rendered files relative to `$HOME` paths.
## Shell & Script Style
- Target Bash 5+; every tracked script begins with `#!/bin/bash` or `#!/usr/bin/env bash` plus `set -euo pipefail` when mutations happen.
- Export helper functions (prompt, gshell, homebrew installers) with `local` variables, double-quoted expansions, and short guard clauses.
- Prefer POSIX-compatible constructs in templates because they may run on busybox during bootstrap.
- Keep logs human-friendly: use the `log_info/log_success/log_error` helpers in `install.sh` and color-coded `printf` sequences instead of echo chains.
- Add `# shellcheck shell=bash` pragmas and `# shellcheck source=...` annotations like in `dot_bashrc.tmpl` when sourcing dynamic paths.
- For remote artifacts, pin versions, require TLS, verify upstream checksums or signatures, and clean temporary files.
- Keep loops small; prefer multi-line package installs (grouped by category) with line continuations and alignment exactly as seen in the Linux package script.
- Guard optional sections with template booleans (e.g., `.install_nvm`, `.install_kubernetes_tools`) so headless machines can skip them cleanly.
- When writing new helper functions (see `dot_functions.tmpl`), document behavior with comments and ensure `set -o pipefail` is applied before pipelines.
- Use `trap` for cleanup (temp dirs, background daemons) as showcased in the `gshell` helper.
## Template & Config Style
- Go template helpers live in `.chezmoitemplates`; expose reusable snippets with `{{- template "name" . -}}` and keep logic-free data files (Brewfile, VSCodium JSON).
- Always close template conditionals with `{{ end -}}` to avoid stray whitespace that might break INI or YAML consumers.
- JSON/JSONC files (VSCodium and OpenCode TUI) use double quotes, 4-space indent, and a trailing newline.
- YAML/Git config entries align with 2-space indent per level; follow `dot_config/lazygit/config.yml` for hex color quoting.
- CSS palettes stay centralized through `@define-color` tokens; new selectors should reference `@background`, `@foreground`, etc., rather than raw hex codes.
- Lazygit custom commands live under `customCommands`; bind new hotkeys with the same uppercase single-letter notation and provide `loadingText` copy.
- VSCodium settings and keybindings are templated via `{{ template "vscodium-settings.json" . }}` and `vscodium-keybindings.json`—extend templates first, then reference them through `.tmpl` wrappers.
## Desktop Stack Specifics
- COSMIC owns login, displays, power, notifications, portals, wallpaper, locking, and session startup; do not override those policies without an explicit requirement.
- Terminal font stack is JetBrainsMono Nerd Font; if you modify fonts, update both Ghostty (once configured) and the VSCodium `editor.fontFamily` array to prevent mismatched glyphs.
- Prompt (`dot_prompt`) shows Git, AWS, GCloud, and Kubernetes info; keep new environment indicators optional and behind quick exit checks to avoid blocking the shell.
- K9s and Lazygit share the Kestrel palette; use the canonical Kestrel design-system values when theming other CLI tools.
- The `clip` alias uses `pbcopy` on macOS and `wl-copy` on Pop!_OS/COSMIC.
- Opencode `tui.json` selects the managed Kestrel theme under `dot_config/opencode/themes/`.
- Wallpapers and branding assets reside under `dot_local/share/wallpapers`; reference them with `${HOME}` paths so symlinks survive `chezmoi apply`.
## Tooling & Dependencies
- macOS installs rely on Homebrew Bundle (`brew bundle --file=dot_config/brewfile/Brewfile`); ensure new taps/casks go through `.chezmoitemplates/Brewfile`.
- Pop!_OS support is intentionally limited to version 24.04 on x86_64; reject other Linux targets before provisioning.
- Prefer Noble archive packages, scoped official vendor repositories, then pinned and verified upstream artifacts.
- Do not install global workstation tools through npm, pnpm, Yarn, or Bun.
- Node tooling enters through `nvm` only when `.install_nvm` is true; respect that flag before invoking npm or corepack.
- Docker, Kubernetes, and optional vendor applications are installed through scoped official repositories.
- `just`, `hugo`, and `gh` are part of the baseline CLI stack; feel free to script against them without additional checks.
- `difft` must stay installed because `.gitconfig` calls it; if you add languages requiring other diff drivers, ensure `difft` remains the default.
- Keep `fzf`, `zoxide`, `bat`, and `eza` usage consistent with the alias definitions in `dot_aliases.tmpl`.
- Prompt helpers assume `git`, `kubectl`, and `gcloud` exist; guard new commands the same way (short-circuit when binaries are missing).
- `gshell` depends on `gcloud`, `fzf`, and `gmktemp` (macOS) or `mktemp` (Linux); document those dependencies if you extend the helper.
## Documentation & Communication
- Reference this `CLAUDE.md` whenever clarifying expectations; link to relevant sections rather than restating them in comments.
- Keep commit messages action-oriented (present tense, why over what).
- Mention impacted OS or desktop stack in PR descriptions (e.g., "Pop COSMIC" or "darwin bash").
- Inline comments are rare; only add them for non-obvious logic (complex template conditionals, perf-sensitive shell loops).
- Cross-file changes should call out dependency order (e.g., "update `.chezmoitemplates/Brewfile` + `dot_config/brewfile/Brewfile.tmpl`").
- Prefer repository-relative file references when handing off work between agents.
- Document new commands or entrypoints either in this guide or in `README`-style comments inside the touched script.
- When editing GitHub workflows, summarize the trigger (`push to master` etc.) so reviewers understand blast radius.
- Capture manual validation steps inside commit notes or PR bodies so humans can finish the process.
- Agent replies should include verification instructions (tests run, commands pending) just like the developer directives demand.
## Troubleshooting Tips
- Pop provisioning issues: rerun the individual ordered script with verbose chezmoi output and inspect APT source/keyring errors first.
- Ghostty config changes require reopening windows; plan edits so you can restart terminals without disrupting running sessions.
- Prompt bugs: temporarily set `PS1` to a static string, then source `dot_prompt` with `set -x` to trace functions.
- `chezmoi apply` stuck? run `chezmoi -v2 apply --debug` and check `~/.local/share/chezmoi/.chezmoilog` for template errors.
- Provisioning failures: rerun a single script with `chezmoi apply --include-scripts --verbose --exact=.chezmoiscripts/linux/<name>` to isolate.
- Workflow deploy issues: use `gh run watch` after `gh workflow run deploy-install-script.yml` to ensure Pages artifacts finish publishing.
- Missing fonts/themes: the repo never bundles proprietary assets; document manual download links inside commit descriptions instead.
- Template rendering errors: `chezmoi cat --template=path/to/file` shows the fully rendered output without touching the filesystem.
## Data & Mocking Guidelines
- Template prompts rely on `chezmoi` data keys (`data.email`, `bitcoin_datadir`); provide safe defaults in tests but never commit personal info.
- When mocking installation commands, guard them with `command -v` checks like the existing scripts to avoid re-install loops during CI.
- `install.sh` expects to run via `curl | bash`; test modifications locally with `bash install.sh` and capture logs for regression notes.
- Custom API endpoints (weather, Mullvad, mempool) should be parameterized via environment variables or script flags before adding secrets.
- For COSMIC changes that cannot be exercised on macOS, mention the limitation and list the Pop VM checks still required.
## System & Secrets
- `.chezmoiignore` purposefully skips platform-specific configs; mention these exclusions in PR descriptions if you change them.
- The Bitcoin datadir prompt uses mounted volumes discovered via `df`; preserve that logic (lines 7-9 in `.chezmoi.toml.tmpl`) when editing prompts.
- Secrets such as `machine_export`, `dracula-pro`, or `become_pass` must never leave the ignore list; double-check before committing assets referencing them.
- Use `.gitconfig_local` for user-specific overrides, `.config/bash/.variables` for environment secrets, and `.config/bash/.aliases` for personal tweaks.
- When editing `.local/bin` scripts referenced in configs, ensure file paths remain `${HOME}`-relative.
- Keep domain references (`dotfiles.w3ird.tech`) accurate in install scripts and workflow outputs.
- Avoid macOS-only binaries inside Linux scripts (and vice versa); leverage template guards or separate files to keep surfaces clean.
- For DRMed fonts/themes, store download instructions, not binaries; `.gitignore` already blocks `dracula-pro` archives.
- Use `chezmoi secrets` or external vaults instead of embedding credential material.
## Verification Checklist
- Run `chezmoi diff` and `chezmoi apply --dry-run` after template edits to confirm renders.
- `shellcheck` every Bash file you touched (`shellcheck path/to/file`); fix or comment intentional quirks with `# shellcheck disable=SCXXXX`.
- Validate JSON/JSONC/YAML via `jq`, `yq`, or the consumer binary.
- On macOS, run `brew bundle --file=dot_config/brewfile/Brewfile --no-lock --verbose` to ensure new entries are typo-free.
- On Pop!_OS, verify APT package candidates and repository signatures before applying to the primary machine.
- Exercise Git helpers such as `git config user.name` after touching `dot_gitconfig.tmpl` or `dot_functions.tmpl` to catch regressions.
- For workflow edits, run `act -W .github/workflows/deploy-install-script.yml` or trigger `gh workflow run` to confirm Pages artifacts build.
- Exercise COSMIC and GUI integration in the Pop VM when desktop behavior changes.
- Re-run `.chezmoiscripts/*` snippets with `chezmoi apply --verbose --force --include-scripts` if you modified provisioning commands.
- Scan `git status` to ensure no ignored secrets slipped in before opening a PR.
## Cursor/Copilot Rules
- No Cursor `.cursorrules` or GitHub Copilot instruction files are present; follow this CLAUDE guide plus in-repo templates as the authoritative source.
## Final Notes
- Keep responses terse but specific, cite repository-relative file paths, and include verification steps in the handoff.
- When uncertain, prefer adding context to this playbook rather than guessing—agents downstream will thank you.
