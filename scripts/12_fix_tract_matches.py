"""
Step 12: re-geocode all 32 D2 schools using the Census Geocoder API (no key needed)
to get current 2020 Census tract codes. Then re-join to ACS.

The NYC DOE school locations file uses 2010 Census tracts. ACS 5-year 2022 uses
2020 boundaries. Six schools fell through the join because of this. We fix by
reverse-geocoding lat/long for all schools to current tract IDs.
"""
import os
import json
import time
import urllib.request
import urllib.parse
import pandas as pd

API_KEY = os.environ["CENSUS_API_KEY"]

mapping = pd.read_csv("C:/Users/iamch/enrollment-forecast/school_tract_mapping.csv", dtype={"tract_fips": str})

def geocode_tract(lat: float, lon: float) -> str | None:
    """Return 6-digit current tract code for a lat/long via the Census Geocoder."""
    url = (
        "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
        f"?x={lon}&y={lat}"
        "&benchmark=Public_AR_Current"
        "&vintage=Current_Current"
        "&format=json"
        "&layers=Census+Tracts"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  ERROR: {e}")
        return None
    tracts = data.get("result", {}).get("geographies", {}).get("Census Tracts", [])
    if not tracts:
        return None
    return tracts[0].get("TRACT")  # already zero-padded by Census API

# Geocode all 32 to get current tracts
print(f"Re-geocoding {len(mapping)} schools to current 2020 census tracts...")
new_tracts = []
for _, row in mapping.iterrows():
    if pd.isna(row["LATITUDE"]) or pd.isna(row["LONGITUDE"]):
        new_tracts.append(None)
        continue
    new_tract = geocode_tract(row["LATITUDE"], row["LONGITUDE"])
    print(f"  {row['DBN']:8s} ({row['location_name'][:40]:40s})  "
          f"old={row['tract_fips']}  new={new_tract}")
    new_tracts.append(new_tract)
    time.sleep(0.1)

mapping["tract_fips_2020"] = new_tracts
mapping.to_csv("C:/Users/iamch/enrollment-forecast/school_tract_mapping.csv", index=False)

# Re-pull ACS for completeness
url = (
    "https://api.census.gov/data/2022/acs/acs5"
    "?get=B19013_001E,NAME"
    "&for=tract:*"
    "&in=state:36+county:061"
    f"&key={API_KEY}"
)
print("\nRe-fetching ACS Manhattan tracts...")
with urllib.request.urlopen(url) as resp:
    data = json.loads(resp.read())
header, *rows = data
acs = pd.DataFrame(rows, columns=header).rename(columns={"B19013_001E": "median_household_income"})
acs["median_household_income"] = pd.to_numeric(acs["median_household_income"], errors="coerce")
# Filter out Census sentinel values (e.g., -666666666 = "not available")
acs.loc[acs["median_household_income"] < 0, "median_household_income"] = pd.NA
acs["tract_fips_2020"] = acs["tract"]

# Re-join
joined = mapping.merge(acs[["tract_fips_2020", "median_household_income"]], on="tract_fips_2020", how="left")
print(f"\nSchools joined: {joined['median_household_income'].notna().sum()} of {len(joined)}")
missing = joined[joined["median_household_income"].isna()]
if len(missing):
    print("Still missing:")
    print(missing[["DBN", "location_name", "tract_fips_2020"]].to_string(index=False))

# Save corrected lookup
school_income = joined[["DBN", "tract_fips_2020", "median_household_income"]].copy()
school_income.to_csv("C:/Users/iamch/enrollment-forecast/school_income.csv", index=False)

# Update dim_school
dim_school = pd.read_csv("C:/Users/iamch/enrollment-forecast/dim_school.csv")
dim_school = dim_school.drop(columns=["median_household_income"], errors="ignore")
dim_school = dim_school.merge(school_income[["DBN", "median_household_income"]], on="DBN", how="left")
dim_school.to_csv("C:/Users/iamch/enrollment-forecast/dim_school.csv", index=False)

# Re-run the correlation
modeled = dim_school[dim_school["Risk_Flag"] != "Excluded"].dropna(
    subset=["median_household_income", "Pct_vs_PreCOVID"]
)
corr = modeled[["median_household_income", "Pct_vs_PreCOVID"]].corr().iloc[0, 1]
print(f"\n=== Updated driver analysis: catchment income vs pct decline ===")
print(f"Pearson correlation: {corr:.3f}")
print(f"Schools analyzed: {len(modeled)} (was 24, now {len(modeled)})")

modeled = modeled.copy()
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

# Show resilient outlier
roosevelt = modeled[modeled["DBN"] == "02M217"]
if len(roosevelt):
    r = roosevelt.iloc[0]
    print(f"\n=== Roosevelt Island resilient outlier ===")
    print(f"  PS 217 Roosevelt Island: income=${r['median_household_income']:,.0f}, "
          f"pct change={r['Pct_vs_PreCOVID']:+.1%}")
