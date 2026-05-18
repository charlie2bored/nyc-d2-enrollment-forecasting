# Enrollment Forecasting Dashboard — Case Study Outline

> Fill in the placeholders (`[ ]`) once Power BI visuals are locked. Each
> section maps to a screenshot or finding from the dashboard.

---

## TL;DR (top of page, 3 sentences)

- Built a 3-scenario enrollment forecasting dashboard for 30 NYC District 2 elementary schools using 12 years of K-5 enrollment data (NYC DOE 2013-22 + NYSED 2022-25).
- **Backtested 2022-25 forecasts against actuals**: the Piecewise-Linear Base scenario landed within 9.5% MAPE; Prophet under-predicted by 20% MAPE, validating the methodological choice to present three scenarios rather than a single Prophet default.
- Forecast horizon now extended to 2027-28; 13 of 30 schools at Red risk; the resilient-outlier (Roosevelt Island) and lowest-income-hit-hardest patterns persist three years on.

---

## 1. Problem framing

- **Stakeholder decision the work supports**: which schools require intervention investment, and how confident are we in the forecast?
- **Personal context (resume bullet alignment)**: mirrors the predictive enrollment modeling work I did at Apple Montessori. Built on public NYC data to demonstrate methodology end-to-end without proprietary information.
- **Why District 2 specifically**: ~30 schools is the same scale as the Apple Montessori network. Manhattan's COVID-driven enrollment shock provides a real exogenous event to model.

## 2. Data

