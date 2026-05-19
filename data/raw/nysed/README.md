# NYSED BEDS Day Enrollment databases

These three Microsoft Access (`.accdb`) files are the only inputs not
committed to this repo — each is ~22 MB, and re-downloads cleanly from
NYSED. They are needed only by `scripts/13_inspect_nysed.py` and
`scripts/14_extract_recent_actuals.py`, which extract post-2022
actual enrollment for the backtest. Scripts 01–12 and 15–16 run
without them (15–16 will run, but their refitted forecasts will not
include the post-2022 actuals).

## Expected layout

After downloading, the directory should look like:

```
data/raw/nysed/
├── 2023/ENROLL2023_20231207.accdb     (2022-23 school year actuals)
├── 2024/ENROLL2024_20241105..accdb    (2023-24 school year actuals — note the double dot in the NYSED filename)
└── 2025/ENROLL2025_20251217.accdb     (2024-25 school year actuals)
```

## Where to download

NYSED publishes BEDS Day Enrollment as part of its annual Information &
Reporting Services releases:

- Public landing page: https://data.nysed.gov/
- Annual BEDS releases: https://www.p12.nysed.gov/irs/statistics/enroll-n-staff/

The filenames embed the release date, so the exact stems change year over
year. If you grab a newer release than what the scripts expect, either
rename it to match the paths above or update the paths inside
`scripts/13_inspect_nysed.py` and `scripts/14_extract_recent_actuals.py`.
