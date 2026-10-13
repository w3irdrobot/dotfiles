---
name: opentofu-conventions
description: Apply Alex's OpenTofu conventions when implementing, refactoring, reviewing, or troubleshooting infrastructure as code, including environment directories, file placement, reusable modules, remote state, locking, and plan/apply workflows. Use for substantive OpenTofu work and relevant Terraform/HCL work; respect the project's chosen CLI and compatibility. Do not migrate an existing Terraform project merely to apply these defaults.
---

# OpenTofu conventions

Read [references/conventions.md](references/conventions.md) before substantive
IaC work. It records personal defaults and agreed organization rules. Explicit
project instructions, state ownership, and established tooling take precedence.

## Apply the conventions

1. Read applicable instructions and inspect the relevant root/module, backend,
   provider requirements, lockfile, justfile, and CI. Establish the target
   environment and selected CLI before running commands.
2. Place new code in the existing file for the service or infrastructure
   responsibility. Keep permissions beside the resource they grant access to.
   Extract a small module when expected reuse gives it a purpose; use root files
   to compose capabilities. Follow the reference when the project is undecided.
3. Separate organization-only changes from changes to resource addresses, module
   boundaries, state locations, or cloud infrastructure. Moving blocks between
   files in one root does not require renaming resources or migrating state.
4. Use project recipes for formatting, linting, initialization, validation, and
   planning as permitted by the task and environment. Treat missing credentials
   or other blockers as missing checks, not evidence that the configuration works.
   Follow project-specific restrictions rather than importing restrictions from
   the reference repository into every project.
5. Review actual plan effects and apply the saved plan when applying is part of
   the requested task. Return concise changes, verification results, and remaining
   issues. Report plans as plans and deployed changes as deployed changes.

This skill guides IaC work; it does not itself scaffold projects or provision a
state bucket. Use a selected, available template through `create-project` when
scaffolding is requested. Do not assume an OpenTofu template exists.
