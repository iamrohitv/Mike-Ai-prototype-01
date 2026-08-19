import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interfaces.desktop.hud import (
    STATE_COLORS,
    arc_coords,
    blend,
    format_battery,
    format_percent,
    particle_field,
    pulse_radius,
    state_color,
    state_status,
    tri,
    waveform_heights,
)


class HudHelpersTest(unittest.TestCase):
    def test_state_color_maps_all_states(self):
        for state, expected in STATE_COLORS.items():
            self.assertEqual(state_color(state), expected)

    def test_state_color_defaults_to_idle(self):
        self.assertEqual(state_color("unknown"), STATE_COLORS["idle"])

    def test_state_status_text(self):
        self.assertIn("LISTENING", state_status("listening"))
        self.assertIn("THINKING", state_status("thinking"))
        self.assertIn("SPEAKING", state_status("speaking"))

    def test_tri_oscillates_between_zero_and_one(self):
        self.assertAlmostEqual(tri(0.0), 0.0)
        self.assertAlmostEqual(tri(0.5), 1.0)
        self.assertAlmostEqual(tri(1.0), 0.0)

    def test_blend_produces_hex_color(self):
        out = blend("#000000", "#ffffff", 0.5)
        self.assertEqual(out, "#7f7f7f")
        self.assertTrue(out.startswith("#"))

    def test_arc_coords_geometry(self):
        x0, y0, x1, y1, sx, sy, ex, ey = arc_coords(100, 100, 50, 0, 90)
        self.assertEqual((x0, y0), (50, 50))
        self.assertEqual((x1, y1), (150, 150))
        self.assertAlmostEqual(sx, 150.0)
        self.assertAlmostEqual(sy, 100.0)
        self.assertAlmostEqual(ex, 100.0, places=6)
        self.assertAlmostEqual(ey, 150.0, places=6)

    def test_waveform_idle_is_flat(self):
        heights = waveform_heights(0, "idle", bars=21)
        self.assertEqual(len(heights), 21)
        self.assertTrue(all(h == heights[0] for h in heights))

    def test_waveform_active_varies(self):
        heights = waveform_heights(5, "listening", bars=21)
        self.assertEqual(len(heights), 21)
        self.assertGreater(len(set(heights)), 1)

    def test_pulse_radius_stays_close_to_base(self):
        base = 50.0
        for frame in range(24):
            r = pulse_radius(base, frame)
            self.assertGreater(r, base * 0.9)
            self.assertLess(r, base * 1.1)

    def test_particle_field_count_and_ranges(self):
        field = particle_field(42, count=26)
        self.assertEqual(len(field), 26)
        for x, y, r in field:
            self.assertGreaterEqual(x, -1.0)
            self.assertLessEqual(x, 1.0)
            self.assertGreaterEqual(y, -1.0)
            self.assertLessEqual(y, 1.0)
            self.assertGreaterEqual(r, 0.1)
            self.assertLessEqual(r, 0.8)

    def test_format_percent(self):
        self.assertEqual(format_percent(42.6), "43%")
        self.assertEqual(format_percent(None), "—")

    def test_format_battery(self):
        self.assertIn("42%", format_battery(42.2, True))
        self.assertIn("42%", format_battery(42.2, False))
        self.assertEqual(format_battery(None, False), "—")


if __name__ == "__main__":
    unittest.main()