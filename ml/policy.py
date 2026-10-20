"""Python version of the game's adaptive director (Assets/Scripts/AdaptiveDirector.cs).

It is used by the simulation to compare the adaptive game with the original
random one. The logic is kept identical to the C# version:

- Each player has a skill rating (theta) and each flag a difficulty rating (b).
  The predicted probability of catching the right flag is sigmoid(theta - b + u),
  where u is the player's personal adjustment for that flag. All three are
  updated after every catch, Elo-style.
- Target: the flag whose predicted success is closest to 70 %, with some
  randomness, plus a bonus for flags the player recently got wrong.
- Wrong flags (distractors): when the player does well, they are more often
  chosen among the flags that look like the target (CLIP similarity).
"""

import math
import random

TARGET_SUCCESS = 0.7
K_PLAYER = 0.15
K_ITEM = 0.05
K_PERSONAL = 0.4
TEMPERATURE = 0.08
REVIEW_BONUS = 0.15


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


class AdaptiveDirector:
    def __init__(self, codes, similar, difficulty=None, rng=None):
        self.codes = list(codes)
        self.similar = similar                      # code -> list of similar codes
        self.b = {c: (difficulty or {}).get(c, 0.0) for c in self.codes}
        self.theta = 0.0
        self.u = {c: 0.0 for c in self.codes}
        self.review = {}                            # code -> rounds left in review
        self.recent = []                            # last results (1 / 0)
        self.last_target = None
        self.rng = rng or random.Random()

    def predict(self, code):
        return sigmoid(self.theta - self.b[code] + self.u[code])

    def pick_target(self):
        scores = []
        for c in self.codes:
            if c == self.last_target:
                continue
            s = -abs(self.predict(c) - TARGET_SUCCESS)
            if c in self.review:
                s += REVIEW_BONUS
            scores.append((s, c))
        m = max(s for s, _ in scores)
        weights = [math.exp((s - m) / TEMPERATURE) for s, _ in scores]
        target = self.rng.choices([c for _, c in scores], weights)[0]
        self.last_target = target
        return target

    def similar_chance(self):
        """Probability that a wrong flag is a look-alike of the target (0.1 to 0.8)."""
        if not self.recent:
            return 0.2
        rate = sum(self.recent) / len(self.recent)
        return min(0.8, max(0.1, 0.2 + (rate - TARGET_SUCCESS) * 2.0))

    def pick_distractor(self, target):
        sims = [c for c in self.similar.get(target, []) if c != target]
        if sims and self.rng.random() < self.similar_chance():
            return self.rng.choice(sims)
        return self.rng.choice([c for c in self.codes if c != target])

    def record(self, target, correct):
        y = 1.0 if correct else 0.0
        err = y - self.predict(target)
        self.theta += K_PLAYER * err
        self.b[target] -= K_ITEM * err
        self.u[target] += K_PERSONAL * err
        self.recent = (self.recent + [y])[-10:]
        for c in list(self.review):
            self.review[c] -= 1
            if self.review[c] <= 0:
                del self.review[c]
        if not correct:
            self.review[target] = 8    # bring it back within the next rounds


class RandomDirector:
    """The original game: random target, random wrong flags."""

    def __init__(self, codes, rng=None):
        self.codes = list(codes)
        self.last_target = None
        self.rng = rng or random.Random()

    def pick_target(self):
        target = self.rng.choice([c for c in self.codes if c != self.last_target])
        self.last_target = target
        return target

    def pick_distractor(self, target):
        return self.rng.choice([c for c in self.codes if c != target])

    def record(self, target, correct):
        pass
