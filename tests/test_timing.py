"""Tests for frames without timing and channel alignment in the loader.

``load_tif`` is replaced by a fake, so no TIF files or tifffile are needed.
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calcium import dyes                              # noqa: E402
from calcium.dyes import DYES, load_recording          # noqa: E402


def fake_stack(times_s, value=100.0):
    frames = np.full((len(times_s), 2, 3), value, np.float32)
    return frames, np.asarray(times_s, float)


def load(dye, fakes, folder, fid, max_min=None):
    """Run load_recording with load_tif returning ``fakes`` in order."""
    for p in dye.paths(Path(folder), fid):
        p.write_bytes(b"")                         # the files only need to exist
    err = io.StringIO()
    with mock.patch.object(dyes, "load_tif", side_effect=fakes), \
            contextlib.redirect_stderr(err):
        out = load_recording(dye, Path(folder), fid, max_min)
    return out, err.getvalue()


class UntimedFrames(unittest.TestCase):
    def test_trailing_zero_times_are_dropped_with_a_warning(self):
        frames, t = fake_stack([0, 4.4, 8.8, 13.2, 0, 0])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            kept, kept_t = dyes._drop_untimed_frames(frames, t, "x.TIF")
        self.assertEqual(len(kept), 4)
        self.assertEqual(list(kept_t), [0, 4.4, 8.8, 13.2])
        self.assertIn("last 2 of 6", err.getvalue())

    def test_a_clean_file_is_untouched_and_silent(self):
        frames, t = fake_stack([0, 5, 10])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            kept, _ = dyes._drop_untimed_frames(frames, t, "x.TIF")
        self.assertEqual(len(kept), 3)
        self.assertEqual(err.getvalue(), "")

    def test_no_timestamps_at_all_is_an_error(self):
        frames, t = fake_stack([0, 0, 0])
        with self.assertRaisesRegex(ValueError, "no frame has a timestamp"):
            dyes._drop_untimed_frames(frames, t, "x.TIF")

    def test_times_that_do_not_increase_are_an_error(self):
        frames, t = fake_stack([0, 5, 4, 15])
        with self.assertRaisesRegex(ValueError, "do not increase"):
            dyes._drop_untimed_frames(frames, t, "x.TIF")

    def test_single_channel_recording_is_trimmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            (_, _, wf, t_s), err = load(DYES["calbryte"],
                                        [fake_stack([0, 3, 6, 0, 0])], tmp, "1")
            self.assertEqual(len(t_s), 3)
            self.assertEqual(len(wf), 3)
            self.assertIn("dropped", err)


class FuraChannels(unittest.TestCase):
    def test_off_by_one_channel_is_trimmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            f340 = fake_stack([0, 4.4, 8.8, 13.2, 17.6], 200.0)     # 5 frames
            f380 = fake_stack([1, 5.4, 9.8, 14.2, 0], 100.0)        # 4 timed
            ((num, den), seg, wf, t_s), err = load(DYES["fura2"],
                                                   [f340, f380], tmp, "001")
            self.assertEqual((len(num), len(den), len(t_s), len(wf)), (4, 4, 4, 4))
            self.assertTrue(np.allclose(wf, 2.0))               # 200 / 100
            self.assertIn("channels have", err)

    def test_large_difference_between_channels_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            f340 = fake_stack([0, 4, 8, 12, 16, 20])
            f380 = fake_stack([1, 5, 9])
            with self.assertRaisesRegex(ValueError, "very different"):
                load(DYES["fura2"], [f340, f380], tmp, "001")

    def test_different_image_sizes_are_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            f340 = fake_stack([0, 4, 8])
            other = (np.ones((3, 5, 5), np.float32), np.array([1.0, 5, 9]))
            with self.assertRaisesRegex(ValueError, "differ in size"):
                load(DYES["fura2"], [f340, other], tmp, "001")

    def test_truncation_keeps_channels_aligned(self):
        """380 is stamped ~1 s after 340: cropping must not split the pair."""
        with tempfile.TemporaryDirectory() as tmp:
            t340 = [0, 30, 60, 90, 120]
            t380 = [1, 31, 61, 91, 121]
            (( num, den), _, _, t_s), _ = load(
                DYES["fura2"], [fake_stack(t340), fake_stack(t380)], tmp,
                "001", max_min=1.0)          # 60 s: 340 keeps 0,30,60
            self.assertEqual((len(num), len(den), len(t_s)), (3, 3, 3))


if __name__ == "__main__":
    unittest.main()
