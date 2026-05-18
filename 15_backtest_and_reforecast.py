"""
Step 15: Backtest existing 3-year forecasts against 2022-25 NYSED actuals, then
re-fit on full 12-year dataset and generate new forecasts (2025-26 to 2027-28).

This script is self-contained — it (a) refits the OLD model on 9 years of data
just for the backtest, then (b) refits the FULL model on 12 years for the new
forecasts. This avoids any contamination from previously-written files.
"""
import warnings
import logging
warnings.filterwarnings("ignore")
logging.getLogger("prophet").setLevel(logging.ERROR)
logging.getLogger("cmdstanpy").setLevel(logging.ERROR)

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm
from prophet import Prophet

COVID_YEAR = 2020
NEW_FORECAST_YEARS = [2025, 2026, 2027]
BACKTEST_YEARS = [2022, 2023, 2024]
EXCLUDE_DBNS = ["02M281", "02M340"]
PHASE_IN_TRUNCATE = {"02M151": 2014, "02M267": 2015, "02M343": 2017, "02M527": 2017}
INTERVAL = 0.80

df_12yr = pd.read_csv("C:/Users/iamch/enrollment-forecast/d2_elementary_12yr.csv")
df_12yr["year_start"] = df_12yr["Year"].str[:4].astype(int)
df_12yr = df_12yr.sort_values(["DBN", "year_start"]).reset_index(drop=True)


# ============================================================================
# Piecewise linear model
# ============================================================================
def fit_school_piecewise(school_df):
    """Fit pre-COVID and post-COVID slopes. Uses all data passed in."""
    t = school_df["year_start"].values
    y = school_df["k5_enroll"].values
    pre_mask = t < COVID_YEAR
    post_mask = t >= COVID_YEAR

    t_pre = t[pre_mask] - COVID_YEAR
    y_pre = y[pre_mask]
    pre_fit = sm.OLS(y_pre, sm.add_constant(t_pre)).fit()
    alpha = pre_fit.params[0]
    beta_pre = pre_fit.params[1]
    pre_resid_std = np.sqrt(pre_fit.mse_resid) if pre_fit.df_resid > 0 else 0.0

    t_post = t[post_mask] - COVID_YEAR
    y_post = y[post_mask]
    if len(y_post) >= 2:
        post_fit = sm.OLS(y_post, sm.add_constant(t_post)).fit()
        post_alpha = post_fit.params[0]
        beta_post = post_fit.params[1]
        post_resid_std = np.sqrt(post_fit.mse_resid) if post_fit.df_resid > 0 else 0.0
    else:
        post_alpha = y_post[0] if len(y_post) else alpha
        beta_post = 0.0
        post_resid_std = pre_resid_std

    return {
        "alpha": alpha, "beta_pre": beta_pre,
        "gamma": post_alpha - alpha,
        "post_alpha": post_alpha, "beta_post": beta_post,
        "pre_resid_std": pre_resid_std,
        "post_resid_std": post_resid_std,
        "pre_baseline_mean": np.mean(y_pre),
        "y_last": y[-1], "t_last": t[-1],
        "n_pre": pre_mask.sum(), "n_post": post_mask.sum(),
    }


def project(fit, horizon_year, scenario, horizon_len):
    h = horizon_year - fit["t_last"]
    y_last = fit["y_last"]
    if scenario == "pessimistic":
        return y_last + fit["beta_post"] * h
    if scenario == "base":
        return y_last
    if scenario == "optimistic":
        target = fit["pre_baseline_mean"]
        recovery_per_year = (target - y_last) / horizon_len
        return y_last + recovery_per_year * h
    raise ValueError(scenario)


def interval(fit, horizon_year, scenario, horizon_len, alpha=1 - INTERVAL):
    h = horizon_year - fit["t_last"]
    sigma = fit["post_resid_std"]
    z = norm.ppf(1 - alpha / 2)
    half_width = z * sigma * np.sqrt(h + 1)
    pt = project(fit, horizon_year, scenario, horizon_len)
    return pt - half_width, pt + half_width


def fit_prophet(school_df, forecast_years):
    train = school_df[["ds", "k5_enroll"]].rename(columns={"k5_enroll": "y"}).copy()
    train["ds"] = pd.to_datetime(train["ds"], format="mixed")
    train = train.sort_values("ds")
    m = Prophet(
        growth="linear",
        yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False,
        n_changepoints=0,
        changepoints=[pd.Timestamp("2020-09-01")],
        changepoint_prior_scale=0.5,
        interval_width=INTERVAL,
    )
    m.fit(train)
    train_dates = list(train["ds"])
    fc_dates = [pd.Timestamp(f"{y}-09-01") for y in forecast_years]
    future = pd.DataFrame({"ds": train_dates + fc_dates})
    return m.predict(future)


