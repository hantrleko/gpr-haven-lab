"""The Python claim sentence and claim_rule.js return the same string."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.claim_text import claim_rule  # noqa: E402

NODE = r"""
const fs = require("fs");
const vm = require("vm");
const ctx = {};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const input = JSON.parse(process.argv[2]);
process.stdout.write(ctx.claimRule(input).claim);
"""


def claim_js(payload: dict) -> str:
    done = subprocess.run(
        ["node", "-e", NODE, str(ROOT / "src" / "havenlab" / "ui" / "claim_rule.js"), json.dumps(payload)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return done.stdout


class StaticClaimTest(unittest.TestCase):
    def test_python_matches_node_including_a_crossing_interval(self):
        cases = (
            {"g": 10, "c": -5, "b": 0, "anchorIsGold": True, "showCsi": True, "showBrent": True, "pct": 0.55, "q": None, "lang": "zh"},
            {"g": 10, "c": -5, "b": 0, "anchorIsGold": True, "showCsi": True, "showBrent": True, "pct": 0.95, "q": 0.04, "lang": "zh"},
            {"g": 10, "c": -5, "b": 0, "anchorIsGold": True, "showCsi": True, "showBrent": True, "pct": 0.18, "pct_lo": 0.03, "pct_hi": 0.34, "q": 0.04, "lang": "zh"},
            {"g": 10, "c": -5, "b": 0, "anchorIsGold": True, "showCsi": True, "showBrent": True, "pct": 0.92, "pct_lo": 0.85, "pct_hi": 0.97, "q": 0.04, "lang": "en", "exploratory": True},
        )
        for payload in cases:
            python = claim_rule(payload)["claim"]
            node = claim_js(payload)
            self.assertEqual(python, node)
            if payload.get("pct") == 0.18:
                self.assertNotIn("避险分流", python)


if __name__ == "__main__":
    unittest.main()
