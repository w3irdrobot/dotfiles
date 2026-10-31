# Contract for execution-node skills

Read this when using any execution-node provisioning, runtime, Git, app-install,
or shared-config deployment skill. It is shared policy, not a request to run the
provisioning skill or the other setup stages.

## Inputs and scope

- Extract explicit answers from the request and current context first. Ask for
  missing important inputs before mutating anything; batch related questions.
  Offer recommendations, but do not turn recommendations into selected values.
- Resolve the exact target/node, OS user/home, OS/architecture, and authorized
  action. “Set up an agent” does not select Maple, Codex, or Claude. Each
  application has its own skill and is independently installable.
- Do not assume machine names, IPs, VM IDs, RAM/disk/CPU sizes, usernames, paths,
  credentials, release numbers, or accounts from the original Maple VM.
  Btrfs is the accepted filesystem default for newly provisioned nodes; this
  does not authorize conversion or formatting of an existing filesystem.
- Read available node guidance and relevant project instructions. Inspect current
  state and report conflicts. A skill's availability does not prove its tools or
  sandbox permissions exist. Discover tool schemas instead of inventing calls.
- Ask for release policy (an exact version or latest stable) when missing. Resolve
  an approved moving channel to an exact release before downloading. Fetch current
  first-party instructions and verify the chosen release supports this OS/CPU.

## Safety and reproducibility

- Provisioning, runtime, Git, app installations, and shared-config deployment are
  separate scopes. Do not chain them automatically. `setup-execution-node` can
  coordinate only the stages in an explicitly approved plan; selecting one child
  skill by itself never selects the others. Missing dependencies require an
  agreed installation plan, not an unrelated workstation bootstrap.
- No automatic destruction, reinstall, migration, credential copying, application
  login, public exposure, firewall changes, account creation, or paid services.
  Destruction needs separate confirmation of the exact resources and attached
  disks, with a clear warning that local state will be lost. Pushed PRs do not
  establish that conversations, credentials, or all local files are disposable.
- Run apps as the agreed unprivileged user. Use narrow administration only for
  approved system work. Never change identity/signing or weaken a sandbox to make
  a check pass. Refuse unmanaged paths, dangling links, and conflicting parents.
- Prefer authenticated, pinned release artifacts. Verify signatures when supplied
  and SHA-256/size against authoritative metadata before execution. Record what
  was verified; a same-origin checksum is not an independent release signature.
  Inspect downloaded installers before execution. Do not use blind curl-to-shell.
- Retain non-secret release provenance and service configuration. Keep tokens,
  passwords, auth stores, pairing links, and private keys out of Git and tool
  output. Let the user complete login/pairing in their own terminal.
- Before changing an existing installation, check for active tasks and obtain
  approval for interruption. Do not overwrite a running binary, auto-upgrade
  providers, kill tasks, or restart services merely to verify installation.
- For a repeat run, inspect and reuse a matching setup. Stop on mismatches or
  partial installs; do not force links, delete state, or silently switch versions.

## Verification and independent trials

For each selected skill: show the resolved plan, perform only that stage, verify
its acceptance criteria, and report changes plus failures/skipped checks. Stop
before the next stage, or return to `setup-execution-node` for its approved
continuation/one-stage-at-a-time policy. Separate these evidence levels:

1. Artifact/configuration exists and passes static checks.
2. Process starts and service/endpoint is healthy.
3. Authenticated provider tool use and fresh-session instruction discovery work.

A version check or running service does not prove an agent can execute commands.
Use a user-approved disposable workspace for live tasks, with bounded commands
and explicit working directories. Never test by searching `/` or printing secrets.