# ============================================================================
# Part 1: backtest — refit old model on 2013-2021 data, forecast 2022-24
# ============================================================================
backtest_rows = []

for dbn, school_df in df_12yr.groupby("DBN"):
    name = school_df["School Name"].iloc[0]
    if dbn in EXCLUDE_DBNS:
        continue
    if dbn in PHASE_IN_TRUNCATE:
        school_df = school_df[school_df["year_start"] >= PHASE_IN_TRUNCATE[dbn]]

    # Train on 2013-2021 only (what we had when we made the original forecasts)
    train_old = school_df[school_df["year_start"] < 2022].sort_values("year_start")
    # Holdout for backtest: 2022, 2023, 2024
    holdout = school_df[school_df["year_start"].isin(BACKTEST_YEARS)]
    if len(holdout) == 0:
        continue

    fit_old = fit_school_piecewise(train_old)
    horizon_len_old = len(BACKTEST_YEARS)

    for scenario in ["pessimistic", "base", "optimistic"]:
        for yr in BACKTEST_YEARS:
            forecast = project(fit_old, yr, scenario, horizon_len_old)
            actual = holdout[holdout["year_start"] == yr]["k5_enroll"].values
            if len(actual) == 0:
                continue
            actual = float(actual[0])
            backtest_rows.append({
                "DBN": dbn, "School Name": name,
                "year_start": yr, "scenario": scenario, "model": "Piecewise Linear",
                "forecast": float(forecast), "actual": actual,
                "error": float(forecast) - actual,
                "abs_error": abs(float(forecast) - actual),
                "pct_error": (float(forecast) - actual) / actual,
            })

    # Prophet backtest: train on 2013-2021, forecast 2022-2024
    fc = fit_prophet(train_old, BACKTEST_YEARS)
    for _, row in fc.iterrows():
        yr = row["ds"].year
        if yr not in BACKTEST_YEARS:
            continue
        actual = holdout[holdout["year_start"] == yr]["k5_enroll"].values
        if len(actual) == 0:
            continue
        actual = float(actual[0])
        backtest_rows.append({
            "DBN": dbn, "School Name": name,
            "year_start": yr, "scenario": "base", "model": "Prophet",
            "forecast": float(row["yhat"]), "actual": actual,
            "error": float(row["yhat"]) - actual,
            "abs_error": abs(float(row["yhat"]) - actual),
            "pct_error": (float(row["yhat"]) - actual) / actual,
        })

backtest = pd.DataFrame(backtest_rows)
backtest.to_csv("C:/Users/iamch/enrollment-forecast/backtest.csv", index=False)

print("=" * 70)
print("BACKTEST: 2022-25 forecasts vs NYSED actuals")
print("=" * 70)
agg = backtest.groupby(["model", "scenario"]).agg(
    n=("DBN", "count"),
    mean_abs_error=("abs_error", "mean"),
    median_abs_error=("abs_error", "median"),
    mape=("pct_error", lambda x: x.abs().mean()),
    bias=("error", "mean"),
).round(3)
print(agg.to_string())

print("\n=== System-wide totals: forecasts vs actuals ===")
sys_actuals = df_12yr[df_12yr["year_start"].isin(BACKTEST_YEARS) & ~df_12yr["DBN"].isin(EXCLUDE_DBNS)].groupby("year_start")["k5_enroll"].sum()
print(f"Actuals (NYSED):          {dict(sys_actuals.astype(int))}")
for (model, scenario), group in backtest.groupby(["model", "scenario"]):
    sys_fc = group.groupby("year_start")["forecast"].sum()
    label = f"{model} {scenario}"
    print(f"  {label:30s}: {dict(sys_fc.round(0).astype(int))}")


# ============================================================================
# Part 2: refit on full 12-year data, forecast 2025-27
# ============================================================================
all_forecasts = []
school_summary = []
excluded = []

