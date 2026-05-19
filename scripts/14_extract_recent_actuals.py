"""
Step 14: extract 2022-23, 2023-24, 2024-25 K-5 enrollment for our 30 D2 schools
from the NYSED BEDS Day Enrollment database, and stitch onto our existing 9-year
from paths import DERIVED, NYSED
NYC DOE time series.

BEDS code mapping
-----------------
NYC DBN "02M041" → NYSED BEDS "310200010041"
  - 31     : NYC
  - 02     : District 2
  - 00     : Manhattan (borough fill)
  - 01     : NYC administrative code
  - 0041   : School number (matches the trailing digits of the DBN)

YEAR values in the NYSED file are end-of-school-year:
  - 2023 → 2022-23 school year
  - 2024 → 2023-24
  - 2025 → 2024-25

Note on snapshot date difference
--------------------------------
NYC DOE Demographic Snapshot: October 31 audited register count.
NYSED BEDS Day:               First Wednesday in October (~3 weeks earlier).
These will differ by small amounts (~1-2% typically); not directly comparable
without methodological caveat. We accept this as a known data-source difference
and call it out in the case study.
"""
from access_parser import AccessParser
import pandas as pd

ACCDB = NYSED / "2025" / "ENROLL2025_20251217.accdb"

p = AccessParser(ACCDB)
nysed = pd.DataFrame(p.parse_table("BEDS Day Enrollment"))

# Clean numeric grade columns (access-parser returns "1234." strings)
grade_cols = ["KFULL", "1", "2", "3", "4", "5"]
for c in grade_cols:
    nysed[c] = pd.to_numeric(nysed[c].astype(str).str.rstrip("."), errors="coerce")
nysed["YEAR"] = pd.to_numeric(nysed["YEAR"].astype(str).str.rstrip("."), errors="coerce").astype("Int64")

# Filter: NYC District 2 Manhattan, individual schools (not the district aggregate)
nysed["entity_str"] = nysed["ENTITY_CD"].astype(str)
d2_nysed = nysed[
    nysed["entity_str"].str.startswith("310200")
    & ~nysed["entity_str"].str.endswith("0000")  # exclude district aggregate
].copy()

# Map BEDS code -> DBN: "310200010041" -> "02M041"
def beds_to_dbn(beds: str) -> str:
    school_number = beds[-4:].lstrip("0").zfill(3)
    return f"02M{school_number}"

d2_nysed["DBN"] = d2_nysed["entity_str"].apply(beds_to_dbn)

# Compute K-5 total
d2_nysed["k5_enroll"] = d2_nysed[grade_cols].sum(axis=1, min_count=1)

# Convert YEAR (end-of-school-year) to year_start (matches our existing convention)
d2_nysed["year_start"] = d2_nysed["YEAR"].astype(int) - 1
d2_nysed["Year"] = d2_nysed["year_start"].astype(str) + "-" + (d2_nysed["year_start"] + 1).astype(str).str[-2:]

# Keep just the years we want (2022-23, 2023-24, 2024-25) and the columns we need
recent = d2_nysed[d2_nysed["year_start"].isin([2022, 2023, 2024])][
    ["DBN", "ENTITY_NAME", "Year", "year_start", "k5_enroll"] + grade_cols
].copy()
recent = recent.rename(columns={
    "ENTITY_NAME": "School Name",
    "KFULL": "Grade K", "1": "Grade 1", "2": "Grade 2",
    "3": "Grade 3", "4": "Grade 4", "5": "Grade 5"
})

# Filter to our 30 modeled schools (load the dbn list)
modeled_dbns = pd.read_csv(DERIVED / "d2_elementary_dbns.csv")["DBN"].tolist()
# Exclude the 2 phase-in schools we already excluded
EXCLUDE = ["02M281", "02M340"]
modeled_dbns = [d for d in modeled_dbns if d not in EXCLUDE]

matched = recent[recent["DBN"].isin(modeled_dbns)].copy()
print(f"=== NYSED data extracted ===")
print(f"Total D2 Manhattan school-year rows (all years 22-25): {len(recent)}")
print(f"Matched to our 30 modeled DBNs: {matched['DBN'].nunique()}/{len(modeled_dbns)} schools")
print(f"Year coverage per school:")
print(matched.groupby("DBN")["year_start"].nunique().value_counts().sort_index().to_string())

missing = set(modeled_dbns) - set(matched["DBN"])
if missing:
    print(f"\nDBNs NOT found in NYSED data: {missing}")

# Quick sanity check: compare 2022-23 NYSED actuals to our 2021-22 NYC DOE actuals
print(f"\n=== Sanity check: NYSED 2022-23 K-5 totals for D2 modeled schools ===")
total_2022 = matched[matched["year_start"] == 2022]["k5_enroll"].sum()
total_2023 = matched[matched["year_start"] == 2023]["k5_enroll"].sum()
total_2024 = matched[matched["year_start"] == 2024]["k5_enroll"].sum()
print(f"  2022-23 (NYSED): {total_2022:,.0f}")
print(f"  2023-24 (NYSED): {total_2023:,.0f}")
print(f"  2024-25 (NYSED): {total_2024:,.0f}")
print(f"  For comparison, 2021-22 (NYC DOE, our existing data): 12,419")

# ============================================================================
# Stitch with the existing 9-year NYC DOE data
# ============================================================================
existing = pd.read_csv(DERIVED / "d2_elementary_9yr.csv")

# We use NYC DOE School Name (from existing data) rather than NYSED's ENTITY_NAME
# for consistency; NYSED uses "PS 41 GREENWICH VILLAGE", NYC DOE has "P.S. 041 ..."
name_lookup = existing.drop_duplicates("DBN").set_index("DBN")["School Name"]
matched["School Name"] = matched["DBN"].map(name_lookup)

# Add ds column matching existing format
matched["ds"] = pd.to_datetime(matched["year_start"].astype(str) + "-09-01")

# Match the column order of d2_elementary_9yr.csv
final_cols = ["DBN", "School Name", "Year", "ds", "k5_enroll",
              "Grade K", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"]
matched_out = matched[final_cols]

# Concat and save
stitched = pd.concat([existing[final_cols], matched_out], ignore_index=True)
stitched = stitched.sort_values(["DBN", "year_start" if "year_start" in stitched.columns else "Year"]).reset_index(drop=True)
stitched.to_csv(DERIVED / "d2_elementary_12yr.csv", index=False)
print(f"\nSaved stitched 12-year dataset (2013-14 through 2024-25) to d2_elementary_12yr.csv")
print(f"Total rows: {len(stitched)}, unique schools: {stitched['DBN'].nunique()}")
