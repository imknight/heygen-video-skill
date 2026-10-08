"""Offline tests for the HeyGen helper. Run: python3 -m unittest discover tests"""
from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "heygen-video" / "scripts"))
import heygen_video as h  # noqa: E402

ASSET = {"type": "asset_id", "asset_id": "a"}


def req(**extra):
    base = {"model": "heygen-video-1", "mode": "text_to_video", "prompt": "x", "duration": 10, "resolution": "768p"}
    base.update(extra)
    return base


class Pricing(unittest.TestCase):
    def test_promo_and_standard(self):
        self.assertEqual(h.estimate(req(), None, date(2026, 10, 31))["estimated_cost"], "0.150")
        self.assertEqual(h.estimate(req(), None, date(2026, 11, 1))["estimated_cost"], "0.300")

    def test_reference_bills_input_video_seconds(self):
        r = req(mode="reference_to_video", resolution="480p", reference_videos=[ASSET])
        self.assertEqual(h.estimate(r, 4, date(2026, 10, 9))["estimated_cost"], "0.280")

    def test_high_res_is_three_times_768p(self):
        r = req(resolution="1080p", aspect_ratio="9:16")
        self.assertEqual(h.estimate(r, None, date(2026, 11, 2))["rate_per_second"], "0.090")

    def test_stale_flag(self):
        self.assertFalse(h.estimate(req(), None, date(2026, 10, 20))["pricing_stale"])
        self.assertTrue(h.estimate(req(), None, date(2026, 12, 1))["pricing_stale"])


class Validation(unittest.TestCase):
    def bad(self, r):
        with self.assertRaises(ValueError):
            h.validate(r)

    def test_rejects_invalid_requests(self):
        self.bad(req(seed=-1))
        self.bad(req(seed=True))
        self.bad(req(style="anime"))
        self.bad(req(reference_images=[ASSET]))
        self.bad(req(prompt_enhancement="max"))
        self.bad(req(callback_url="http://example.com"))
        self.bad(req(resolution="2k", aspect_ratio="1:1"))
        self.bad(req(mode="image_to_video", image=ASSET, aspect_ratio="16:9"))
        self.bad(req(mode="reference_to_video", reference_audio=[ASSET]))
        self.bad(req(mode="reference_to_video", reference_images=[{"type": "url", "url": "http://x"}]))
        self.bad(req(mode="reference_to_video", reference_images=[ASSET] * 10))

    def test_accepts_valid_requests(self):
        h.validate(req(seed=0, aspect_ratio="9:16", prompt_enhancement="disabled"))
        h.validate(req(mode="t2v", resolution="1080p"))
        h.validate(req(mode="image_to_video", image=ASSET))
        h.validate(req(mode="reference_to_video", aspect_ratio="adaptive",
                       reference_images=[ASSET], reference_audio=[ASSET]))


if __name__ == "__main__":
    unittest.main()
