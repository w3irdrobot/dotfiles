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

## Manual activation

Review package hooks and units before enabling services. The installer leaves
System76 service activation, privileged groups, graphics/boot settings, and
firmware flashing to you.

Check Fedora's `tuned`/`tuned-ppd`, `power-profiles-daemon`, TLP, and `auto-cpufreq` before enabling
`system76-power`; resolve competing backends while keeping Plasma's PowerDevil
desktop power management. Review firmware-manager polkit/group permissions
locally and perform firmware updates separately.

Follow the hardware checks in [the rehearsal guide](testing.md) before treating
lemp14 support as verified.

References: [driver guidance](https://system76.com/support/system76-driver/),
[software roles](https://system76.com/support/system76-software/), and
[Fedora driver source](https://system76.com/support/system76-driver/#fedora).

System76's wildcard install and DKMS instructions cover several hardware types;
dotfiles does not install every driver on a Lemur Pro. In particular, do not add
Thelio/OLED drivers or replace the in-kernel ACPI module without a demonstrated
need. Review the installed Fedora kernel and actual hardware behavior first.
The guide's service masking, `adm` membership, and firmware updates are separate
manual choices, not installer side effects.
