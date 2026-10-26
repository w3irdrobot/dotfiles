# System76 setup

On confirmed System76 hardware, selecting `core` (including the default install)
or `hardware` adds `system76-driver`, `system76-firmware`, `system76-power`, and
the `firmware-manager` GUI. The intended laptop is a Lemur Pro **lemp14**; its
real hardware behavior remains unverified.

Detection reads `/sys/class/dmi/id/sys_vendor` without sudo, normalizes known
System76 vendor names, and reports a sanitized product name. Other vendors or
unavailable DMI information skip the packages. An explicit `--modules system76`
requires the same confirmed vendor information.

Packages use the `szydell/system76` Fedora COPR linked from System76's own driver
guide. The selected repository is restricted to these four packages; it is not
an official Fedora repository. Modern kernels include `system76_acpi`,
so setup selects no extra DKMS packages. Thelio I/O, OLED, NVIDIA, and GNOME
extensions are not generic Lemur requirements.

## Confirmed service activation

Install/system-update checks the installed, RPM-owned units and shows a plan,
then asks through the terminal before making service changes. Declining or
having no terminal leaves activation deferred; rerun install/update in a terminal
when ready. Linking alone and dry-runs do not activate services. Local drop-ins,
missing/masked required units, unexpected owners, or transitional states require
manual review rather than guessing. The known Fedora-wide
`/usr/lib/systemd/system/service.d/10-timeout-abort.conf` is accepted only as a
regular file owned by `systemd`, containing solely `[Service]` and
`TimeoutStopFailureMode=abort` (apart from comments/blank lines). This packaged
shutdown-timeout policy is left unchanged; extra or modified drop-ins still stop
activation. Do not delete or mask Fedora's default to work around the check.

The confirmed plan enables/starts `system76-firmware-daemon.service` and
`com.system76.PowerDaemon.service`, and enables `system76-power-wake.service`
without starting the wake hook immediately. The driver RPM has no
`system76.service`; do not try enabling that nonexistent unit.

Present competing backends (`tuned`, `tuned-ppd`, `power-profiles-daemon`, TLP,
and `auto-cpufreq`) are stopped and persistently masked only after confirmation.
Their enablement links are retained for recovery. Plasma PowerDevil stays intact.
An already complete setup needs no new confirmation or service changes.

If power activation fails, setup attempts to stop/disable newly activated
System76 power and unmask/restart the backends changed by this run. Read the
restoration output: a failure to stop System76 power keeps competitors masked
to avoid running both, and recovery itself can fail. The independent firmware
daemon may remain enabled. A wake-hook failure leaves the functioning daemons
running and reports the incomplete step; inspect/fix it manually.

Privileged groups, graphics/boot settings, firmware flashing, and Firmware
Manager's user notification service/timer remain unchanged. Review polkit/group
permissions locally and perform firmware updates separately. Package hooks are
upstream behavior; the confirmation applies to dotfiles' explicit service steps.

Follow the hardware checks in [the rehearsal guide](testing.md) before treating
lemp14 support as verified.

References: [driver guidance](https://system76.com/support/system76-driver/),
[software roles](https://system76.com/support/system76-software/), and
[Fedora driver source](https://system76.com/support/system76-driver/#fedora).

System76's wildcard install and DKMS instructions cover several hardware types;
dotfiles does not install every driver on a Lemur Pro. In particular, do not add
Thelio/OLED drivers or replace the in-kernel ACPI module without a demonstrated
need. Review the installed Fedora kernel and actual hardware behavior first.
The guide's `adm` membership and firmware updates remain separate manual choices.
