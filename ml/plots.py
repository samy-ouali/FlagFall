"""Figures for the README (saved in docs/figures)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from PIL import Image
from sklearn.manifold import TSNE

from common import FIG_DIR, FLAGS_DIR

BLUE = "#2a78d6"
ORANGE = "#eb6834"
GREY = "#8a8985"
TEXT = "#0b0b0b"
MUTED = "#52514e"
SURFACE = "#fcfcfb"
GRID = "#ecebe8"


def _style(ax, title, xlabel=None, ylabel=None, grid=True):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=12, color=TEXT, pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, color=MUTED)
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d6d5d0")
    ax.tick_params(colors=MUTED)
    if grid:
        ax.grid(color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)


def _save(fig, name):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, dpi=150)
    plt.close(fig)


def _thumb(code, height=28):
    img = Image.open(FLAGS_DIR / f"{code}.png").convert("RGBA")
    img.thumbnail((height * 3, height))
    return np.asarray(img)


def plot_flag_map(emb, codes):
    """Each flag placed on a 2-D map: flags that CLIP finds similar end up close together."""
    xy = TSNE(n_components=2, perplexity=8, init="pca", random_state=0).fit_transform(emb)
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(xy[:, 0], xy[:, 1], s=0)
    for (x, y), code in zip(xy, codes):
        box = AnnotationBbox(OffsetImage(_thumb(code), zoom=0.8), (x, y), frameon=True,
                             pad=0.1, bboxprops={"edgecolor": "#d6d5d0", "linewidth": 0.5})
        ax.add_artist(box)
    _style(ax, "Flag map: similar-looking flags are close together (CLIP embeddings, t-SNE)",
           grid=False)
    ax.set_xticks([])
    ax.set_yticks([])
    _save(fig, "flag_map.png")


def plot_similar_pairs(pairs, names):
    """The most similar pairs of flags, side by side with their similarity score."""
    n = len(pairs)
    cols = 3
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(10, 1.6 * rows))
    fig.set_facecolor(SURFACE)
    for ax in axes.ravel():
        ax.axis("off")
    for ax, (s, a, b) in zip(axes.ravel(), pairs):
        pair = np.full((60, 260, 4), 255, dtype=np.uint8)
        pair[..., 3] = 0
        for k, code in enumerate((a, b)):
            t = _thumb(code, 56)
            x0 = 8 + k * 132
            pair[2:2 + t.shape[0], x0:x0 + t.shape[1]] = t
        ax.imshow(pair)
        ax.set_title(f"{names[a]} / {names[b]}  ({s:.2f})", fontsize=9, color=TEXT)
    fig.suptitle("Most similar flag pairs according to CLIP (cosine similarity)",
                 x=0.01, ha="left", fontsize=12, color=TEXT)
    _save(fig, "similar_pairs.png")


def plot_model_comparison(results, suffix=""):
    """Log-loss of each model on the held-out events (lower is better)."""
    names = list(results.keys())
    vals = [results[n]["log_loss"] for n in names]
    fig, ax = plt.subplots(figsize=(6.5, 3))
    y = np.arange(len(names))
    ax.barh(y, vals, color=BLUE, height=0.5)
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    for yi, v in zip(y, vals):
        ax.text(v + 0.005, yi, f"{v:.3f}", va="center", color=TEXT)
    ax.set_xlim(0, max(vals) * 1.2)
    _style(ax, "Predicting whether the player catches the right flag\n"
               "(log-loss on the last 30% of events, lower is better)", "Log-loss")
    ax.grid(axis="y", visible=False)
    _save(fig, f"model_comparison{suffix}.png")


def plot_difficulty(ratings, names, n=12, suffix=""):
    """Easiest and hardest flags according to the fitted difficulty (Elo-style rating)."""
    s = ratings.sort_values()
    sel = list(s.index[:n]) + list(s.index[-n:])
    vals = s[sel].values
    fig, ax = plt.subplots(figsize=(7, 7))
    y = np.arange(len(sel))
    colors = [BLUE if v < 0 else ORANGE for v in vals]
    ax.barh(y, vals, color=colors, height=0.6)
    ax.set_yticks(y, [names[c] for c in sel])
    ax.invert_yaxis()
    ax.axvline(0, color=MUTED, linewidth=0.8)
    _style(ax, f"Flag difficulty learned from the data\n({n} easiest in blue, {n} hardest in orange)",
           "Difficulty (logit scale, higher = harder)")
    ax.grid(axis="y", visible=False)
    _save(fig, f"flag_difficulty{suffix}.png")


def plot_policy_comparison(curves):
    """Simulated players: success rate and knowledge over time, random vs adaptive game."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    colors = {"Random (original game)": GREY, "Adaptive (ML)": BLUE}
    for name, c in curves.items():
        axes[0].plot(c["round"], c["success_rate"], color=colors[name], linewidth=2, label=name)
        axes[1].plot(c["round"], c["knowledge"], color=colors[name], linewidth=2, label=name)
    axes[0].axhline(0.7, color=ORANGE, linewidth=1, linestyle="--")
    axes[0].text(axes[0].get_xlim()[1], 0.71, "target 70%", color=ORANGE, ha="right", va="bottom")
    _style(axes[0], "Success rate (rolling, simulated players)", "Round", "Share of correct catches")
    _style(axes[1], "Flags the player knows (simulated)", "Round", "Mean P(recognise) over all 60 flags")
    axes[0].set_ylim(0, 1)
    axes[1].set_ylim(0, 1)
    axes[1].legend(frameon=False, labelcolor=TEXT, loc="lower right")
    _save(fig, "policy_simulation.png")
