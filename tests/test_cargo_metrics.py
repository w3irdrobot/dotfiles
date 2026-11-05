"""Disposable Linux fixtures: no real builds, toolchain installs or home changes."""

import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/cargo_metrics.py"
FAKE_CARGO = '''#!/usr/bin/python3
import json, os, signal, subprocess, sys, time
mode = os.environ.get("FIXTURE_MODE", "normal")
if mode == "sleep":
    open(os.environ["READY_FILE"], "w").close()
    time.sleep(30)
elif mode == "interrupt":
    interrupted = False
    def handler(signum, frame):
        global interrupted
        with open(os.environ["SIGNAL_FILE"], "a") as f:
            f.write("interrupt\\n")
        interrupted = True
    signal.signal(signal.SIGINT, handler)
    open(os.environ["READY_FILE"], "w").close()
    while not interrupted:
        time.sleep(0.01)
    time.sleep(0.2)
elif mode == "signal":
    os.kill(os.getpid(), signal.SIGTERM)
elif mode == "nested":
    subprocess.run(["cargo", "check"], env=dict(os.environ, FIXTURE_MODE="normal"), check=True)
elif mode == "tty":
    print(json.dumps([os.isatty(i) for i in range(3)]), flush=True)
elif mode == "stdin":
    sys.stdout.buffer.write(sys.stdin.buffer.read())
    sys.stderr.write("fixture stderr\\n")
else:
    print(json.dumps(sys.argv[1:]))
sys.exit(int(os.environ.get("FIXTURE_EXIT", "0")))
'''
FAKE_NIX = '''#!/usr/bin/python3
import json, os, sys
args = sys.argv[1:]
if "-c" in args or "--command" in args:
    i = args.index("-c") if "-c" in args else args.index("--command")
    command = args[i+1:]
    os.environ["PATH"] = os.environ["REAL_BIN"] + ":" + os.environ["PATH"]
    os.execvp(command[0], command)
print(json.dumps(args))
'''


class CargoMetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / "install"
        self.bin = self.install / "bin"
        self.bin.mkdir(parents=True)
        self.real = self.root / "real"
        self.real.mkdir()
        launcher = self.install / "cargo_metrics.py"
        shutil.copyfile(SOURCE, launcher)
        launcher.chmod(0o755)
        for name in ("cargo", "nix", "cargo-metrics-enter"):
            (self.bin / name).symlink_to(launcher)
        for name, content in (("cargo", FAKE_CARGO), ("nix", FAKE_NIX)):
            path = self.real / name
            path.write_text(content)
            path.chmod(0o755)
        self.metrics = self.root / "metrics"
        self.env = dict(
            os.environ, PATH=f"{self.bin}:{self.real}:/usr/bin:/bin",
            CARGO_METRICS_DIR=str(self.metrics), REAL_BIN=str(self.real),
        )
        for key in ("CARGO_METRICS_DISABLE", "CARGO_METRICS_PARENT_ID", "FIXTURE_MODE", "FIXTURE_EXIT"):
            self.env.pop(key, None)

    def run_tool(self, args, **kwargs):
        return subprocess.run(
            args, env=self.env, cwd=self.root, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=10, **kwargs,
        )

    def records(self):
        return [json.loads(line) for p in sorted(self.metrics.glob("*/*.jsonl")) for line in p.read_text().splitlines()]

    def test_argument_and_exit_passthrough(self):
        self.env["FIXTURE_EXIT"] = "37"
        args = ["+some-toolchain", "test", "--features", "a,b", "--", "spaces and symbols $*", ""]
        result = self.run_tool(["cargo", *args])
        self.assertEqual(result.returncode, 37)
        self.assertEqual(json.loads(result.stdout), args)
        self.assertEqual(result.stderr, b"")
        start, finish = self.records()
        self.assertEqual(start["arguments"]["toolchain_selector"], "some-toolchain")
        self.assertEqual(start["arguments"]["options"], [["--features", "a,b"]])
        self.assertEqual(finish["exit_code"], 37)
        self.assertGreaterEqual(finish["elapsed_seconds"], 0)
        self.assertGreater(finish["resources"]["max_rss_kib"], 0)

    def test_streams_are_inherited(self):
        self.env["FIXTURE_MODE"] = "stdin"
        result = self.run_tool(["cargo", "run"], input=b"hello\x00world\n")
        self.assertEqual(result.stdout, b"hello\x00world\n")
        self.assertEqual(result.stderr, b"fixture stderr\n")

    def test_tty_descriptors_are_not_replaced_by_pipes(self):
        self.env["FIXTURE_MODE"] = "tty"
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(["cargo", "run"], env=self.env, cwd=self.root, stdin=slave, stdout=slave, stderr=slave)
            self.assertTrue(select.select([master], [], [], 5)[0])
            self.assertEqual(json.loads(os.read(master, 4096).strip()), [True, True, True])
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            os.close(master)
            os.close(slave)

    def test_private_permissions_and_no_secret_logging(self):
        secret = "secret-sentinel-never-record"
        self.env["RUSTFLAGS"] = "--cfg=" + secret
        self.env["UNRELATED_TOKEN"] = secret
        self.run_tool(["cargo", "test", "--config", "token=" + secret, "--", secret])
        files = list(self.metrics.glob("*/*.jsonl"))
        self.assertEqual(len(files), 1)
        self.assertNotIn(secret, files[0].read_text())
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(files[0].parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.metrics.stat().st_mode & 0o777, 0o700)
        self.assertIn("RUSTFLAGS", self.records()[0]["configuration"]["flag_sha256"])

    def test_unavailable_metrics_fails_open(self):
        self.metrics.write_text("not a directory")
        result = self.run_tool(["cargo", "check"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), ["check"])
        self.assertEqual(result.stderr, b"")

    def test_public_destination_fails_open(self):
        self.metrics.mkdir(mode=0o755)
        result = self.run_tool(["cargo", "build"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.records(), [])

    def test_disabled_does_not_create_storage(self):
        self.env["CARGO_METRICS_DISABLE"] = "1"
        self.assertEqual(self.run_tool(["cargo", "check"]).returncode, 0)
        self.assertFalse(self.metrics.exists())

    def test_no_underlying_cargo(self):
        (self.real / "cargo").unlink()
        self.env["PATH"] = str(self.bin)
        result = self.run_tool(["cargo", "build"])
        self.assertEqual(result.returncode, 127)
        self.assertFalse(self.metrics.exists())

    def test_multiple_wrapper_path_entries_do_not_recurse(self):
        self.env["PATH"] = f"{self.bin}:{self.bin}:{self.real}:/usr/bin:/bin"
        self.assertEqual(self.run_tool(["cargo", "build"]).returncode, 0)
        self.assertEqual(len(self.records()), 2)

    def test_nested_cargo_has_parent_link(self):
        self.env["FIXTURE_MODE"] = "nested"
        self.assertEqual(self.run_tool(["cargo", "clippy"]).returncode, 0)
        starts = [r for r in self.records() if r["event"] == "start"]
        self.assertEqual(len(starts), 2)
        parent = next(r for r in starts if not r["parent_invocation_id"])
        child = next(r for r in starts if r["parent_invocation_id"])
        self.assertEqual(child["parent_invocation_id"], parent["invocation_id"])

    def test_parallel_invocations_do_not_interleave_records(self):
        processes = [subprocess.Popen(["cargo", "check"], env=self.env, cwd=self.root, stdout=subprocess.DEVNULL) for _ in range(6)]
        for process in processes:
            self.assertEqual(process.wait(timeout=10), 0)
        self.assertEqual(len(self.records()), 12)
        self.assertEqual(len({r["invocation_id"] for r in self.records()}), 6)

    def test_child_signal_is_preserved(self):
        self.env["FIXTURE_MODE"] = "signal"
        self.assertEqual(self.run_tool(["cargo", "build"]).returncode, -signal.SIGTERM)
        self.assertEqual(self.records()[-1]["signal"], signal.SIGTERM)

    def test_parent_signal_reaches_child(self):
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            with self.subTest(signal=signum):
                ready = self.root / f"ready-{signum}"
                self.env.update(FIXTURE_MODE="sleep", READY_FILE=str(ready))
                process = subprocess.Popen(
                    ["cargo", "build"], env=self.env, cwd=self.root,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                try:
                    deadline = time.monotonic() + 5
                    while not ready.exists() and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertTrue(ready.exists())
                    process.send_signal(signum)
                    self.assertEqual(process.wait(timeout=5), -signum)
                    finishes = [r for r in self.records() if r["event"] == "finish"]
                    self.assertTrue(any(r["signal"] == signum for r in finishes))
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()

    def test_nix_commands_keep_selected_cargo_and_record_metrics(self):
        for command in (["develop", "-c"], ["shell", "--command"], ["develop", "--command=cargo"]):
            args = command + (["cargo"] if not command[-1].startswith("--command=") else []) + ["check"]
            result = self.run_tool(["nix", *args])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), ["check"])
        starts = [r for r in self.records() if r["event"] == "start"]
        self.assertEqual(len(starts), 3)
        self.assertTrue(all(r["cargo_executable"] == str(self.real / "cargo") for r in starts))

    def test_other_nix_commands_are_unchanged(self):
        args = ["build", ".#package", "--no-link"]
        result = self.run_tool(["nix", *args])
        self.assertEqual(json.loads(result.stdout), args)
        self.assertFalse(self.metrics.exists())

    def test_terminal_ctrl_c_is_not_forwarded_twice(self):
        ready = self.root / "ready"
        signals = self.root / "signals"
        env = dict(self.env, FIXTURE_MODE="interrupt", READY_FILE=str(ready), SIGNAL_FILE=str(signals))
        pid, master = pty.fork()
        if pid == 0:
            os.chdir(self.root)
            os.execvpe("cargo", ["cargo", "build"], env)
        reaped = False
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(ready.exists())
            os.write(master, b"\x03")
            while time.monotonic() < deadline:
                waited, status = os.waitpid(pid, os.WNOHANG)
                if waited:
                    reaped = True
                    break
                time.sleep(0.01)
            self.assertTrue(reaped, "terminal cancellation did not finish")
            self.assertEqual(os.waitstatus_to_exitcode(status), 0)
            self.assertEqual(signals.read_text(), "interrupt\n")
            self.assertEqual(self.records()[-1]["exit_code"], 0)
        finally:
            if not reaped:
                os.killpg(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(master)

    def test_finish_write_failure_does_not_change_cargo_result(self):
        driver = self.root / "driver.py"
        driver.write_text(
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('metrics', {str(self.install / 'cargo_metrics.py')!r})\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(m)\n"
            "write = m.write_record\n"
            "def failing(fd, record):\n"
            "    if record['event'] == 'finish': raise OSError('disk full')\n"
            "    return write(fd, record)\n"
            "m.write_record = failing\n"
            "sys.argv = ['cargo', 'check']\n"
            "sys.exit(m.main())\n"
        )
        self.env["FIXTURE_EXIT"] = "37"
        result = self.run_tool(["/usr/bin/python3", str(driver)])
        self.assertEqual(result.returncode, 37)
        self.assertEqual(json.loads(result.stdout), ["check"])
        self.assertEqual(result.stderr, b"")
        self.assertEqual([r["event"] for r in self.records()], ["start"])


if __name__ == "__main__":
    unittest.main()
