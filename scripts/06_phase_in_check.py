"""Step 6: identify all phase-in schools (where K-5 wasn't fully populated early)."""
import pandas as pd
from paths import DERIVED

df = pd.read_csv(DERIVED / "d2_elementary_9yr.csv")
elem_grade_cols = ["Grade K", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"]

# For each school, find the first year all K-5 grades had >0 students (= "mature year")
def first_mature_year(g):
    g_sorted = g.sort_values("Year")
    for _, row in g_sorted.iterrows():
        if all(row[c] > 0 for c in elem_grade_cols):
            return row["Year"]
    return None

mature = df.groupby("DBN").apply(first_mature_year, include_groups=False)
schools = df.drop_duplicates("DBN").set_index("DBN")["School Name"]

phase_in = mature[mature != "2013-14"].copy()
phase_in_df = pd.DataFrame({
    "School": schools.loc[phase_in.index],
    "First fully-populated K-5 year": phase_in.values
}).sort_values("First fully-populated K-5 year")

print("=== Schools NOT fully populated K-5 in 2013-14 ===")
print(phase_in_df.to_string())

# For Sixth Avenue specifically
sixth = df[df["DBN"] == "02M340"].sort_values("Year")
print(f"\n=== Sixth Avenue Elementary full history ===")
print(sixth[["Year"] + elem_grade_cols + ["k5_enroll"]].to_string(index=False))
