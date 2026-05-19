"""Step 1: profile the raw dataset."""
import pandas as pd
from paths import RAW

df = pd.read_csv(RAW / "demographic_snapshot.csv")

print("=== SHAPE ===")
print(df.shape)
print()
print("=== COLUMNS ===")
for c in df.columns:
    print(f"  {c!r}  dtype={df[c].dtype}")
print()
print("=== HEAD (3 rows) ===")
print(df.head(3).to_string())
print()
print("=== YEAR VALUES ===")
year_col = [c for c in df.columns if 'year' in c.lower()][0]
print(df[year_col].value_counts().sort_index())
