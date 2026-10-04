"""Tests for the Tcl/Tk path fix (uses a fake Python install, no Tk needed)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calcium.gui.tcltk import point_tcl_tk_at_base_python   # noqa: E402


def fake_install(tmp, tcl="9.0", tk="9.0", extra=()):
    lib = Path(tmp) / "lib"
    for stem, ver, marker in (("tcl", tcl, "init.tcl"), ("tk", tk, "tk.tcl")):
        if ver:
            (lib / f"{stem}{ver}").mkdir(parents=True)
            (lib / f"{stem}{ver}" / marker).write_text("")
    for d in extra:                              # dirs without the marker file
        (lib / d).mkdir(parents=True, exist_ok=True)
    return Path(tmp)


class TclTkPaths(unittest.TestCase):
    def test_sets_both_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = fake_install(tmp)
            env = {}
            changed = point_tcl_tk_at_base_python(
                base, env, {"TCL_LIBRARY": "9.0", "TK_LIBRARY": "9.0"})
            self.assertEqual(env["TCL_LIBRARY"], str(base / "lib" / "tcl9.0"))
            self.assertEqual(env["TK_LIBRARY"], str(base / "lib" / "tk9.0"))
            self.assertEqual(set(changed), {"TCL_LIBRARY", "TK_LIBRARY"})

    def test_existing_variables_are_not_overridden(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = fake_install(tmp)
            env = {"TCL_LIBRARY": "/mine/tcl"}
            point_tcl_tk_at_base_python(base, env, {})
            self.assertEqual(env["TCL_LIBRARY"], "/mine/tcl")
            self.assertIn("TK_LIBRARY", env)

    def test_prefers_the_version_python_was_linked_with(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = fake_install(tmp, tcl="8.6", tk="8.6")
            for stem, ver, marker in (("tcl", "9.0", "init.tcl"),
                                      ("tk", "9.0", "tk.tcl")):
                (base / "lib" / f"{stem}{ver}").mkdir()
                (base / "lib" / f"{stem}{ver}" / marker).write_text("")
            env = {}
            point_tcl_tk_at_base_python(
                base, env, {"TCL_LIBRARY": "8.6", "TK_LIBRARY": "8.6"})
            self.assertTrue(env["TCL_LIBRARY"].endswith("tcl8.6"))
            self.assertTrue(env["TK_LIBRARY"].endswith("tk8.6"))

    def test_falls_back_to_newest_when_version_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = fake_install(tmp, tcl="9.0", tk="9.0")
            env = {}
            point_tcl_tk_at_base_python(base, env, {})
            self.assertTrue(env["TCL_LIBRARY"].endswith("tcl9.0"))

    def test_ignores_directories_without_the_marker_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = fake_install(tmp, tcl="9.0", tk=None, extra=("tcl8", "tk9.0"))
            env = {}
            point_tcl_tk_at_base_python(base, env, {})
            self.assertTrue(env["TCL_LIBRARY"].endswith("tcl9.0"))   # not tcl8
            self.assertNotIn("TK_LIBRARY", env)                      # no tk.tcl

    def test_nothing_found_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {}
            self.assertEqual(point_tcl_tk_at_base_python(Path(tmp), env, {}), {})
            self.assertEqual(env, {})


if __name__ == "__main__":
    unittest.main()
