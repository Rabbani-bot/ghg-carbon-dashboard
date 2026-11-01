"""Generate a reproducible activity dataset for a model manufacturer.

Data are generated with a fixed seed for "Model Manufacturing Co.", a modelled case company.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEED = 42


def generate(seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    months = pd.period_range("2025-01", "2025-12", freq="M")
    sites = {"Plant A": 1.0, "Plant B": 0.7, "Warehouse C": 0.25}
    season = 1 + 0.15 * np.cos(2 * np.pi * (np.arange(12) - 0) / 12)  # winter heating peak

    rows = []
    for site, size in sites.items():
        for i, m in enumerate(months):
            rows += [
                (str(m), site, "natural_gas", "kWh", size * 180_000 * season[i] * rng.normal(1, 0.05)),
                (str(m), site, "diesel", "litre", size * 4_000 * rng.normal(1, 0.08)),
                (str(m), site, "grid_electricity", "kWh", size * 420_000 * (2 - season[i]) * rng.normal(1, 0.04)),
            ]
        # refrigerant top-ups happen occasionally
        for m in rng.choice(months.astype(str), size=2, replace=False):
            rows.append((m, site, "refrigerant_R410A", "kg", size * rng.uniform(3, 9)))
    activity = pd.DataFrame(rows, columns=["month", "site", "activity", "unit", "quantity"])

    # Scope 3, category 1 (purchased goods): supplier-specific intensities (kgCO2e per USD)
    suppliers = pd.DataFrame({
        "supplier": [f"Supplier {c}" for c in "ABCDEFGH"],
        "material": ["steel", "aluminium", "plastics", "packaging", "chemicals", "electronics", "steel", "logistics"],
        "annual_spend_usd": [2.4e6, 1.1e6, 0.9e6, 0.6e6, 0.8e6, 0.7e6, 0.5e6, 0.4e6],
        "intensity_kg_per_usd": [1.65, 2.10, 0.95, 0.55, 1.20, 0.45, 1.05, 0.60],
        # lower-carbon alternative available on the market for the same material (assumption)
        "alt_intensity_kg_per_usd": [1.05, 1.20, 0.80, 0.50, 1.00, 0.45, 1.05, 0.55],
        "alt_cost_premium_pct": [6.0, 9.0, 4.0, 2.0, 5.0, 0.0, 0.0, 3.0],
    })
    return activity, suppliers


if __name__ == "__main__":
    a, s = generate()
    a.to_csv(ROOT / "data" / "activity_2025.csv", index=False)
    s.to_csv(ROOT / "data" / "suppliers_2025.csv", index=False)
    print(f"activity rows: {len(a)}, suppliers: {len(s)}")
