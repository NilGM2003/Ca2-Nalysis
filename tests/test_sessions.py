"""Tests for the session store, config round-trip and folder scan.

Run from the repo root (no extra packages needed):

    uv run python -m unittest discover -s tests -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calcium.config import SessionConfig            # noqa: E402
from calcium.dyes import DYES, find_tif             # noqa: E402
from calcium.scan import scan_folder, split_common_prefix   # noqa: E402
from calcium.sessionstore import (                  # noqa: E402
    load_all_sessions, load_session, save_session, session_path,
    validate_session_name)
from calcium.workspace import results_dir, rois_dir  # noqa: E402


def touch(folder, *names):
    for n in names:
        (Path(folder) / n).write_bytes(b"")


def make_cfg(tmp, **over):
    kw = dict(
        name="20261001", data_dir=Path(tmp) / "data",
        out_dir=Path(tmp) / "out", file_ids=["001", "002"],
        protocol={"001": [(2, "ISO"), (4, "Yoda1"), (18.30, "ISO")],
                  "002": [(2, "ISO"), (4, "Yoda1")]},
        dye="fura2", experiment_type="chemical",
        off_labels={"STOP", "ISO"}, truncate_min={"002": 10.0},
        dose_exclude_files={"1"}, dose_exclude_dose={9.0},
        dose_label="Yoda1 (1:1000)")
    kw.update(over)
    return SessionConfig(**kw)


class ConfigRoundTrip(unittest.TestCase):
    def test_roundtrip_through_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            back = SessionConfig.from_dict(json.loads(json.dumps(cfg.to_dict())))
            self.assertEqual(cfg, back)
            self.assertIsInstance(back.off_labels, set)
            self.assertIsInstance(back.protocol["001"][0], tuple)

    def test_outputs_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            for outs in (None, {"traces.csv", "dose_pooled.png"}):
                cfg = make_cfg(tmp, outputs=outs, experiment_type="lifu",
                               dye="calbryte", off_labels={"STOP"})
                back = SessionConfig.from_dict(json.loads(json.dumps(cfg.to_dict())))
                self.assertEqual(cfg, back)
                self.assertEqual(back.outputs, outs)

    def test_unknown_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "unknown output"):
                make_cfg(tmp, outputs={"dose_pooled.png", "nonsense.csv"})

    def test_unknown_setting_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_cfg(tmp).to_dict()
            d["dye_name"] = "fura2"                      # typo
            with self.assertRaisesRegex(ValueError, "unknown setting"):
                SessionConfig.from_dict(d)

    def test_missing_required_setting_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_cfg(tmp).to_dict()
            del d["protocol"]
            with self.assertRaisesRegex(ValueError, "missing required"):
                SessionConfig.from_dict(d)

    def test_validation_still_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_cfg(tmp).to_dict()
            d["file_ids"] = ["001", "003"]               # 003 has no protocol
            with self.assertRaisesRegex(ValueError, "003"):
                SessionConfig.from_dict(d)


class Store(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            cfg = make_cfg(tmp, out_dir=results_dir(ws) / "20261001")
            path = save_session(cfg, ws)
            self.assertEqual(path, session_path("20261001", ws))
            self.assertFalse(path.with_suffix(".json.tmp").exists())

            back = load_session(path, ws)
            self.assertEqual(back.out_dir, results_dir(ws) / "20261001")
            self.assertEqual(back.rois_dir, rois_dir(ws))
            # everything except the derived paths is unchanged
            self.assertEqual(back.protocol, cfg.protocol)
            self.assertEqual(back.off_labels, cfg.off_labels)
            self.assertEqual(back.data_dir, cfg.data_dir)

    def test_workspace_paths_are_not_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            cfg = make_cfg(tmp, out_dir=results_dir(ws) / "20261001",
                           rois_dir=rois_dir(ws))
            stored = json.loads(save_session(cfg, ws).read_text())
            self.assertNotIn("out_dir", stored)
            self.assertNotIn("rois_dir", stored)
            self.assertEqual(stored["schema_version"], 1)

    def test_custom_out_dir_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            cfg = make_cfg(tmp, out_dir=Path(tmp) / "elsewhere")
            back = load_session(save_session(cfg, ws), ws)
            self.assertEqual(back.out_dir, Path(tmp) / "elsewhere")

    def test_bad_names_rejected(self):
        for bad in ("", "../x", "a b", "a/b", ".hidden", "x:y"):
            with self.assertRaises(ValueError, msg=bad):
                validate_session_name(bad)
        validate_session_name("20261001")
        validate_session_name("hek_yoda1-2.0")

    def test_unsupported_schema_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            path = save_session(make_cfg(tmp), ws)
            d = json.loads(path.read_text())
            d["schema_version"] = 99
            path.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError, "schema_version"):
                load_session(path, ws)

    def test_one_broken_session_does_not_hide_the_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            save_session(make_cfg(tmp, name="good"), ws)
            (session_path("good", ws).parent / "broken.json").write_text("{nope")
            sessions, problems = load_all_sessions(ws)
            self.assertIn("good", sessions)
            self.assertTrue(any("broken.json" in p for p in problems))

    def test_builtin_sessions_roundtrip(self):
        """Every existing sessions/sYYYYMMDD.py survives to_dict/from_dict."""
        with tempfile.TemporaryDirectory() as tmp:
            sessions, _ = load_all_sessions(Path(tmp) / "empty-ws")
        if not sessions:
            self.skipTest("built-in sessions/ package not importable here")
        for name, cfg in sessions.items():
            back = SessionConfig.from_dict(json.loads(json.dumps(cfg.to_dict())))
            self.assertEqual(cfg, back, msg=name)


class Scan(unittest.TestCase):
    def folder(self, *names):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        touch(tmp.name, *names)
        return Path(tmp.name)

    def test_fura2_pairs(self):
        r = scan_folder(self.folder("001_340.TIF", "001_380.TIF",
                                    "002_340.TIF", "002_380.TIF", "RoiSet.zip"))
        self.assertEqual((r.dye, r.file_ids), ("fura2", ["001", "002"]))
        self.assertEqual(r.warnings, [])

    def test_unpaired_channel_is_reported_not_used(self):
        r = scan_folder(self.folder("001_340.TIF", "001_380.TIF", "002_340.TIF"))
        self.assertEqual(r.file_ids, ["001"])
        self.assertTrue(any("002" in w and "380" in w for w in r.warnings))

    def test_calbryte_plain_files_sorted_naturally(self):
        r = scan_folder(self.folder("10.TIF", "2.TIF", "1.TIF"))
        self.assertEqual((r.dye, r.file_ids), ("calbryte", ["1", "2", "10"]))

    def test_case_and_extension_do_not_matter(self):
        r = scan_folder(self.folder("A_340.tif", "A_380.TIFF"))
        self.assertEqual((r.dye, r.file_ids), ("fura2", ["A"]))

    def test_hidden_files_ignored(self):
        r = scan_folder(self.folder("._001_340.TIF", ".DS_Store", "1.TIF"))
        self.assertEqual((r.dye, r.file_ids), ("calbryte", ["1"]))

    def test_mixed_folder_uses_larger_group_and_warns(self):
        r = scan_folder(self.folder("001_340.TIF", "001_380.TIF",
                                    "002_340.TIF", "002_380.TIF", "9.TIF"))
        self.assertEqual((r.dye, r.file_ids), ("fura2", ["001", "002"]))
        self.assertTrue(any("calbryte" in w and "9" in w for w in r.warnings))

    def test_empty_folder(self):
        r = scan_folder(self.folder("notes.txt"))
        self.assertIsNone(r.dye)
        self.assertEqual(r.file_ids, [])
        self.assertTrue(r.warnings)

    def test_not_a_folder(self):
        with self.assertRaises(NotADirectoryError):
            scan_folder(Path(tempfile.gettempdir()) / "definitely-not-here-xyz")

    def test_shared_prefix_is_split_off(self):
        r = scan_folder(self.folder("20260623_1.tif", "20260623_10.tif",
                                    "20260623_2.tif"))
        self.assertEqual((r.dye, r.prefix, r.file_ids),
                         ("calbryte", "20260623_", ["1", "2", "10"]))

    def test_single_file_with_prefix(self):
        r = scan_folder(self.folder("20260623_1.tif"))
        self.assertEqual((r.prefix, r.file_ids), ("20260623_", ["1"]))

    def test_prefix_with_fura2_pairs(self):
        r = scan_folder(self.folder("20261001_001_340.TIF", "20261001_001_380.TIF",
                                    "20261001_002_340.TIF", "20261001_002_380.TIF"))
        self.assertEqual((r.dye, r.prefix, r.file_ids),
                         ("fura2", "20261001_", ["001", "002"]))

    def test_no_prefix_without_a_separator(self):
        r = scan_folder(self.folder("001_340.TIF", "001_380.TIF",
                                    "002_340.TIF", "002_380.TIF"))
        self.assertEqual((r.prefix, r.file_ids), ("", ["001", "002"]))

    def test_split_common_prefix_edge_cases(self):
        self.assertEqual(split_common_prefix(["a_1", "a_2"]), ("a_", ["1", "2"]))
        self.assertEqual(split_common_prefix(["1", "2", "10"]), ("", ["1", "2", "10"]))
        self.assertEqual(split_common_prefix(["001", "002"]), ("", ["001", "002"]))
        self.assertEqual(split_common_prefix(["x_", "x_1"]), ("", ["x_", "x_1"]))
        self.assertEqual(split_common_prefix(["Hek 1", "Hek 2"]), ("Hek ", ["1", "2"]))
        self.assertEqual(split_common_prefix([]), ("", []))

    def test_dye_paths_use_the_prefix(self):
        folder = self.folder("20260623_1.tif", "exp_001_340.TIF", "exp_001_380.TIF")
        self.assertEqual(DYES["calbryte"].paths(folder, "1", "20260623_")[0].name,
                         "20260623_1.tif")
        self.assertEqual([p.name for p in DYES["fura2"].paths(folder, "001", "exp_")],
                         ["exp_001_340.TIF", "exp_001_380.TIF"])

    def test_find_tif_ignores_case(self):
        folder = self.folder("sample_340.tif")
        self.assertEqual(find_tif(folder, "SAMPLE_340").name, "sample_340.tif")
        self.assertEqual(find_tif(folder, "other").name, "other.TIF")


if __name__ == "__main__":
    unittest.main()
