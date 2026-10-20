"""Learn flag difficulty and player skill from the game logs, and export the model for Unity.

Steps
-----
1. Load the catch events logged by the game (one row per caught flag).
2. Compare three ways of predicting whether the player catches the right flag,
   on the last 30 % of events (chronological split, like in real use):
     - Baseline: always predict the average success rate.
     - Elo: the online rating model used inside the game (AdaptiveDirector.cs).
     - Logistic regression: Elo prediction + the player's history with this flag
       + how similar the other flags on screen were (CLIP).
3. Fit the final flag difficulties on all data (Rasch model = logistic regression
   with one coefficient per player and one per flag).
4. Export Assets/StreamingAssets/flag_model.json, read by the game: difficulty
   and look-alike flags for each country.

Usage (from the repository root):
    python ml/train_difficulty.py              # real logs in ml/data/logs/
    python ml/train_difficulty.py --simulated  # simulated logs (does not touch the game file)
"""

import argparse
import json
import math
from collections import defaultdict
from datetime import date

import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.preprocessing import OneHotEncoder

from common import (LOGS_DIR, ML_DIR, MODEL_JSON, OUTPUT_DIR, load_countries,
                    load_similarity, similar_lists)
import plots
from policy import K_ITEM, K_PERSONAL, K_PLAYER, sigmoid

SIM_DIR = ML_DIR / "data" / "simulated"
TEST_SHARE = 0.3
N_SIMILAR = 4


def load_logs(folder):
    files = sorted(folder.glob("*.csv"))
    if not files:
        return None
    df = pd.concat([pd.read_csv(f, dtype={"onscreen": str}) for f in files], ignore_index=True)
    df = df[df["event"] == "catch"].copy()
    df["correct"] = df["correct"].astype(int)
    df["onscreen"] = df["onscreen"].fillna("")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # chronological order (stable, so events of the same second keep their order)
    return df.sort_values(["timestamp", "session_id", "game_time"], kind="stable").reset_index(drop=True)


def add_online_features(df, sim):
    """Replay the events in order and compute, for each one, what was known BEFORE it.

    This is exactly what the game can compute live, so there is no information
    from the future (no data leakage).
    """
    theta = defaultdict(float)                    # player skill
    b = defaultdict(float)                        # flag difficulty
    u = defaultdict(float)                        # (player, flag) personal adjustment
    n_prev = defaultdict(int)
    n_ok = defaultdict(int)
    feats = []
    for row in df.itertuples():
        key = (row.player, row.target)
        logit = theta[row.player] - b[row.target] + u[key]
        others = [c for c in row.onscreen.split("|") if c and c in sim.index]
        max_sim = max((sim.loc[row.target, c] for c in others), default=0.0)
        feats.append({
            "elo_logit": logit,
            "elo_p": sigmoid(logit),
            "log_prev_attempts": math.log1p(n_prev[key]),
            "prev_success_rate": (n_ok[key] + 1) / (n_prev[key] + 2),
            "max_onscreen_similarity": max_sim,
        })
        # Elo update, identical to AdaptiveDirector.cs
        err = row.correct - sigmoid(logit)
        theta[row.player] += K_PLAYER * err
        b[row.target] -= K_ITEM * err
        u[key] += K_PERSONAL * err
        n_prev[key] += 1
        n_ok[key] += row.correct
    return pd.concat([df, pd.DataFrame(feats, index=df.index)], axis=1)


