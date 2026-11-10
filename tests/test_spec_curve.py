"""The specification registry is the full 324-cell grid, and the hash does not move."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.spec_curve import registry_hash, specification_grid  # noqa: E402


class SpecCurveTest(unittest.TestCase):
    def test_grid_has_324_rows_and_a_stable_hash(self):
        rows = specification_grid()
        self.assertEqual(len(rows), 324)
        self.assertEqual(len({tuple(sorted(row.items())) for row in rows}), 324)
        self.assertEqual(registry_hash(rows), registry_hash(specification_grid()))
        self.assertEqual(len(registry_hash()), 16)


if __name__ == "__main__":
    unittest.main()
