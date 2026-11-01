import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from generate_data import generate  # noqa: E402
from inventory import load_factors, scope12, scope3_cat1, supplier_switch_options, abatement_options  # noqa: E402


class TestInventory(unittest.TestCase):
    def setUp(self):
        self.activity, self.suppliers = generate()
        self.factors = load_factors()

    def test_hand_calculation(self):
        a = pd.DataFrame([("2025-01", "X", "diesel", "litre", 1000.0)],
                         columns=["month", "site", "activity", "unit", "quantity"])
        r = scope12(a, self.factors)
        self.assertAlmostEqual(r["tco2e"].iloc[0], 1000 * 2.512 / 1000)
        self.assertEqual(r["scope"].iloc[0], 1)

    def test_missing_factor_raises(self):
        a = pd.DataFrame([("2025-01", "X", "coal", "kg", 1.0)], columns=["month", "site", "activity", "unit", "quantity"])
        with self.assertRaises(ValueError):
            scope12(a, self.factors)

    def test_unit_mismatch_raises(self):
        a = pd.DataFrame([("2025-01", "X", "diesel", "kg", 1.0)], columns=["month", "site", "activity", "unit", "quantity"])
        with self.assertRaises(ValueError):
            scope12(a, self.factors)

    def test_scope3_switch_never_increases(self):
        base = scope3_cat1(self.suppliers)["tco2e"].sum()
        alt = scope3_cat1(self.suppliers, set(self.suppliers["supplier"]))["tco2e"].sum()
        self.assertLessEqual(alt, base)

    def test_switch_abatement_matches_scenario(self):
        sw = supplier_switch_options(self.suppliers)
        chosen = set(sw["supplier"].head(2))
        base = scope3_cat1(self.suppliers)["tco2e"].sum()
        alt = scope3_cat1(self.suppliers, chosen)["tco2e"].sum()
        self.assertAlmostEqual(base - alt, sw.loc[sw["supplier"].isin(chosen), "abatement_tco2e"].sum(), places=6)

    def test_macc_sorted_and_positive(self):
        m = abatement_options(scope12(self.activity, self.factors))
        self.assertTrue((m["abatement_tco2e"] > 0).all())
        self.assertTrue(m["cost_per_tco2e"].is_monotonic_increasing)

    def test_reproducible(self):
        a2, _ = generate()
        pd.testing.assert_frame_equal(self.activity, a2)


if __name__ == "__main__":
    unittest.main()
