"""Read-only checks for the bundled upstream Apache 2.0 license payloads."""

import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

# SHA-256 of the original public license bytes, captured before migration.
# Keep these fixtures independent of Git refs and removed source paths.
FRONTEND_SHA256 = "0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594"
FULL_SHA256 = "58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd"
LICENSES = {
    "stow/opencode/.config/opencode/skills/frontend-design/LICENSE.txt": FRONTEND_SHA256,
    "stow/opencode/.config/opencode/skills/skill-creator/LICENSE.txt": FULL_SHA256,
}


class BundledLicenses(unittest.TestCase):
    def test_meaningful_apache_license_text(self):
        for relative_path, expected_sha256 in LICENSES.items():
            with self.subTest(path=relative_path):
                payload = (ROOT / relative_path).read_bytes()
                self.assertTrue(payload.strip(), "bundled license must not be empty")
                text = payload.decode("utf-8")
                self.assertIn("Apache License\n", text)
                self.assertIn("Version 2.0, January 2004", text)
                self.assertIn("TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION", text)
                self.assertIn("2. Grant of Copyright License.", text)
                self.assertIn("END OF TERMS AND CONDITIONS", text)
                if expected_sha256 == FULL_SHA256:
                    self.assertIn("APPENDIX: How to apply the Apache License to your work.", text)
                    self.assertIn('Licensed under the Apache License, Version 2.0 (the "License");', text)

    def test_exact_original_license_bytes(self):
        for relative_path, expected_sha256 in LICENSES.items():
            with self.subTest(path=relative_path):
                payload = (ROOT / relative_path).read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), expected_sha256)


if __name__ == "__main__":
    unittest.main()
