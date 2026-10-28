---
name: bash-conventions
description: Apply Alex's Bash conventions when implementing, refactoring, reviewing, or debugging shell scripts and sourced Bash helpers, including strict mode, DEBUG tracing, main/function organization, ShellCheck, and shfmt. Prefer Bash and Linux for new scripts; respect existing project targets and shell requirements. Do not migrate interactive functions to scripts when they must affect the caller's shell.
---

# Bash conventions

Read [references/conventions.md](references/conventions.md) before substantive
Bash work. It records personal defaults; project-specific instructions, existing
targets, and established tooling take precedence.

## Apply the conventions

1. Identify whether the code is an executable script, a sourced library/helper,
   or interactive shell configuration. Inspect its callers and project workflow
   before changing options, environment variables, or installation behavior.
2. For new standalone commands, prefer Linux-targeted Bash scripts available on
   PATH. Use strict mode and opt-in DEBUG tracing, with a thin main that calls
   focused functions. Retain functions where caller-shell effects require them.
3. Preserve arguments, exit statuses, and observable output. Use Bash arrays and
   quoted expansions for command construction; treat strict mode as a useful
   baseline rather than a substitute for explicit handling of important failures.
4. Use existing project scripts/recipes for syntax, ShellCheck, formatting, and
   relevant tests. ShellCheck is the linter and shfmt is the formatter; follow
   existing settings or formatter defaults. See the reference for commands and
   EditorConfig behavior.
5. Test meaningful behavior or regressions when needed, using representative
   arguments and failure paths. Do not add a test framework just for this skill
   or execute operational scripts merely to check their syntax. Report actual
   checks and any missing tools or environment blockers accurately.

Keep changes within the requested task. Moving existing shell functions into
scripts, altering PATH, and selecting a Bash minimum version are deliberate
project decisions, not automatic consequences of loading this skill.
