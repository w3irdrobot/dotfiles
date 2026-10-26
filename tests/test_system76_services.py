"""System76 service plans/confirmation/recovery with a synthetic systemd state."""

import copy
import json
import subprocess
import unittest

import test_dotfiles

FIRMWARE = "system76-firmware-daemon.service"
POWER = "com.system76.PowerDaemon.service"
WAKE = "system76-power-wake.service"


class System76Services(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        self.state_file = self.base / "units.json"
        self.confirm = self.base / "confirmation"
        self.confirm.write_text("yes\n")
        self.env.update(TEST_UNITS=str(self.state_file), TEST_CONFIRM=str(self.confirm), TEST_FAILURE_MARKER=str(self.base / "failed-once"))
        self.state = {}
        for unit in (FIRMWARE, POWER, WAKE, "tuned.service", "tuned-ppd.service"):
            self.state[unit] = {
                "LoadState": "loaded", "ActiveState": "active" if unit.startswith("tuned") else "inactive",
                "UnitFileState": "enabled" if unit.startswith("tuned") else "disabled", "DropInPaths": "",
                "FragmentPath": ("/etc/systemd/system/" if unit == FIRMWARE else "/usr/lib/systemd/system/") + unit,
            }
        self.save()
        self.module = self.repo / "modules/system76.sh"
        self.dropin = self.base / 'usr/lib/systemd/system/service.d/10-timeout-abort.conf'
        self.module.write_text(self.module.read_text().removesuffix('main "$@"\n').replace(
            "</dev/tty", '<"$TEST_CONFIRM"').replace(
            '/usr/lib/systemd/system/service.d/10-timeout-abort.conf', str(self.dropin)))
        self.mock("systemctl", """from pathlib import Path
state = json.loads(Path(os.environ['TEST_UNITS']).read_text())
args = sys.argv[1:]
if args[0] == 'show':
    unit = args[1]
    prop = next(a.split('=', 1)[1] for a in args if a.startswith('--property='))
    print(state.get(unit, {'LoadState': 'not-found', 'ActiveState': 'inactive'}).get(prop, ''))
elif args[0] in ('is-active', 'is-enabled'):
    unit = args[-1]
    if unit == os.environ.get('TEST_HEALTH_FAIL'): sys.exit(3)
    prop, expected = ('ActiveState', 'active') if args[0] == 'is-active' else ('UnitFileState', 'enabled')
    sys.exit(0 if state[unit][prop] == expected else 3)
else:
    sys.exit(97)
""")
        self.mock("rpm", """if '-qf' not in sys.argv: sys.exit(97)
if sys.argv[-1].endswith('/service.d/10-timeout-abort.conf'):
    if os.environ.get('TEST_DROPIN_QUERY_FAIL'): sys.exit(97)
    print(os.environ.get('TEST_DROPIN_OWNER', 'systemd'))
    sys.exit(0)
print(os.environ.get('TEST_OWNER', 'system76-firmware' if 'system76-firmware-daemon' in sys.argv[-1] else 'system76-power'))
""")
        self.mock("sudo", """from pathlib import Path
args = sys.argv[1:]
if args[0] != 'systemctl': sys.exit(97)
action, unit = args[1], args[-1]
path = Path(os.environ['TEST_UNITS'])
state = json.loads(path.read_text())
if action == 'mask':
    state[unit]['_enablement_before_mask'] = state[unit]['UnitFileState']
    state[unit]['UnitFileState'] = 'masked'
    state[unit]['LoadState'] = 'masked'
    state[unit]['ActiveState'] = 'inactive'
elif action == 'unmask':
    state[unit]['LoadState'] = 'loaded'
    state[unit]['UnitFileState'] = state[unit].pop('_enablement_before_mask')
elif action == 'enable':
    state[unit]['UnitFileState'] = 'enabled'
    if '--now' in args: state[unit]['ActiveState'] = 'active'
elif action == 'disable': state[unit]['UnitFileState'] = 'disabled'
elif action == 'start': state[unit]['ActiveState'] = 'active'
elif action == 'stop': state[unit]['ActiveState'] = 'inactive'
else: sys.exit(97)
if action == 'mask' and unit == os.environ.get('TEST_MASK_STAYS_ACTIVE'):
    state[unit]['ActiveState'] = 'active'
path.write_text(json.dumps(state))
marker = Path(os.environ['TEST_FAILURE_MARKER'])
if action == os.environ.get('TEST_FAIL_ACTION') and unit == os.environ.get('TEST_FAIL_UNIT') and not marker.exists():
    marker.write_text('partial operation failed')
    sys.exit(43)
""")

    def save(self):
        self.state_file.write_text(json.dumps(self.state))

    def current(self):
        return json.loads(self.state_file.read_text())

    def library(self, body="activate_system76"):
        return subprocess.run(
            [test_dotfiles.BASH, "-c", 'source "$1"\nDRY_RUN=0\n' + body + "\n", "system76-services", str(self.module)],
            env=self.env, cwd=self.repo, text=True, capture_output=True, timeout=20,
        )

    def mutations(self):
        return [c for c in self.calls() if c[0] == "sudo"]

    def test_confirmation_activates_daemons_masks_conflicts_and_only_enables_wake(self):
        result = self.library()
        self.assertEqual(0, result.returncode, result.stderr)
        current = self.current()
        for unit in (POWER, FIRMWARE):
            self.assertEqual("active", current[unit]["ActiveState"])
            self.assertEqual("enabled", current[unit]["UnitFileState"])
        self.assertEqual("enabled", current[WAKE]["UnitFileState"])
        self.assertEqual("inactive", current[WAKE]["ActiveState"])
        for unit in ("tuned.service", "tuned-ppd.service"):
            self.assertEqual("masked", current[unit]["LoadState"])
            self.assertEqual("masked", current[unit]["UnitFileState"])
            self.assertEqual("enabled", current[unit]["_enablement_before_mask"])
        for call in self.mutations():
            self.assertFalse(any(word in " ".join(call) for word in ("PowerDevil", "gpasswd", "usermod", "flash", "--user", "system76.service")))
        self.assertIn("No firmware flashing", result.stderr)

    def test_decline_and_eof_leave_all_service_state_unchanged(self):
        for answer in ("no\n", "", "yes; execute something\n"):
            self.log.unlink(missing_ok=True)
            self.confirm.write_text(answer)
            result = self.library()
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("activation deferred", result.stderr)
            self.assertEqual(self.state, self.current())
            self.assertEqual([], self.mutations())

    def test_repeat_run_needs_no_mutations_or_new_confirmation(self):
        self.assertEqual(0, self.library().returncode)
        self.log.unlink()
        result = self.library('confirm_system76_activation() { exit 97; }; activate_system76')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("already active and enabled", result.stderr)
        self.assertEqual([], self.mutations())

    def test_missing_masked_or_overridden_required_units_fail_before_changes(self):
        original = copy.deepcopy(self.state)
        for prop, value in (("LoadState", "not-found"), ("LoadState", "masked"),
                            ("DropInPaths", "/etc/systemd/system/custom.conf"),
                            ("FragmentPath", "/run/systemd/system/custom.service")):
            self.log.unlink(missing_ok=True)
            self.state = copy.deepcopy(original)
            self.state[POWER][prop] = value
            self.save()
            self.assert_failed(self.library())
            self.assertEqual([], self.mutations())
        self.state = original
        self.save()
        self.env["TEST_OWNER"] = "unmanaged"
        self.assert_failed(self.library(), "Unexpected System76 unit package owner")
        self.assertEqual([], self.mutations())

    def test_firmware_failure_does_not_remove_existing_power_backend(self):
        self.env.update(TEST_FAIL_ACTION="enable", TEST_FAIL_UNIT=FIRMWARE)
        self.assert_failed(self.library(), "power backends were not changed")
        self.assertEqual(self.state["tuned.service"], self.current()["tuned.service"])
        self.assertFalse(any("mask" in c for c in self.mutations()))

    def test_partial_power_failure_restores_previous_backend_without_touching_wake(self):
        self.env.update(TEST_FAIL_ACTION="enable", TEST_FAIL_UNIT=POWER)
        self.assert_failed(self.library(), "review the restoration output")
        current = self.current()
        for unit in ("tuned.service", "tuned-ppd.service", POWER, WAKE):
            self.assertEqual(self.state[unit], current[unit])
        self.assertEqual("active", current[FIRMWARE]["ActiveState"])

    def test_partial_mask_failure_also_restores_backend_state(self):
        self.env.update(TEST_FAIL_ACTION="mask", TEST_FAIL_UNIT="tuned-ppd.service")
        self.assert_failed(self.library(), "Could not mask")
        for unit in ("tuned.service", "tuned-ppd.service", POWER):
            self.assertEqual(self.state[unit], self.current()[unit])

    def test_power_health_failure_restores_the_original_backend(self):
        self.env["TEST_HEALTH_FAIL"] = POWER
        self.assert_failed(self.library(), "active/enabled check")
        for unit in ("tuned.service", "tuned-ppd.service", POWER):
            self.assertEqual(self.state[unit], self.current()[unit])

    def test_other_hardware_refuses_activation_before_service_queries(self):
        dmi = self.base / "dmi"
        dmi.mkdir()
        (dmi / "sys_vendor").write_text("Other vendor")
        self.assert_failed(self.library("main"), "requires confirmed System76")
        self.assertFalse(any(c[0] in ("systemctl", "sudo", "rpm") for c in self.calls()))

    def test_competing_backend_must_actually_be_inactive_before_power_activation(self):
        self.env["TEST_MASK_STAYS_ACTIVE"] = "tuned.service"
        self.assert_failed(self.library(), "not masked/inactive")
        self.assertFalse(any(c[-1] == POWER and 'enable' in c for c in self.mutations()))
        self.assertEqual(self.state["tuned.service"], self.current()["tuned.service"])

    def test_wake_failure_reports_incomplete_step_without_removing_working_daemons(self):
        self.env.update(TEST_FAIL_ACTION="enable", TEST_FAIL_UNIT=WAKE)
        self.assert_failed(self.library(), "wake integration could not be enabled")
        for unit in (POWER, FIRMWARE):
            self.assertEqual("active", self.current()[unit]["ActiveState"])
        self.assertFalse(any('unmask' in c for c in self.mutations()))

    def test_failed_power_stop_keeps_competitors_masked_for_manual_recovery(self):
        self.env.update(TEST_FAIL_ACTION="stop", TEST_FAIL_UNIT=POWER, TEST_HEALTH_FAIL=POWER)
        self.assert_failed(self.library(), "leaving competing backends masked")
        self.assertFalse(any('unmask' in c for c in self.mutations()))

    def test_previously_inactive_backend_is_not_started_during_recovery(self):
        self.state["tuned.service"]["ActiveState"] = "inactive"
        self.save()
        self.env.update(TEST_FAIL_ACTION="enable", TEST_FAIL_UNIT=POWER)
        self.assert_failed(self.library())
        self.assertEqual(self.state["tuned.service"], self.current()["tuned.service"])

    def test_runtime_only_mask_is_not_treated_as_persistent_protection(self):
        self.state['tuned.service'].update(LoadState='masked', ActiveState='inactive', UnitFileState='masked-runtime')
        self.save()
        self.assert_failed(self.library(), 'mask is not persistent')
        self.assertEqual([], self.mutations())

    def fedora_dropin(self):
        self.dropin.parent.mkdir(parents=True, exist_ok=True)
        self.dropin.write_text('# This file is part of the systemd package.\n\n[Service]\nTimeoutStopFailureMode=abort\n')
        for unit in (FIRMWARE, POWER, WAKE):
            self.state[unit]['DropInPaths'] = str(self.dropin)
        self.save()

    def test_packaged_fedora_shutdown_default_is_accepted_for_all_three_units(self):
        self.fedora_dropin()
        before = self.dropin.read_bytes()
        result = self.library()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('active', self.current()[FIRMWARE]['ActiveState'])
        self.assertEqual('active', self.current()[POWER]['ActiveState'])
        self.assertEqual('enabled', self.current()[WAKE]['UnitFileState'])
        self.assertEqual(before, self.dropin.read_bytes())

    def test_fedora_default_does_not_allow_additional_or_modified_dropins(self):
        self.fedora_dropin()
        self.state[FIRMWARE]['DropInPaths'] += ' /etc/systemd/system/custom.conf'
        self.save()
        self.assert_failed(self.library(), 'unreviewed drop-ins')
        self.assertEqual([], self.mutations())
        self.fedora_dropin()
        for settings in ('[Service]\nTimeoutStopFailureMode=kill\n',
                         '[Service]\nTimeoutStopFailureMode=abort\nExecStart=/unexpected\n'):
            self.dropin.write_text(settings)
            self.assert_failed(self.library(), 'unreviewed settings')
            self.assertEqual([], self.mutations())

    def test_missing_symlinked_unowned_and_wrong_owner_shutdown_defaults_are_refused(self):
        self.fedora_dropin()
        self.dropin.unlink()
        self.assert_failed(self.library(), 'Conflicting Fedora shutdown drop-in')
        target = self.base / 'other.conf'
        target.write_text('[Service]\nTimeoutStopFailureMode=abort\n')
        self.dropin.symlink_to(target)
        self.assert_failed(self.library(), 'Conflicting Fedora shutdown drop-in')
        self.dropin.unlink()
        self.fedora_dropin()
        self.env['TEST_DROPIN_OWNER'] = 'other'
        self.assert_failed(self.library(), 'Unexpected Fedora shutdown drop-in package owner')
        self.env['TEST_DROPIN_QUERY_FAIL'] = '1'
        self.assert_failed(self.library(), 'not RPM-owned')
        self.assertEqual([], self.mutations())
