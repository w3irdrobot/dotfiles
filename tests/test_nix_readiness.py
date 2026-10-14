"""Daemon startup race fixtures with a fake clock; no real sleeps or native Nix."""

import subprocess
import unittest

import test_dotfiles


class NixReadiness(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        # Fixture.setUp redirects Linux paths, including the literal socket test.
        self.module = self.repo / "modules/nix.sh"
        # A file-backed clock survives the probe's command-substitution subshell.
        self.module.write_text(self.module.read_text().replace("SECONDS", "$(clock)"))
        self.events = self.base / "events"
        self.socket = self.base / "nix/var/nix/daemon-socket/socket"
        self.socket.parent.mkdir(parents=True)
        # Only the -S predicate is emulated. All readiness/control flow is real.
        self.module.write_text(self.module.read_text().replace(
            f"[[ -S {self.socket} ]]", '[[ $(clock) -ge $SOCKET_AT ]]'))

    def run_wait(self, *, socket_at=0, service_status=0, ping_status=0,
                 ping_cost=0, service_cost=0, dry_run=False, function="wait_nix_daemon_ready",
                 ping_error="fixture ping error", ping_ready_at=100):
        script = r'''set -euo pipefail
die() { printf '%s\n' "$*" >&2; exit 1; }
log() { printf '%s\n' "$*" >&2; }
printf '0\n' > "$CLOCK"
clock() { local now; read -r now < "$CLOCK"; printf '%s\n' "$now"; }
advance() { printf '%s\n' "$(( $(clock) + $1 ))" > "$CLOCK"; }
record() { printf '%s\n' "$*" >> "$EVENTS"; }
sleep() { record "sleep $*"; advance "$1"; }
timeout() {
    [[ $1 == --kill-after=1s && $2 == *s ]] || exit 97
    local limit=${2%s}
    shift 2
    case $1 in
        systemctl)
            [[ $* == 'systemctl is-active --quiet nix-daemon.service' ]] || exit 97
            record "service $limit $(clock)"
            advance "$SERVICE_COST"
            return "$SERVICE_STATUS"
            ;;
        /usr/bin/nix)
            [[ $LC_ALL == C ]] || exit 97
            [[ ${*:2} == '--extra-experimental-features nix-command flakes store ping --store daemon' ]] || exit 97
            record "ping $limit $(clock)"
            if ((PING_COST > limit)); then
                advance "$limit"
                return 124
            fi
            advance "$PING_COST"
            (($(clock) < PING_READY_AT)) || return 0
            if ((PING_STATUS)); then printf '%s\n' "$PING_ERROR" >&2; fi
            return "$PING_STATUS"
            ;;
        *) exit 97 ;;
    esac
}
preflight_stub() { record preflight; }
run() { if ((! DRY_RUN)); then record "start $*"; fi; }
source "$1"
if [[ $2 == setup_nix ]]; then
    preflight_nix() { preflight_stub; }
    nix_package_owned() { record ownership; }
    validate_nix() { record "validate $*"; }
fi
"$2"
printf 'ready at %s\n' "$(clock)"
'''
        env = self.env | {
            "EVENTS": str(self.events), "SOCKET_AT": str(socket_at),
            "SERVICE_STATUS": str(service_status), "PING_STATUS": str(ping_status),
            "PING_COST": str(ping_cost), "SERVICE_COST": str(service_cost),
            "DRY_RUN": str(int(dry_run)),
            "CLOCK": str(self.base / "clock"), "PING_ERROR": ping_error,
            "PING_READY_AT": str(ping_ready_at), "LC_ALL": "POSIX",
        }
        return subprocess.run(
            [test_dotfiles.BASH, "-c", script, "nix-readiness", str(self.module), function],
            cwd=self.repo, env=env, text=True, capture_output=True, timeout=5,
        )

    def calls(self):
        return self.events.read_text().splitlines() if self.events.exists() else []

    def test_socket_appears_one_second_after_active(self):
        result = self.run_wait(socket_at=1)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["service 1 0", "sleep 1", "service 1 1", "ping 5 1"], self.calls())

    def test_inactive_or_failed_service_stops_without_sleep_or_ping(self):
        for status in (1, 3, 4, 124, 137, 97):
            with self.subTest(status=status):
                self.events.unlink(missing_ok=True)
                result = self.run_wait(service_status=status)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("service is not active", result.stderr)
                self.assertEqual(["service 1 0"], self.calls())

    def test_missing_socket_exhausts_exact_deadline(self):
        result = self.run_wait(socket_at=100)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("30-second budget (32-second maximum)", result.stderr)
        self.assertEqual(30, self.calls().count("sleep 1"))
        self.assertEqual("service 1 29", self.calls()[-2])
        self.assertFalse(any(c.startswith("ping") for c in self.calls()))

    def test_ping_failure_is_not_hidden_or_retried(self):
        result = self.run_wait(ping_status=1)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("fixture ping error", result.stderr)
        self.assertIn("store ping failed (exit 1)", result.stderr)
        self.assertEqual(["service 1 0", "ping 5 0"], self.calls())

    def connection_error(self, reason="Connection refused", socket=None):
        return ("warning: 'ping' is a deprecated alias for 'info'\n"
                "Store URL: daemon\n"
                f"error: cannot connect to socket at '{socket or self.socket}': {reason}")

    def test_stale_socket_connection_refused_then_ready(self):
        result = self.run_wait(ping_status=1, ping_error=self.connection_error(), ping_ready_at=1)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["service 1 0", "ping 5 0", "sleep 1", "service 1 1", "ping 5 1"],
                         self.calls())

    def test_socket_disappearing_during_ping_then_ready(self):
        result = self.run_wait(ping_status=1,
                               ping_error=self.connection_error("No such file or directory"),
                               ping_ready_at=1)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("ping 5 1", self.calls()[-1])

    def test_connection_diagnostic_with_other_exit_status_is_not_retried(self):
        result = self.run_wait(ping_status=2, ping_error=self.connection_error())
        self.assertNotEqual(0, result.returncode)
        self.assertIn("store ping failed (exit 2)", result.stderr)
        self.assertEqual(["service 1 0", "ping 5 0"], self.calls())

    def test_wrong_socket_permission_and_configuration_errors_are_not_retried(self):
        errors = [self.connection_error(socket="/wrong/socket"),
                  self.connection_error("Permission denied"),
                  "error: invalid Nix configuration",
                  self.connection_error() + "\nerror: invalid Nix configuration"]
        for error in errors:
            with self.subTest(error=error):
                self.events.unlink(missing_ok=True)
                result = self.run_wait(ping_status=1, ping_error=error)
                self.assertNotEqual(0, result.returncode)
                self.assertIn(error, result.stderr)
                self.assertIn("store ping failed (exit 1)", result.stderr)
                self.assertEqual(["service 1 0", "ping 5 0"], self.calls())

    def test_repeated_known_connection_errors_exhaust_shared_deadline(self):
        for reason in ("Connection refused", "No such file or directory"):
            with self.subTest(reason=reason):
                self.events.unlink(missing_ok=True)
                error = self.connection_error(reason)
                result = self.run_wait(ping_status=1, ping_error=error)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("30-second budget (32-second maximum)", result.stderr)
                self.assertIn(error, result.stderr)
                self.assertEqual(30, self.calls().count("sleep 1"))
                self.assertEqual("ping 1 29", self.calls()[-2])

    def test_connection_errors_with_slow_probes_consume_same_budget(self):
        result = self.run_wait(ping_status=1, ping_cost=4, ping_error=self.connection_error())
        self.assertNotEqual(0, result.returncode)
        self.assertIn("readiness timed out", result.stderr)
        self.assertEqual([f"ping {min(5, 30 - t)} {t}" for t in range(0, 30, 5)],
                         [c for c in self.calls() if c.startswith("ping")])

    def test_unexpected_timeout_wrapper_error_is_not_retried(self):
        result = self.run_wait(ping_status=125)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("exit 125", result.stderr)
        self.assertEqual(["service 1 0", "ping 5 0"], self.calls())

    def test_hung_pings_share_budget_and_last_probe_is_clamped(self):
        result = self.run_wait(ping_cost=100)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("readiness timed out", result.stderr)
        self.assertEqual(["ping 5 0", "ping 5 6", "ping 5 12", "ping 5 18", "ping 5 24"],
                         [c for c in self.calls() if c.startswith("ping")])
        # Spend time checking service too: final probe has only one second left.
        self.events.unlink()
        result = self.run_wait(ping_cost=100, service_cost=1)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("ping 1 29", self.calls()[-1])

    def test_slow_success_within_deadline_is_ready(self):
        result = self.run_wait(socket_at=26, ping_cost=3)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ready at 29", result.stdout)
        self.assertEqual("ping 4 26", self.calls()[-1])

    def test_success_after_deadline_is_not_accepted(self):
        result = self.run_wait(socket_at=29, ping_cost=1)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("readiness timed out", result.stderr)

    def test_service_check_consumes_remaining_budget_before_ping(self):
        result = self.run_wait(socket_at=29, service_cost=3)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(any(c.startswith("ping") for c in self.calls()))

    def test_dry_run_helper_executes_no_commands_or_sleeps(self):
        result = self.run_wait(dry_run=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.calls())

    def test_setup_waits_between_start_and_strict_bootstrap_validation(self):
        result = self.run_wait(socket_at=1, function="setup_nix")
        self.assertEqual(0, result.returncode, result.stderr)
        calls = self.calls()
        self.assertLess(calls.index("start sudo systemctl enable --now nix-daemon.service"),
                        calls.index("service 1 0"))
        self.assertEqual("validate bootstrap", calls[-1])

    def test_setup_readiness_failure_never_reaches_validation(self):
        result = self.run_wait(ping_status=1, function="setup_nix")
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(any(c.startswith("validate") for c in self.calls()))

    def test_setup_dry_run_never_enters_readiness(self):
        result = self.run_wait(dry_run=True, function="setup_nix")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["preflight"], self.calls())


if __name__ == "__main__":
    unittest.main()
