"""Step 2: filter to District 2 Manhattan elementary schools, check coverage."""
import pandas as pd

df = pd.read_csv("C:/Users/iamch/enrollment-forecast/demographic_snapshot.csv")

# District 2, Manhattan: DBN starts with "02M"
d2 = df[df["DBN"].str.startswith("02M")].copy()
print(f"District 2 rows: {len(d2)}, unique schools: {d2['DBN'].nunique()}")

# Year coverage per school
coverage = d2.groupby("DBN")["Year"].nunique().value_counts().sort_index()
print("\n=== Year-count distribution across D2 schools ===")
print(coverage.to_string())

# Identify schools NOT appearing in all 5 years
incomplete = d2.groupby("DBN")["Year"].nunique()
incomplete = incomplete[incomplete < 5]
print(f"\nSchools with < 5 years of data: {len(incomplete)}")
if len(incomplete):
    print(incomplete.to_string())

# Elementary = has any K-5 enrollment, AND has effectively no 9-12
elem_grade_cols = ["Grade K", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"]
hs_grade_cols = ["Grade 9", "Grade 10", "Grade 11", "Grade 12"]
ms_grade_cols = ["Grade 6", "Grade 7", "Grade 8"]

# Use the most recent year for the elementary classification
latest = d2[d2["Year"] == "2021-22"].copy()
latest["k5_enroll"] = latest[elem_grade_cols].sum(axis=1)
latest["ms_enroll"] = latest[ms_grade_cols].sum(axis=1)
latest["hs_enroll"] = latest[hs_grade_cols].sum(axis=1)

# Pure elementary: has K-5, no HS, and K-5 is dominant (>=70% of total grade enrollment ex-PK)
graded_total = latest["k5_enroll"] + latest["ms_enroll"] + latest["hs_enroll"]
latest["k5_share"] = latest["k5_enroll"] / graded_total.replace(0, pd.NA)

pure_elem = latest[(latest["k5_enroll"] > 0) & (latest["hs_enroll"] == 0) & (latest["k5_share"] >= 0.7)]
print(f"\n=== Pure-ish elementary schools in D2 (K-5 dominant, no HS) ===")
print(f"Count: {len(pure_elem)}")

# Also show K-8 schools (common in NYC)
k8 = latest[(latest["k5_enroll"] > 0) & (latest["hs_enroll"] == 0) & (latest["ms_enroll"] > 0) & (latest["k5_share"] < 0.7)]
print(f"K-8 (or similar) schools in D2: {len(k8)}")

# Show the pure elementary list
print("\n=== Pure elementary list ===")
cols = ["DBN", "School Name", "Total Enrollment", "k5_enroll", "k5_share"]
print(pure_elem[cols].sort_values("k5_enroll", ascending=False).to_string(index=False))

# Save the elementary DBNs
pure_elem_dbns = pure_elem["DBN"].tolist()
pd.Series(pure_elem_dbns).to_csv(
    "C:/Users/iamch/enrollment-forecast/d2_elementary_dbns.csv",
    index=False, header=["DBN"]
)
print(f"\nSaved {len(pure_elem_dbns)} DBNs to d2_elementary_dbns.csv")
