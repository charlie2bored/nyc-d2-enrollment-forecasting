"""
Step 8: Prophet enrollment forecast per D2 elementary school, as comparison to the
piecewise linear model.

Prophet configuration notes
---------------------------
With only ~9 annual observations per school, most of Prophet's machinery does
not apply. We disable all seasonality (only one observation per year) and force
the model to behave as a piecewise linear trend with a single known changepoint
at the 2020-09-01 school year start.

  - yearly/weekly/daily seasonality : disabled
  - growth : linear
  - changepoints                    : single explicit point at 2020-09-01
  - n_changepoints                  : 0 (disables auto-detection; we use ours)
  - changepoint_prior_scale         : 0.5  (allow a strong trend change at COVID)
  - interval_width                  : 0.80
  - mcmc_samples                    : 0   (point fits; faster, fine for output)

Same exclusions and phase-in truncation as the piecewise model so results are
comparable.
"""
import warnings
import logging
import numpy as np
import pandas as pd
from paths import DERIVED, OUTPUT

warnings.filterwarnings("ignore")
logging.getLogger("prophet").setLevel(logging.ERROR)
logging.getLogger("cmdstanpy").setLevel(logging.ERROR)

from prophet import Prophet

EXCLUDE_DBNS = ["02M281", "02M340"]
PHASE_IN_TRUNCATE = {"02M151": 2014, "02M267": 2015, "02M343": 2017, "02M527": 2017}
COVID_CHANGEPOINT = pd.Timestamp("2020-09-01")
FORECAST_YEARS = [2022, 2023, 2024]
INTERVAL = 0.80

df = pd.read_csv(DERIVED / "d2_elementary_9yr.csv")
df["ds"] = pd.to_datetime(df["ds"])
df["year_start"] = df["ds"].dt.year

forecasts = []

for dbn, school_df in df.groupby("DBN"):
    name = school_df["School Name"].iloc[0]
    if dbn in EXCLUDE_DBNS:
        continue
    if dbn in PHASE_IN_TRUNCATE:
        school_df = school_df[school_df["year_start"] >= PHASE_IN_TRUNCATE[dbn]]

    train = school_df[["ds", "k5_enroll"]].rename(columns={"k5_enroll": "y"}).sort_values("ds")

    m = Prophet(
        growth="linear",
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,
        n_changepoints=0,
        changepoints=[COVID_CHANGEPOINT],
        changepoint_prior_scale=0.5,
        interval_width=INTERVAL,
    )
    m.fit(train)

    # Build future frame: training years + forecast years (annual, Sept 1)
    future_dates = list(train["ds"]) + [pd.Timestamp(f"{y}-09-01") for y in FORECAST_YEARS]
    future = pd.DataFrame({"ds": future_dates})
    fc = m.predict(future)

    for _, row in fc.iterrows():
        yr = row["ds"].year
        in_train = yr in train["ds"].dt.year.values
        forecasts.append({
            "DBN": dbn, "School Name": name,
            "year_start": int(yr),
            "scenario": "prophet_train" if in_train else "prophet_forecast",
            "yhat": float(row["yhat"]),
            "yhat_lower": float(row["yhat_lower"]),
            "yhat_upper": float(row["yhat_upper"]),
        })

prophet_df = pd.DataFrame(forecasts)
prophet_df.to_csv(OUTPUT / "forecasts_prophet.csv", index=False)

# ----------------------------------------------------------------------------
# Compare to piecewise linear
# ----------------------------------------------------------------------------
pw = pd.read_csv(OUTPUT / "forecasts_piecewise.csv")
pw_base = pw[(pw["scenario"] == "base") & (pw["year_start"].isin(FORECAST_YEARS))]
pr_fc = prophet_df[prophet_df["scenario"] == "prophet_forecast"]

compare = pw_base.merge(
    pr_fc, on=["DBN", "School Name", "year_start"],
    suffixes=("_piecewise_base", "_prophet"),
)
compare["abs_diff"] = (compare["yhat_piecewise_base"] - compare["yhat_prophet"]).abs()
compare["pct_diff"] = compare["abs_diff"] / compare["yhat_piecewise_base"]

print("=== Forecast comparison: piecewise base vs Prophet ===")
print(f"Mean abs diff per school-year:  {compare['abs_diff'].mean():.1f} students")
print(f"Median abs diff:                {compare['abs_diff'].median():.1f}")
print(f"Max abs diff:                   {compare['abs_diff'].max():.1f}")
print(f"Median pct diff:                {compare['pct_diff'].median():.1%}")
print()

print("=== System-wide 2024-25 totals ===")
totals_pw = pw[(pw["year_start"] == 2024)].groupby("scenario")["yhat"].sum()
total_prophet_2024 = prophet_df[(prophet_df["year_start"] == 2024) &
                                (prophet_df["scenario"] == "prophet_forecast")]["yhat"].sum()
print(totals_pw.to_string())
print(f"prophet        {total_prophet_2024:.0f}")
print()

# Example: a Red-flag school side-by-side
example = "02M041"  # PS 41 Greenwich Village
print(f"=== Side-by-side example: PS 41 Greenwich Village ({example}) ===")
print("\nPiecewise (all scenarios):")
print(pw[pw["DBN"] == example][["year_start", "scenario", "yhat", "yhat_lower", "yhat_upper"]]
      .sort_values(["scenario", "year_start"]).to_string(index=False))
print("\nProphet:")
print(prophet_df[prophet_df["DBN"] == example][
    ["year_start", "scenario", "yhat", "yhat_lower", "yhat_upper"]
].sort_values("year_start").to_string(index=False))
