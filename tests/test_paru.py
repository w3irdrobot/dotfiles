"""Frozen fallback contracts, exercised with disposable files and fake tools."""

import hashlib
import json
import os
from pathlib import Path
import pty
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
COMMIT = "7830fac148f8cd2143307386ead67d7ffd2efa33"
LOCK = "10137b6b653655e5069618f1ca9071e4c104286d2a1deb7b7ea25a3eda2ea2e7"
ARCHIVE = "94869ec2dac20d3d34b5aa6cb32ffa6e2f1f434e79201287729a6028266e248a"


class ParuTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="paru-tests-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.tools = self.base / "tools"
        self.tools.mkdir()
        self.log = self.base / "calls"
        self.log.touch()
        self.env = {"HOME": str(self.home), "PATH": str(self.tools),
                    "TMPDIR": str(self.base), "LC_ALL": "C",
                    "TEST_LOG": str(self.log)}
        for name in ("cat", "cp", "mktemp", "rm", "sha256sum"):
            tool = shutil.which("gsha256sum") if name == "sha256sum" else None
            tool = tool or shutil.which(name)
            self.assertIsNotNone(tool, name)
            (self.tools / name).symlink_to(tool)
        self.mock("pacman", "sys.exit(1 if '-Si' in sys.argv else 0)")
        self.mock("pkg-config", "print(os.environ.get('ABI', '16.0.1'))")
        self.mock("nix", "sys.exit(int(os.environ.get('NIX_STATUS', '0')))")
        self.mock("readelf", "print(os.environ.get('ELF', 'native /usr/lib'))")
        self.module = self.base / "paru.sh"
        text = (ROOT / "modules/paru.sh").read_text()
        for name in ("pkg-config", "nix"):
            text = text.replace("/usr/bin/" + name, str(self.tools / name))
        self.tty_input = self.base / "tty-input"
        self.tty_input.write_text("n\n")
        self.tty_output = self.base / "tty-output"
        self.tty_output.touch()
        text = text.replace("</dev/tty", "<" + str(self.tty_input))
        text = text.replace(">/dev/tty", ">" + str(self.tty_output))
        self.module.write_text(text)
        self.recipe = self.base / "PKGBUILD"
        text = (ROOT / "modules/paru-recipe/PKGBUILD").read_text()
        self.source = self.base / ("paru-" + COMMIT)
        self.source.mkdir()
        self.lock = self.source / "Cargo.lock"
        self.lock.write_bytes(b"fixture committed lock\n")
        text = text.replace(LOCK, hashlib.sha256(self.lock.read_bytes()).hexdigest())
        text = text.replace("/nix/store/", str(self.tools) + "/")
        text = text.replace("/usr/bin/readelf", str(self.tools / "readelf"))
        self.recipe.write_text(text)
        rustdir = self.tools / "pinned/bin"
        rustdir.mkdir(parents=True)
        self.cargo = rustdir / "cargo"
        self.rustc = rustdir / "rustc"
        self.mock_path(self.rustc, "print('rustc 1.98.1 (fixture)')")
        self.mock_path(self.cargo, """
if '--version' in sys.argv:
    print('cargo 1.98.0 (fixture)')
else:
    import json
    with open(os.environ['TEST_LOG'] + '.env', 'w') as output:
        json.dump({key: os.environ.get(key) for key in (
            'CC', 'CXX', 'PKG_CONFIG', 'PKG_CONFIG_LIBDIR', 'RUSTFLAGS',
            'CARGO_ENCODED_RUSTFLAGS', 'PKG_CONFIG_PATH', 'LIBRARY_PATH',
            'LD_LIBRARY_PATH', 'NIX_LDFLAGS')}, output)
    if os.environ.get('MUTATE') == '1':
        with open('Cargo.lock', 'ab') as lock: lock.write(b'changed')
    sys.exit(int(os.environ.get('CARGO_STATUS', '0')))
""")

    def mock_path(self, path, body):
        path.write_text(f"#!{sys.executable}\nimport os, sys\n"
                        "with open(os.environ['TEST_LOG'], 'a') as log:\n"
                        "    log.write(os.path.basename(sys.argv[0]) + ' ' + ' '.join(sys.argv[1:]) + '\\n')\n"
                        + body + "\n")
        path.chmod(0o755)

    def mock(self, name, body):
        self.mock_path(self.tools / name, body)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def run_module(self, command, dry=0, tty=False):
        script = f"""
ROOT={str(ROOT)!r}
DRY_RUN={dry}
die() {{ printf '%s\\n' "$*" >&2; exit 1; }}
log() {{ printf '%s\\n' "$*" >&2; }}
validate_existing_paru() {{ printf 'validate\\n' >> "$TEST_LOG"; }}
preflight_nix() {{ printf 'preflight\\n' >> "$TEST_LOG"; }}
setup_nix() {{ printf 'setup %s\\n' "$*" >> "$TEST_LOG"; }}
source {str(self.module)!r}
{command}
"""
        if tty:
            master, slave = pty.openpty()
            try:
                return subprocess.run([BASH, "-c", script], env=self.env,
                                      stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, timeout=10)
            finally:
                os.close(master)
                os.close(slave)
        return subprocess.run([BASH, "-c", script], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def run_recipe(self, stage, config=None):
        load_config = f"source {str(config)!r}" if config else ""
        return subprocess.run([BASH, "-c", f"""
source {str(self.recipe)!r}
srcdir={str(self.base)!r}
PARU_CARGO={str(self.cargo)!r}
RUSTC={str(self.rustc)!r}
{load_config}
{stage}
"""], env=self.env, capture_output=True, text=True, timeout=10)

    def test_production_recipe_has_verified_pins_and_no_resolution(self):
        text = (ROOT / "modules/paru-recipe/PKGBUILD").read_text()
        for pin in (COMMIT, LOCK, ARCHIVE):
            self.assertIn(pin, text)
        self.assertIn("cargo fetch --locked", (ROOT / "modules/paru.sh").read_text())
        self.assertNotIn(" update ", text)
        self.assertNotIn("--nodeps", text)
        self.assertNotIn("--noconfirm", text)
        self.assertIn("libalpm.so=16-64", text)

    def test_dry_run_has_no_effects(self):
        before = sorted(p.name for p in self.base.iterdir())
        result = self.run_module("ensure_paru", dry=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--frozen", result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertEqual(before, sorted(p.name for p in self.base.iterdir()))
        self.assertEqual(list(self.home.iterdir()), [])

    def test_existing_helper_skips_fallback(self):
        self.mock("paru", "sys.exit(0)")
        result = self.run_module("ensure_paru")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["validate"])

    def test_repository_helper_is_not_replaced(self):
        self.mock("pacman", "sys.exit(0)")
        result = self.run_module("ensure_paru")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Repository paru", result.stderr)
        self.assertEqual(self.calls(), ["pacman -Si -- paru"])

    def test_refused_review_cleans_up_without_nix_or_fetch(self):
        before = sorted(p.name for p in self.base.iterdir())
        result = self.run_module("ensure_paru")
        self.assertEqual(result.returncode, 1)
        self.assertIn("interactively", result.stderr)
        self.assertEqual(self.calls(), ["pacman -Si -- paru"])
        self.assertEqual(before, sorted(p.name for p in self.base.iterdir()))
        self.assertEqual(list(self.home.iterdir()), [])

    def test_approved_fallback_uses_native_makepkg_and_build_only_pin(self):
        result = self.run_module("approve_paru_recipe() { :; }; ensure_paru")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertIn("preflight", calls)
        self.assertIn("setup --bootstrap", calls)
        nix = next(c for c in calls if c.startswith("nix "))
        self.assertIn("7fd4004d0511991fff3a0524856a9be09e28c5f0#rustc", nix)
        self.assertIn("7fd4004d0511991fff3a0524856a9be09e28c5f0#cargo", nix)
        invocation = "\n".join(calls)
        self.assertIn("exec /usr/bin/makepkg --force --install", invocation)
        self.assertNotIn("--nodeps", invocation)
        self.assertNotIn("--syncdeps", invocation)
        self.assertNotIn("--noconfirm", invocation)
        self.assertFalse(any(c.startswith("cargo ") for c in calls))
        self.assertEqual(list(self.home.iterdir()), [])

    def test_build_install_failure_is_reported_without_lock_workaround(self):
        self.env["NIX_STATUS"] = "42"
        result = self.run_module("approve_paru_recipe() { :; }; ensure_paru")
        self.assertEqual(result.returncode, 1)
        self.assertIn("must not be updated", result.stderr)

    def test_noninteractive_review_refuses(self):
        result = self.run_module(f"approve_paru_recipe {str(self.recipe)!r}")
        self.assertEqual(result.returncode, 1)
        self.assertIn("interactively", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_review_defaults_to_no(self):
        for answer in ("\n", "n\n", "yes\n"):
            self.tty_input.write_text(answer)
            result = self.run_module(f"approve_paru_recipe {str(self.recipe)!r}", tty=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("cancelled", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_review_requires_explicit_single_letter_yes(self):
        self.tty_input.write_text("y\n")
        result = self.run_module(f"approve_paru_recipe {str(self.recipe)!r}", tty=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.tty_output.read_text(), self.recipe.read_text())

    def test_native_runtime_and_base_devel_checked(self):
        result = self.run_module("validate_paru_build_dependencies")
        self.assertEqual(result.returncode, 0, result.stderr)
        for dep in ("base-devel", "git", "pacman", "openssl", "libalpm.so=16-64"):
            self.assertIn("pacman -T " + dep, self.calls())
        self.assertIn("pkg-config --modversion libalpm", self.calls())

    def test_unsupported_abi_refuses(self):
        self.env["ABI"] = "17.0.0"
        result = self.run_module("validate_paru_build_dependencies")
        self.assertEqual(result.returncode, 1)
        self.assertIn("16 only", result.stderr)

    def test_missing_dependency_refuses(self):
        self.mock("pacman", "sys.exit(1)")
        result = self.run_module("validate_paru_build_dependencies")
        self.assertEqual(result.returncode, 1)
        self.assertIn("base-devel", result.stderr)
        self.assertEqual(self.calls(), ["pacman -T base-devel"])

    def test_locked_fetch_preserves_bytes(self):
        before = self.lock.read_bytes()
        result = self.run_recipe("prepare")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cargo fetch --locked --target x86_64-unknown-linux-gnu", self.calls())
        self.assertEqual(before, self.lock.read_bytes())

    def test_frozen_build_preserves_bytes(self):
        before = self.lock.read_bytes()
        result = self.run_recipe("build")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cargo build --release --frozen --target x86_64-unknown-linux-gnu", self.calls())
        self.assertEqual(before, self.lock.read_bytes())

    def test_makepkg_config_cannot_override_native_build_flags(self):
        config = self.base / "makepkg-rust.conf"
        config.write_text("""
export RUSTFLAGS='-C force-frame-pointers=yes'
export CC=/nix/store/wrong/bin/cc CXX=/nix/store/wrong/bin/c++
export PKG_CONFIG=/nix/store/wrong/bin/pkg-config PKG_CONFIG_LIBDIR=/nix/store/wrong/lib/pkgconfig
export CARGO_ENCODED_RUSTFLAGS='-Cwrong' PKG_CONFIG_PATH=/nix/store/wrong/lib/pkgconfig
export LIBRARY_PATH=/nix/store/wrong/lib LD_LIBRARY_PATH=/nix/store/wrong/lib NIX_LDFLAGS=-L/nix/store/wrong/lib
""")
        result = self.run_recipe("build", config=config)
        self.assertEqual(result.returncode, 0, result.stderr)
        environment = json.loads(Path(str(self.log) + ".env").read_text())
        self.assertEqual(environment["CC"], "/usr/bin/cc")
        self.assertEqual(environment["CXX"], "/usr/bin/c++")
        self.assertEqual(environment["PKG_CONFIG"], "/usr/bin/pkg-config")
        self.assertEqual(environment["PKG_CONFIG_LIBDIR"], "/usr/lib/pkgconfig:/usr/share/pkgconfig")
        self.assertEqual(environment["RUSTFLAGS"],
                         "-C linker=/usr/bin/cc -C linker-features=-lld -C link-self-contained=-linker")
        for key in ("CARGO_ENCODED_RUSTFLAGS", "PKG_CONFIG_PATH", "LIBRARY_PATH",
                    "LD_LIBRARY_PATH", "NIX_LDFLAGS"):
            self.assertIsNone(environment[key], key)

    def test_makepkg_destinations_override_environment_and_configured_cache(self):
        # Execute the real launcher child against a fake makepkg. Model only
        # makepkg's documented restore-env/config and cached-package branches.
        cache = self.base / "global-cache"
        cache.mkdir()
        cached_package = cache / "paru-cached.pkg.tar.zst"
        cached_package.write_bytes(b"unverified cached package")
        paths = ("PKGDEST", "SRCDEST", "SRCPKGDEST", "LOGDEST", "BUILDDIR")
        self.env.update({key: str(cache) for key in paths})
        self.env["TEST_CACHE"] = str(cache)
        self.mock("makepkg", """
paths = ('PKGDEST', 'SRCDEST', 'SRCPKGDEST', 'LOGDEST', 'BUILDDIR')
saved = {key: os.environ[key] for key in paths if key in os.environ}
configured = {key: os.environ['TEST_CACHE'] for key in paths}
configured.update(saved)  # load_makepkg_config restores environment precedence
assert all(os.path.realpath(value) == os.getcwd() for value in configured.values()), configured
assert os.getcwd() != os.environ['TEST_CACHE']
assert '--force' in sys.argv and '--install' in sys.argv
assert not os.path.exists(os.path.join(configured['PKGDEST'], 'paru-cached.pkg.tar.zst'))
with open(os.environ['TEST_LOG'], 'a') as log:
    log.write('fresh-verified-build-required\\n')
""")
        (self.tools / "cargo").symlink_to(self.cargo)
        (self.tools / "rustc").symlink_to(self.rustc)
        self.mock("nix", f"""
import subprocess
command = sys.argv[sys.argv.index('--command') + 1:]
command[0] = {BASH!r}
command[-1] = command[-1].replace('/usr/bin/makepkg', {str(self.tools / 'makepkg')!r})
sys.exit(subprocess.run(command, check=False).returncode)
""")
        result = self.run_module("approve_paru_recipe() { :; }; ensure_paru")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("fresh-verified-build-required", self.calls())
        self.assertEqual(cached_package.read_bytes(), b"unverified cached package")
        self.assertEqual(list(cache.iterdir()), [cached_package])

    def test_installer_aur_upgrade_always_ignores_paru(self):
        self.mock("paru", "sys.exit(0)")
        for dry in (0, 1):
            result = self.run_module("""
source "$ROOT/lib/dotfiles.sh"
preflight_custom_modules() { :; }
validate_existing_paru() { :; }
install_packages() { :; }
setup_modules() { :; }
update_system
""", dry=dry)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("-Sua --ignore paru", result.stderr)
        self.assertEqual(self.calls(), ["paru -Sua --ignore paru"])

    def test_changed_lock_refuses_before_cargo(self):
        self.lock.write_bytes(b"modified before build")
        result = self.run_recipe("prepare")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cargo.lock changed", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_wrong_toolchain_refuses_before_fetch(self):
        self.mock_path(self.rustc, "print('rustc 1.97.0 (fixture)')")
        result = self.run_recipe("prepare")
        self.assertEqual(result.returncode, 1)
        self.assertIn("rustc 1.98.1 required", result.stderr)
        self.assertNotIn("cargo fetch --locked --target x86_64-unknown-linux-gnu", self.calls())

    def test_wrong_cargo_refuses_before_fetch(self):
        self.mock_path(self.cargo, "print('cargo 1.98.1 (fixture)')")
        result = self.run_recipe("prepare")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cargo 1.98.0 required", result.stderr)
        self.assertNotIn("cargo fetch --locked --target x86_64-unknown-linux-gnu", self.calls())

    def test_post_cargo_hash_checked_even_after_failure(self):
        for stage in ("prepare", "build"):
            for status in ("0", "42"):
                self.lock.write_bytes(b"fixture committed lock\n")
                self.env.update(MUTATE="1", CARGO_STATUS=status)
                result = self.run_recipe(stage)
                self.assertEqual(result.returncode, 1)
                self.assertIn("Cargo.lock changed", result.stderr)

    def test_cargo_failure_status_preserved(self):
        self.env["CARGO_STATUS"] = "42"
        for stage in ("prepare", "build"):
            result = self.run_recipe(stage)
            self.assertEqual(result.returncode, 42, result.stderr)

    def test_nix_runtime_link_refused(self):
        # Fixture recipe translates this prefix along with the pinned tool paths.
        self.env["ELF"] = str(self.tools) + "/runtime/libc.so"
        result = self.run_recipe("build")
        self.assertEqual(result.returncode, 1)
        self.assertIn("runtime reference", result.stderr)


if __name__ == "__main__":
    unittest.main()
