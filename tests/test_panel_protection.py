import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProtectedControlPanelTests(unittest.TestCase):
    def test_panel_files_match_admin_approved_hashes(self):
        manifest = json.loads((ROOT / "panel_protection.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("policy"), "Changes require explicit administrator approval")
        for item in manifest["files"]:
            with self.subTest(path=item["path"]):
                actual = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
                self.assertEqual(actual, item["sha256"],
                                 f"Protected panel file changed without updating its approved baseline: {item['path']}")


if __name__ == "__main__":
    unittest.main()
