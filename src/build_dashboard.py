"""Build the dashboard figure, summary tables and a self-contained HTML report."""
from pathlib import Path
import base64
import io
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_data import generate  # noqa: E402
from inventory import load_factors, scope12, scope3_cat1, supplier_switch_options, abatement_options  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
COL = {"Scope 1": "#2E6F95", "Scope 2": "#5FA8D3", "Scope 3 (cat. 1)": "#A7C957", "accent": "#BC4749"}


def main() -> dict:
    activity, suppliers = generate()
    activity.to_csv(ROOT / "data" / "activity_2025.csv", index=False)
    suppliers.to_csv(ROOT / "data" / "suppliers_2025.csv", index=False)

    s12 = scope12(activity, load_factors())
    s3 = scope3_cat1(suppliers)
    totals = {
        "Scope 1": s12.loc[s12["scope"] == 1, "tco2e"].sum(),
        "Scope 2": s12.loc[s12["scope"] == 2, "tco2e"].sum(),
        "Scope 3 (cat. 1)": s3["tco2e"].sum(),
    }
    total = sum(totals.values())

    sw = supplier_switch_options(suppliers)
    top3 = set(sw.sort_values("abatement_tco2e", ascending=False)["supplier"].head(3))
    s3_alt = scope3_cat1(suppliers, use_alternative=top3)
    s3_cut_pct = 100 * (1 - s3_alt["tco2e"].sum() / s3["tco2e"].sum())
    macc = abatement_options(s12)

    monthly = s12.groupby(["month", "scope"])["tco2e"].sum().unstack().rename(columns={1: "Scope 1", 2: "Scope 2"})

    fig, ax = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("Model Manufacturing Co. - 2025 GHG inventory and decarbonisation options\n"
                 "Modelled case company, reproducible (seeded) activity data", fontsize=13, fontweight="bold")

    a = ax[0, 0]
    names, vals = list(totals), list(totals.values())
    bars = a.barh(names, vals, color=[COL[n] for n in names])
    for b, v in zip(bars, vals):
        a.text(v, b.get_y() + b.get_height() / 2, f"  {v:,.0f} t ({100*v/total:.0f}%)", va="center")
    a.set_title(f"Total footprint: {total:,.0f} tCO2e")
    a.set_xlabel("tCO2e"); a.invert_yaxis(); a.set_xlim(0, max(vals) * 1.35)

    a = ax[0, 1]
    monthly.plot(ax=a, color=[COL["Scope 1"], COL["Scope 2"]], marker="o")
    a.set_title("Monthly Scope 1 and 2 (summer cooling load drives Scope 2)")
    a.set_ylabel("tCO2e"); a.set_xlabel(""); a.tick_params(axis="x", rotation=45)

    a = ax[1, 0]
    p = s3.sort_values("tco2e", ascending=False)
    a.bar(p["supplier"], p["tco2e"], color=[COL["accent"] if s in top3 else COL["Scope 3 (cat. 1)"] for s in p["supplier"]])
    cum = 100 * p["tco2e"].cumsum() / p["tco2e"].sum()
    a2 = a.twinx(); a2.plot(p["supplier"], cum, color="black", marker="o"); a2.set_ylim(0, 105); a2.set_ylabel("cumulative %")
    a.set_title(f"Scope 3 cat. 1 by supplier - switching the 3 red suppliers cuts cat. 1 by {s3_cut_pct:.1f}%")
    a.set_ylabel("tCO2e"); a.tick_params(axis="x", rotation=45)

    a = ax[1, 1]
    x = 0
    for _, r in macc.iterrows():
        a.bar(x, r["cost_per_tco2e"], width=r["abatement_tco2e"], align="edge",
              color="#6A994E" if r["cost_per_tco2e"] < 0 else "#E9C46A", edgecolor="white")
        x += r["abatement_tco2e"]
    a.axhline(0, color="black", lw=0.8)
    a.set_title("Marginal abatement cost curve (operational options)")
    a.set_xlabel("cumulative abatement, tCO2e/yr"); a.set_ylabel("USD per tCO2e (negative = saving)")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "dashboard.png", dpi=130)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=110); plt.close(fig)

    summary = {
        "total_tco2e": round(total, 1),
        "by_scope_tco2e": {k: round(v, 1) for k, v in totals.items()},
        "suppliers_switched": sorted(top3),
        "scope3_cat1_reduction_pct": round(s3_cut_pct, 1),
        "macc_options": len(macc),
        "macc_no_regret_tco2e": round(macc.loc[macc["cost_per_tco2e"] < 0, "abatement_tco2e"].sum(), 1),
        "macc_total_tco2e": round(macc["abatement_tco2e"].sum(), 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    macc.round(1).to_csv(OUT / "macc_options.csv", index=False)
    sw.round(2).to_csv(OUT / "supplier_switch_options.csv", index=False)

    img = base64.b64encode(buf.getvalue()).decode()
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Carbon dashboard</title>
<style>body{{font-family:system-ui,Arial;max-width:1100px;margin:24px auto;padding:0 16px;color:#222}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 8px;text-align:right}}th{{background:#eef}}
.note{{background:#fff4e5;border-left:4px solid #e9a23b;padding:8px 12px}}</style></head><body>
<h1>Scope 1-3 carbon dashboard and decarbonisation scenarios</h1>
<p class="note"><b>Note.</b> Modelled case company with reproducible (seeded) activity data. Emission factors are representative values close to published
DESNZ/DEFRA 2024 factors and IPCC AR5 GWPs; replace them with current official factors for real reporting.</p>
<img src="data:image/png;base64,{img}" style="width:100%">
<h2>Key results (computed, not assumed)</h2>
<ul><li>Total footprint: {total:,.0f} tCO2e (Scope 1 {totals['Scope 1']:,.0f}; Scope 2 {totals['Scope 2']:,.0f}; Scope 3 cat. 1 {totals['Scope 3 (cat. 1)']:,.0f})</li>
<li>Switching the three highest-abatement suppliers ({', '.join(sorted(top3))}) to lower-carbon alternatives reduces Scope 3 cat. 1 by {s3_cut_pct:.1f}%.</li>
<li>{len(macc)} operational options evaluated; no-regret (negative-cost) options abate {summary['macc_no_regret_tco2e']:,.0f} tCO2e/yr.</li></ul>
<h2>Abatement options</h2>{macc.round(1).to_html(index=False)}
<h2>Method</h2><ol><li>Activity data x emission factor = tCO2e (Scope 1 fuels and refrigerants, Scope 2 location-based electricity).</li>
<li>Scope 3 category 1 uses supplier-specific spend intensities (kgCO2e/USD).</li>
<li>Scenario: replace intensity with the alternative supplier intensity; cost premium does not change quantity bought.</li>
<li>MACC: options sorted by annualised net cost per tonne abated; bar width = abatement.</li></ol>
</body></html>"""
    (OUT / "report.html").write_text(html)
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
