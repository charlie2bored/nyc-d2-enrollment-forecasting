"""
Step 7: Piecewise linear enrollment forecast per D2 elementary school.

Model
-----
For each school we fit:

    y_t = alpha + beta_pre * t                              (pre-COVID)
    y_t = alpha + beta_pre * t_covid + gamma + beta_post*(t - t_covid)
                                                            (post-COVID)

where:
  - alpha       = pre-COVID intercept (level)
  - beta_pre    = pre-COVID annual slope (estimated from 7 pre-COVID years)
  - gamma       = COVID level shock (one-time drop at 2020-21)
  - beta_post   = post-COVID annual slope (estimated from 2 post-COVID years)
  - t_covid     = 2020 (the 2020-21 school year)

This is a piecewise linear regression with a known structural break, fit via OLS.

Scenarios (3-year horizon: 2022-23, 2023-24, 2024-25)
-----------------------------------------------------
  - Pessimistic : continue post-COVID slope linearly
  - Base        : enrollment stabilizes at 2021-22 level (slope -> 0)
  - Optimistic  : recover linearly toward pre-COVID baseline over 3 years

Exclusions
----------
  - The River School (02M281) and Sixth Avenue (02M340): reached K-5 maturity in
    or after 2018-19 and 2019-20 respectively. Not enough mature pre-COVID
    history to model. Will be reported as "insufficient data" in the dashboard.

Phase-in handling
-----------------
  - For the other 4 phase-in schools (Yorkville, East Side, Peck Slip, PS 527),
    we truncate the training data to their first mature year onward.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from paths import DERIVED, OUTPUT

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
COVID_YEAR = 2020  # 2020-21 school year is the structural break
FORECAST_YEARS = [2022, 2023, 2024]  # 2022-23, 2023-24, 2024-25 school years
EXCLUDE_DBNS = ["02M281", "02M340"]  # River, Sixth Avenue — insufficient mature data
PHASE_IN_TRUNCATE = {
    "02M151": 2014,  # Yorkville Community School
    "02M267": 2015,  # East Side Elementary School, PS 267
    "02M343": 2017,  # The Peck Slip School
    "02M527": 2017,  # PS 527 East Side School for Social Action
}
INTERVAL = 0.80  # 80% prediction interval

# ----------------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------------
df = pd.read_csv(DERIVED / "d2_elementary_9yr.csv")
df["year_start"] = df["Year"].str[:4].astype(int)

# ----------------------------------------------------------------------------
# Per-school model fit
# ----------------------------------------------------------------------------
def fit_school(school_df: pd.DataFrame):
    """Fit piecewise linear model. Returns dict of fit params and uncertainty."""
    t = school_df["year_start"].values
    y = school_df["k5_enroll"].values

    pre_mask = t < COVID_YEAR
    post_mask = t >= COVID_YEAR

    # Pre-COVID OLS: y = alpha + beta_pre * (t - t_covid)
    # Centering on t_covid makes alpha = pre-COVID level *at* the break point.
    t_pre = t[pre_mask] - COVID_YEAR
    y_pre = y[pre_mask]
    X_pre = sm.add_constant(t_pre)
    pre_fit = sm.OLS(y_pre, X_pre).fit()
    alpha = pre_fit.params[0]            # pre-COVID level at break
    beta_pre = pre_fit.params[1]         # pre-COVID annual slope
    pre_resid_std = np.sqrt(pre_fit.mse_resid) if pre_fit.df_resid > 0 else 0.0

    # Post-COVID: 2 data points -> slope and shock determined exactly
    # gamma = y(2020) - alpha           (one-time shock at the break)
    # beta_post = y(2021) - y(2020)     (slope per year)
    t_post = t[post_mask]
    y_post = y[post_mask]
    # In our data we always have both 2020 and 2021
    y_2020 = y_post[t_post == COVID_YEAR][0]
    y_2021 = y_post[t_post == COVID_YEAR + 1][0]
    gamma = y_2020 - alpha
    beta_post = y_2021 - y_2020

    pre_baseline = alpha + beta_pre * 0   # = alpha; pre-COVID expected level at 2020
    pre_baseline_mean = np.mean(y_pre)    # alternate baseline = simple pre-COVID mean

    return {
        "alpha": alpha,
        "beta_pre": beta_pre,
        "gamma": gamma,
        "beta_post": beta_post,
        "pre_resid_std": pre_resid_std,
        "y_2021": y_2021,
        "pre_baseline_mean": pre_baseline_mean,
        "n_pre": pre_mask.sum(),
        "n_post": post_mask.sum(),
        "pre_fit": pre_fit,
    }

def project(fit, horizon_year: int, scenario: str):
    """Return point forecast for a given school in a given year and scenario."""
    h = horizon_year - (COVID_YEAR + 1)  # years past 2021-22 (the last observed year)
    y_2021 = fit["y_2021"]
    if scenario == "pessimistic":
        # Continue post-COVID slope
        return y_2021 + fit["beta_post"] * h
    if scenario == "base":
        # Stabilize at 2021-22 level
        return y_2021
    if scenario == "optimistic":
        # Linear recovery toward pre-COVID mean over the horizon
        target = fit["pre_baseline_mean"]
        recovery_per_year = (target - y_2021) / max(len(FORECAST_YEARS), 1)
        return y_2021 + recovery_per_year * h
    raise ValueError(scenario)

def interval(fit, horizon_year: int, scenario: str, alpha: float = 1 - INTERVAL):
    """
    Return (lower, upper) prediction interval.

    Uses pre-COVID residual std-dev as the noise scale, widened by sqrt(h+1)
    to reflect growing uncertainty into the future. The width matches the
    pre-COVID year-over-year variation; honest given we cannot estimate
    post-COVID noise from 2 data points.
    """
    h = horizon_year - (COVID_YEAR + 1)
    sigma = fit["pre_resid_std"]
    # Two-sided z for the requested interval
    from scipy.stats import norm
    z = norm.ppf(1 - alpha / 2)
    half_width = z * sigma * np.sqrt(h + 1)
    pt = project(fit, horizon_year, scenario)
    return pt - half_width, pt + half_width

# ----------------------------------------------------------------------------
# Run the model
# ----------------------------------------------------------------------------
all_forecasts = []
school_summary = []
excluded = []

for dbn, school_df in df.groupby("DBN"):
    name = school_df["School Name"].iloc[0]

    if dbn in EXCLUDE_DBNS:
        excluded.append({"DBN": dbn, "School Name": name,
                         "reason": "phase-in school reached maturity too recently"})
        continue

    # Truncate phase-in schools to their mature window
    if dbn in PHASE_IN_TRUNCATE:
        school_df = school_df[school_df["year_start"] >= PHASE_IN_TRUNCATE[dbn]]

    school_df = school_df.sort_values("year_start").reset_index(drop=True)

    fit = fit_school(school_df)

    # Emit actuals
    for _, row in school_df.iterrows():
        all_forecasts.append({
            "DBN": dbn, "School Name": name,
            "year_start": int(row["year_start"]),
            "scenario": "actual",
            "yhat": float(row["k5_enroll"]),
            "yhat_lower": float(row["k5_enroll"]),
            "yhat_upper": float(row["k5_enroll"]),
        })

    # Emit forecasts for each scenario / horizon year
    for scenario in ["pessimistic", "base", "optimistic"]:
        for yr in FORECAST_YEARS:
            yhat = project(fit, yr, scenario)
            lo, hi = interval(fit, yr, scenario)
            all_forecasts.append({
                "DBN": dbn, "School Name": name,
                "year_start": yr,
                "scenario": scenario,
                "yhat": float(yhat),
                "yhat_lower": float(lo),
                "yhat_upper": float(hi),
            })

    # Per-school summary row
    pre_baseline = fit["pre_baseline_mean"]
    current = fit["y_2021"]
    pct_below_pre_covid = (current - pre_baseline) / pre_baseline
    forecast_2024 = project(fit, 2024, "base")
    pct_change_3yr = (forecast_2024 - current) / current

    # Risk flag using base-case forecast
    if pct_below_pre_covid <= -0.25:
        risk = "Red"
    elif pct_below_pre_covid <= -0.10:
        risk = "Yellow"
    else:
        risk = "Green"

    school_summary.append({
        "DBN": dbn, "School Name": name,
        "pre_covid_baseline_mean": round(pre_baseline, 1),
        "current_2021_22": int(current),
        "pct_vs_pre_covid": round(pct_below_pre_covid, 3),
        "beta_pre": round(fit["beta_pre"], 2),
        "covid_shock_gamma": round(fit["gamma"], 1),
        "post_covid_slope": round(fit["beta_post"], 1),
        "base_forecast_2024_25": round(forecast_2024, 0),
        "risk_flag": risk,
        "n_pre_covid_years": fit["n_pre"],
    })

forecasts_df = pd.DataFrame(all_forecasts)
summary_df = pd.DataFrame(school_summary)
excluded_df = pd.DataFrame(excluded)

forecasts_df.to_csv(OUTPUT / "forecasts_piecewise.csv", index=False)
summary_df.to_csv(OUTPUT / "school_summary_piecewise.csv", index=False)
excluded_df.to_csv(OUTPUT / "schools_excluded.csv", index=False)

# ----------------------------------------------------------------------------
# Print summary
# ----------------------------------------------------------------------------
print(f"Schools modeled: {len(summary_df)}")
print(f"Schools excluded: {len(excluded_df)}")
print()
print("=== Risk flag distribution ===")
print(summary_df["risk_flag"].value_counts().to_string())
print()
print("=== Red-flag schools (>25% below pre-COVID baseline) ===")
red = summary_df[summary_df["risk_flag"] == "Red"].sort_values("pct_vs_pre_covid")
print(red[["DBN", "School Name", "pre_covid_baseline_mean", "current_2021_22",
          "pct_vs_pre_covid", "base_forecast_2024_25"]].to_string(index=False))
print()
print("=== System-wide totals (base case) ===")
totals = forecasts_df[forecasts_df["scenario"].isin(["actual", "base"])].groupby(
    ["year_start", "scenario"])["yhat"].sum().unstack(fill_value=0)
print(totals.to_string())
print()
print("=== All scenarios, system-wide 2024-25 ===")
ts_2024 = forecasts_df[forecasts_df["year_start"] == 2024].groupby("scenario")["yhat"].sum()
print(ts_2024.to_string())
