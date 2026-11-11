"""A dead page or a browser challenge is a failed source, not an empty success."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from havenlab.source_check import classify_body


class SourceCheckTest(unittest.TestCase):
    def test_404_is_failed(self) -> None:
        self.assertEqual(classify_body(404, b"not found"), "failed")

    def test_javascript_challenge_is_blocked(self) -> None:
        body = b"<html>This site requires JavaScript to verify your browser</html>"
        self.assertEqual(classify_body(200, body), "blocked")

    def test_csv_is_ok(self) -> None:
        self.assertEqual(classify_body(200, b"DATE,DFII10\n2003-01-02,2.1\n"), "ok")


if __name__ == "__main__":
    unittest.main()
