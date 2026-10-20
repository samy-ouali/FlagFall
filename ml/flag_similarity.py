"""Compute how visually similar the flags are, with a pre-trained CLIP model.

Each flag image is turned into a 512-dimensional vector (an "embedding") by the
image encoder of CLIP. Flags that look alike get vectors that point in similar
directions, so the cosine similarity between two vectors measures how easy the
two flags are to confuse.

Outputs:
    ml/output/flag_similarity.csv     full similarity matrix (codes x codes)
    docs/figures/flag_map.png         2-D map of the flags (t-SNE of the embeddings)
    docs/figures/similar_pairs.png    the most similar pairs of flags

Usage (from the repository root):
    python ml/flag_similarity.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from common import FLAGS_DIR, FIG_DIR, OUTPUT_DIR, load_countries
import plots

MODEL_NAME = "openai/clip-vit-base-patch32"


def load_flag(path: Path, size: int = 224) -> Image.Image:
    """Open a flag and pad it to a square, so CLIP's square crop keeps the whole flag."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((size, size))
    canvas = Image.new("RGB", (size, size), (128, 128, 128))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return canvas


@torch.no_grad()
def embed_flags(codes):
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    model = CLIPModel.from_pretrained(MODEL_NAME).eval()
    images = [load_flag(FLAGS_DIR / f"{c}.png") for c in codes]
    inputs = processor(images=images, return_tensors="pt")
    features = model.get_image_features(**inputs)
    if not torch.is_tensor(features):  # newer transformers versions return an output object
        features = features.pooler_output
    features = features / features.norm(dim=-1, keepdim=True)  # unit length
    return features.numpy()


def main():
    countries = load_countries()
    codes = list(countries["code"])
    print(f"Embedding {len(codes)} flags with {MODEL_NAME} ...")
    emb = embed_flags(codes)

    # Cosine similarity = dot product of unit vectors.
    sim = emb @ emb.T
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(sim, index=codes, columns=codes).to_csv(OUTPUT_DIR / "flag_similarity.csv")
    np.save(OUTPUT_DIR / "flag_embeddings.npy", emb)

    names = dict(zip(countries["code"], countries["name_en"]))
    pairs = [(sim[i, j], codes[i], codes[j])
             for i in range(len(codes)) for j in range(i + 1, len(codes))]
    pairs.sort(reverse=True)
    print("Most similar pairs:")
    for s, a, b in pairs[:12]:
        print(f"  {names[a]:<15} {names[b]:<15} {s:.3f}")

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plots.plot_flag_map(emb, codes)
    plots.plot_similar_pairs(pairs[:12], names)
    print(f"Saved similarity matrix to {OUTPUT_DIR} and figures to {FIG_DIR}")


if __name__ == "__main__":
    main()
