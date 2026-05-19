"""
Step 16: Rebuild Power BI star schema with the 12-year data + backtest table.

Changes from version 1
----------------------
- 12 years of actuals (2013-14 through 2024-25), up from 9
- New forecast horizon: 2025-26, 2026-27, 2027-28 (was 2022-23, 2023-24, 2024-25)
- New fact table: backtest (per-school forecast vs actual for 2022-25)
- dim_school: current_enrollment is now 2024-25 (was 2021-22)
- dim_school: risk_flag recomputed against 2024-25 vs pre-COVID baseline
"""
import pandas as pd
from paths import DERIVED, OUTPUT, POWERBI

# Load all source data
pw = pd.read_csv(OUTPUT / "forecasts_piecewise.csv")
pr = pd.read_csv(OUTPUT / "forecasts_prophet.csv")
summary = pd.read_csv(OUTPUT / "school_summary_piecewise.csv")
excluded = pd.read_csv(OUTPUT / "schools_excluded.csv")
backtest = pd.read_csv(OUTPUT / "backtest.csv")
income = pd.read_csv(DERIVED / "school_income.csv")

# ============================================================================
# Unified fact_forecasts table
# ============================================================================
pw["model"] = "Piecewise Linear"
pr["model"] = "Prophet"

# Normalize scenario labels
def normalize_pw(s):
    if s == "actual":
        return "Actual"
    return {"base": "Base", "optimistic": "Optimistic", "pessimistic": "Pessimistic"}[s]

pw["scenario_clean"] = pw["scenario"].apply(normalize_pw)

# Drop Prophet's training period (we already have Actuals from piecewise); keep only its forecasts
pr_fc = pr[pr["scenario"] == "prophet_forecast"].copy()
pr_fc["scenario_clean"] = "Base"  # treat Prophet's single forecast as its Base

pw_part = pw.drop(columns=["scenario"]).rename(columns={"scenario_clean": "scenario"})[
    ["DBN", "School Name", "year_start", "scenario", "model", "yhat", "yhat_lower", "yhat_upper"]
]
pr_part = pr_fc.drop(columns=["scenario"]).rename(columns={"scenario_clean": "scenario"})[
    ["DBN", "School Name", "year_start", "scenario", "model", "yhat", "yhat_lower", "yhat_upper"]
]
fact = pd.concat([pw_part, pr_part], ignore_index=True)
fact["school_year"] = fact["year_start"].astype(str) + "-" + (fact["year_start"] + 1).astype(str).str[-2:]
fact["is_forecast"] = fact["scenario"] != "Actual"

fact_out = fact[["DBN", "year_start", "school_year", "scenario", "model",
                 "yhat", "yhat_lower", "yhat_upper", "is_forecast"]].rename(columns={
    "yhat": "Enrollment", "yhat_lower": "Enrollment_Lower", "yhat_upper": "Enrollment_Upper"
})
fact_out.to_csv(POWERBI / "fact_forecasts.csv", index=False)

# ============================================================================
# dim_school with updated risk flags and current enrollment
# ============================================================================
NEIGHBORHOOD = {
    "02M001": "Lower East Side", "02M002": "Lower East Side",
    "02M003": "West Village", "02M006": "Upper East Side",
    "02M011": "Chelsea", "02M033": "Chelsea",
    "02M040": "Gramercy", "02M041": "West Village",
    "02M042": "Lower East Side", "02M051": "Chelsea / Hell's Kitchen",
    "02M059": "Midtown East", "02M077": "Upper East Side",
    "02M089": "Battery Park City", "02M111": "Upper East Side",
    "02M116": "Murray Hill", "02M124": "Chinatown",
    "02M130": "Tribeca", "02M150": "Tribeca",
    "02M151": "Yorkville", "02M158": "Upper East Side",
    "02M183": "Upper East Side", "02M198": "Upper East Side",
    "02M212": "Hell's Kitchen", "02M217": "Roosevelt Island",
    "02M225": "Lower East Side", "02M234": "Tribeca",
    "02M267": "Upper East Side", "02M281": "Battery Park City",
    "02M290": "Upper East Side", "02M340": "Midtown South",
    "02M343": "Seaport", "02M527": "Upper East Side",
}

