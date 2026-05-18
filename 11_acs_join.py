"""
Step 11: pull ACS 5-year 2022 median household income by census tract, join to D2 schools.

Variable
--------
B19013_001E : Median household income in the past 12 months (2022 inflation-adjusted dollars)
              ACS 5-year estimates 2018-2022
              Source: https://www.census.gov/data/developers/data-sets/acs-5year.html
"""
import os
import json
import urllib.request
import pandas as pd

API_KEY = os.environ.get("CENSUS_API_KEY", "REDACTED-CENSUS-API-KEY")

url = (
    "https://api.census.gov/data/2022/acs/acs5"
    "?get=B19013_001E,NAME"
    "&for=tract:*"
    "&in=state:36+county:061"  # New York County (Manhattan)
    f"&key={API_KEY}"
)
print(f"Fetching ACS data...")
with urllib.request.urlopen(url) as resp:
    data = json.loads(resp.read())

# data[0] is header row, rest are records
header, *rows = data
acs = pd.DataFrame(rows, columns=header)
acs = acs.rename(columns={"B19013_001E": "median_household_income"})
acs["median_household_income"] = pd.to_numeric(acs["median_household_income"], errors="coerce")
acs["tract_fips"] = acs["tract"]  # already 6-digit zero-padded in the API response

print(f"Pulled {len(acs)} Manhattan tracts")
print(f"Tracts with valid income: {acs['median_household_income'].notna().sum()}")
print(f"Income range: ${acs['median_household_income'].min():,.0f} - ${acs['median_household_income'].max():,.0f}")

acs.to_csv("C:/Users/iamch/enrollment-forecast/acs_manhattan_income.csv", index=False)

# Join to our school -> tract mapping
mapping = pd.read_csv("C:/Users/iamch/enrollment-forecast/school_tract_mapping.csv", dtype={"tract_fips": str})
mapping["tract_fips"] = mapping["tract_fips"].str.zfill(6)

joined = mapping.merge(acs[["tract_fips", "median_household_income"]], on="tract_fips", how="left")
print(f"\n=== Join result ===")
print(f"Schools joined: {joined['median_household_income'].notna().sum()} of {len(joined)}")
missing = joined[joined["median_household_income"].isna()]
if len(missing):
    print("Missing income (tract not found in ACS):")
    print(missing[["DBN", "location_name", "tract_fips"]].to_string(index=False))

print(f"\n=== Sample income by school ===")
print(joined.sort_values("median_household_income", ascending=False)[
    ["DBN", "location_name", "NTA_Name", "median_household_income"]
].head(10).to_string(index=False))
print("\n=== Lowest-income catchments ===")
print(joined.sort_values("median_household_income")[
    ["DBN", "location_name", "NTA_Name", "median_household_income"]
].head(10).to_string(index=False))

# Save the per-school income lookup
school_income = joined[["DBN", "tract_fips", "median_household_income"]].copy()
school_income.to_csv("C:/Users/iamch/enrollment-forecast/school_income.csv", index=False)

# ----------------------------------------------------------------------------
# Update dim_school with income, then redo the correlation analysis
# ----------------------------------------------------------------------------
dim_school = pd.read_csv("C:/Users/iamch/enrollment-forecast/dim_school.csv")
dim_school = dim_school.merge(school_income[["DBN", "median_household_income"]], on="DBN", how="left")
dim_school.to_csv("C:/Users/iamch/enrollment-forecast/dim_school.csv", index=False)

# Correlation of catchment income vs enrollment decline (modeled schools only)
modeled = dim_school[dim_school["Risk_Flag"] != "Excluded"].copy()
modeled = modeled.dropna(subset=["median_household_income", "Pct_vs_PreCOVID"])
corr = modeled[["median_household_income", "Pct_vs_PreCOVID"]].corr().iloc[0, 1]
print(f"\n=== Driver analysis: catchment income vs pct decline ===")
print(f"Pearson correlation (income vs pct_vs_pre_covid): {corr:.3f}")
print(f"  (negative = higher-income catchments had LARGER enrollment declines)")
print(f"Schools analyzed: {len(modeled)}")

# Group: income quartile vs avg decline
modeled["income_quartile"] = pd.qcut(
    modeled["median_household_income"], 4,
    labels=["Q1 (lowest)", "Q2", "Q3", "Q4 (highest)"]
)
q_summary = modeled.groupby("income_quartile", observed=True).agg(
    n_schools=("DBN", "count"),
    mean_pct_decline=("Pct_vs_PreCOVID", "mean"),
    mean_income=("median_household_income", "mean"),
).round(3)
print(f"\n=== Mean enrollment decline by catchment income quartile ===")
print(q_summary.to_string())
