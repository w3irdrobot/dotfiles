"""Exercise only disposable homes; never deploy into the operator's home."""

import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/link-agent-config.py"
spec = importlib.util.spec_from_file_location("link_agent_config", SCRIPT)
linker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linker)


class AgentConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)

    def run_linker(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--home", str(self.home), "--tools", "maple", *args],
            text=True, capture_output=True, check=False,
            env={key: value for key, value in os.environ.items()
                 if key not in {"CODEX_HOME", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME"}},
        )

    def test_dry_run_has_no_side_effects(self):
        result = self.run_linker("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Would link:", result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_links_complete_skills_and_is_idempotent(self):
        for _ in range(2):
            result = self.run_linker()
            self.assertEqual(result.returncode, 0, result.stderr)
        for destination, source in linker.links(self.home):
            self.assertTrue(destination.is_symlink())
            self.assertEqual(os.readlink(destination), str(source))
        skill = self.home / ".agents/skills/rust-conventions"
        self.assertTrue((skill / "references/conventions.md").is_file())
        self.assertTrue((self.home / ".agents/skills/frontend-design/LICENSE.txt").is_file())
        self.assertFalse((self.home / ".config").exists())

    def test_all_conflicts_preflight_before_any_writes(self):
        conflict = self.home / ".agents/skills/frontend-design"
        conflict.mkdir(parents=True)
        result = self.run_linker()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / ".agents/AGENTS.md").exists())
        self.assertEqual(list(conflict.parent.iterdir()), [conflict])

    def test_existing_instructions_remain_untouched(self):
        instructions = self.home / ".agents/AGENTS.md"
        instructions.parent.mkdir()
        instructions.write_text("My existing rules")
        result = self.run_linker()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(instructions.read_text(), "My existing rules")

    def test_dangling_and_foreign_links_are_refused(self):
        destination = self.home / ".agents"
        destination.mkdir()
        instructions = destination / "AGENTS.md"
        for target in (self.home / "missing", ROOT / "README.md"):
            with self.subTest(target=target):
                instructions.symlink_to(target)
                result = self.run_linker("--dry-run")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(os.readlink(instructions), str(target))
                instructions.unlink()

    def test_symlink_parent_is_refused_without_writing_through_it(self):
        outside = self.home / "outside"
        outside.mkdir()
        (self.home / ".agents").symlink_to(outside, target_is_directory=True)
        result = self.run_linker()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_interrupted_deployment_resumes_and_preserves_other_skills(self):
        instructions, source = linker.links(self.home)[0]
        instructions.parent.mkdir()
        instructions.symlink_to(source)
        unrelated = self.home / ".agents/skills/other/SKILL.md"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("Unmanaged")
        result = self.run_linker()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(unrelated.read_text(), "Unmanaged")

    def test_invalid_arguments_and_nonexistent_home(self):
        for args in (("--unknown",), ("--home", str(self.home / "missing"))):
            result = self.run_linker(*args)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_allowlist_validation(self):
        for names in (["../escape"], ["rust-conventions"] * 2, [1], [], {}):
            with self.subTest(names=names), patch.object(
                Path, "read_text", return_value=json.dumps(names)
            ):
                with self.assertRaises(ValueError):
                    linker.links(self.home)

    def test_all_tools_share_one_source_and_keep_opencode_agents_scoped(self):
        result = self.run_linker("--tools", "maple,codex,claude,opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in (".agents/AGENTS.md", ".codex/AGENTS.md", ".claude/CLAUDE.md",
                     ".config/opencode/AGENTS.md"):
            self.assertEqual((self.home / name).resolve(), linker.INSTRUCTIONS)
        for base in (".agents/skills", ".claude/skills", ".config/opencode/skills"):
            self.assertEqual((self.home / base / "create-project").resolve(),
                             linker.SKILLS / "create-project")
        self.assertTrue((self.home / ".config/opencode/agents/rust-engineer.md").is_file())
        self.assertFalse((self.home / ".claude/agents").exists())
        result = self.run_linker("--tools", "maple,codex,claude,opencode")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_tool_selection_and_codex_override_preflight(self):
        for tools in ("", "codex,codex", "t3code", "maple,unknown"):
            self.assertNotEqual(self.run_linker("--tools", tools).returncode, 0)
        override = self.home / ".codex/AGENTS.override.md"
        override.parent.mkdir()
        override.write_text("Existing override")
        self.assertNotEqual(self.run_linker("--tools", "codex").returncode, 0)
        self.assertFalse((self.home / ".agents").exists())

    def test_stow_layout_reuses_canonical_resources_without_writing_checkout(self):
        destination = self.home / ".config/opencode"
        destination.parent.mkdir()
        destination.symlink_to(ROOT / "stow/opencode/.config/opencode")
        result = self.run_linker("--tools", "opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((destination / "skills/rust-conventions").resolve(),
                         linker.SKILLS / "rust-conventions")

    @unittest.skipUnless(shutil.which("stow"), "GNU Stow is not installed")
    def test_real_stow_then_all_tool_deployment(self):
        result = subprocess.run(
            ["stow", "--no-folding", "--dir", str(ROOT / "stow"), "--target", str(self.home), "opencode"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_linker("--tools", "maple,codex,claude,opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / ".config/opencode/AGENTS.md").resolve(), linker.INSTRUCTIONS)
        self.assertEqual((self.home / ".claude/skills/skill-creator/SKILL.md").read_text(),
                         (linker.SKILLS / "skill-creator/SKILL.md").read_text())

    def test_custom_tool_home_refuses_before_writes(self):
        with patch.dict(os.environ, {"CODEX_HOME": str(self.home / "custom")}), \
                patch.object(sys, "argv", [str(SCRIPT), "--home", str(self.home),
                                           "--tools", "codex"]):
            self.assertEqual(linker.main(), 1)
        self.assertEqual(list(self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