- **Primary historical**: NYC DOE Demographic Snapshot ([2017-22](https://data.cityofnewyork.us/Education/2017-18-2021-22-Demographic-Snapshot/c7ru-d68s), [2013-18](https://data.cityofnewyork.us/Education/2013-2018-Demographic-Snapshot-School/s52a-8aq6)). Stitched on the 2017-18 overlap year, byte-identical match.
- **Backtest validation**: [NYSED BEDS Day Enrollment](https://data.nysed.gov/downloads.php) for 2022-23, 2023-24, 2024-25. BEDS code → DBN mapping: `310200010NNN → 02MNNN`.
- **Catchment income**: ACS 5-year 2022 estimates, table B19013, joined at the 2020 census tract level via the Census Geocoder API.
- **Scope**: 32 pure elementary schools in District 2 Manhattan. 30 modeled; 2 excluded (River School, Sixth Avenue Elementary — reached K-5 maturity too recently).
- **Phase-in handling**: 4 schools (Yorkville, East Side, Peck Slip, PS 527) truncated to their first fully-populated K-5 year onward.
- **Caveat**: NYC DOE uses October 31 audited register count; NYSED uses BEDS Day (first Wednesday of October, ~3 weeks earlier). The two sources differ by 1-2% on overlapping years — accept as a methodological note.

## 3. Methodology

- **Primary model: piecewise linear regression** with a known structural break at 2020-21. Pre-COVID slope estimated by OLS on 2013-19 data; post-COVID slope estimated by OLS on 2020-24 data (5 post-COVID years after the data update).
- **Three scenarios**:
  - **Pessimistic** — extrapolate the post-COVID slope linearly.
  - **Base** — enrollment stabilizes at the most recent observed level.
  - **Optimistic** — linear recovery toward the pre-COVID baseline over the forecast horizon.
- **Comparison model: Facebook Prophet** — configured to match the data shape (no seasonality, single known changepoint at 2020-09-01).

## 4. The validation event: backtesting against 2022-25 actuals

**Methodology**: Refit both models on the data we had available at the original forecast date (2013-14 through 2021-22 only). Forecast 2022-23, 2023-24, 2024-25. Compare against NYSED actuals.

### System-wide totals

| Year | Actual | Piecewise Base | Piecewise Optimistic | Piecewise Pessimistic | Prophet (default) |
|---|---:|---:|---:|---:|---:|
| 2022-23 | 11,911 | 12,206 | 13,347 | 11,169 | 11,154 |
| 2023-24 | 12,047 | 12,206 | 14,488 | 10,132 | 9,847 |
| 2024-25 | 11,973 | **12,206** | 15,628 | 9,095 | 8,536 |

### Error metrics (mean absolute percentage error)

| Model & scenario | MAPE | Bias | Verdict |
|---|---:|---:|---|
| **Piecewise Base** | **9.5%** | +8 | **Best in class** |
| Piecewise Pessimistic | 18.1% | -64 | Too pessimistic |
| **Prophet (default)** | **20.0%** | **-73** | **Most pessimistic — under-predicted by 28% on year 3** |
| Piecewise Optimistic | 27.0% | +87 | No recovery happened |

### What this validates

1. **The Base scenario was within ~4% of system-wide reality.** Schools stabilized at the post-COVID level; they did not continue declining and did not recover.
2. **Prophet under-predicted by 28%** at the 3-year horizon (8,536 vs 11,973). Its piecewise-linear changepoint logic correctly identified the COVID break but extrapolated the 2020→2022 slope as a continuing trend rather than a one-time level shift.
3. **The methodological argument holds empirically**: with only 2 post-COVID data points at the original forecast date, no model could reliably distinguish "level shift" from "continuing decline." Presenting three scenarios bracketed the uncertainty; reporting a single Prophet number would have communicated a 28%-too-pessimistic projection as confident truth.

This is the single strongest analytical finding in the case study: **the methodology was tested, and it beat Prophet by 10 percentage points of MAPE.**

## 5. Updated forecasts (refit on full 12-year data, 2025-26 → 2027-28)

### System-wide 2027-28 scenario range

| Scenario | 2027-28 enrollment |
|---|---:|
| Pessimistic | 11,268 |
| **Base** | **12,186** |
| Optimistic | 15,836 |
| Prophet (refit on full data) | 10,140 |

### School-level

- **13 Red** (>25% below pre-COVID baseline as of 2024-25), 9 Yellow, 8 Green.
- Worst declines: PS 1 Alfred E. Smith (-52%), PS 2 Meyer London (-47%), Yorkville Community (-44%), PS 130 Hernando De Soto (-43%), PS 290 Manhattan New School (-41%).
- **Resilient outlier persists**: PS/IS 217 Roosevelt Island grew through the entire window. Geographic isolation continues to insulate this school's enrollment.

### Driver analysis (income vs decline) — unchanged finding, now stronger with 3 more years of data

- Pearson correlation between catchment median household income and pct enrollment change: ~0.14 (essentially zero).
- The lowest-income quartile (Chinatown / Lower East Side) still has the largest declines. PS 1, PS 2, and PS 42 (Chinatown/LES) lead the Red list.
- The "wealthy families left" narrative remains refuted by the data.

## 6. Limitations & caveats

- **Two data sources stitched** (NYC DOE pre-2022, NYSED post-2022) with a known snapshot-date difference (~3 weeks). Documented in code; differences are small (~1-2%) but real.
- **Topcoding at $250,001** for catchment income suppresses variation at the high end.
- **Catchment income ≠ student family income.** NYC school choice means student bodies don't match catchment demographics perfectly.
- **Two schools excluded** (River, Sixth Avenue) — reached K-5 maturity too recently to forecast.
- **1 school missing in backtest**: Ella Baker (02M225) didn't appear in NYSED 2022-25; possible BEDS code change or school restructure. 29 of 30 schools have full backtest data.

## 7. What I'd build next

- **Family-level attrition risk model**. Given that the broad-based decline is now structurally locked in, school-level forecasts say *how many*; family-level would say *who*.
- **Spatial features and capacity utilization**. The Roosevelt Island finding suggests "friction of exit" — not income — is the variable that matters. A catchment isolation index would test this directly.
- **Continue the validation cycle**. The 2025-26 school year is happening now. Pull 2025-26 actuals once published (~late 2026) and re-validate the 2027-28 forecasts.

---

## Power BI visual checklist

- [ ] Page 1 (Executive Summary): system-wide fan chart with three scenarios over 15 years (2013-14 → 2027-28); KPI cards (30 schools, 13 Red, 2024-25 = 11,977, 2027-28 Base = 12,186)
- [ ] Page 2 (School Grid): matrix with risk-flag color coding, scenario + model slicers
- [ ] Page 3 (Single-school deep dive): use PS 41 Greenwich Village or PS 1 Alfred E. Smith as worked example
- [ ] **Page 4 (Backtest) — the killer page**: bar chart of MAPE by model/scenario; system-wide line chart showing forecasts diverging from actuals; per-school error scatter
- [ ] Page 5 (Methodology): piecewise vs Prophet comparison, income-vs-decline scatter (null result), data quality callouts

## Resume bullet (updated)

> "Built and **back-tested** a multi-scenario enrollment forecasting dashboard for 30 NYC public elementary schools using NYC DOE + NYSED data and ACS catchment demographics. Piecewise linear scenarios with Prophet comparison; **back-test against 2022-25 actuals showed the base scenario landed within 4% of system-wide reality while Prophet under-predicted by 28%**, validating the methodological choice of analyst-bounded scenarios over single-point ML defaults. Power BI dashboard with 5-year forecasts, school-level drill-down, and driver analysis."
