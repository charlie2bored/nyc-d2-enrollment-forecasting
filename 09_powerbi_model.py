"""
Step 9: Build a star schema for Power BI from the forecast outputs.

Produces three CSVs:
  - dim_school.csv     (one row per school)
  - dim_year.csv       (one row per school year, 2013-14 .. 2024-25)
  - fact_forecasts.csv (school x year x scenario x model)

Star schema lets a single Power BI matrix or chart switch between scenarios or
models via slicers, without rebuilding visuals.
"""
import pandas as pd

pw = pd.read_csv("C:/Users/iamch/enrollment-forecast/forecasts_piecewise.csv")
pr = pd.read_csv("C:/Users/iamch/enrollment-forecast/forecasts_prophet.csv")
summary = pd.read_csv("C:/Users/iamch/enrollment-forecast/school_summary_piecewise.csv")
excluded = pd.read_csv("C:/Users/iamch/enrollment-forecast/schools_excluded.csv")

# -----------------------------------------------------------------------------
# Unify into one fact table
# -----------------------------------------------------------------------------
pw["model"] = "Piecewise Linear"
pr["model"] = "Prophet"

# Normalize scenario labels: piecewise has actual/base/optimistic/pessimistic;
# Prophet has prophet_train/prophet_forecast (one scenario).
def normalize_pw(row):
    if row["scenario"] == "actual":
        return "Actual"
    return {"base": "Base", "optimistic": "Optimistic", "pessimistic": "Pessimistic"}[row["scenario"]]

def normalize_pr(row):
    return "Actual" if row["scenario"] == "prophet_train" else "Forecast"

pw["scenario_clean"] = pw.apply(normalize_pw, axis=1)
pr["scenario_clean"] = pr.apply(normalize_pr, axis=1)

# For Prophet, distinguish train-period "Actual" from piecewise "Actual" -- they
# should agree on the actual numbers but Prophet's "Actual" is its fit, not the
# raw observation. Drop Prophet's training-period rows so "Actual" in the fact
# table is unambiguous (sourced from piecewise actuals only).
pr = pr[pr["scenario_clean"] == "Forecast"].copy()
pr["scenario_clean"] = "Base"  # Prophet's default forecast = its "base case"

pw_part = pw.drop(columns=["scenario"]).rename(columns={"scenario_clean": "scenario"})[
    ["DBN", "School Name", "year_start", "scenario", "model", "yhat", "yhat_lower", "yhat_upper"]
]
pr_part = pr.drop(columns=["scenario"]).rename(columns={"scenario_clean": "scenario"})[
    ["DBN", "School Name", "year_start", "scenario", "model", "yhat", "yhat_lower", "yhat_upper"]
]
fact = pd.concat([pw_part, pr_part], ignore_index=True)

# Add school year label for the year axis
fact["school_year"] = fact["year_start"].astype(str) + "-" + (fact["year_start"] + 1).astype(str).str[-2:]
# Flag actuals vs forecasts for conditional formatting in Power BI
fact["is_forecast"] = fact["scenario"] != "Actual"

# Drop the school name from fact (it lives in dim_school); keep DBN as FK
fact_out = fact[["DBN", "year_start", "school_year", "scenario", "model",
                 "yhat", "yhat_lower", "yhat_upper", "is_forecast"]].copy()
fact_out = fact_out.rename(columns={
    "yhat": "Enrollment",
    "yhat_lower": "Enrollment_Lower",
    "yhat_upper": "Enrollment_Upper",
})
fact_out.to_csv("C:/Users/iamch/enrollment-forecast/fact_forecasts.csv", index=False)

# -----------------------------------------------------------------------------
# dim_school
# -----------------------------------------------------------------------------
dim_school = summary.copy()
dim_school = dim_school.rename(columns={
    "pre_covid_baseline_mean": "PreCOVID_Baseline",
    "current_2021_22": "Current_Enrollment",
    "pct_vs_pre_covid": "Pct_vs_PreCOVID",
    "beta_pre": "PreCOVID_Slope",
    "covid_shock_gamma": "COVID_Shock",
    "post_covid_slope": "PostCOVID_Slope",
    "base_forecast_2024_25": "Forecast_2024_25_Base",
    "risk_flag": "Risk_Flag",
    "n_pre_covid_years": "N_PreCOVID_Years",
})

