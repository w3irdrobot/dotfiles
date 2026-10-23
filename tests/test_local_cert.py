"""Certificate output permissions in disposable working directories."""

import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "stow/openssl/.local/bin/generate_local_cert"


class LocalCert(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="local-cert-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        mock = self.bin / "openssl"
        mock.write_text(
            f"#!{sys.executable}\nimport pathlib, sys\n"
            "pathlib.Path('called').touch()\n"
            "args = sys.argv[1:]\n"
            "for flag in ('-out', '-keyout'):\n"
            "    pathlib.Path(args[args.index(flag)+1]).write_text('fixture-only')\n"
        )
        mock.chmod(0o755)

    def run_cert(self):
        return subprocess.run(
            [shutil.which("bash"), "--noprofile", "--norc", "-c",
             'umask 022; bash "$1"', "cert-test", str(SCRIPT)],
            cwd=self.root, env={"PATH": str(self.bin) + os.pathsep + os.environ["PATH"]},
            capture_output=True, text=True, timeout=15,
        )

    def test_restricts_new_outputs_with_permissive_caller_umask(self):
        result = self.run_cert()
        self.assertEqual(0, result.returncode, result.stderr)
        for name in ("localhost.key", "localhost.crt"):
            self.assertEqual(0o600, stat.S_IMODE((self.root / name).stat().st_mode))

    def test_existing_files_and_dangling_links_are_refused_without_execution(self):
        for name in ("localhost.key", "localhost.crt"):
            path = self.root / name
            for link in (False, True):
                with self.subTest(name=name, link=link):
                    if link:
                        path.symlink_to(self.root / "absent")
                    else:
                        path.write_text("existing-user-data")
                        path.chmod(0o644)
                    result = self.run_cert()
                    self.assertNotEqual(0, result.returncode)
                    self.assertFalse((self.root / "called").exists())
                    if link:
                        self.assertTrue(path.is_symlink())
                    else:
                        self.assertEqual("existing-user-data", path.read_text())
                        self.assertEqual(0o644, stat.S_IMODE(path.stat().st_mode))
                    path.unlink()


if __name__ == "__main__":
    unittest.main()
