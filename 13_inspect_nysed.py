"""Step 13: inspect NYSED BEDS Day Enrollment data, find D2 Manhattan schools."""
from access_parser import AccessParser
import pandas as pd

paths = {
    "2024-25": r"C:\Users\iamch\enrollment-forecast\nysed\2025\ENROLL2025_20251217.accdb",
    "2023-24": r"C:\Users\iamch\enrollment-forecast\nysed\2024\ENROLL2024_20241105..accdb",
    "2022-23": r"C:\Users\iamch\enrollment-forecast\nysed\2023\ENROLL2023_20231207.accdb",
}

for label, path in paths.items():
    print(f"\n========== {label} ({path}) ==========")
    p = AccessParser(path)
    table = p.parse_table("BEDS Day Enrollment")
    df = pd.DataFrame(table)
    print(f"Rows: {len(df):,}")

    # Year column
    if "YEAR" in df.columns:
        years = df["YEAR"].dropna().astype(str).str.rstrip(".").value_counts()
        print(f"YEAR values: {years.head().to_dict()}")

    # Look at NYC schools (Manhattan BEDS code starts with 31)
    df["entity_str"] = df["ENTITY_CD"].astype(str)
    # Manhattan District 2: BEDS code starts with 310200
    d2 = df[df["entity_str"].str.startswith("310200")]
    print(f"District 2 Manhattan schools: {len(d2)}")
    # Show one example
    if len(d2):
        sample = d2.iloc[0]
        print(f"Example: {sample['ENTITY_CD']}  {sample['ENTITY_NAME']}")
        print(f"  Grade K full: {sample['KFULL']}  G1: {sample['1']}  G2: {sample['2']}  G3: {sample['3']}  G4: {sample['4']}  G5: {sample['5']}")

    # Find a known school by name to confirm structure
    ps41 = df[df["ENTITY_NAME"].astype(str).str.contains("PS 41|P.S. 41|PS041", regex=True, na=False)]
    print(f"PS 41 matches: {len(ps41)}")
    if len(ps41):
        for _, row in ps41.head(5).iterrows():
            print(f"  {row['ENTITY_CD']}  {row['ENTITY_NAME']}  YEAR={row['YEAR']}")
