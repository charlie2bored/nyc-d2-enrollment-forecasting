"""Step 3: build K-5 enrollment time series for D2 elementary, characterize COVID impact."""
import pandas as pd
from paths import DERIVED, RAW

df = pd.read_csv(RAW / "demographic_snapshot.csv")
dbns = pd.read_csv(DERIVED / "d2_elementary_dbns.csv")["DBN"].tolist()

elem_grade_cols = ["Grade K", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"]
d2e = df[df["DBN"].isin(dbns)].copy()
d2e["k5_enroll"] = d2e[elem_grade_cols].sum(axis=1)

# Pivot to schools x years
ts = d2e.pivot_table(index="DBN", columns="Year", values="k5_enroll", aggfunc="sum")
ts["School Name"] = d2e.drop_duplicates("DBN").set_index("DBN")["School Name"]

# Compute COVID delta: 2019-20 (last pre-COVID-impact) -> 2021-22
ts["pre_covid"] = ts["2019-20"]
ts["post_covid"] = ts["2021-22"]
ts["pct_change_covid"] = (ts["post_covid"] - ts["pre_covid"]) / ts["pre_covid"]
ts["abs_change_covid"] = ts["post_covid"] - ts["pre_covid"]

# Also compute pre-COVID trend (2017-18 -> 2019-20)
ts["pre_trend_pct"] = (ts["2019-20"] - ts["2017-18"]) / ts["2017-18"]

print("=== COVID impact summary (32 D2 elementary schools) ===")
print(f"Median pct change 2019-20 to 2021-22: {ts['pct_change_covid'].median():.1%}")
print(f"Mean pct change:                       {ts['pct_change_covid'].mean():.1%}")
print(f"Min  (worst decline):                  {ts['pct_change_covid'].min():.1%}")
print(f"Max  (most growth):                    {ts['pct_change_covid'].max():.1%}")
print(f"Schools with >10% decline:             {(ts['pct_change_covid'] < -0.10).sum()}")
print(f"Schools with >20% decline:             {(ts['pct_change_covid'] < -0.20).sum()}")
print(f"Schools that grew through COVID:       {(ts['pct_change_covid'] > 0).sum()}")
print()
print("=== Worst declines ===")
print(ts.sort_values("pct_change_covid").head(5)[
    ["School Name", "2017-18", "2018-19", "2019-20", "2020-21", "2021-22", "pct_change_covid"]
].to_string())
print()
print("=== Schools that grew ===")
print(ts[ts["pct_change_covid"] > 0].sort_values("pct_change_covid", ascending=False)[
    ["School Name", "2017-18", "2018-19", "2019-20", "2020-21", "2021-22", "pct_change_covid"]
].to_string())
print()
print("=== Median enrollment trajectory across 32 schools ===")
yr_cols = ["2017-18", "2018-19", "2019-20", "2020-21", "2021-22"]
print(ts[yr_cols].median().to_string())
print()
print("=== Aggregate (sum) trajectory ===")
print(ts[yr_cols].sum().to_string())

ts.to_csv(DERIVED / "d2_elementary_timeseries.csv")
print("\nSaved per-school time series to d2_elementary_timeseries.csv")
