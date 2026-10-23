"""Pinned signed-pack state fixtures; never execute a real nono binary or pull."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

import test_dotfiles


class NonoPack(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    assert_failed = test_dotfiles.Fixture.assert_failed
    run_cli = test_dotfiles.Fixture.run_cli

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        (self.path / "python3").symlink_to(shutil.which("python3"))
        (self.path / "cmp").symlink_to(shutil.which("cmp"))
        self.config = self.home / ".config"
        self.root = self.config / "nono/packages/nolabs-ai/opencode"
        self.lock = self.config / "nono/packages/lockfile.json"
        self.payload = self.base / "pack-payload"
        self.payload.mkdir()
        module = self.repo / "modules/nono.sh"
        text = module.read_text()
        # Substitute small deterministic bytes for production artifact bytes,
        # retaining the real validation logic and v0.80.0 metadata schema.
        block = text.split("hashes = {", 1)[1].split("\n}", 1)[0]
        self.hashes = {}
        for relative, digest in re.findall(r"'([^']+)': '([0-9a-f]{64})'", block):
            content = relative.encode()
            if relative == "wiring/profile-drafts-dir-marker":
                content = b""
            path = self.payload / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            self.hashes[relative] = hashlib.sha256(content).hexdigest()
            text = text.replace(digest, self.hashes[relative])
        manifest = b'{"name":"opencode","version":"0.4.0"}'
        (self.payload / "package.json").write_bytes(manifest)
        manifest_hash = hashlib.sha256(manifest).hexdigest()
        old = re.search(r"manifest_hash = '([^']+)'", text)[1]
        text = text.replace(old, manifest_hash)
        bundle = {"fixture": "signed bundle"}
        bundle_hash = hashlib.sha256(json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        old = re.search(r"bundle_hash = '([^']+)'", text)[1]
        text = text.replace(old, bundle_hash)
        module.write_text(text)
        (self.payload / ".nono-trust.bundle").write_text(json.dumps([
            {"installed_path": name, "digest": digest, "bundle": bundle}
            for name, digest in {**self.hashes, "package.json": manifest_hash}.items()
        ]))
        self.metadata = {
            "lockfile_version": 4, "registry": "https://registry.nono.sh",
            "packages": {"nolabs-ai/opencode": {
                "version": "0.4.0", "pinned": True,
                "provenance": {
                    "signer_identity": "https://github.com/nolabs-ai/nono-packs/.github/workflows/publish-opencode.yml@refs/tags/opencode-v0.4.0",
                    "repository": "nolabs-ai/nono-packs",
                    "workflow": ".github/workflows/publish-opencode.yml",
                    "ref": "refs/tags/opencode-v0.4.0",
                },
                "artifacts": {name: {"sha256": digest, "type": "profile" if name.startswith("profiles/") else "plugin"}
                              for name, digest in self.hashes.items()},
                "wiring_record": [
                    {"type": "write_file", "dest": str(self.config / "nono/profile-drafts/.nono-opencode-pack-marker"),
                     "sha256": self.hashes["wiring/profile-drafts-dir-marker"]},
                    *({"type": "symlink", "link": link} for link, _ in self.wiring()),
                ],
            }},
        }
        self.metadata_path = self.base / "metadata.json"
        self.metadata_path.write_text(json.dumps(self.metadata))
        # Every operational command is a disposable mock, including the binary
        # extracted from the checksum-verified archive fixture.
        self.mock("nono", f'''from pathlib import Path
import shutil
root = Path({str(self.root)!r})
lock = Path({str(self.lock)!r})
args = sys.argv[1:]
if args == ['pull', 'nolabs-ai/opencode@0.4.0', '--registry', 'https://registry.nono.sh']:
    sys.exit(23) if os.environ.get('FAIL_PULL') else None
    shutil.copytree({str(self.payload)!r}, root)
    data = json.loads(Path({str(self.metadata_path)!r}).read_text())
    data['packages']['nolabs-ai/opencode']['pinned'] = False
    lock.write_text(json.dumps(data))
    marker = Path({str(self.config / 'nono/profile-drafts/.nono-opencode-pack-marker')!r})
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_bytes(b'')
    for link, target in {self.wiring()!r}:
        path = Path(link)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
elif args == ['pin', 'nolabs-ai/opencode']:
    sys.exit(24) if os.environ.get('FAIL_PIN') else None
    data = json.loads(lock.read_text())
    data['packages']['nolabs-ai/opencode']['pinned'] = True
    lock.write_text(json.dumps(data))
else:
    sys.exit(97)
''')
        binary = (self.path / "nono").read_bytes()
        target = self.home / ".local/share/dotfiles/nono/0.80.0/nono"
        target.parent.mkdir(parents=True)
        target.write_bytes(binary)
        target.chmod(0o755)
        (self.home / ".local/bin").mkdir(parents=True)
        (self.home / ".local/bin/nono").symlink_to(target)
        self.mock("wget", "sys.exit(0)")
        self.mock("sha256sum", "sys.stdin.read(); sys.exit(0)")
        self.mock("tar", f"sys.stdout.buffer.write({binary!r})")

    def wiring(self):
        return [(str(self.config / "opencode/plugins/nono-sandbox.ts"), str(self.root / "plugin/nono-sandbox.ts")),
                (str(self.config / "opencode/skills/nono-sandbox"), str(self.root / "skills/nono-sandbox"))]

    def run_nono(self, *args):
        return subprocess.run([test_dotfiles.BASH, str(self.repo / "modules/nono.sh"), *args],
                              cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=20)

    def installed(self):
        shutil.copytree(self.payload, self.root)
        self.lock.write_text(json.dumps(self.metadata))
        marker = self.config / "nono/profile-drafts/.nono-opencode-pack-marker"
        marker.parent.mkdir(parents=True)
        marker.write_bytes(b"")
        for link, target in self.wiring():
            path = Path(link)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(target)

    def test_missing_pack_is_pulled_from_explicit_origin_and_persistently_pinned(self):
        self.env["NONO_REGISTRY"] = "https://untrusted.invalid"
        result = self.run_nono()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(json.loads(self.lock.read_text())["packages"]["nolabs-ai/opencode"]["pinned"])
        calls = [c[1:] for c in self.calls() if c[0] == "nono"]
        self.assertEqual([["pull", "nolabs-ai/opencode@0.4.0", "--registry", "https://registry.nono.sh"],
                          ["pin", "nolabs-ai/opencode"]], calls)
        before = self.snapshot()
        result = self.run_nono()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(2, len([c for c in self.calls() if c[0] == "nono"]))

    def test_exact_installed_pack_and_custom_profiles_are_unchanged(self):
        self.installed()
        profiles = self.config / "nono/profiles"
        profiles.mkdir()
        (profiles / "opencode-dev.json").write_bytes(b'custom profile bytes\n')
        before = self.snapshot()
        self.assertEqual(0, self.run_nono().returncode)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any(c[0] == "nono" for c in self.calls()))

    def test_check_is_read_only_and_does_not_execute_nono_or_download(self):
        for existing in (False, True):
            if existing:
                self.installed()
            before = self.snapshot()
            result = self.run_nono("--check")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(before, self.snapshot())
            self.assertFalse(any(c[0] in ("nono", "wget", "tar", "install") for c in self.calls()))

    def test_existing_exact_unpinned_pack_is_only_pinned_after_validation(self):
        self.installed()
        data = json.loads(self.lock.read_text())
        data["packages"]["nolabs-ai/opencode"]["pinned"] = False
        self.lock.write_text(json.dumps(data))
        before = self.snapshot()
        result = self.run_nono("--check")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any(c[0] == "nono" for c in self.calls()))
        result = self.run_nono()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([["nono", "pin", "nolabs-ai/opencode"]],
                         [c for c in self.calls() if c[0] == "nono"])

    def test_wrong_version_origin_and_signer_are_refused_without_writes(self):
        self.installed()
        for field in ("version", "registry", "signer"):
            data = json.loads(json.dumps(self.metadata))
            package = data["packages"]["nolabs-ai/opencode"]
            if field == "version":
                package["version"] = "0.3.0"
            elif field == "registry":
                data["registry"] = "https://untrusted.invalid"
            else:
                package["provenance"]["signer_identity"] = "untrusted"
            self.lock.write_text(json.dumps(data))
            before = self.snapshot()
            self.assert_failed(self.run_nono())
            self.assertEqual(before, self.snapshot())
        self.assertFalse(any(c[0] in ("nono", "wget") for c in self.calls()))

    def test_edited_artifact_manifest_and_trust_bundle_are_preserved(self):
        self.installed()
        for relative in ("profiles/opencode.json", "package.json", ".nono-trust.bundle"):
            path = self.root / relative
            original = path.read_bytes()
            path.write_bytes(b"edited")
            before = self.snapshot()
            self.assert_failed(self.run_nono())
            self.assertEqual(before, self.snapshot())
            path.write_bytes(original)
        self.assertFalse(any(c[0] in ("nono", "wget") for c in self.calls()))

    def test_unknown_trust_artifact_with_null_digest_is_refused(self):
        self.installed()
        trust = self.root / ".nono-trust.bundle"
        entries = json.loads(trust.read_text())
        entries[0].update(installed_path="unexpected-file", digest=None)
        trust.write_text(json.dumps(entries))
        before = self.snapshot()
        self.assert_failed(self.run_nono())
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any(c[0] in ("nono", "wget") for c in self.calls()))

    def test_unmanaged_package_and_wiring_paths_are_not_adopted(self):
        for path in [self.root, *(Path(link) for link, _ in self.wiring())]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("unmanaged")
            before = self.snapshot()
            self.assert_failed(self.run_nono())
            self.assertEqual(before, self.snapshot())
            path.unlink()
        self.assertFalse(any(c[0] in ("nono", "wget") for c in self.calls()))

    def test_package_parent_symlink_is_refused(self):
        packages = self.config / "nono/packages"
        packages.parent.mkdir(parents=True)
        packages.symlink_to(self.base / "elsewhere")
        before = self.snapshot()
        self.assert_failed(self.run_nono(), "Conflicting parent")
        self.assertEqual(before, self.snapshot())

    def test_staging_and_cli_temporary_conflicts_are_preserved(self):
        for relative in ("nono/packages/.staging/nolabs-ai", "nono/packages/lockfile.json.tmp",
                         "nono/profile-drafts/.nono-opencode-pack-marker.nono-tmp"):
            path = self.config / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(self.base / "missing")
            before = self.snapshot()
            self.assert_failed(self.run_nono())
            self.assertEqual(before, self.snapshot())
            path.unlink()
        self.assertFalse(any(c[0] in ("nono", "wget") for c in self.calls()))

    def test_failed_pull_and_pin_do_not_print_success(self):
        for variable in ("FAIL_PULL", "FAIL_PIN"):
            self.env.pop("FAIL_PULL", None)
            self.env[variable] = "1"
            result = self.run_nono()
            self.assert_failed(result, "stopping before configuration links")
            self.assertNotIn("are ready", result.stderr)
            self.assertFalse(any(c[0] == "stow" for c in self.calls()))

    def test_orchestrator_dry_run_never_calls_setup(self):
        self.mock("stow", "sys.exit(0 if '--simulate' in sys.argv else 97)")
        script = '''set -euo pipefail
ROOT=$1
source "$ROOT/lib/dotfiles.sh"
MODULES=(nono)
DRY_RUN=1
setup_modules
'''
        before = self.snapshot()
        result = subprocess.run([test_dotfiles.BASH, "-c", script, "test", str(self.repo)],
                                env=self.env, text=True, capture_output=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.calls())
        self.assertIn("Module planned: nono", result.stderr)


if __name__ == "__main__":
    unittest.main()
