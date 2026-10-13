# Alex's Rust conventions

Accepted personal defaults, captured 2026-10-07. Apply them where the project has
not made a different choice. These are judgment-based preferences, not reasons
to rewrite unrelated working code.

## Code organization and dependencies

- Keep `main.rs` focused on bringing the application together: configuration,
  component construction, wiring, and starting execution. Put substantial
  behavior in modules. For an HTTP server, define routes and handlers in other
  modules and compose them into the running server at the entry point.
- Keep `lib.rs` primarily for module declarations, public exports, and re-exports.
  Put substantial implementations in their own modules rather than accumulating
  them in the crate root.
- Split crates when reuse gives the boundary a purpose: code shared by another
  workspace binary, or code that plausibly deserves a separately published crate.
  This is a heuristic, not a requirement to publish or extract every module.
  A single crate is fine for a small tool.
- Favor clear, one-way dependencies and avoid circular dependency pressure.
  If two modules or crates need each other's internals, reconsider ownership and
  boundaries. Move genuinely shared concepts to an appropriate lower-level
  module or crate when that clarifies the design; do not add abstractions or
  shared crates solely to achieve an elaborate hierarchy.
- For new multi-crate projects, prefer a workspace with members under `crates/`
  and resolver 3 where appropriate. Follow an existing project's layout.

## Errors

- Use `anyhow` at application boundaries for propagating and reporting failures.
  Add context where it makes a failure actionable, such as identifying the
  operation or resource involved.
- Use typed errors with `thiserror` in libraries and domain code, where callers
  benefit from distinguishing failure cases and deciding how to respond.
- Preserve useful error information as typed failures reach the application
  boundary. Do not erase domain distinctions prematurely or add typed error
  plumbing to every application-only helper without a reason.

## Testing

- Prefer focused unit tests while building behavior. Test code that could cause
  problems or whose behavior is easy to misunderstand; skip simple functions
  whose tests would merely restate their implementation.
- Treat serialization as a contract when output shape matters. Test Serde output
  against the JSON or other structure the application expects, including relevant
  field names, enum representation, optional fields, and nesting. A serialize /
  deserialize round trip alone does not establish the intended external shape.
  Compare structured values unless exact serialized text is itself the contract.
- Keep cross-module integration tests separate from implementation modules,
  normally under the crate's `tests/` directory. Unit tests can live alongside
  the module they exercise.
- Prefer mocks or test doubles to keep routine tests fast and focused. Introduce
  them at useful boundaries rather than designing every internal function around
  a mocking framework.
- Add a small suite of end-to-end or real-component tests when the application's
  risks call for it. Use them to cover behavior mocks cannot establish, such as
  actual interaction with a database or external service implementation. Not
  every application needs this infrastructure.

## Portable development and real-component tests

- Prefer Docker for provisioning real components needed by development and tests.
  Reuse an existing container setup; choose the smallest reproducible setup that
  meets the application's needs when adding one.
- Aim for machine-independent setup with documented commands and configuration,
  so someone can get a new project running quickly without reproducing one
  developer's host setup. Avoid hardcoded personal paths and dependencies on
  manually configured local services.
- Keep fast mock-based tests runnable without starting the real-component
  environment. Make commands for starting services, running real-component
  tests, and cleaning up discoverable through the project's workflow.

## Toolchains, formatting, and workflow

- Prefer edition 2024 for new projects and stable Rust for builds.
- Use unpinned nightly for rustfmt's import-formatting options. An unpinned
  toolchain does not update automatically; `rustup update nightly` is a separate
  maintenance action, not something to run for every feature.
- The personal formatter defaults group standard, external, and crate imports
  (`group_imports = "StdExternalCrate"`), use module import granularity,
  reorder imports, set a 100-column width, and use four-space indentation.
  The project's formatter configuration is the executable source of truth.
- Prefer `just` as the workflow interface. The default recipe lists available
  recipes. Baseline names are `fmt`, `fmt-check`, `check`, `lint`, `test`,
  `build`, `run`, and aggregate `verify`.
- Use the project's existing recipes and CI to determine required checks.
  Templates and tooling own repeatable configuration; avoid copying an entire
  starter setup into an existing project as part of an unrelated change.

## Runtime and dependencies

- Tokio is the usual choice when using async Rust, including async CLIs.
  Synchronous programs remain a supported choice; do not introduce async into
  existing synchronous code solely to match this preference.
- Use `tracing` for logging, with environment-configured filtering via
  `tracing-subscriber`. Keep CLI application output on stdout and logs on stderr.
- Common library choices are Clap for CLI arguments, `anyhow` / `thiserror` for
  errors, Serde for serialization, Axum for HTTP, and `config` / dotenvy where
  configuration loading is needed. Add dependencies for actual needs rather
  than treating this list as a mandatory bundle.
- `watchexec` is preferred for server restarts during development. Use it when
  useful to the project, rather than requiring it for all Rust work.
