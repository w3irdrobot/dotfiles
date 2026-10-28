---
name: create-project
description: Create and verify a new project using Alex's project-templates repository and cargo-generate, in a new directory or directly in an existing/current directory. Use when asked to create, scaffold, initialize, or start a project from personal templates, including Rust CLIs and workspaces. Resolve the project type from the prompt or ask; there is no default type. Do not use for cloning existing repositories or adding features to existing projects.
---

# Create a project

Use the versioned template for scaffolding and its recipes for verification.
Keep this skill focused on selecting inputs and coordinating those tools; the
template owns generated files, dependencies, and language conventions.

## Resolve the inputs

Extract these from the request and context. Ask only for missing or ambiguous
inputs, combining questions where useful:

- **Project type/template:** there is no default. Use an explicit type from the
  prompt, or ask which type the user wants, even if only one template exists.
  A request for a "Rust project" does not choose between a CLI, library, server,
  or workspace. A request for a "Rust CLI" selects `rust/cli`.
- **Project name:** use a kebab-case Rust package name for Rust templates. Resolve
  name normalization before generation so the destination check matches the
  directory cargo-generate will create.
- **Destination:** honor an explicit path. Otherwise read the execution node's
  documented checkout root and use `<root>/<remote-host>/<owner-or-namespace>/<repository>`.
  Ask if the root or host/namespace is unknown. Preserve nested namespaces and omit `.git`.
  The template repository's owner is not automatically the new project's owner.
- **Generation mode:** "here", "in the current directory", or an explicit request
  to scaffold into an existing directory selects in-place generation with
  `--init`. Treat that request as authorization to add scaffold files, not to
  overwrite existing files. Otherwise create a new project directory.
  In-place generation keeps the destination path independent of the package name.
- **Template options:** for `rust/cli` and `rust/workspace`, use `async=true` (Tokio) unless the user
  requests synchronous execution. This defaults an option, not the project type.
- **Template source:** use `git@github.com:w3irdrobot/project-templates.git`,
  branch `master`, unless the user supplies a source or revision/tag. Honor a
  requested revision/tag instead of the branch selector. Use a local template
  checkout only when requested, such as during template development.

Known supported templates are `rust/cli` and `rust/workspace`. For another type, check the current
template catalog: `cargo-generate.toml` and the README in the matching local
checkout, or in the source repository. New templates may have been added since
this skill was written. Read the selected template's inputs and verification
instructions. If the requested type has no template, explain that and ask how
the user wants to proceed; do not substitute the CLI or invent its scaffold.

## Check the destination and tools

1. Inspect the intended parent directory and destination before writing. Create
   missing parents only after checking the existing ancestor and resolved path.
   If the destination exists and in-place generation was requested, inspect its
   contents, including hidden files, and the selected template's output paths.
   Proceed when those paths do not conflict; an empty directory or one containing
   only `.git` is a normal destination, not a reason to ask again. Preserve
   unrelated files and Git metadata. For conflicting files, ask how to resolve
   those specific conflicts before generation. If a destination exists but the
   user did not request in-place generation, ask how to proceed rather than
   silently switching modes or choosing another name.
2. Check `cargo generate --version` (0.23 or newer), `just --version`, and the
   installed Rust toolchains/components. The Rust templates require stable Rust with
   Clippy and nightly with rustfmt. Follow the chosen template's requirements.
   If prerequisites are missing, report what is missing and the relevant setup
   commands; do not claim generation or verification succeeded.
3. Honor the active sandbox. On an access denial, use the sandbox diagnostic
   workflow before attempting remediation. A failed generation may leave files;
   inspect and report them rather than retrying into or deleting them blindly.

## Generate

For a new directory, run from the resolved parent using the current tool's working-directory option.
Substitute the actual project name and quote shell arguments as needed:

```bash
cargo generate \
  --git git@github.com:w3irdrobot/project-templates.git \
  --branch master \
  rust/cli \
  --name my-tool \
  --define async=true \
  --silent \
  --no-workspace
```

Use `async=false` for a synchronous CLI. Supply all selected template inputs
explicitly so the agent does not depend on interactive terminal prompts.
`--no-workspace` prevents generation from editing a parent Cargo workspace;
workspace integration is a separate, explicit user choice.

For **in-place generation**, run the same command with `--init` added, using the
existing destination itself as `workdir`. Do not generate a nested project and
move its files afterward. For example, from the current directory:

```bash
cargo generate \
  --git git@github.com:w3irdrobot/project-templates.git \
  --branch master \
  rust/workspace \
  --name my-tool \
  --define async=true \
  --silent \
  --init \
  --no-workspace
```

`--init` generates directly in the current directory without creating a subfolder
or initializing Git. Do not combine it with `--destination`; select the exact
directory through `workdir`. For a requested exact new path whose basename
differs from the package name, create that directory after checking its parent,
then use this same in-place mode.

For a requested local source, replace the Git source and branch options with
`--path /absolute/path/to/project-templates/rust/cli`, omitting the positional
`rust/cli` (or use the corresponding `rust/workspace` path).

Do not use `--overwrite`, `--force-git-init`, or automatic command approval to bypass a
generation problem. Inspect the error and preserve any existing user work.

## Verify and finish

In the generated directory:

1. Inspect the generated README, `justfile`, and Git status. Confirm generation
   produced the selected project at the requested path. Preserve a repository
   that already existed, including its branch, configuration, and remotes.
   In-place generation does not initialize Git: if the destination has no
   repository and is not inside another one, use
   `git init --initial-branch=master` there. If Git discovers a parent repository,
   retain it unless the user requested a separate repository; ask when unclear.
2. Check the new repository's branch with `git symbolic-ref --short HEAD`.
   If needed, rename this newly generated branch with `git branch -m master`.
   Do not rename branches in an existing repository.
3. Run `just` to confirm the available workflow, then `just fmt`, `just verify`,
   and `just build` for the Rust templates. Format the fresh scaffold before
   checking it because project-name expansion can change import ordering. In
   a directory containing existing Rust code, limit formatting to generated
   files or confirm that the project-wide recipe will not change unrelated work.
   Other templates use their documented checks.
   Preserve the generated `Cargo.lock`; it belongs in the application's eventual
   commit. If a check fails, investigate and report the actual failure. If it
   reveals a template defect, identify it rather than silently replacing the
   template's scaffold with custom code.
4. Report the absolute project path, chosen template/source, options, branch,
   and verification results. Mention any blocker and the next concrete step.
   Keep the report short.

Commit, push, and remote repository creation require the user's request. If
requested, follow the Git workflow separately, including identity/signing and
SSH remotes. The interactive `config_git` helper can be run by the user from
their normal shell; do not guess identity or signing choices.