# Add neighborhood approximations for D2 schools (rough, useful for filtering)
# Source: NYC DOE school directory; coarse-grained.
NEIGHBORHOOD = {
    "02M001": "Lower East Side", "02M002": "Lower East Side",
    "02M003": "West Village", "02M006": "Upper East Side",
    "02M011": "Chelsea",       "02M033": "Chelsea",
    "02M040": "Gramercy",      "02M041": "West Village",
    "02M042": "Lower East Side", "02M051": "Chelsea / Hell's Kitchen",
    "02M059": "Midtown East",  "02M077": "Upper East Side",
    "02M089": "Battery Park City", "02M111": "Upper East Side",
    "02M116": "Murray Hill",   "02M124": "Chinatown",
    "02M130": "Tribeca",       "02M150": "Tribeca",
    "02M151": "Yorkville",     "02M158": "Upper East Side",
    "02M183": "Upper East Side", "02M198": "Upper East Side",
    "02M212": "Hell's Kitchen", "02M217": "Roosevelt Island",
    "02M225": "Lower East Side", "02M234": "Tribeca",
    "02M267": "Upper East Side", "02M281": "Battery Park City",
    "02M290": "Upper East Side", "02M340": "Midtown South",
    "02M343": "Seaport",       "02M527": "Upper East Side",
}
dim_school["Neighborhood"] = dim_school["DBN"].map(NEIGHBORHOOD).fillna("Manhattan")

# Add an excluded flag for the 2 dropped schools so they can be shown as "no forecast"
excluded["Risk_Flag"] = "Excluded"
excluded["Neighborhood"] = excluded["DBN"].map(NEIGHBORHOOD)
excluded_minimal = excluded.rename(columns={"reason": "Exclusion_Reason"})
excluded_minimal = excluded_minimal[["DBN", "School Name", "Risk_Flag", "Neighborhood", "Exclusion_Reason"]]

dim_school = pd.concat([dim_school, excluded_minimal], ignore_index=True)
dim_school["Exclusion_Reason"] = dim_school["Exclusion_Reason"].fillna("")
dim_school.to_csv("C:/Users/iamch/enrollment-forecast/dim_school.csv", index=False)

# -----------------------------------------------------------------------------
# dim_year
# -----------------------------------------------------------------------------
years = list(range(2013, 2025))  # 2013-14 .. 2024-25
dim_year = pd.DataFrame({
    "year_start": years,
    "school_year": [f"{y}-{str(y+1)[-2:]}" for y in years],
    "is_forecast": [y >= 2022 for y in years],
    "is_pre_covid": [y < 2020 for y in years],
    "is_covid_period": [y in (2020, 2021) for y in years],
})
dim_year.to_csv("C:/Users/iamch/enrollment-forecast/dim_year.csv", index=False)

# -----------------------------------------------------------------------------
# Summary printout
# -----------------------------------------------------------------------------
print("=== Star schema export complete ===")
print(f"  fact_forecasts.csv : {len(fact_out):,} rows  ({fact_out['DBN'].nunique()} schools × "
      f"{fact_out['year_start'].nunique()} years × {fact_out['scenario'].nunique()} scenarios × "
      f"{fact_out['model'].nunique()} models)")
print(f"  dim_school.csv     : {len(dim_school)} rows (incl. {len(excluded_minimal)} excluded)")
print(f"  dim_year.csv       : {len(dim_year)} rows ({sum(dim_year['is_forecast'])} forecast years)")
print()
print("Relationships for Power BI:")
print("  dim_school[DBN]        1 --- * fact_forecasts[DBN]")
print("  dim_year[year_start]   1 --- * fact_forecasts[year_start]")
print()
print("=== Risk flag distribution ===")
print(dim_school["Risk_Flag"].value_counts().to_string())
print()
print("=== Schools by neighborhood (top 5) ===")
print(dim_school["Neighborhood"].value_counts().head(5).to_string())