for dbn, school_df in df_12yr.groupby("DBN"):
    name = school_df["School Name"].iloc[0]
    if dbn in EXCLUDE_DBNS:
        excluded.append({"DBN": dbn, "School Name": name,
                         "reason": "phase-in school reached maturity too recently"})
        continue
    if dbn in PHASE_IN_TRUNCATE:
        school_df = school_df[school_df["year_start"] >= PHASE_IN_TRUNCATE[dbn]]

    school_df = school_df.sort_values("year_start").reset_index(drop=True)
    fit = fit_school_piecewise(school_df)
    horizon_len = len(NEW_FORECAST_YEARS)

    for _, row in school_df.iterrows():
        all_forecasts.append({
            "DBN": dbn, "School Name": name,
            "year_start": int(row["year_start"]),
            "scenario": "actual",
            "yhat": float(row["k5_enroll"]),
            "yhat_lower": float(row["k5_enroll"]),
            "yhat_upper": float(row["k5_enroll"]),
        })

    for scenario in ["pessimistic", "base", "optimistic"]:
        for yr in NEW_FORECAST_YEARS:
            yhat = project(fit, yr, scenario, horizon_len)
            lo, hi = interval(fit, yr, scenario, horizon_len)
            all_forecasts.append({
                "DBN": dbn, "School Name": name,
                "year_start": yr, "scenario": scenario,
                "yhat": float(yhat), "yhat_lower": float(lo), "yhat_upper": float(hi),
            })

    pre_baseline = fit["pre_baseline_mean"]
    current = fit["y_last"]
    pct_below = (current - pre_baseline) / pre_baseline
    if pct_below <= -0.25:
        risk = "Red"
    elif pct_below <= -0.10:
        risk = "Yellow"
    else:
        risk = "Green"

    school_summary.append({
        "DBN": dbn, "School Name": name,
        "pre_covid_baseline_mean": round(pre_baseline, 1),
        "current_2024_25": int(current),
        "pct_vs_pre_covid": round(pct_below, 3),
        "beta_pre": round(fit["beta_pre"], 2),
        "covid_shock_gamma": round(fit["gamma"], 1),
        "post_covid_slope": round(fit["beta_post"], 1),
        "base_forecast_2027_28": round(project(fit, 2027, "base", horizon_len), 0),
        "pessimistic_forecast_2027_28": round(project(fit, 2027, "pessimistic", horizon_len), 0),
        "optimistic_forecast_2027_28": round(project(fit, 2027, "optimistic", horizon_len), 0),
        "risk_flag": risk,
        "n_pre_covid_years": fit["n_pre"],
        "n_post_covid_years": fit["n_post"],
    })

forecasts_df = pd.DataFrame(all_forecasts)
summary_df = pd.DataFrame(school_summary)
excluded_df = pd.DataFrame(excluded)

forecasts_df.to_csv("C:/Users/iamch/enrollment-forecast/forecasts_piecewise.csv", index=False)
summary_df.to_csv("C:/Users/iamch/enrollment-forecast/school_summary_piecewise.csv", index=False)
excluded_df.to_csv("C:/Users/iamch/enrollment-forecast/schools_excluded.csv", index=False)

# Prophet — refit on full 12 years
prophet_forecasts = []
for dbn, school_df in df_12yr.groupby("DBN"):
    name = school_df["School Name"].iloc[0]
    if dbn in EXCLUDE_DBNS:
        continue
    if dbn in PHASE_IN_TRUNCATE:
        school_df = school_df[school_df["year_start"] >= PHASE_IN_TRUNCATE[dbn]]
    fc = fit_prophet(school_df, NEW_FORECAST_YEARS)
    train_years = set(school_df["year_start"].values)
    for _, row in fc.iterrows():
        yr = row["ds"].year
        prophet_forecasts.append({
            "DBN": dbn, "School Name": name,
            "year_start": int(yr),
            "scenario": "prophet_train" if yr in train_years else "prophet_forecast",
            "yhat": float(row["yhat"]),
            "yhat_lower": float(row["yhat_lower"]),
            "yhat_upper": float(row["yhat_upper"]),
        })
pd.DataFrame(prophet_forecasts).to_csv("C:/Users/iamch/enrollment-forecast/forecasts_prophet.csv", index=False)


print("\n" + "=" * 70)
print("NEW FORECASTS (refit on full 12-year data)")
print("=" * 70)
print("\n=== System-wide 2027-28 scenario range ===")
print(forecasts_df[forecasts_df["year_start"] == 2027].groupby("scenario")["yhat"].sum().round(0).astype(int).to_string())
prophet_df = pd.DataFrame(prophet_forecasts)
prophet_2027 = prophet_df[(prophet_df["year_start"] == 2027) & (prophet_df["scenario"] == "prophet_forecast")]["yhat"].sum()
print(f"prophet           {int(prophet_2027)}")

print("\n=== Updated risk flag distribution ===")
print(summary_df["risk_flag"].value_counts().to_string())
