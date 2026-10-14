"""Interactive startup in disposable homes/checkouts, never the live shell HOME."""

from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


class ShellStartup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="shell-startup-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        # Exercise both linked-worktree layout and spaces without any Git state.
        self.repo = self.base / "primary checkout/.worktrees/custom checkout"
        self.repo.mkdir(parents=True)
        self.home = self.base / "fresh home"
        self.home.mkdir()
        self.path = self.base / "fixture commands"
        self.path.mkdir()
        self.log = self.base / "source-paths.log"
        self.completion = self.base / "fixture completion"
        shutil.copytree(ROOT / "shell", self.repo / "shell")
        shutil.copytree(ROOT / "stow/bash", self.repo / "stow/bash")
        # Replace the sole fixed system-source path in the fixture, not behavior.
        # --noprofile --norc below prevents any other host startup files loading.
        startup = self.repo / "shell/startup.sh"
        startup.write_text(startup.read_text().replace(
            "/usr/share/bash-completion/bash_completion", shlex.quote(str(self.completion)),
        ))
        (self.home / ".bashrc").symlink_to(self.repo / "stow/bash/.bashrc")
        # Log only file paths, never source lines, variable values, or commands.
        for helper in (self.repo / "shell").glob("*.sh"):
            helper.write_text(
                'printf "%s\\n" "${BASH_SOURCE[0]}" >> "$TEST_SOURCE_LOG"\n'
                + helper.read_text()
            )
        self.completion.write_text(
            'printf "%s\\n" "${BASH_SOURCE[0]}" >> "$TEST_SOURCE_LOG"\n'
            'COMPLETION_READY=1\n'
        )
        for command in ("readlink", "dirname"):
            executable = shutil.which(command)
            self.assertIsNotNone(executable, f"{command} is required for startup fixtures")
            (self.path / command).symlink_to(executable)
        self.mock_init("fzf", "FZF_READY=1", "fzf")
        self.mock_init("zoxide", "ZOXIDE_READY=1", "zoxide")
        self.inherited_path = ":".join((
            str(self.path), str(self.base / "nix profile/bin"), str(self.base / "project dev/bin"),
        ))
        self.env = {
            "HOME": str(self.home), "PATH": self.inherited_path,
            "LC_ALL": "C", "TMPDIR": str(self.base),
            "TEST_SOURCE_LOG": str(self.log), "DEBUG": "1",
        }

    def mock_init(self, command, assignment, event):
        args = ["--bash"] if command == "fzf" else ["init", "bash"]
        script = self.path / command
        script.write_text(
            f"#!{sys.executable}\nimport sys\n"
            f"assert sys.argv[1:] == {args!r}\n"
            f"print({assignment!r})\n"
            f"print('printf \\\'%s\\\\n\\\' {event} >> \"$TEST_SOURCE_LOG\"')\n"
        )
        script.chmod(0o755)

    def native_bitwarden(self):
        script = self.path / "bitwarden"
        script.write_text(
            f"#!{sys.executable}\nfrom pathlib import Path\n"
            f"Path({str(self.base / 'app-executed')!r}).write_text('unexpected app execution')\n"
            "raise SystemExit(97)\n"
        )
        script.chmod(0o755)

    def run_shell(self, body="", interactive=True, before="", expected_status=0):
        script = 'set -e\n' + before + '\nsource "$HOME/.bashrc"\n' + body
        result = subprocess.run(
            [BASH, "--noprofile", "--norc", "-ic" if interactive else "-c", script],
            cwd=self.base, env=self.env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(expected_status, result.returncode, result.stdout + result.stderr)
        self.assertFalse((self.base / "app-executed").exists())
        return result

    def sources(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def expected_sources(self, native=False, local=False):
        paths = [str(self.repo / "shell" / name) for name in (
            "startup.sh", "init.sh", "variables.sh", "aliases.sh", "functions.sh",
        )]
        if native:
            paths.append(str(self.repo / "shell/bitwarden.sh"))
        if local:
            paths.extend(str(self.repo / "shell/../local/bash" / name) for name in (
                "init.sh", "variables.sh", "aliases.sh", "functions.sh",
            ))
        return [*paths, str(self.completion), "fzf", str(self.repo / "shell/prompt.sh"), "zoxide"]

    def test_fresh_home_only_needs_bashrc_and_loads_checkout_helpers(self):
        result = self.run_shell('''
declare -F take scratch gshell ai __prompt_command
printf '%s:%s:%s\n' "$COMPLETION_READY" "$FZF_READY" "$ZOXIDE_READY"
alias clip
''')
        for function in ("take", "scratch", "gshell", "ai", "__prompt_command"):
            self.assertIn(function, result.stdout.splitlines())
        self.assertIn("1:1:1", result.stdout)
        self.assertIn("xclip -selection clipboard", result.stdout)
        self.assertEqual(self.expected_sources(), self.sources())
        self.assertEqual([".bashrc"], sorted(p.name for p in self.home.iterdir()))
        self.assertEqual([".bashrc"], sorted(p.name for p in (ROOT / "stow/bash").iterdir()))
        self.assertFalse((ROOT / "stow/bitwarden").exists())

    def test_noninteractive_shell_returns_without_loading_any_helpers(self):
        result = self.run_shell('''
printf '%s\n' "$PATH"
[[ ! -v XDG_CONFIG_HOME && ! -v SSH_AUTH_SOCK ]]
! declare -F take _dotfiles_load_shell
''', interactive=False)
        self.assertEqual(self.inherited_path + "\n", result.stdout)
        self.assertEqual([], self.sources())

    def test_path_options_and_unrelated_variables_survive_repeat_startup(self):
        result = self.run_shell('''
source "$HOME/.bashrc"
[[ $- == "$original_flags" && $SHELLOPTS == "$original_options" ]] || exit 97
[[ $ROOT == root-sentinel && $root == lower-root-sentinel ]] || exit 97
[[ $directory == directory-sentinel && $profile == profile-sentinel ]] || exit 97
[[ $_dotfiles_repo == caller-sentinel ]] || exit 97
[[ $PWD == "$original_directory" ]] || exit 97
if declare -F _dotfiles_load_shell; then exit 97; fi
[[ $PROMPT_COMMAND == __prompt_command && -n $__prompt_green ]] || exit 97
printf '%s\n' "$PATH"
''', before='''
set +e
original_flags=$- original_options=$SHELLOPTS
original_directory=$PWD
ROOT=root-sentinel root=lower-root-sentinel directory=directory-sentinel profile=profile-sentinel
_dotfiles_repo=caller-sentinel
''')
        self.assertEqual(str(self.home / ".local/bin") + ":" + self.inherited_path + "\n", result.stdout)
        self.assertEqual(self.expected_sources() * 2, self.sources())
        self.assertNotIn("+ source", result.stderr)  # DEBUG must not enable tracing.

    def test_loader_bookkeeping_does_not_leak_into_the_caller(self):
        self.run_shell('''
[[ ! -v _dotfiles_repo && ! -v _dotfiles_override ]]
[[ ! -v _dotfiles_bashrc && ! -v _dotfiles_directory ]]
! declare -F _dotfiles_load_shell
''')

    def test_override_declarations_persist_at_top_level(self):
        local = self.repo / "local/bash"
        local.mkdir(parents=True)
        (local / "variables.sh").write_text('''
declare -x LOCAL_EXPORTED=dummy-export
declare -a LOCAL_ARRAY=(one "two words")
declare -A LOCAL_MAP=([key]="dummy value")
typeset LOCAL_TYPED=dummy-type
declare LOCAL_EXISTING=replaced
''')
        self.run_shell('''
[[ $LOCAL_EXPORTED == dummy-export && $LOCAL_TYPED == dummy-type ]]
[[ ${LOCAL_ARRAY[0]} == one && ${LOCAL_ARRAY[1]} == "two words" ]]
[[ ${LOCAL_MAP[key]} == "dummy value" && $LOCAL_EXISTING == replaced ]]
[[ $(declare -p LOCAL_EXPORTED) == "declare -x "* ]]
source "$HOME/.bashrc"
[[ $LOCAL_EXISTING == replaced && ${LOCAL_ARRAY[1]} == "two words" ]]
[[ $ROOT == root-sentinel && $directory == directory-sentinel ]]
[[ $_dotfiles_bashrc == caller-bashrc && $_dotfiles_directory == caller-directory ]]
_dotfiles_load_shell
''', before='''
LOCAL_EXISTING=original ROOT=root-sentinel directory=directory-sentinel
_dotfiles_bashrc=caller-bashrc _dotfiles_directory=caller-directory
_dotfiles_load_shell() { [[ $LOCAL_EXISTING == replaced ]]; }
''')

    def test_failed_symlink_resolution_never_sources_emitted_path(self):
        readlink = self.path / "readlink"
        readlink.unlink()
        # Even plausible stdout from a failing resolver must not be sourced.
        readlink.write_text(
            f'#!{BASH}\nprintf "%s\\n" "$HOME/../decoy/stow/bash/.bashrc"\nexit 43\n'
        )
        readlink.chmod(0o755)
        decoy = self.base / "decoy/shell/startup.sh"
        decoy.parent.mkdir(parents=True)
        (self.base / "decoy/stow/bash").mkdir(parents=True)
        decoy.write_text('printf forbidden-decoy-source\n')
        result = self.run_shell(expected_status=1)
        self.assertEqual("", result.stdout)
        self.assertEqual([], self.sources())

    def test_native_agent_default_preserves_explicit_empty_or_other_socket(self):
        self.native_bitwarden()
        cases = ((None, str(self.home / ".bitwarden-ssh-agent.sock")),
                 ("", ""), (str(self.base / "explicit-agent"), str(self.base / "explicit-agent")))
        for socket, expected in cases:
            with self.subTest(socket=socket):
                if socket is None:
                    self.env.pop("SSH_AUTH_SOCK", None)
                else:
                    self.env["SSH_AUTH_SOCK"] = socket
                if self.log.exists():
                    self.log.unlink()
                result = self.run_shell('printf "%s" "$SSH_AUTH_SOCK"')
                self.assertEqual(expected, result.stdout)
                self.assertEqual(self.expected_sources(native=True), self.sources())

    def test_absent_native_app_does_not_set_a_socket(self):
        self.run_shell('[[ ! -v SSH_AUTH_SOCK ]]')
        self.assertNotIn(str(self.repo / "shell/bitwarden.sh"), self.sources())

    def test_repo_local_overrides_run_in_order_after_defaults(self):
        self.native_bitwarden()
        local = self.repo / "local/bash"
        local.mkdir(parents=True)
        bodies = {
            "init.sh": '[[ $EDITOR == vim && $SSH_AUTH_SOCK == "$HOME/.bitwarden-ssh-agent.sock" ]] || return 97\nLOCAL_INIT=1\n',
            "variables.sh": '[[ $LOCAL_INIT == 1 ]] || return 97\nexport SSH_AUTH_SOCK="$HOME/local-agent.sock"\nEDITOR=fixture-editor\nLOCAL_VARIABLES=1\n',
            "aliases.sh": '[[ $LOCAL_VARIABLES == 1 ]] || return 97\nalias clip="fixture-clipboard"\nLOCAL_ALIASES=1\n',
            "functions.sh": '[[ $LOCAL_ALIASES == 1 ]] || return 97\nfunction take() { printf local-take; }\n',
        }
        for name, body in bodies.items():
            (local / name).write_text(
                'printf "%s\\n" "${BASH_SOURCE[0]}" >> "$TEST_SOURCE_LOG"\n' + body,
            )
        result = self.run_shell('''
printf '%s\n' "$SSH_AUTH_SOCK" "$EDITOR"
alias clip
take
''')
        self.assertIn(str(self.home / "local-agent.sock"), result.stdout)
        self.assertIn("fixture-editor", result.stdout)
        self.assertIn("fixture-clipboard", result.stdout)
        self.assertTrue(result.stdout.endswith("local-take"))
        self.assertEqual(self.expected_sources(native=True, local=True), self.sources())

    def test_old_home_overrides_and_distro_profile_are_never_read_or_changed(self):
        files = [self.home / name for name in (
            ".init", ".variables", ".aliases", ".functions", ".prompt", ".bash_profile", ".hushlogin",
        )]
        files.extend(self.home / ".config/bash" / name for name in (
            ".init", ".variables", ".aliases", ".functions", "bitwarden.sh",
        ))
        for path in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('printf forbidden-home-source\n')
        before = {path: path.read_bytes() for path in files}
        result = self.run_shell('printf clean-startup')
        self.assertEqual("clean-startup", result.stdout)
        self.assertEqual(before, {path: path.read_bytes() for path in files})
        self.assertEqual(self.expected_sources(), self.sources())

    def test_optional_checkout_local_directory_is_ignored(self):
        self.assertIn("/local/", (ROOT / ".gitignore").read_text().splitlines())

    def test_failed_local_override_stops_startup_and_preserves_failure_status(self):
        local = self.repo / "local/bash"
        local.mkdir(parents=True)
        (local / "init.sh").write_text("return 43\n")
        self.run_shell(expected_status=43)
        self.assertEqual(self.expected_sources()[:5], self.sources())


if __name__ == "__main__":
    unittest.main()
