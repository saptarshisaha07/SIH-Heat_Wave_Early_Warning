"""Unit tests for Thermal Index & WBGT mathematical functions (Task 07)."""

import unittest
from app.services.thermal_index import (
    heat_index,
    wbgt,
    compute_thermal_metrics,
)


class TestThermalIndex(unittest.TestCase):
    """Test suite verifying NWS Rothfusz Heat Index and simplified BOM WBGT calculations."""

    def test_imports_and_numeric_return_types(self):
        """Verify heat_index and wbgt return numeric float values."""
        hi_val = heat_index(30.0, 50.0)
        wbgt_val = wbgt(30.0, 50.0)

        self.assertIsInstance(hi_val, (int, float))
        self.assertIsInstance(wbgt_val, (int, float))

    def test_heat_index_humid_vs_dry(self):
        """High humidity at same temperature must produce significantly higher Heat Index."""
        hi_humid = heat_index(35.0, 70.0)
        hi_dry = heat_index(35.0, 20.0)

        self.assertGreater(hi_humid, hi_dry)
        # 35 C at 70% RH is extreme heat danger (> 48 C)
        self.assertGreaterEqual(hi_humid, 48.0)
        # 35 C at 20% RH feels close to ambient
        self.assertLessEqual(hi_dry, 36.0)

    def test_celsius_fahrenheit_conversion_and_steadman(self):
        """Mild temperatures (< 26.7 C / 80 F) should use Steadman approximation."""
        # 20 C at 50% RH -> 68 F, 50% RH
        hi_mild = heat_index(20.0, 50.0)
        self.assertAlmostEqual(hi_mild, 20.0, delta=1.5)

        # 15 C at 60% RH
        hi_cool = heat_index(15.0, 60.0)
        self.assertAlmostEqual(hi_cool, 14.5, delta=1.5)

    def test_nws_rothfusz_benchmarks_and_adjustments(self):
        """Verify Heat Index matches published NOAA/NWS reference tables and adjustments."""
        # Case 1: 30 C (~86 F) at 60% RH -> ~32.5 C (90.5 F)
        hi_30 = heat_index(30.0, 60.0)
        self.assertAlmostEqual(hi_30, 32.5, delta=1.5)

        # Case 2: 38 C (~100 F) at 50% RH -> ~50 C (122 F)
        hi_38 = heat_index(38.0, 50.0)
        self.assertAlmostEqual(hi_38, 50.0, delta=2.0)

        # Case 3: High humidity adjustment trigger (T=28.5 C / 83.3 F, RH=90%)
        hi_high_rh = heat_index(28.5, 90.0)
        self.assertGreaterEqual(hi_high_rh, 34.0)

        # Case 4: Low humidity adjustment trigger (T=35 C / 95 F, RH=10%)
        hi_low_rh = heat_index(35.0, 10.0)
        self.assertLess(hi_low_rh, 35.0)

    def test_simplified_wbgt_calculation_and_solar_nudge(self):
        """Verify simplified outdoor WBGT (BOM approximation) and solar radiation adjustment."""
        wbgt_base = wbgt(35.0, 70.0)
        # 35 C at 70% RH has high vapor pressure (~39.4 hPa) -> WBGT ~ 39.3 C
        self.assertGreaterEqual(wbgt_base, 35.0)

        # With high solar radiation (800 W/m2), WBGT should increase by ~0.75 C
        wbgt_solar = wbgt(35.0, 70.0, solar_radiation=800.0)
        self.assertGreater(wbgt_solar, wbgt_base)
        self.assertAlmostEqual(wbgt_solar - wbgt_base, 0.75, delta=0.2)

        # Mild solar radiation (< 600 W/m2) adds no extra nudge
        wbgt_mild_sun = wbgt(35.0, 70.0, solar_radiation=400.0)
        self.assertEqual(wbgt_mild_sun, wbgt_base)

    def test_wbgt_docstring_not_full_iso_7243(self):
        """Ensure WBGT docstring clearly identifies as simplified BOM approximation, not full ISO 7243."""
        doc = wbgt.__doc__ or ""
        self.assertIn("Australian Bureau of Meteorology", doc)
        self.assertNotIn("ISO 7243", doc)

    def test_compute_thermal_metrics_wrapper(self):
        """Verify convenience helper returns dictionary with expected keys and types."""
        metrics = compute_thermal_metrics(32.0, 65.0, solar_radiation=500.0)
        self.assertIn("heat_index_c", metrics)
        self.assertIn("wbgt_c", metrics)
        self.assertIsInstance(metrics["heat_index_c"], float)
        self.assertIsInstance(metrics["wbgt_c"], float)

    def test_input_validation(self):
        """Verify that invalid types and out-of-range bounds raise ValueError."""
        # Booleans rejected
        with self.assertRaises(ValueError):
            heat_index(True, 50.0)
        with self.assertRaises(ValueError):
            wbgt(30.0, False)

        # Out-of-bounds humidity
        with self.assertRaises(ValueError):
            heat_index(35.0, 110.0)
        with self.assertRaises(ValueError):
            heat_index(35.0, -5.0)

        # Out-of-bounds temperature
        with self.assertRaises(ValueError):
            heat_index(100.0, 50.0)

        # Non-numeric strings
        with self.assertRaises(ValueError):
            heat_index("hot", 50.0)

        # Negative solar radiation
        with self.assertRaises(ValueError):
            wbgt(35.0, 50.0, solar_radiation=-100.0)


if __name__ == "__main__":
    unittest.main()
