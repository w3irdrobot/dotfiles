# Alex's Bash conventions

Accepted personal defaults. Apply them where the project has not made a
different choice; avoid unrelated rewrites to make existing code match them.

## Language and target

- Write Bash-specific code, not POSIX sh by default. Bash is the user's chosen
  shell, and changing that would be a dedicated migration.
- Target Linux for new scripts. Bash arrays, [[ tests ]], process substitution,
  and normal Linux tools are available choices when useful. Respect explicit
  runtime/version requirements and existing cross-platform projects.
- Prefer `#!/usr/bin/env bash` for standalone scripts. Do not infer that a .sh
  extension means POSIX code; make the intended shell clear to tooling.
- No particular minimum Bash version has been selected globally. Check the
  project's runtime before using version-dependent features.

## Scripts and interactive functions

- Prefer standalone commands made available on PATH through the user's or
  project's existing installation method. Keep their source versioned where
  appropriate rather than growing an unstructured personal function collection.
- Keep functions when the operation must affect the current shell. Changing its
  working directory, exporting variables for subsequent commands, or managing
  shell-local state cannot be replaced by an ordinary child-process script.
  Helpers like `take` and `scratch` are examples where functions remain useful.
- Do not automatically migrate existing functions or change PATH. Confirm the
  intended invocation and caller-visible behavior as part of that task.

## Script setup and organization

Start standalone scripts with strict mode and opt-in command tracing:

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
    set -x
fi
```

- Use `DEBUG=1` to enable tracing; an unset variable or another value leaves it
  off. Do not turn tracing on unconditionally.
- Keep larger scripts organized as helpers above a thin `main`, followed by
  `main "$@"`. Main brings the steps together rather than holding every detail.
- Use local variables in functions where appropriate. Keep configuration and
  function responsibilities clear rather than relying on accidental globals.
- Sourced files and interactive functions should not impose `set -euo pipefail`
  or `set -x` on the caller. Place script-wide options in executable entry points;
  use a subshell if a helper intentionally needs isolated option/environment changes.

## Arguments, failures, and output

- Quote expansions and preserve argument boundaries, especially "$@". Use arrays
  to build optional command arguments rather than concatenating a command string
  or using eval. Parse simple options directly when sufficient; do not introduce
  an argument-parsing dependency without a need.
- Use explicit checks for important failures and expected nonzero results.
  `set -e` has exceptions in conditions, compound commands, and function calls;
  it is not a universal guarantee that a failure stops execution.
- Separate declarations from command substitutions when the command's exit status
  matters: `local result` followed by `result="$(command)"`. A declaration builtin
  can otherwise mask the command's failure.
- Do not swallow errors with broad `|| true`. Handle an expected failure with
  a specific fallback or diagnosis and preserve meaningful exit statuses.
- Put command results on stdout and diagnostics/progress on stderr where the
  command may be composed with other tools. Prefer printf for predictable output
  formatting; avoid parsing ls output or splitting paths on whitespace.
- Make temporary-resource cleanup and traps fit the script's actual needs.
  Do not introduce elaborate error frameworks or global traps for every command.

## Linting, formatting, and verification

- ShellCheck is the standard linter. Resolve findings or explain a narrowly scoped
  suppression when an intentional pattern needs one; avoid blanket exclusions.
- Use shfmt from [mvdan/sh](https://github.com/mvdan/sh) for deterministic formatting.
  Follow existing project recipes and EditorConfig/formatter settings. For new
  projects without settings, use shfmt's default style; no custom indentation
  or printer flags have been selected as a personal standard.
- Typical standalone-script checks are:

  ```bash
  bash -n script.sh
  shellcheck script.sh
  shfmt -d script.sh
  ```

  Use `shfmt -w script.sh` to apply formatting. Prefer non-mutating format checks
  in CI. These commands do not replace behavior testing where failures matter.
- Bash shebangs guide dialect detection. For sourced files, use the project's
  shell directives or EditorConfig dialect setting as needed. shfmt parser/printer
  flags such as `-ln bash` disable its EditorConfig formatting options, so do not
  add them blindly when a project relies on EditorConfig.
- Scope formatting to the task; avoid changing unrelated shell configuration.
  Report missing tools rather than claiming their checks passed.
- Use the project's existing test approach. Test meaningful argument handling,
  failure behavior, and output contracts; mocks or controlled commands can avoid
  requiring real operational effects. No global Bash test framework or coverage
  target has been selected.

Sources: [ShellCheck](https://www.shellcheck.net/),
[shfmt manual](https://github.com/mvdan/sh/blob/master/cmd/shfmt/shfmt.1.scd).
