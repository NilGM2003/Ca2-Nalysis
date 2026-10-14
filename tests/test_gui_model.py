"""Tests for the app's form logic (no window needed).

    uv run python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calcium.gui import model                         # noqa: E402
from calcium.outputs import applicable_keys            # noqa: E402
from calcium.scan import ScanResult                   # noqa: E402
from calcium.workspace import results_dir, rois_dir   # noqa: E402


def good_form(tmp, **over):
    data = Path(tmp) / "data"
    data.mkdir(exist_ok=True)
    f = model.default_form()
    f.update(name="20261001", data_dir=str(data), dye="fura2",
             experiment_type="chemical", off_labels="STOP, ISO",
             file_ids=["001", "002"],
             outputs=sorted(applicable_keys("chemical")),
             protocols={"001": "2, ISO\n4, Yoda1\n6, ISO",
                        "002": "2, ISO\n5, Yoda1\n8, ISO"})
    f.update(over)
    return f


class ProtocolText(unittest.TestCase):
    def test_parse_basic(self):
        self.assertEqual(model.parse_protocol_text("2, 4.5V\n4, STOP"),
                         [(2, "4.5V"), (4, "STOP")])

    def test_comments_blank_lines_and_separators(self):
        text = "# header\n\n2  ISO   # wash\n 18.30,Yoda1 10uM\n"
        self.assertEqual(model.parse_protocol_text(text),
                         [(2, "ISO"), (18.3, "Yoda1 10uM")])

    def test_bad_lines_name_the_line(self):
        with self.assertRaisesRegex(ValueError, "line 2"):
            model.parse_protocol_text("2, ISO\nfoo, Yoda1")
        with self.assertRaisesRegex(ValueError, "line 1"):
            model.parse_protocol_text("3")

    def test_seconds_must_be_below_60(self):
        with self.assertRaisesRegex(ValueError, "mm.ss"):
            model.parse_protocol_text("5.75, ISO")

    def test_times_must_increase(self):
        with self.assertRaisesRegex(ValueError, "increase"):
            model.parse_protocol_text("4, ISO\n2, Yoda1")

    def test_text_roundtrip(self):
        ev = [(2, "ISO"), (4, "Yoda1"), (18.3, "ISO")]
        self.assertEqual(model.parse_protocol_text(model.protocol_to_text(ev)), ev)

    def test_truncate(self):
        self.assertEqual(model.parse_truncate("6: 27, 1=15"), {"6": 27.0, "1": 15.0})
        self.assertEqual(model.parse_truncate(""), {})
        with self.assertRaises(ValueError):
            model.parse_truncate("six")


class BuildConfig(unittest.TestCase):
    def test_valid_chemical_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            cfg = model.build_config(good_form(tmp), ws)
            self.assertEqual(cfg.dye, "fura2")
            self.assertEqual(cfg.off_labels, {"STOP", "ISO"})
            self.assertEqual(cfg.out_dir, results_dir(ws) / "20261001")
            self.assertEqual(cfg.rois_dir, rois_dir(ws))
            self.assertEqual(cfg.protocol["002"][1], (5, "Yoda1"))

    def test_form_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            cfg = model.build_config(good_form(tmp), ws)
            again = model.build_config(model.form_from_config(cfg), ws)
            self.assertEqual(cfg, again)

    def test_all_problems_reported_at_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            form = good_form(tmp, name="bad name", data_dir="/nope/nowhere",
                             resp_k="abc")
            form["protocols"]["001"] = "oops"
            form["protocols"]["002"] = ""
            with self.assertRaises(model.FormError) as cm:
                model.build_config(form, Path(tmp) / "ws")
            text = " | ".join(cm.exception.problems)
            for needle in ("session name", "does not exist", "file 001",
                           "file 002", "Responder k"):
                self.assertIn(needle, text)

    def test_only_off_labels_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            form = good_form(tmp)
            form["protocols"]["001"] = "2, ISO\n6, ISO"
            with self.assertRaisesRegex(model.FormError, "nothing to analyse"):
                model.build_config(form, Path(tmp) / "ws")

    def test_lifu_needs_numeric_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            form = good_form(tmp, experiment_type="lifu", off_labels="STOP",
                             file_ids=["001"])
            form["protocols"] = {"001": "2, ISO\n4, STOP"}
            with self.assertRaisesRegex(model.FormError, "no number"):
                model.build_config(form, Path(tmp) / "ws")
            form["protocols"] = {"001": "2, 4.5V\n4, STOP"}
            cfg = model.build_config(form, Path(tmp) / "ws")
            self.assertEqual(cfg.protocol["001"], [(2, "4.5V"), (4, "STOP")])

    def test_truncate_must_name_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            form = good_form(tmp, truncate="999: 5")
            with self.assertRaisesRegex(model.FormError, "999"):
                model.build_config(form, Path(tmp) / "ws")

    def test_whole_number_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            form = good_form(tmp, min_area="15.5")
            with self.assertRaisesRegex(model.FormError, "whole number"):
                model.build_config(form, Path(tmp) / "ws")


class Outputs(unittest.TestCase):
    def test_everything_ticked_means_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            form = good_form(tmp)                       # chemical
            form["outputs"] = sorted(applicable_keys("chemical"))
            self.assertIsNone(model.build_config(form, Path(tmp) / "ws").outputs)

    def test_subset_is_kept_and_wrong_type_keys_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            form = good_form(tmp)                       # chemical
            form["outputs"] = ["condition_summary.csv", "cells.png",
                               "dose_pooled.png"]        # last one is LIFU-only
            cfg = model.build_config(form, Path(tmp) / "ws")
            self.assertEqual(cfg.outputs, {"condition_summary.csv", "cells.png"})

    def test_nothing_ticked_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            form = good_form(tmp)
            form["outputs"] = ["dose_pooled.png"]        # nothing that applies
            with self.assertRaisesRegex(model.FormError, "at least one"):
                model.build_config(form, Path(tmp) / "ws")

    def test_form_roundtrip_with_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            form = good_form(tmp)
            form["outputs"] = ["metrics.csv", "traces.csv"]
            cfg = model.build_config(form, ws)
            again = model.build_config(model.form_from_config(cfg), ws)
            self.assertEqual(cfg, again)

    def test_default_form_ticks_all_lifu_outputs(self):
        self.assertEqual(set(model.default_form()["outputs"]),
                         applicable_keys("lifu"))

    def test_form_from_old_session_lists_everything_that_applies(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = model.build_config(good_form(tmp), Path(tmp) / "ws")   # None
            self.assertEqual(set(model.form_from_config(cfg)["outputs"]),
                             applicable_keys("chemical"))


class FilePrefix(unittest.TestCase):
    def test_prefix_roundtrip_and_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            form = good_form(tmp, dye="calbryte", experiment_type="lifu",
                             off_labels="STOP", file_prefix="20260623_",
                             file_ids=["1", "2"])
            form["protocols"] = {"1": "2, 1Hz@DC20\n8, STOP",
                                 "2": "2, 10Hz@DC20\n8, STOP"}
            cfg = model.build_config(form, ws)
            self.assertEqual(cfg.file_prefix, "20260623_")
            self.assertEqual(cfg, model.build_config(model.form_from_config(cfg), ws))

            self.assertEqual(model.missing_files(cfg),
                             ["20260623_1.TIF", "20260623_2.TIF"])
            data = Path(cfg.data_dir)
            (data / "20260623_1.tif").write_bytes(b"")
            self.assertEqual(model.missing_files(cfg), ["20260623_2.TIF"])
            (data / "20260623_2.TIF").write_bytes(b"")
            self.assertEqual(model.missing_files(cfg), [])

    def test_prefix_with_slash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            form = good_form(tmp, file_prefix="a/b_")
            with self.assertRaisesRegex(model.FormError, "prefix"):
                model.build_config(form, Path(tmp) / "ws")

    def test_apply_scan_sets_prefix(self):
        form = model.default_form()
        scan = ScanResult(Path("."), "calbryte", ["1", "2"], [], "20260623_")
        model.apply_scan(form, scan)
        self.assertEqual(form["file_prefix"], "20260623_")


class FormOperations(unittest.TestCase):
    def test_apply_scan_keeps_existing_protocols(self):
        form = model.default_form()
        form["file_ids"] = ["001"]
        form["protocols"] = {"001": "2, ISO"}
        scan = ScanResult(Path("."), "fura2", ["001", "002"], ["a warning"])
        msgs = model.apply_scan(form, scan)
        self.assertEqual(form["dye"], "fura2")
        self.assertEqual(form["file_ids"], ["001", "002"])
        self.assertEqual(form["protocols"], {"001": "2, ISO", "002": ""})
        self.assertIn("a warning", msgs)

    def test_apply_scan_with_nothing_found_changes_nothing(self):
        form = model.default_form()
        form["file_ids"] = ["x"]
        model.apply_scan(form, ScanResult(Path("."), None, [], ["empty"]))
        self.assertEqual(form["file_ids"], ["x"])

    def test_copy_protocol_to_all(self):
        form = model.default_form()
        form["file_ids"] = ["1", "2", "3"]
        form["protocols"] = {"1": "2, ISO", "2": "", "3": "9, X"}
        model.copy_protocol_to_all(form, "1")
        self.assertEqual(set(form["protocols"].values()), {"2, ISO"})


if __name__ == "__main__":
    unittest.main()
