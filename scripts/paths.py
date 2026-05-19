"""
Shared path constants for the analysis pipeline.

Every script reads its inputs and writes its outputs by importing the
folder constants from this module instead of hardcoding absolute paths.
This makes the repo runnable from any clone, on any OS.

Usage:
    from paths import RAW, DERIVED, OUTPUT, POWERBI, NYSED

    df = pd.read_csv(RAW / "demographic_snapshot.csv")
    df.to_csv(DERIVED / "d2_elementary_dbns.csv", index=False)

Layout (anchored to the repo root, two levels up from this file):
    data/raw/      source NYC DOE / NYSED files (user-supplied for NYSED)
    data/derived/  intermediate joins and lookups
    data/output/   model outputs (forecasts, backtest, summaries)
    data/powerbi/  star-schema CSVs imported by the Power BI dashboard
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
RAW = DATA / "raw"
DERIVED = DATA / "derived"
OUTPUT = DATA / "output"
POWERBI = DATA / "powerbi"
NYSED = RAW / "nysed"

# Ensure write targets exist on a fresh clone (idempotent).
for _d in (DERIVED, OUTPUT, POWERBI):
    _d.mkdir(parents=True, exist_ok=True)
