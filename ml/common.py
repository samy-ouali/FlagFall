"""Paths and helpers shared by the ML scripts."""

from pathlib import Path

import pandas as pd

ML_DIR = Path(__file__).resolve().parent
ROOT = ML_DIR.parent
FLAGS_DIR = ROOT / "Assets" / "Flags"
STREAMING_ASSETS = ROOT / "Assets" / "StreamingAssets"
MODEL_JSON = STREAMING_ASSETS / "flag_model.json"
OUTPUT_DIR = ML_DIR / "output"
LOGS_DIR = ML_DIR / "data" / "logs"          # put the CSV files written by the game here
FIG_DIR = ROOT / "docs" / "figures"


def load_countries() -> pd.DataFrame:
    """code, name_fr, name_en for every flag used in the game."""
    return pd.read_csv(ML_DIR / "countries.csv", encoding="utf-8")


def similar_lists(sim: pd.DataFrame, k: int = 4) -> dict:
    """For each flag, the k most similar other flags (most similar first)."""
    out = {}
    for code in sim.index:
        row = sim.loc[code].drop(code).sort_values(ascending=False)
        out[code] = list(row.index[:k])
    return out


def load_similarity() -> pd.DataFrame:
    """Flag-by-flag CLIP similarity matrix computed by flag_similarity.py."""
    path = OUTPUT_DIR / "flag_similarity.csv"
    if not path.exists():
        raise FileNotFoundError("Run `python ml/flag_similarity.py` first.")
    return pd.read_csv(path, index_col=0)
