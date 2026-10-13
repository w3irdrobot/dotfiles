---
name: skill-creator
description: Create, review, or improve reusable OpenCode skills, including trigger descriptions, focused instructions, references, helper scripts, and proportionate validation. Use when the user asks to turn a workflow into a skill or refine an existing skill.
license: Complete terms in LICENSE.txt
---

# Create and improve skills

Adapted from the existing local skill-creator guide. Modified 2026-10-07 to focus
on OpenCode and proportionate validation rather than mandatory packaging.

Skills hold reusable guidance the model needs for a particular task. Keep
repeatable behavior in tools or scripts and judgment-based choices in concise
instructions. Do not duplicate what the harness or other authoritative guidance
already provides.

## Understand the job

- Extract intent, examples, constraints, and corrections from the conversation.
  Ask for missing information that changes the workflow; avoid re-interviewing
  the user about decisions already made.
- Establish what should trigger the skill, what adjacent tasks should not, and
  what a successful result looks like. A skill should have a clear responsibility.
- When editing, read the existing skill and relevant resources. Preserve useful
  behavior and distinguish the user's accepted choices from proposals.
- For OpenCode-specific configuration or discovery, load `customize-opencode`.
  Follow applicable project instructions and use the actual installed harness.

## Write the smallest useful skill

Use `SKILL.md` in a directory matching its lowercase, hyphen-separated name:

```text
my-skill/
├── SKILL.md
├── references/   # Detailed guidance, when needed
└── scripts/      # Reusable deterministic behavior, when needed
```

- Include YAML frontmatter with `name` and `description`. The description should
  explain what the skill does and when to load it, including meaningful scope
  boundaries. It is visible before the body is loaded.
- Write direct instructions with brief rationale for non-obvious choices.
  Prefer defaults and tradeoffs over rigid rules that ignore project context.
- Keep the body focused. Link detailed references from the body and say when
  they are needed; avoid loading every reference for every use.
- Add helpers when they eliminate recurring mechanical work or fragile inline
  code. Use templates/generators for scaffolding instead of reproducing their
  output in prose.
- Avoid redundant documentation and artifacts the user will not use. Preserve
  applicable attribution and licenses when adapting existing material.

## Validate in proportion to the change

- Check frontmatter and directory structure with the bundled validator:

  ```bash
  uv run --with pyyaml python scripts/quick_validate.py /absolute/path/to/my-skill
  ```

  Run from this skill's directory, or use an absolute path to the script. If
  Python already has PyYAML, invoking the script directly is sufficient.
- For prose changes, review representative prompts and ambiguous/negative cases
  against the instructions. Distinguish a manual review from an actual model run.
- Execute new helper scripts against meaningful examples and failure cases.
  Test output contracts and edge cases rather than mirroring implementation.
- Use end-to-end trials when the workflow warrants them. Isolate generated
  projects or external side effects appropriately and report actual results.
- Add formal trigger tests, comparisons, or benchmarks when requested or when
  repeated failures justify them. Do not automatically launch subagents or an
  evaluation suite for every skill edit. Obtain authorization for delegation.
- Do not assume Claude Code's `claude -p` tooling tests OpenCode behavior.
  Any harness-specific evaluation runner needs to match the user's environment.

## Finish and iterate

Report the installed path, useful behavior, and verification results concisely.
Remind the user to restart OpenCode after changing skills. Package with the
bundled `scripts/package_skill.py` only when distribution is requested; local
installation does not require a `.skill` archive.

Improve the skill based on concrete use. Generalize useful corrections without
turning a single example into a universal constraint.
