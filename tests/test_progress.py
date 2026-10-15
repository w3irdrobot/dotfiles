"""Human-readable progress and follow-ups, without live installs or credentials."""

import shlex
import shutil
import subprocess
import unittest

import test_dotfiles


class Progress(unittest.TestCase):
    setUp_fixture = test_dotfiles.Fixture.setUp
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    run_cli = test_dotfiles.Fixture.run_cli
    assert_failed = test_dotfiles.Fixture.assert_failed
    minimal_modules = test_dotfiles.Fixture.minimal_modules
    local_git = test_dotfiles.Fixture.local_git
    git_fixture = test_dotfiles.Fixture.git_fixture

    def setUp(self):
        self.setUp_fixture()
        self.sentinel = "FAKE_PRIVATE_ENV_SENTINEL_DO_NOT_LOG_81f2"
        for name in ("EXA_API_KEY", "GITHUB_MCP_TOKEN", "MAPLE_API_KEY"):
            self.env[name] = self.sentinel
        self.mock("stow", "sys.exit(0)")
        self.mock("sudo", "sys.exit(0)")
        self.mock("pacman", """if '-Qq' in sys.argv:
    sys.exit(1)
sys.exit(0 if '-Si' in sys.argv else 97)""")

    def assert_ordered(self, text, phrases):
        position = -1
        for phrase in phrases:
            found = text.find(phrase, position + 1)
            self.assertGreater(found, position, f"Missing/out-of-order {phrase!r}:\n{text}")
            position = found

    def assert_no_secrets(self, result):
        self.assertNotIn(self.sentinel, result.stdout + result.stderr)

    def helper(self, body, modules=()):
        script = 'set -euo pipefail; ROOT=$1; source "$ROOT/lib/dotfiles.sh"\n'
        script += "DRY_RUN=0; GROUPS_CSV=core,ai,desktop; MODULES_CSV=''; DOCKER_GROUP=0\n"
        script += "MODULES=(" + " ".join(map(shlex.quote, modules)) + ")\n"
        script += body
        return subprocess.run([test_dotfiles.BASH, "-c", script, "progress-fixture", str(self.repo)],
                              cwd=self.repo, env=self.env, text=True,
                              capture_output=True, timeout=20)

    def test_install_logs_ordered_phases_and_scoped_followups(self):
        self.minimal_modules()
        result = self.run_cli("install", "--groups", "cloud")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_ordered(result.stderr, (
            "Starting install", "Platform validation:", "Selected groups: cloud",
            "Selected modules (1): fixture-cloud", "Preflight:", "Package preflight:",
            "Database refresh:", "Repository policy:", "Package sources:",
            "Official package targets", "AUR package targets: none", "Full upgrade:",
            "AUR setup:", "Module configuration: fixture-cloud",
            "Preparing module: fixture-cloud", "Module preparation finished: fixture-cloud",
            "Configuration links: verifying", "Config link preparation: fixture-cloud",
            "Config links ready: fixture-cloud", "Dotfiles launcher:", "Complete: install",
        ))
        self.assertIn("Next steps:", result.stdout)
        self.assertNotIn("Next steps:", result.stderr)
        for text in ("nono pull", "EXA_API_KEY", "Bitwarden", "mullvad-daemon", "variables.sh"):
            self.assertNotIn(text, result.stdout)
        self.assert_no_secrets(result)

    def test_failed_module_preserves_exit_status_and_has_no_success_or_instructions(self):
        self.minimal_modules()
        (self.repo / "modules/fixture-cloud.sh").write_text(
            "#!/usr/bin/env bash\nprintf 'fixture module failed\n' >&2\nexit 43\n"
        )
        result = self.run_cli("install", "--groups", "cloud")
        self.assertEqual(43, result.returncode, result.stderr)
        self.assertIn("Failure during Module configuration: fixture-cloud (exit 43)", result.stderr)
        self.assertNotIn("Module preparation finished: fixture-cloud", result.stderr)
        self.assertNotIn("Complete:", result.stderr)
        self.assertNotIn("Next steps:", result.stdout + result.stderr)
        self.assertFalse((self.home / ".local/bin/dotfiles").exists())
        self.assert_no_secrets(result)

    def test_failed_stow_has_config_phase_context_and_preserves_status(self):
        self.minimal_modules()
        self.mock("stow", "sys.exit(0 if '--simulate' in sys.argv else 29)")
        result = self.run_cli("link", "--groups", "cloud")
        self.assertEqual(29, result.returncode, result.stderr)
        self.assertIn("Failure during Configuration links: applying selected packages (exit 29)", result.stderr)
        self.assertNotIn("Complete:", result.stderr)
        self.assertNotIn("Next steps:", result.stdout)
        self.assert_no_secrets(result)

    def test_initialization_failure_has_bounded_context_without_followups(self):
        (self.repo / "lib/dotfiles.sh").unlink()
        result = self.run_cli("link")
        self.assertEqual(1, result.returncode)
        self.assertIn("Failure during CLI initialization (exit 1)", result.stderr)
        self.assertNotIn("Next steps:", result.stdout)
        self.assert_no_secrets(result)

    def test_dry_run_is_plan_only_without_effects_or_post_install_instructions(self):
        self.minimal_modules()
        before = self.snapshot()
        result = self.run_cli("install", "--groups", "cloud", "--dry-run")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertIn("PLAN ONLY:", result.stdout)
        self.assertIn("PLAN ONLY:", result.stderr)
        self.assertNotIn("Complete:", result.stderr)
        self.assertNotIn("Next steps:", result.stdout)
        self.assertFalse(any(call[0] in ("sudo", "paru", "wget", "curl", "chmod") for call in self.calls()))
        self.assert_no_secrets(result)

    def test_selected_followups_are_private_manual_and_nonoverwriting(self):
        selected = ("bash", "opencode", "git", "ssh", "bitwarden", "nono", "nix", "mullvad", "bitcoin", "electrs")
        variables = self.repo / "local/bash/variables.sh"
        variables.parent.mkdir(parents=True)
        variables.write_text(self.sentinel)
        result = self.helper('DOCKER_GROUP=1; print_next_steps install\n', selected)
        self.assertEqual(0, result.returncode, result.stderr)
        text = result.stdout
        for phrase in ("new terminal", "~/.bash_profile", "~/.bashrc", "local/bash/variables.sh",
                       "examples/local-variables.sh", "mkdir -p", "cp -n", "! -e", "! -L",
                       "chmod 0600", "EXA_API_KEY", "GITHUB_MCP_TOKEN", "MAPLE_API_KEY",
                       "~/.gitconfig_local", "native Bitwarden", "~/.bitwarden-ssh-agent.sock",
                        "Nono and its pinned OpenCode pack are ready", "Log out and back in",
                       "mullvad-daemon.service", "Tor", "electrs", "per-project flakes"):
            self.assertIn(phrase, text)
        self.assertIn("instructions only", text)
        self.assertIn("No personal credentials", text)
        self.assertEqual(self.sentinel, variables.read_text())
        self.assertEqual({}, self.snapshot())
        self.assertEqual([], self.calls())
        self.assert_no_secrets(result)

    def test_link_does_not_claim_nono_pack_was_installed(self):
        result = self.helper('print_next_steps link\n', ("nono",))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("linking and dry-runs do not install the pack", result.stdout)
        self.assertNotIn("pack are ready", result.stdout)
        self.assertNotIn("nono pull", result.stdout)

    def test_provider_followups_without_managed_bash_do_not_claim_exports_are_loaded(self):
        result = self.helper('print_next_steps link\n', ("opencode",))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Prefer credential injection", result.stdout)
        self.assertNotIn("private export setup", result.stdout)
        self.assertIn("Linking did not install packages", result.stdout)
        self.assertNotIn("mkdir -p", result.stdout)
        self.assertNotIn("nono pull", result.stdout)
        self.assert_no_secrets(result)

    def test_update_followups_are_short_and_keep_selections_explicit(self):
        result = self.helper('MODULES_CSV=opencode; print_next_steps update configs\n',
                             ("bash", "opencode", "nono", "bitwarden"))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Restart affected apps", result.stdout)
        self.assertIn("Config updates do not install new dependencies", result.stdout)
        self.assertIn("repeat --groups core,ai,desktop --modules opencode", result.stdout)
        self.assertNotIn("EXA_API_KEY", result.stdout)
        self.assertNotIn("nono pull", result.stdout)
        self.assertLessEqual(len(result.stdout.splitlines()), 6)
        self.assert_no_secrets(result)

    def test_repository_origin_error_does_not_echo_credentials_embedded_in_url(self):
        self.git_fixture()
        self.local_git("remote", "set-url", "origin",
                       f"https://user:{self.sentinel}@example.invalid/private.git")
        result = self.run_cli("update", "configs")
        self.assert_failed(result, "unexpected origin")
        self.assertIn("Inspect origin locally", result.stderr)
        self.assert_no_secrets(result)
        self.assertNotIn("Next steps:", result.stdout)

    def test_bootstrap_origin_error_does_not_echo_url_userinfo(self):
        self.git_fixture()
        self.local_git("remote", "set-url", "origin",
                       f"https://user:{self.sentinel}@example.invalid/private.git")
        self.destination.parent.mkdir(parents=True)
        shutil.copytree(self.repo, self.destination, symlinks=True)
        result = self.run_cli(bootstrap=True)
        self.assert_failed(result, "unexpected origin")
        self.assertIn("Inspect origin locally", result.stderr)
        self.assert_no_secrets(result)
        self.assertNotIn("Complete:", result.stderr)

    def test_source_library_is_quiet_and_does_not_change_caller_options_or_traps(self):
        script = """ROOT=$1
before_options=$-
before_traps=$(trap -p)
source "$ROOT/lib/dotfiles.sh"
[[ $- == "$before_options" && $(trap -p) == "$before_traps" ]]
"""
        result = subprocess.run([test_dotfiles.BASH, "-c", script, "source-fixture", str(self.repo)],
                                cwd=self.repo, env=self.env, text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout + result.stderr)

    def bootstrap_clone(self, dispatch_status=0):
        dispatcher = self.repo / "bin/setup"
        dispatcher.write_text(f"#!/usr/bin/env bash\nexit {dispatch_status}\n")
        self.mock("git", f"""import shutil
if 'check-ref-format' in sys.argv:
    sys.exit(0)
if 'clone' in sys.argv:
    shutil.copytree({str(self.repo)!r}, sys.argv[-1], symlinks=True)
    sys.exit(0)
sys.exit(97)""")

    def test_bootstrap_logs_validation_prerequisites_clone_and_dispatch(self):
        self.bootstrap_clone()
        result = self.run_cli(bootstrap=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_ordered(result.stderr, ("Bootstrap platform validation:", "Platform validation passed",
                                           "Git prerequisites:", "Git clone tooling is available",
                                           "Checkout clone:", "Setup dispatch:", "Complete: bootstrap"))
        self.assert_no_secrets(result)

    def test_bootstrap_failed_dispatch_preserves_status_without_success(self):
        self.bootstrap_clone(dispatch_status=37)
        result = self.run_cli(bootstrap=True)
        self.assertEqual(37, result.returncode, result.stderr)
        self.assertIn("Failure during Setup dispatch: running the selected checkout entrypoint (exit 37)", result.stderr)
        self.assertNotIn("Complete:", result.stderr)
        self.assertNotIn("Next steps:", result.stdout)
        self.assert_no_secrets(result)

    def test_bootstrap_existing_checkout_logs_safe_update_before_dispatch(self):
        (self.repo / "bin/setup").write_text("#!/usr/bin/env bash\nexit 0\n")
        self.git_fixture()
        self.destination.parent.mkdir(parents=True)
        shutil.copytree(self.repo, self.destination, symlinks=True)
        result = self.run_cli(bootstrap=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_ordered(result.stderr, ("Git prerequisites:", "Checkout update:",
                                           "Setup dispatch:", "Complete: bootstrap"))
        self.assertNotIn("Checkout clone:", result.stderr)
        self.assert_no_secrets(result)

    def test_bootstrap_dry_run_is_explicit_and_does_not_clone(self):
        self.bootstrap_clone()
        result = self.run_cli("--dry-run", bootstrap=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("PLAN ONLY:", result.stdout)
        self.assertNotIn("Complete:", result.stderr)
        self.assertEqual({}, self.snapshot())
        self.assertFalse(any("clone" in call for call in self.calls()))
        self.assert_no_secrets(result)

    def test_template_is_commented_and_does_not_encourage_local_api_key_exports(self):
        template = test_dotfiles.ROOT / "examples/local-variables.sh"
        text = template.read_text()
        self.assertTrue(all(not line.strip() or line.lstrip().startswith("#") for line in text.splitlines()))
        for name in ("EXA_API_KEY", "GITHUB_MCP_TOKEN", "MAPLE_API_KEY"):
            self.assertNotIn("# export " + name, text)
            self.assertIn(name, (test_dotfiles.ROOT / "stow/opencode/.config/opencode/opencode.jsonc").read_text())
        self.assertNotIn("set -", text)
        self.assertIn("credential injection", text)
        self.assertNotIn(self.sentinel, text)


if __name__ == "__main__":
    unittest.main()
