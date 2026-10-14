"""Tests for the list of results a session can produce (outputs.py)."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calcium.outputs import (OUTPUTS, all_keys, applicable_keys,   # noqa: E402
                             specs_for, wanted, wants_any)


def cfg(experiment_type, outputs=None):
    return SimpleNamespace(experiment_type=experiment_type, outputs=outputs)


class Registry(unittest.TestCase):
    def test_keys_are_unique(self):
        keys = [k for s in OUTPUTS for k in s.keys()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_formats_are_png_or_csv(self):
        for s in OUTPUTS:
            self.assertTrue(s.formats and set(s.formats) <= {"png", "csv"}, s.name)
            self.assertTrue(set(s.experiments) <= {"lifu", "chemical"}, s.name)

    def test_types_have_different_outputs(self):
        lifu, chem = applicable_keys("lifu"), applicable_keys("chemical")
        self.assertIn("dose_pooled.png", lifu)
        self.assertNotIn("dose_pooled.png", chem)
        self.assertIn("condition_summary.csv", chem)
        self.assertNotIn("condition_summary.csv", lifu)
        for common in ("wholefield.png", "cells.png", "celltraces.png",
                       "traces.csv", "metrics.csv"):
            self.assertIn(common, lifu & chem)
        self.assertEqual(lifu | chem, all_keys())

    def test_specs_for_keeps_order_and_groups_together(self):
        groups = [s.group for s in specs_for("lifu")]
        seen = []
        for g in groups:                       # each group appears in one block
            if not seen or seen[-1] != g:
                seen.append(g)
        self.assertEqual(len(seen), len(set(seen)))


class Wanted(unittest.TestCase):
    def test_none_means_everything_that_applies(self):
        self.assertTrue(wanted(cfg("lifu"), "latency.csv"))
        self.assertFalse(wanted(cfg("lifu"), "condition_summary.csv"))
        self.assertTrue(wanted(cfg("chemical"), "condition_summary.csv"))
        self.assertFalse(wanted(cfg("chemical"), "latency.csv"))

    def test_explicit_selection(self):
        c = cfg("lifu", {"traces.csv", "dose_pooled.png"})
        self.assertTrue(wanted(c, "traces.csv"))
        self.assertTrue(wanted(c, "dose_pooled.png"))
        self.assertFalse(wanted(c, "dose_pooled.csv"))
        self.assertFalse(wanted(c, "cells.png"))

    def test_selection_never_enables_the_wrong_type(self):
        c = cfg("chemical", {"dose_pooled.png", "condition_summary.csv"})
        self.assertFalse(wanted(c, "dose_pooled.png"))
        self.assertTrue(wanted(c, "condition_summary.csv"))

    def test_wants_any(self):
        c = cfg("lifu", {"latency.png"})
        self.assertTrue(wants_any(c, "latency.png", "latency.csv"))
        self.assertFalse(wants_any(c, "by_dc.png", "by_dc.csv"))


if __name__ == "__main__":
    unittest.main()
