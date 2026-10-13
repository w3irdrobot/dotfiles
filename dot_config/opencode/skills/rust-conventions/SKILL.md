---
name: rust-conventions
description: Apply Alex's Rust conventions when implementing, refactoring, reviewing, or testing Rust code, including crate organization, errors, serialization contracts, and development workflows. Use for substantive Rust work in new or existing projects. Project-specific instructions and established architecture take precedence. For scaffolding a new project, use create-project as well.
---

# Rust conventions

Read [references/conventions.md](references/conventions.md) before substantive
Rust implementation, refactoring, review, or test design. It contains personal
defaults and the rationale behind them, rather than a universal Rust style guide.

## Apply the conventions

1. Read applicable project instructions and inspect the relevant code, manifests,
   `justfile`, formatter configuration, and CI. Follow explicit project choices
   over these defaults. Avoid unrelated architecture or dependency changes just
   to make an existing project match personal preferences.
2. Use the reference to guide decisions the project has not already settled.
   Keep entry points focused on composition, modules responsible for behavior,
   and dependencies flowing in a clear direction. Explain meaningful tradeoffs
   briefly; ask when a consequential choice is genuinely ambiguous.
3. Let existing tools enforce mechanical rules. Use project recipes and
   configuration rather than duplicating formatting or lint rules in prose or
   replacing them while working on a feature.
4. Add tests for meaningful risks and observable contracts. Choose unit,
   integration, or real-component coverage according to what can fail; do not
   create tests that only mirror simple implementation details.
5. Run checks appropriate to the change using the project's workflow. For the
   personal Rust CLI starter, `just verify` runs formatting, compilation, Clippy,
   and tests; `just build` checks the release build when relevant. Report actual
   results and any blockers without treating unrun checks as passing.

Use `create-project` for new-project scaffolding. The versioned template owns the
scaffold; this skill guides subsequent Rust work.
