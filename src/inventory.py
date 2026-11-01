"""GHG Protocol-style Scope 1, 2 and 3 (category 1) inventory and scenario analysis."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load_factors() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "emission_factors.csv")


def scope12(activity: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Return activity rows with tCO2e and scope. Raises if an activity has no factor or unit mismatches."""
    merged = activity.merge(factors[["activity", "unit", "kgco2e_per_unit", "scope"]],
                            on="activity", how="left", suffixes=("", "_factor"))
    if merged["kgco2e_per_unit"].isna().any():
        missing = merged.loc[merged["kgco2e_per_unit"].isna(), "activity"].unique()
        raise ValueError(f"No emission factor for: {list(missing)}")
    bad_unit = merged["unit"] != merged["unit_factor"]
    if bad_unit.any():
        raise ValueError("Unit mismatch between activity data and emission factors")
    merged["tco2e"] = merged["quantity"] * merged["kgco2e_per_unit"] / 1000
    return merged.drop(columns="unit_factor")


def scope3_cat1(suppliers: pd.DataFrame, use_alternative: set[str] | None = None) -> pd.DataFrame:
    """Supplier-specific spend-based Scope 3 category 1 emissions."""
    use_alternative = use_alternative or set()
    s = suppliers.copy()
    switched = s["supplier"].isin(use_alternative)
    s["intensity_used"] = np.where(switched, s["alt_intensity_kg_per_usd"], s["intensity_kg_per_usd"])
    s["spend_used"] = np.where(switched, s["annual_spend_usd"] * (1 + s["alt_cost_premium_pct"] / 100),
                               s["annual_spend_usd"])
    # emissions driven by quantity bought: premium raises spend but not quantity, so use base spend
    s["tco2e"] = s["annual_spend_usd"] * s["intensity_used"] / 1000
    s["switched"] = switched
    return s


def supplier_switch_options(suppliers: pd.DataFrame) -> pd.DataFrame:
    """Abatement and cost of switching each supplier to its lower-carbon alternative."""
    s = suppliers.copy()
    s["abatement_tco2e"] = s["annual_spend_usd"] * (s["intensity_kg_per_usd"] - s["alt_intensity_kg_per_usd"]) / 1000
    s["extra_cost_usd"] = s["annual_spend_usd"] * s["alt_cost_premium_pct"] / 100
    s = s[s["abatement_tco2e"] > 0].copy()
    s["cost_per_tco2e"] = s["extra_cost_usd"] / s["abatement_tco2e"]
    return s.sort_values("cost_per_tco2e")


def abatement_options(baseline_s12: pd.DataFrame, seed: int = 7) -> pd.DataFrame:
    """Operational decarbonisation options with stated, editable assumptions.

    Abatement is computed from the baseline inventory (share of a source avoided);
    costs are annualised net costs in USD (negative = saving). Assumptions are representative.
    """
    by_act = baseline_s12.groupby("activity")["tco2e"].sum()
    gas, elec, diesel = by_act.get("natural_gas", 0), by_act.get("grid_electricity", 0), by_act.get("diesel", 0)
    refr = by_act.get("refrigerant_R410A", 0)
    opts = [
        ("LED lighting retrofit", elec * 0.06, -18_000),
        ("Compressed-air leak programme", elec * 0.04, -12_000),
        ("Variable-speed drives on pumps/fans", elec * 0.08, -9_000),
        ("Boiler tuning and insulation", gas * 0.07, -6_000),
        ("Heat recovery from compressors", gas * 0.10, 4_000),
        ("Rooftop solar PV (1 MWp)", elec * 0.15, 15_000),
        ("Heat pump for space heating", gas * 0.18, 38_000),
        ("Refrigerant leak detection + low-GWP retrofit", refr * 0.80, 6_000),
        ("Fleet telematics and eco-driving", diesel * 0.08, -2_500),
        ("Electric forklifts", diesel * 0.30, 22_000),
        ("Renewable electricity PPA (part)", elec * 0.30, 30_000),
        ("Process scheduling to cut idle load", elec * 0.03, -4_000),
    ]
    df = pd.DataFrame(opts, columns=["option", "abatement_tco2e", "annual_net_cost_usd"])
    df["cost_per_tco2e"] = df["annual_net_cost_usd"] / df["abatement_tco2e"]
    return df.sort_values("cost_per_tco2e").reset_index(drop=True)
