"""Pre-upgrade Btrfs snapshot and reboot reporting checks."""

import shlex
import subprocess
import unittest

import test_dotfiles


class UpgradeSnapshot(unittest.TestCase):
    setUp_fixture = test_dotfiles.Fixture.setUp
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        self.setUp_fixture()
        self.state = self.home / ".local/state"
        self.btrfs_temp = self.base / "btrfs-top"
        self.kernel_marker = self.base / "kernel-upgraded"
        self.env.update({
            "TEST_FSTYPE": "btrfs",
            "TEST_SNAPSHOTS_MOUNTED": "0",
            "TEST_BOOT_SEPARATE": "0",
            "TEST_LOW_SPACE": "0",
            "TEST_SNAPSHOT_FAIL": "0",
            "TEST_BTRFS_TEMP": str(self.btrfs_temp),
            "TEST_KERNEL_MARKER": str(self.kernel_marker),
        })
        self.mock("findmnt", """import os, sys
args = sys.argv[1:]
target_index = args.index('--target') + 1 if '--target' in args else None
target = args[target_index] if target_index is not None else '/'
mounted = os.environ['TEST_SNAPSHOTS_MOUNTED'] == '1'
boot_separate = os.environ['TEST_BOOT_SEPARATE'] == '1'
if 'FSTYPE' in args:
    if target == '/':
        print(os.environ['TEST_FSTYPE'])
    elif target == '/.snapshots' and mounted:
        print('btrfs')
    elif target == '/boot' and boot_separate:
        print('vfat')
    else:
        print('ext4')
elif 'SOURCE' in args:
    print('/dev/mapper/test[/root]' if target == '/' else '/dev/mapper/test[/@snapshots]')
elif 'FSROOT' in args:
    print('/root' if target == '/' else '/@snapshots')
elif 'TARGET' in args:
    if target == '/.snapshots':
        print('/.snapshots' if mounted else '/')
    elif target == '/boot':
        print('/boot' if boot_separate else '/')
    else:
        print('/')
""")
        self.mock("btrfs", "sys.exit(0)")
        self.mock("df", """import os, sys
available = '1024' if os.environ['TEST_LOW_SPACE'] == '1' else '100000000'
print('Filesystem 1024-blocks Used Available Capacity Mounted on')
print('/dev/test 200000000 1000 ' + available + ' 1% /')
""")
        self.mock("sudo", """import os, sys
from pathlib import Path
args = sys.argv[1:]
if not args:
    sys.exit(97)
if args[0] == 'dnf':
    if 'repoquery' in args:
        for name in args[args.index('--queryformat') + 2:]:
            print(name)
    if 'upgrade' in args:
        Path(os.environ['TEST_KERNEL_MARKER']).write_text('kernel upgraded')
    sys.exit(0)
if args[0] == 'mktemp':
    path = Path(os.environ['TEST_BTRFS_TEMP'])
    path.mkdir(parents=True, exist_ok=True)
    print(path)
    sys.exit(0)
if args[0] in ('mount', 'umount', 'rmdir'):
    sys.exit(0)
if args[0] == 'btrfs' and len(args) >= 3 and args[1] == 'subvolume':
    action = args[2]
    if action == 'create':
        Path(args[3]).mkdir(parents=True, exist_ok=True)
    elif action == 'snapshot':
        if os.environ['TEST_SNAPSHOT_FAIL'] == '1':
            sys.exit(1)
        Path(args[-1]).mkdir(parents=True, exist_ok=True)
    elif action == 'delete':
        pass
    sys.exit(0)
sys.exit(97)""")
        self.mock("rpm", """import os, sys
from pathlib import Path
args = sys.argv[1:]
if args == ['--verifydb']:
    sys.exit(0)
if '-qa' in args:
    print('kernel-core 0:6.1.0-1.fc44.x86_64')
    print('rpm 0:6.0.0-1.fc44.x86_64')
    if Path(os.environ['TEST_KERNEL_MARKER']).exists():
        print('kernel-core 0:6.2.0-1.fc44.x86_64')
    sys.exit(0)
if '-q' in args:
    sys.exit(1)
sys.exit(97)""")
        self.mock("paru", "print('paru v2.1.0') if '--version' in sys.argv else None")

    def library(self, body, dry_run=False):
        script = """set -euo pipefail
ROOT=$1
DRY_RUN=$2
source "$ROOT/lib/dotfiles.sh"
"""
        script += body
        return subprocess.run(
            [test_dotfiles.BASH, "-c", script, "upgrade-snapshot-fixture",
             str(self.repo), str(int(dry_run))],
            cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=20,
        )

    def run_packages(self):
        return self.library(
            "SELECTED_GROUPS=(core)\n"
            "MODULES=()\n"
            "PACKAGES=()\n"
            "install_packages\n"
            "end_system_upgrade\n"
        )

    def snapshot_calls(self):
        return [call for call in self.calls()
                if call[:3] == ["sudo", "btrfs", "subvolume"] and "snapshot" in call]

    def rollback_notes(self):
        notes = list((self.state / "dotfiles/upgrades").glob("dotfiles-*/rollback.txt"))
        self.assertEqual(1, len(notes), notes)
        return notes[0]

    def test_snapshot_precedes_full_upgrade_and_reports_boot_packages(self):
        result = self.run_packages()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        snapshots = self.snapshot_calls()
        self.assertEqual(1, len(snapshots), self.calls())
        snapshot = snapshots[0]
        self.assertIn("-r", snapshot)
        self.assertTrue(snapshot[-2].endswith("/root"), snapshot)
        self.assertIn("/@snapshots/dotfiles-", snapshot[-1])
        calls = self.calls()
        upgrade = next(index for index, call in enumerate(calls)
                       if call[:2] == ["sudo", "dnf"] and "upgrade" in call)
        self.assertLess(calls.index(snapshot), upgrade)
        notes = self.rollback_notes()
        text = notes.read_text()
        self.assertIn("mount -o subvolid=5", text)
        self.assertIn("@snapshots/dotfiles-", text)
        self.assertIn("Boot-critical packages changed: kernel-core", result.stderr)
        self.assertIn("Reboot before", result.stderr)
        self.assertTrue((notes.parent / "packages-before.txt").exists())
        self.assertFalse((notes.parent / "foreign-before.txt").exists())

    def test_snapshot_failure_aborts_before_the_full_upgrade(self):
        self.env["TEST_SNAPSHOT_FAIL"] = "1"
        result = self.run_packages()
        self.assert_failed(result, "Could not create the pre-upgrade Btrfs snapshot")
        self.assertFalse(any(call[:2] == ["sudo", "dnf"] and "upgrade" in call
                             for call in self.calls()))
        self.assertTrue(any(call[:2] == ["sudo", "umount"] for call in self.calls()))
        self.assertEqual([], list((self.state / "dotfiles/upgrades").glob("dotfiles-*")))

    def test_low_free_space_aborts_before_the_snapshot(self):
        self.env["TEST_LOW_SPACE"] = "1"
        result = self.run_packages()
        self.assert_failed(result, "at least 2048 MiB")
        self.assertFalse(self.snapshot_calls())
        self.assertFalse(any(call[:2] == ["sudo", "dnf"] and "upgrade" in call
                             for call in self.calls()))

    def test_non_btrfs_root_skips_snapshot_without_aborting(self):
        self.env["TEST_FSTYPE"] = "ext4"
        result = self.library("begin_system_upgrade\nend_system_upgrade\n")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("not btrfs", result.stderr)
        self.assertFalse(self.snapshot_calls())

    def test_dry_run_describes_the_snapshot_without_touching_the_host(self):
        result = self.library("begin_system_upgrade\n", dry_run=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Would verify Btrfs snapshot support", result.stderr)
        self.assertFalse([call for call in self.calls() if call[0] == "findmnt"])

    def test_pruning_keeps_the_configured_number_of_snapshots(self):
        parent = self.base / "snapshots"
        parent.mkdir()
        for day in range(1, 7):
            (parent / f"dotfiles-202601{day:02d}-000000").mkdir()
        result = self.library(
            f"export DOTFILES_SNAPSHOT_KEEP=3\n"
            f"prune_dotfiles_snapshots {shlex.quote(str(parent))} dotfiles-20260107-000000\n"
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        deleted = [call[-1].rsplit("/", 1)[-1] for call in self.calls()
                   if call[:3] == ["sudo", "btrfs", "subvolume"] and "delete" in call]
        self.assertEqual(["dotfiles-20260101-000000", "dotfiles-20260102-000000",
                          "dotfiles-20260103-000000", "dotfiles-20260104-000000"],
                         deleted)
