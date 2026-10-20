"""Simulated players, to develop and test the ML pipeline before real playtests.

IMPORTANT: everything produced by this script is SYNTHETIC. The players follow a
simple model that I chose (below); the results only show that the pipeline works
and how the adaptive game behaves *if* players behave like this model.

Player model
------------
- Each flag has a true difficulty: well-known flags (US, France, Japan...) are
  easier, the others harder, plus some noise.
- Each player has a skill level. The probability of recognising a flag is
  sigmoid(knowledge), where knowledge starts at (skill - difficulty).
- When a look-alike of the target is on screen (CLIP similarity > 0.85), the
  player is more likely to catch the wrong flag, and then catches a look-alike.
- Learning: every attempt increases the knowledge of the target flag, more when
  the flag was not well known yet (gain proportional to 1 - P(recognise)).
  Most of the learning happens on successful catches: when the player catches a
  wrong flag, the game does not show the right one, so little is learnt.

Two outputs:
1. ml/data/simulated/*.csv : game logs in the exact format written by the game
   (GameLogger.cs), used to test train_difficulty.py.
2. docs/figures/policy_simulation.png : original random game vs adaptive game.

Usage (from the repository root):
    python ml/simulate_players.py
"""

import csv
import math
import random
from datetime import datetime, timedelta

import numpy as np

from common import ML_DIR, OUTPUT_DIR, load_countries, load_similarity, similar_lists
import plots
from policy import AdaptiveDirector, RandomDirector, sigmoid

SIM_DIR = ML_DIR / "data" / "simulated"
WELL_KNOWN = {"us", "fr", "jp", "ca", "br", "gb", "de", "it", "es", "ch", "cn", "kr", "in", "mx"}
CONFUSION_THRESHOLD = 0.85
CONFUSION_WEIGHT = 2.0
LEARN_CORRECT = 0.4       # learning when the right flag is caught
LEARN_WRONG = 0.05        # a wrong catch teaches little: the game never shows the right flag
N_ON_SCREEN = 3            # wrong flags visible when the player catches one

LOG_COLUMNS = ["session_id", "player", "timestamp", "game_time", "event", "target",
               "caught", "correct", "reaction_time", "fall_speed", "onscreen", "policy"]


class SimPlayer:
    def __init__(self, name, codes, true_difficulty, sim, rng):
        self.name = name
        self.rng = rng
        self.sim = sim
        skill = rng.gauss(0.3, 0.8)
        self.knowledge = {c: skill - true_difficulty[c] for c in codes}

    def p_recognise(self, code):
        return sigmoid(self.knowledge[code])

    def attempt(self, target, onscreen):
        """Return the flag the player catches."""
        max_sim = max((self.sim.loc[target, c] for c in onscreen), default=0.0)
        confusion = max(0.0, max_sim - CONFUSION_THRESHOLD) / (1 - CONFUSION_THRESHOLD)
        p = sigmoid(self.knowledge[target] - CONFUSION_WEIGHT * confusion)
        if self.rng.random() < p:
            caught = target
        else:  # catches a wrong flag, more likely a look-alike
            w = [math.exp(8 * self.sim.loc[target, c]) for c in onscreen]
            caught = self.rng.choices(onscreen, w)[0]
        # learning
        gain = (LEARN_CORRECT if caught == target else LEARN_WRONG) * (1 - self.p_recognise(target))
        self.knowledge[target] += gain
        return caught

    def mean_knowledge(self):
        return float(np.mean([self.p_recognise(c) for c in self.knowledge]))


def true_difficulties(codes, rng):
    return {c: (-1.2 if c in WELL_KNOWN else 0.6) + rng.gauss(0, 0.5) for c in codes}


def play(director, player, n_rounds=None, lives=3, max_rounds=200):
    """Play one game. Returns a list of catch events (target, caught, onscreen)."""
    events = []
    target = director.pick_target()
    while True:
        onscreen = [director.pick_distractor(target) for _ in range(N_ON_SCREEN)]
        caught = player.attempt(target, onscreen)
        correct = caught == target
        director.record(target, correct)
        events.append((target, caught, onscreen))
        if correct:
            target = director.pick_target()
        else:
            lives -= 1
        if n_rounds is not None:
            if len(events) >= n_rounds:
                break
        elif lives <= 0 or len(events) >= max_rounds:
            break
    return events


