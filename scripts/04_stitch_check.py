"""Step 4: check schema compatibility between 2013-18 and 2017-22 datasets, then stitch."""
import pandas as pd

old = pd.read_csv("C:/Users/iamch/enrollment-forecast/demographic_snapshot_2013_2018.csv")
new = pd.read_csv("C:/Users/iamch/enrollment-forecast/demographic_snapshot.csv")

print("=== OLD shape ===", old.shape)
print("=== OLD years ===", sorted(old["Year"].unique()) if "Year" in old.columns else "no Year col")
print()
print("=== OLD columns ===")
for c in old.columns:
    print(f"  {c!r}")
print()
print("=== Column overlap with new dataset ===")
old_cols = set(old.columns)
new_cols = set(new.columns)
print(f"In both: {len(old_cols & new_cols)}")
print(f"Only in old: {sorted(old_cols - new_cols)}")
print(f"Only in new: {sorted(new_cols - old_cols)}")
