#!/usr/bin/python3
"""Node-local Cargo telemetry; symlink as cargo, nix and cargo-metrics-enter.

No build output is intercepted. Only the standard library is required on Linux.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid


SOURCE = Path(__file__).resolve()
SAFE_VALUE = re.compile(r"[A-Za-z0-9_.,/+:-]{1,256}\Z")
BUILD_OPTIONS = {
    "--package", "-p", "--features", "-F", "--target", "--profile", "--jobs", "-j",
}
BUILD_SWITCHES = {
    "--release", "--workspace", "--all", "--all-targets", "--all-features",
    "--no-default-features", "--locked", "--frozen", "--offline", "--lib",
    "--bins", "--tests", "--examples", "--benches", "--no-run",
}


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def resolve_tool(name):
    """Keep PATH order, excluding our own shims (including alternate symlinks)."""
    for directory in os.environ.get("PATH", os.defpath).split(os.pathsep):
        candidate = Path(directory or ".") / name
        try:
            if candidate.resolve() != SOURCE and candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate.absolute())
        except OSError:
            continue
    return None


def build_arguments(args):
    """Never record arbitrary args, --config values or arguments after --."""
    command = None
    toolchain = None
    options = []
    i = 0
    if args and args[0].startswith("+"):
        if SAFE_VALUE.fullmatch(args[0][1:]):
            toolchain = args[0][1:]
        i += 1
    # Cargo global options may precede the command. Only identify known commands;
    # arbitrary external subcommand names can themselves contain private data.
    commands = {
        "build", "b", "check", "c", "test", "t", "run", "r", "bench", "doc",
        "rustc", "rustdoc", "clippy", "fmt", "metadata", "clean", "fetch",
        "update", "generate-lockfile", "tree", "version", "help", "install",
        "uninstall", "package", "publish", "verify-project", "locate-project",
    }
    while i < len(args):
        arg = args[i]
        if arg == "--":
            break
        if arg in ("--config", "--manifest-path", "--lockfile-path", "-C", "-Z"):
            i += 2
            continue
        if arg in commands and command is None:
            command = arg
        elif arg in BUILD_SWITCHES:
            options.append(arg)
        elif arg in BUILD_OPTIONS:
            if i + 1 < len(args) and SAFE_VALUE.fullmatch(args[i + 1]):
                options.append([arg, args[i + 1]])
            i += 1
        elif "=" in arg:
            key, value = arg.split("=", 1)
            if key in BUILD_OPTIONS and SAFE_VALUE.fullmatch(value):
                options.append([key, value])
        i += 1
    return {"command": command or "other", "toolchain_selector": toolchain, "options": options}


def git_context():
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel", "--git-common-dir", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=0.3,
            env=env, check=False, stdin=subprocess.DEVNULL,
        )
        lines = result.stdout.decode(errors="replace").splitlines()
        if result.returncode == 0 and len(lines) == 3:
            return {"worktree": lines[0], "common_dir": str(Path(lines[1]).absolute()), "commit": lines[2]}
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def configuration():
    paths = {}
    for key in (
        "CARGO_BUILD_BUILD_DIR", "CARGO_BUILD_TARGET_DIR", "CARGO_TARGET_DIR",
        "CARGO_HOME", "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER", "RUSTC",
    ):
        value = os.environ.get(key)
        if value:
            paths[key] = value
    settings = {}
    for key in ("CARGO_INCREMENTAL", "CARGO_BUILD_JOBS"):
        value = os.environ.get(key)
        if value and SAFE_VALUE.fullmatch(value):
            settings[key] = value
    hashes = {}
    # Flags can contain private values. Fingerprint them; never store the values.
    for key in ("RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "RUSTDOCFLAGS"):
        if key in os.environ:
            hashes[key] = hashlib.sha256(os.environ[key].encode()).hexdigest()
    return {"environment_paths": paths, "environment_settings": settings, "flag_sha256": hashes}


def open_record(invocation_id, started):
    root = Path(os.environ.get("CARGO_METRICS_DIR", str(Path.home() / ".cache/build-metrics/cargo")))
    directory = root / started[:10]
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.mkdir(exist_ok=True, mode=0o700)
    # Refuse a public or foreign destination rather than changing its permissions.
    for path in (root, directory):
        st = path.stat()
        if path.is_symlink() or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise OSError("metrics destination must be private and owned")
    return os.open(
        directory / (invocation_id + ".jsonl"),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600,
    )


def write_record(fd, record):
    data = (json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
    while data:
        n = os.write(fd, data)
        if n <= 0:
            raise OSError("short metrics write")
        data = data[n:]


def exec_tool(tool, args, env=None):
    os.execve(tool, [tool, *args], os.environ if env is None else env)


def nix(tool, args):
    """Restore shims *after* Nix constructs PATH, without changing its selection."""
    subcommand = next((i for i, arg in enumerate(args) if arg in ("develop", "shell")), None)
    if subcommand is not None:
        for i in range(subcommand + 1, len(args)):
            arg = args[i]
            if arg in ("-c", "--command") and i + 1 < len(args):
                args = [*args[:i + 1], str(SOURCE.parent / "bin/cargo-metrics-enter"), *args[i + 1:]]
                break
            if arg.startswith("--command="):
                args = [*args[:i], "--command", str(SOURCE.parent / "bin/cargo-metrics-enter"), arg.split("=", 1)[1], *args[i + 1:]]
                break
    exec_tool(tool, args)


def enter(args):
    if not args:
        return 127
    os.environ["PATH"] = str(SOURCE.parent / "bin") + os.pathsep + os.environ.get("PATH", os.defpath)
    tool = shutil.which(args[0])
    if tool is None:
        print(f"cargo-metrics: command not found: {args[0]}", file=sys.stderr)
        return 127
    exec_tool(tool, args[1:])


def measure(tool, args):
    setup_start = time.monotonic()
    invocation_id = str(uuid.uuid4())
    started = timestamp()
    fd = None
    try:
        fd = open_record(invocation_id, started)
        record = {
            "schema_version": 1, "event": "start", "invocation_id": invocation_id,
            "parent_invocation_id": os.environ.get("CARGO_METRICS_PARENT_ID"),
            "timestamp": started, "pid": os.getpid(), "hostname": os.uname().nodename,
            "cwd": os.getcwd(), "cargo_executable": tool,
            "rustc_executable": resolve_tool("rustc"), "git": git_context(),
            "arguments": build_arguments(args), "configuration": configuration(),
            "load_average": os.getloadavg(), "logical_cpus": os.cpu_count(),
        }
        write_record(fd, record)
    except Exception:
        if fd is not None:
            os.close(fd)
        # Telemetry never prevents Cargo from running, including broken storage.
        exec_tool(tool, args)

    env = dict(os.environ, CARGO_METRICS_PARENT_ID=invocation_id)
    started_monotonic = time.monotonic()
    old_handlers = {}
    child = None

    def forward(signum, _frame):
        # Foreground terminal Ctrl-C/Ctrl-\ already reaches Cargo in our shared
        # process group. Forwarding it again can turn graceful cancellation into
        # a second interrupt. Non-terminal callers can still signal the launcher.
        if signum in (signal.SIGINT, signal.SIGQUIT) and os.isatty(0):
            try:
                if os.tcgetpgrp(0) == os.getpgrp():
                    return
            except OSError:
                pass
        if child:
            try:
                os.kill(child, signum)
            except ProcessLookupError:
                pass

    forwarded = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)
    # Child shares the caller's process group and inherited terminal descriptors.
    # Block signals over fork/handler setup so an early signal isn't lost.
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, forwarded)
    try:
        child = os.fork()
    except OSError:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        os.close(fd)
        exec_tool(tool, args)
    if child == 0:
        for signum in forwarded:
            signal.signal(signum, signal.SIG_DFL)
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        try:
            exec_tool(tool, args, env)
        except OSError:
            os.write(2, b"cargo-metrics: could not execute Cargo\n")
            os._exit(126)
    for signum in forwarded:
        old_handlers[signum] = signal.signal(signum, forward)
    signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    try:
        while True:
            try:
                _, status, usage = os.wait4(child, 0)
                break
            except InterruptedError:
                continue
        elapsed = time.monotonic() - started_monotonic
        try:
            write_record(fd, {
                "schema_version": 1, "event": "finish", "invocation_id": invocation_id,
                "timestamp": timestamp(), "elapsed_seconds": elapsed,
                "setup_seconds": started_monotonic - setup_start,
                "exit_code": os.WEXITSTATUS(status) if os.WIFEXITED(status) else None,
                "signal": os.WTERMSIG(status) if os.WIFSIGNALED(status) else None,
                "resources": {
                    "user_cpu_seconds": usage.ru_utime, "system_cpu_seconds": usage.ru_stime,
                    "max_rss_kib": usage.ru_maxrss,
                    "filesystem_input_operations": usage.ru_inblock,
                    "filesystem_output_operations": usage.ru_oublock,
                    "voluntary_context_switches": usage.ru_nvcsw,
                    "involuntary_context_switches": usage.ru_nivcsw,
                },
            })
        except Exception:
            pass
    finally:
        os.close(fd)
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
    if os.WIFSIGNALED(status):
        signum = os.WTERMSIG(status)
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)
        return 128 + signum
    return os.WEXITSTATUS(status)


def main():
    name = Path(sys.argv[0]).name
    args = sys.argv[1:]
    if name == "cargo-metrics-enter":
        return enter(args)
    if name not in ("cargo", "nix"):
        print("Install this file using the documented cargo/nix symlinks.", file=sys.stderr)
        return 2
    tool = resolve_tool(name)
    if tool is None:
        print(f"{name}: command not found (no underlying executable on PATH)", file=sys.stderr)
        return 127
    if os.environ.get("CARGO_METRICS_DISABLE") == "1":
        exec_tool(tool, args)
    if name == "nix":
        nix(tool, args)
    return measure(tool, args)


if __name__ == "__main__":
    sys.exit(main())
