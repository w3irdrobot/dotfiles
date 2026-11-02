# Optional virtual desktop and CUA Driver

Use when an execution node needs to view and operate GUI application builds.
This is an opt-in runtime component, not a workstation bootstrap. A selected GUI
setup includes OS prerequisites, user-level CUA Driver installation, approved
desktop lifecycle, and rendering/input acceptance. An explicitly package-only
request does not include the driver. Never infer permission to expose a display
or change the hypervisor.

## Resolve scope

Confirm the guest OS/architecture, execution user, target application and renderer,
whether a GPU device exists, and whether only packages or a working desktop was
approved. Inspect existing displays and active GUI jobs before changing anything.
Keep package administration separate from the unprivileged execution user; do not
grant sudo just to install dependencies. Never restart active agent services for
this stage or add GPU passthrough without approval.

## Debian 13 x86_64 package baseline

For the approved minimal X11/XFCE, software-rendering, and recording option, run
as guest root (not on the hypervisor or operator workstation):

```bash
apt-get update
apt-get --simulate install --no-install-recommends \
  xvfb xauth x11-utils \
  xfce4-session xfwm4 xfce4-settings \
  dbus-x11 at-spi2-core libxi6 \
  libgl1-mesa-dri mesa-vulkan-drivers vulkan-tools mesa-utils \
  fonts-dejavu-core fonts-noto-core fonts-noto-cjk fonts-noto-color-emoji \
  ffmpeg curl ca-certificates
```

Review dependency changes and disk requirements, then run the same install command
without `--simulate` after approval. Refuse unexpected removals or unrelated
upgrades; do not run a distribution upgrade. Use normal signed distribution
repositories. For another OS/release, verify package names and current support
rather than blindly translating this list. Do not install a display manager,
enable autologin, or change the default boot target.

Verify requested package states/versions with `dpkg-query`, check `dpkg --audit`,
and check command availability as the execution user. Record package versions in
the handoff. This proves prerequisites only; do not label rendering verified.

## Install CUA Driver as the execution user

For selected GUI setup, install the driver after the OS packages; do not leave it
as an optional follow-up or report it installed merely because dependencies exist.
Inspect any existing driver version, executable path, ownership, and running
desktop/driver jobs first. Reuse a matching installation; stop before replacing
an active or mismatched version. Never reinstall a working driver blindly.

Consult the current first-party
[quickstart](https://cua.ai/docs/cua-driver/quickstart) and
[connection guide](https://cua.ai/docs/cua-driver/guides/connect-your-agent).
Resolve the approved release policy to an exact supported version. As the normal
execution user, create a private scratch directory and download both
`https://cua.ai/driver/install.sh` and
`https://cua.ai/driver/_install-rust.sh` there under those exact filenames.
Inspect both scripts, including artifact sources and verification behavior. Keeping
the helper beside the wrapper makes the reviewed wrapper execute that local copy
rather than download an unreviewed helper during execution; verify that behavior
against the current scripts before running them.

With `reviewed_dir` set to that directory and `version` set to the resolved exact
release, run the reviewed installer as the execution user, not root:

```bash
CUA_DRIVER_RS_VERSION="$version" bash "$reviewed_dir/install.sh" \
  --bin-dir "$HOME/.local/bin" --no-modify-path --require-signature
"$HOME/.local/bin/cua-driver" --version
```

Check current signature-verifier prerequisites first. If `--require-signature`
needs a missing verifier such as cosign, obtain approval for a verified install
of that prerequisite; do not silently omit signature verification. Verify the
release checksums as well, record the exact installed version, artifact source,
verification evidence, and executable path. Verify command availability in a
fresh login without rewriting shell startup files. CLI version checks establish
installation only, not a ready desktop. Do not change provider authentication,
install MCP configuration, or register extra skills as an installer side effect.

## Configure the approved user session

- Run the desktop, target application/MDE launcher, and driver as the execution
  user. Give them the same `DISPLAY`, private `XAUTHORITY`, and D-Bus session
  address. Use a fixed resolution and explicit lifecycle ownership; an ordinary
  SSH shell does not necessarily inherit the desktop environment. Keep session
  variables scoped to desktop-aware launchers, not every provider process.
- Disable X11 TCP listening and retain X authorization; never use `xhost +`.
  Human viewing/VNC and network exposure are separate choices, not dependencies.
- CLI-first operation is sufficient; MCP and skill registration are optional,
  explicit changes. Start the driver inside the intended desktop session. Review
  input permission scope; a shared desktop is not isolation from the same user's
  credentials or other applications.
- Allow one GUI task per desktop, or allocate separate displays/sessions for
  concurrent tasks. Save private screenshots/recordings in task-specific artifact
  directories with an agreed retention policy; never commit them automatically.

## Rendering and automation acceptance

No `/dev/dri` device is required to try Mesa software Vulkan (lavapipe). Its
installation or device enumeration does not prove GPUI can create a presentation
surface under Xvfb. Validate in stages, only within approved test scope:

1. Display and window manager work at the chosen resolution.
2. Inspect `glxinfo -B` and `vulkaninfo --summary` inside that session, then launch
   the actual target/PR build and inspect a rendered frame. A working OpenGL probe
   does not establish Vulkan presentation or Maple rendering.
3. Run `cua-driver doctor`, inspect warnings, capture a real application screenshot,
   and perform a harmless input action. A zero exit status is not readiness.
4. Check `cua-driver call list_apps` and actual AT-SPI support separately from
   screenshot/input control; custom-rendered apps may expose limited semantics.
5. Verify a short FFmpeg recording and, if required, GIF conversion; verify the
   intended session survives SSH disconnects without restarting existing agents.

If Xvfb cannot support the renderer, report the actual error and propose a
separately approved alternative such as Xorg with a dummy display. Do not silently
add it or claim native-platform acceptance from software-rendered Linux tests.
Package-only work ends with desktop lifecycle, CUA, application rendering/input,
accessibility, and recording explicitly marked unverified.
