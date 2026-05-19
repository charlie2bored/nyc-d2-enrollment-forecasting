"""Step 10: extract census tracts for the 32 D2 elementary schools."""
import pandas as pd

loc = pd.read_csv("C:/Users/iamch/enrollment-forecast/school_locations.csv")
dbns_active = pd.read_csv("C:/Users/iamch/enrollment-forecast/d2_elementary_dbns.csv")["DBN"].tolist()
all_d2_elem = dbns_active + ["02M281", "02M340"]

# Filter to our schools. system_code uses the DBN format (district+borough+school)
d2 = loc[loc["system_code"].isin(all_d2_elem)][[
    "system_code", "location_name", "primary_address_line_1",
    "LATITUDE", "LONGITUDE", "Census_tract", "NTA_Name"
]].copy()

# Some schools may have multiple location records across fiscal years; keep one per DBN
d2 = d2.drop_duplicates(subset="system_code").rename(columns={"system_code": "DBN"})

print(f"Matched {len(d2)} of {len(all_d2_elem)} D2 elementary schools")
missing = set(all_d2_elem) - set(d2["DBN"])
if missing:
    print(f"Missing: {missing}")

# Format census tract as full FIPS (state-county-tract).
# Manhattan = New York County = state 36, county 061.
# Tract codes in NYC are 6 digits, zero-padded; the CSV stores as float so we cast carefully.
def to_tract_fips(t):
    if pd.isna(t):
        return None
    # Tract codes are typically integers; convert to 6-digit zero-padded string
    return str(int(t)).zfill(6)

d2["tract_fips"] = d2["Census_tract"].apply(to_tract_fips)
d2["state_fips"] = "36"
d2["county_fips"] = "061"  # New York County

print("\n=== Sample mapping ===")
print(d2[["DBN", "location_name", "primary_address_line_1", "Census_tract",
          "tract_fips", "NTA_Name"]].head(10).to_string(index=False))

# Unique tracts (some schools may share a tract)
unique_tracts = sorted(d2["tract_fips"].dropna().unique())
print(f"\nUnique census tracts: {len(unique_tracts)}")
print(unique_tracts)

d2.to_csv("C:/Users/iamch/enrollment-forecast/school_tract_mapping.csv", index=False)
print(f"\nSaved school -> tract mapping to school_tract_mapping.csv")
