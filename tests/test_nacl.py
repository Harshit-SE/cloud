import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class NaclTests(unittest.TestCase):

    def test_sample_packets(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/nacl_sim.py"),
                str(ROOT / "network/nacl.json"),
                str(ROOT / "network/packets_sample.jsonl"),
                "--check",
            ],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Correct: 6 / 6", result.stdout)


if __name__ == "__main__":
    unittest.main()