def evaluate(df):
    split = int(len(df) * (1 - TEST_SHARE))
    train, test = df.iloc[:split], df.iloc[split:]
    y = test["correct"].values
    results = {}

    p_base = np.full(len(test), train["correct"].mean())
    results["Baseline (average rate)"] = p_base

    results["Elo (in-game model)"] = test["elo_p"].clip(1e-4, 1 - 1e-4).values

    cols = ["elo_logit", "log_prev_attempts", "prev_success_rate",
            "max_onscreen_similarity", "fall_speed"]
    lr = LogisticRegression(max_iter=1000).fit(train[cols], train["correct"])
    results["Logistic regression"] = lr.predict_proba(test[cols])[:, 1]

    out = {}
    for name, p in results.items():
        out[name] = {"log_loss": float(log_loss(y, p, labels=[0, 1])),
                     "auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else None}
        print(f"  {name:<26} log-loss {out[name]['log_loss']:.3f}   AUC {out[name]['auc']:.3f}")
    coefs = dict(zip(cols, lr.coef_[0].round(3)))
    print(f"  Logistic regression coefficients: {coefs}")
    return out, coefs, len(train), len(test)


def fit_difficulty(df, codes):
    """Rasch model: P(correct) = sigmoid(skill_player - difficulty_flag)."""
    enc_p = OneHotEncoder(handle_unknown="ignore").fit(df[["player"]])
    enc_f = OneHotEncoder(categories=[codes], handle_unknown="ignore").fit(df[["target"]])
    X = hstack([enc_p.transform(df[["player"]]), -enc_f.transform(df[["target"]])]).tocsr()
    model = LogisticRegression(C=1.0, max_iter=2000).fit(X, df["correct"])
    n_players = len(enc_p.categories_[0])
    diff = pd.Series(model.coef_[0][n_players:], index=codes)
    seen = df["target"].value_counts().reindex(codes).fillna(0)
    diff[seen == 0] = np.nan                     # no data: unknown, set to 0 below
    return (diff - diff.mean()).fillna(0.0), seen


def confusion_counts(df):
    wrong = df[df["correct"] == 0]
    return wrong.groupby(["target", "caught"]).size()


def build_similar(sim, df, codes):
    """CLIP look-alikes, boosted by the confusions really observed in the logs."""
    base = sim.copy()
    conf = confusion_counts(df) if df is not None else pd.Series(dtype=float)
    if len(conf):
        attempts = df["target"].value_counts()
        for (t, c), n in conf.items():
            if t in base.index and c in base.columns:
                base.loc[t, c] += 0.5 * n / attempts[t]
    return similar_lists(base.loc[codes, codes], N_SIMILAR)


def export(countries, difficulty, similar, source, n_events, path):
    data = {
        "source": source,
        "created": date.today().isoformat(),
        "n_events": int(n_events),
        "target_success": 0.7,
        "countries": [
            {"code": r.code, "name_fr": r.name_fr, "name_en": r.name_en,
             "difficulty": round(float(difficulty.get(r.code, 0.0)), 3),
             "similar": similar[r.code]}
            for r in countries.itertuples()
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported model to {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--simulated", action="store_true", help="use ml/data/simulated instead of real logs")
    args = ap.parse_args()

    countries = load_countries()
    codes = list(countries["code"])
    names = dict(zip(countries["code"], countries["name_en"]))
    sim = load_similarity()

    folder = SIM_DIR if args.simulated else LOGS_DIR
    df = load_logs(folder)
    source = "simulated" if args.simulated else "playtests"
    out_json = OUTPUT_DIR / "flag_model_simulated.json" if args.simulated else MODEL_JSON

    if df is None or len(df) < 50:
        print(f"Not enough data in {folder} (need at least 50 catches).")
        print("Exporting a model with similarity only (all difficulties = 0).")
        export(countries, {}, build_similar(sim, None, codes), "similarity only", 0, out_json)
        return

    print(f"{len(df)} catches, {df['player'].nunique()} players, "
          f"{df['session_id'].nunique()} sessions, success rate {df['correct'].mean():.1%}")
    df = add_online_features(df, sim)
    print("Prediction on the last 30% of events:")
    results, coefs, n_train, n_test = evaluate(df)
    difficulty, seen = fit_difficulty(df, codes)

    tag = "_simulated" if args.simulated else ""
    plots.plot_model_comparison(results, suffix=tag)
    plots.plot_difficulty(difficulty[seen > 0], names, suffix=tag)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"metrics{tag}.json").write_text(json.dumps({
        "source": source, "n_catches": len(df), "n_train": n_train, "n_test": n_test,
        "models": results, "logistic_coefficients": {k: float(v) for k, v in coefs.items()},
    }, indent=2))
    export(countries, difficulty, build_similar(sim, df, codes), source, len(df), out_json)


if __name__ == "__main__":
    main()
