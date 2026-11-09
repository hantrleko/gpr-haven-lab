"""Card tails for a gold-up / CSI-down window match claim_rule.js."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.cards import _sentence, split_claim  # noqa: E402

NODE = r"""
const fs = require("fs");
const vm = require("vm");
const ctx = {};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const input = JSON.parse(process.argv[2]);
process.stdout.write(ctx.claimRule(input).claim);
"""


def claim_js(g, c, pct, q):
    payload = {
        "g": g,
        "c": c,
        "b": 0,
        "anchorIsGold": True,
        "showCsi": True,
        "showBrent": True,
        "pct": pct,
        "q": q,
        "lang": "zh",
    }
    done = subprocess.run(
        ["node", "-e", NODE, str(ROOT / "src" / "havenlab" / "ui" / "claim_rule.js"), json.dumps(payload)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return done.stdout


class CardClaimTest(unittest.TestCase):
    def test_split_claim_matches_the_page_rule(self):
        cases = (
            (10, -5, 0.55, None),
            (10, -5, 0.95, 0.04),
            (10, -5, 0.95, 0.2),
        )
        for g, c, pct, q in cases:
            self.assertEqual(split_claim(g, c, pct, q).rstrip(), claim_js(g, c, pct, q).rstrip())

    def test_hormuz_card_keeps_the_gold_decline_sentence(self):
        window = {"partial": 0, "n_after": 6, "cum": {"gold": -15.79, "csi": -1.83}}
        _line, tail = _sentence(window, pct=0.04, q=0.47)
        self.assertEqual(tail, "黄金在这段窗口里下跌。")
        self.assertNotIn("避险分流", tail)


if __name__ == "__main__":
    unittest.main()