dim_school = summary.rename(columns={
    "pre_covid_baseline_mean": "PreCOVID_Baseline",
    "current_2024_25": "Current_Enrollment",
    "pct_vs_pre_covid": "Pct_vs_PreCOVID",
    "beta_pre": "PreCOVID_Slope",
    "covid_shock_gamma": "COVID_Shock",
    "post_covid_slope": "PostCOVID_Slope",
    "base_forecast_2027_28": "Forecast_2027_28_Base",
    "pessimistic_forecast_2027_28": "Forecast_2027_28_Pessimistic",
    "optimistic_forecast_2027_28": "Forecast_2027_28_Optimistic",
    "risk_flag": "Risk_Flag",
    "n_pre_covid_years": "N_PreCOVID_Years",
    "n_post_covid_years": "N_PostCOVID_Years",
})
dim_school["Neighborhood"] = dim_school["DBN"].map(NEIGHBORHOOD).fillna("Manhattan")
dim_school = dim_school.merge(income[["DBN", "median_household_income"]], on="DBN", how="left")

excluded["Risk_Flag"] = "Excluded"
excluded["Neighborhood"] = excluded["DBN"].map(NEIGHBORHOOD)
excluded_minimal = excluded.rename(columns={"reason": "Exclusion_Reason"})[
    ["DBN", "School Name", "Risk_Flag", "Neighborhood", "Exclusion_Reason"]
]

dim_school = pd.concat([dim_school, excluded_minimal], ignore_index=True)
dim_school["Exclusion_Reason"] = dim_school["Exclusion_Reason"].fillna("")
dim_school.to_csv(POWERBI / "dim_school.csv", index=False)

# ============================================================================
# dim_year (now 2013-14 through 2027-28 = 15 years)
# ============================================================================
years = list(range(2013, 2028))
dim_year = pd.DataFrame({
    "year_start": years,
    "school_year": [f"{y}-{str(y+1)[-2:]}" for y in years],
    "is_forecast": [y >= 2025 for y in years],
    "is_pre_covid": [y < 2020 for y in years],
    "is_covid_period": [y in (2020, 2021) for y in years],
    "is_post_covid_observed": [y in (2020, 2021, 2022, 2023, 2024) for y in years],
    "is_backtest_window": [y in (2022, 2023, 2024) for y in years],
})
dim_year.to_csv(POWERBI / "dim_year.csv", index=False)

# ============================================================================
# fact_backtest: forecasts vs actuals for 2022-25
# ============================================================================
bt = backtest.copy()
bt["scenario"] = bt["scenario"].map({"base": "Base", "optimistic": "Optimistic", "pessimistic": "Pessimistic"})
bt["school_year"] = bt["year_start"].astype(str) + "-" + (bt["year_start"] + 1).astype(str).str[-2:]
bt_out = bt[["DBN", "year_start", "school_year", "scenario", "model",
             "forecast", "actual", "error", "abs_error", "pct_error"]].rename(columns={
    "forecast": "Forecast", "actual": "Actual",
    "error": "Error", "abs_error": "Abs_Error", "pct_error": "Pct_Error"
})
bt_out.to_csv(POWERBI / "fact_backtest.csv", index=False)

# ============================================================================
# Print summary
# ============================================================================
print("=== Updated Power BI star schema ===")
print(f"  fact_forecasts.csv : {len(fact_out):,} rows")
print(f"  fact_backtest.csv  : {len(bt_out):,} rows (NEW)")
print(f"  dim_school.csv     : {len(dim_school)} rows")
print(f"  dim_year.csv       : {len(dim_year)} rows (covers {dim_year['year_start'].min()}-{dim_year['year_start'].max()})")
print()
print("=== Backtest aggregate metrics ===")
agg = bt.groupby(["model", "scenario"]).agg(
    n=("DBN", "count"),
    mape=("pct_error", lambda x: x.abs().mean()),
    bias=("error", "mean"),
).round(3)
print(agg.to_string())
print()
print("=== System-wide totals: forecasts vs actuals ===")
print(f"  Actual 2022-25:    11,911 / 12,047 / 11,973  -> mean 11,977")
sys_pw_base = bt[(bt["model"] == "Piecewise Linear") & (bt["scenario"] == "Base")].groupby("year_start")["forecast"].sum()
sys_prophet = bt[bt["model"] == "Prophet"].groupby("year_start")["forecast"].sum()
print(f"  Piecewise Base:    {sys_pw_base.values.astype(int).tolist()}  -> mean {sys_pw_base.mean():.0f}")
print(f"  Prophet:           {sys_prophet.values.astype(int).tolist()}  -> mean {sys_prophet.mean():.0f}")
