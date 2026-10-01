import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class RegimeTableTest(unittest.TestCase):
    def test_generated_module_matches_csv(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/regime_table.py"), "--check"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
