# Alex's OpenTofu conventions

Personal defaults agreed during the environment discussion. Apply them where a
project has not made a different choice. The reviewed GCP repository is a useful
layout reference, not a universal provider, version, or operational policy.

## Roots and environments

- Give environments their own directories and state locations. Prefer concise
  names such as `staging/` and `production/`; a cloud project/account identifier
  belongs in configuration and need not dictate the directory name.
- Use separate roots for shared infrastructure or another distinct state/lifecycle
  boundary when needed. Keep boundaries intentional; not every service requires
  a separate state or directory.
- Preserve existing directory names and backend locations during ordinary work.
  A deliberate directory rename is not automatically a backend-prefix rename.
- Use `modules/` for reusable modules. Environment roots compose them using local
  module paths when they share a repository. Follow an existing repository's
  layout rather than introducing wrappers or workspace-based environments solely
  to match a generic starter.

## File placement

- Prefer `main.tf` for the root's setup and shared environment context: the
  `terraform` block, backend, CLI/provider version requirements, provider
  configurations, and environment-wide locals.
- Fixed environment choices can live directly in that directory's HCL. Use
  shared locals in `main.tf` for environment name, region, account/project ID,
  and tags/labels where useful. Keep service-specific values with their service.
  Do not create root variables and tfvars just to restate fixed choices.
- Use a service or infrastructure responsibility file to connect related pieces:
  for example, `chainlink_oracle.tf` may compose its database, identity, and
  secrets; `network.tf` owns shared networking.
- Put resource-specific permissions in the same file as the resource they govern.
  Registry grants belong with registries, bucket grants with buckets, and
  database access grants with the relevant database configuration. Follow the
  permission target, not merely the identity receiving permission.
- Identity creation and impersonation/trust bindings stay with the identity.
  Organization-wide or project-wide IAM may have its own responsibility file/root.
- Keep inputs in `variables.tf` when needed and exports in `outputs.tf`.
  Supporting locals and data sources belong with the responsibility using them;
  genuinely shared environment locals belong in `main.tf`.
- Extend the existing responsibility file before creating a new one. Create files
  for distinct responsibilities or useful subdivisions of a large responsibility,
  not for every resource, ticket, or incremental change. Avoid overlapping
  catch-all files that offer several plausible homes for the same resource.
- Do not create empty conventional files solely to complete a directory skeleton.

## Module boundaries

- Start with resources directly in the environment root. Extract a module when
  actual or expected reuse gives the boundary a purpose.
- Prefer small capability modules with focused inputs and outputs, composed in
  one service/responsibility file in the environment. Avoid a large whole-service
  module merely to keep one environment's configuration together.
- Let the root own its backend and provider configurations. Reusable modules
  declare required providers and accept explicit inputs; use provider mappings
  where aliases or multiple configurations are needed.
- Keep inputs typed, describe their purpose, and expose outputs consumers actually
  need. Validate meaningful constraints rather than adding boilerplate checks.
- Moving unchanged blocks between files in one root preserves resource addresses.
  Extraction into a module, changing resource names, or converting to `for_each`
  can change addresses; handle that as an explicit refactor with appropriate
  moved/import/state migration steps supported by the selected CLI.

## Cloud and remote state

- AWS is the preferred cloud. Support GCP when requested or chosen by the project.
  Do not silently replace a project's provider or infer AWS from a GCP reference.
- One shared state bucket with a distinct location per root is the personal
  default. For AWS use S3 keys; for GCP use GCS prefixes. Include enough project
  and environment context to avoid collisions between roots sharing the bucket.
- For new AWS backends, prefer native S3 locking with `use_lockfile = true`.
  Do not add a DynamoDB locking table. Preserve existing backend/locking choices
  outside an intentional migration, and verify the pinned CLI supports the
  selected mechanism. Use the GCS backend's built-in locking for GCP.
- Backend storage must exist before a root can initialize against it. Treat
  provisioning/bootstrap of that storage separately from consuming it; do not
  hide that prerequisite in a scaffold's normal init recipe.
- Non-sensitive backend settings may use init-resolvable locals/variables on
  compatible OpenTofu versions. Backend evaluation cannot depend on resources,
  state-derived/data-source values, or provider-defined functions. Check the
  selected version rather than assuming Terraform has identical capabilities.
- Use the project's credential/profile mechanisms. Fixed infrastructure settings
  in HCL are not a reason to put credentials or secret values there. Backend
  configuration and saved plans can persist values supplied during initialization.

## Versions and workflow

- Pin the OpenTofu CLI version for root configurations, using `required_version`
  and matching existing installation/CI mechanisms. Do not copy a particular
  version from a reference repository without selecting it for the new project.
- Constrain provider versions and commit each root's `.terraform.lock.hcl`.
  Upgrade providers deliberately; ordinary init/checks should not force upgrades.
  Reusable modules should declare compatible requirements rather than imposing
  a root's exact CLI pin on every consumer without a need.
- Prefer `just` as the workflow interface, with a default that lists recipes.
  Follow a project's existing recipe names; standardize new ones consistently
  when establishing a workflow. Formatting, linting, validation, and plans are
  different checks and should be reported accurately.
- Save the plan, then apply that specific plan. A typical root workflow is:

  ```bash
  tofu init
  tofu plan -out tofuplan.out
  tofu apply tofuplan.out
  ```

  Expose these through `just init`, `just plan`, and `just apply` where appropriate.
  Keep plan artifacts, local state, and `.terraform/` out of Git.
- Applying infrastructure or changing live state must fit the requested task.
  A formatting or organization change does not authorize deployment.
- Check actual plan effects, including replacements/deletions and unintended
  changes, against the intended scope. A successful command does not by itself
  establish correctness. Use existing tests and CI; no additional test framework
  or infrastructure test policy has been selected as a universal requirement.

## Backend references

- [OpenTofu S3 backend](https://opentofu.org/docs/language/settings/backends/s3/)
- [Backend configuration and init-time values](https://opentofu.org/docs/language/settings/backends/configuration/)

Check version-specific documentation when implementing; the current docs can
describe features newer than a project's pinned toolchain.