def write_logs(codes, sim, similar, rng, n_players=25, sessions=8):
    """Simulated playtest: n_players x sessions games, half random, half adaptive."""
    SIM_DIR.mkdir(parents=True, exist_ok=True)
    for f in SIM_DIR.glob("*.csv"):
        f.unlink()
    truth = true_difficulties(codes, rng)
    t0 = datetime(2027, 3, 1, 14, 0, 0)
    n_events = 0
    for p in range(n_players):
        player = SimPlayer(f"player{p:02d}", codes, truth, sim, rng)
        director_ad = AdaptiveDirector(codes, similar, rng=rng)
        for s in range(sessions):
            adaptive = s % 2 == 1
            director = director_ad if adaptive else RandomDirector(codes, rng=rng)
            events = play(director, player)
            sid = f"sim-{p:02d}-{s}"
            start = t0 + timedelta(days=p, hours=s)
            rows, game_time = [], 0.0
            for target, caught, onscreen in events:
                rt = max(0.6, rng.lognormvariate(math.log(3.0 - player.p_recognise(target)), 0.3))
                game_time += rt
                rows.append({
                    "session_id": sid, "player": player.name,
                    "timestamp": (start + timedelta(seconds=game_time)).isoformat(timespec="seconds"),
                    "game_time": f"{game_time:.2f}", "event": "catch", "target": target,
                    "caught": caught, "correct": int(caught == target),
                    "reaction_time": f"{rt:.2f}", "fall_speed": f"{3 + 0.05 * game_time:.2f}",
                    "onscreen": "|".join(onscreen),   # all wrong flags on screen, including a wrongly caught one
                    "policy": "adaptive" if adaptive else "random",
                })
            with open(SIM_DIR / f"{sid}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
                w.writeheader()
                w.writerows(rows)
            n_events += len(rows)
    print(f"Wrote {n_players * sessions} simulated sessions ({n_events} catches) to {SIM_DIR}")
    return truth


def compare_policies(codes, sim, similar, difficulty, seed=1, n_players=200, n_rounds=300, window=20):
    """Same simulated players, original random game vs adaptive game, practice mode (no game over)."""
    curves = {}
    for name in ("Random (original game)", "Adaptive (ML)"):
        rng = random.Random(seed)          # same players for both games
        succ = np.zeros((n_players, n_rounds))
        know = np.zeros((n_players, n_rounds))
        for p in range(n_players):
            truth = true_difficulties(codes, rng)
            player = SimPlayer(f"p{p}", codes, truth, sim, random.Random(seed * 1000 + p))
            director = (AdaptiveDirector(codes, similar, difficulty, rng=random.Random(p))
                        if name.startswith("Adaptive") else RandomDirector(codes, rng=random.Random(p)))
            target = director.pick_target()
            for r in range(n_rounds):
                onscreen = [director.pick_distractor(target) for _ in range(N_ON_SCREEN)]
                caught = player.attempt(target, onscreen)
                correct = caught == target
                director.record(target, correct)
                succ[p, r] = correct
                know[p, r] = player.mean_knowledge()
                if correct:
                    target = director.pick_target()
        mean_succ = succ.mean(axis=0)
        rolling = np.convolve(mean_succ, np.ones(window) / window, mode="valid")
        curves[name] = {
            "round": np.arange(window, n_rounds + 1),
            "success_rate": rolling,
            "knowledge": know.mean(axis=0)[window - 1:],
            "final_knowledge": float(know[:, -1].mean()),
            "start_knowledge": float(know[:, 0].mean()),
            "mean_success": float(succ.mean()),
        }
        print(f"{name:<24} success rate {succ.mean():.1%}  "
              f"knowledge {know[:, 0].mean():.1%} -> {know[:, -1].mean():.1%}")
    plots.plot_policy_comparison(curves)
    return curves


def main():
    countries = load_countries()
    codes = list(countries["code"])
    sim = load_similarity()
    similar = similar_lists(sim)
    rng = random.Random(42)
    write_logs(codes, sim, similar, rng)

    # The adaptive game starts from the flag difficulties learned on the
    # simulated playtest (like it will start from the real playtests).
    from train_difficulty import fit_difficulty, load_logs, SIM_DIR as LOG_DIR
    difficulty, _ = fit_difficulty(load_logs(LOG_DIR), codes)
    curves = compare_policies(codes, sim, similar, difficulty.to_dict())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    import json
    summary = {k: {kk: v[kk] for kk in ("mean_success", "start_knowledge", "final_knowledge")}
               for k, v in curves.items()}
    (OUTPUT_DIR / "policy_simulation.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
