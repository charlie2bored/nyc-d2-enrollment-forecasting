"""Step 5: stitch the two datasets, verify 2017-18 overlap, produce 9-year time series."""
import pandas as pd

old = pd.read_csv("C:/Users/iamch/enrollment-forecast/demographic_snapshot_2013_2018.csv")
new = pd.read_csv("C:/Users/iamch/enrollment-forecast/demographic_snapshot.csv")
dbns = pd.read_csv("C:/Users/iamch/enrollment-forecast/d2_elementary_dbns.csv")["DBN"].tolist()

elem_grade_cols = ["Grade K", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"]
keep_cols = ["DBN", "School Name", "Year"] + elem_grade_cols

old_d2 = old[old["DBN"].isin(dbns)][keep_cols].copy()
new_d2 = new[new["DBN"].isin(dbns)][keep_cols].copy()

# Sanity check: 2017-18 should match across datasets
old_1718 = old_d2[old_d2["Year"] == "2017-18"].set_index("DBN")[elem_grade_cols]
new_1718 = new_d2[new_d2["Year"] == "2017-18"].set_index("DBN")[elem_grade_cols]
common = old_1718.index.intersection(new_1718.index)
diffs = (old_1718.loc[common] - new_1718.loc[common]).abs().sum().sum()
print(f"=== 2017-18 overlap sanity check ===")
print(f"Schools in both: {len(common)}/{len(dbns)}")
print(f"Total absolute difference across all K-5 cells: {diffs} (should be 0)")

# Stitch: drop old's 2017-18 (use the new dataset's version), then concat
old_pre = old_d2[old_d2["Year"] != "2017-18"].copy()
stitched = pd.concat([old_pre, new_d2], ignore_index=True)
stitched["k5_enroll"] = stitched[elem_grade_cols].sum(axis=1)

# Convert Year to a forecastable date (use Sept 1 of the start of the school year)
stitched["year_start"] = stitched["Year"].str[:4].astype(int)
stitched["ds"] = pd.to_datetime(stitched["year_start"].astype(str) + "-09-01")

# Coverage check across all 9 years
coverage = stitched.groupby("DBN")["Year"].nunique()
print(f"\n=== 9-year coverage ===")
print(coverage.value_counts().sort_index().to_string())
missing = coverage[coverage < 9]
print(f"\nSchools missing some years: {len(missing)}")
if len(missing):
    for dbn, n in missing.items():
        years_present = stitched[stitched["DBN"] == dbn]["Year"].tolist()
        name = stitched[stitched["DBN"] == dbn]["School Name"].iloc[0]
        print(f"  {dbn} {name}: {n} years -> {sorted(years_present)}")

# Wide-format view to see trajectories
wide = stitched.pivot_table(index="DBN", columns="Year", values="k5_enroll", aggfunc="sum")
wide["School Name"] = stitched.drop_duplicates("DBN").set_index("DBN")["School Name"]
yr_cols = sorted([c for c in wide.columns if isinstance(c, str) and c[:4].isdigit()])

# Aggregate trajectory
print("\n=== Aggregate D2 elementary K-5 enrollment (9 years) ===")
print(wide[yr_cols].sum().to_string())

# The River School deep-dive (since it was the suspicious growth outlier)
river_dbn = "02M281"
print(f"\n=== The River School ({river_dbn}) full grade-by-grade history ===")
river = stitched[stitched["DBN"] == river_dbn].sort_values("year_start")
print(river[["Year"] + elem_grade_cols + ["k5_enroll"]].to_string(index=False))

# Save stitched long-format
out = stitched[["DBN", "School Name", "Year", "ds", "k5_enroll"] + elem_grade_cols]
out.to_csv("C:/Users/iamch/enrollment-forecast/d2_elementary_9yr.csv", index=False)
print(f"\nSaved 9-year stitched data ({len(out)} rows) to d2_elementary_9yr.csv")
