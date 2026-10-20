"""Download the flags listed in countries.csv into Assets/Flags/.

Flags come from flagcdn.com (public-domain flag images, 2560 px wide, the same
source and size as the original 15 flags of the game). Existing files are kept.

Usage (from the repository root):
    python ml/download_flags.py
"""

import csv
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLAGS_DIR = ROOT / "Assets" / "Flags"
COUNTRIES_CSV = Path(__file__).resolve().parent / "countries.csv"
URL = "https://flagcdn.com/w2560/{code}.png"


def load_codes():
    with open(COUNTRIES_CSV, encoding="utf-8") as f:
        return [row["code"] for row in csv.DictReader(f)]


def main():
    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    for code in load_codes():
        path = FLAGS_DIR / f"{code}.png"
        if path.exists():
            continue
        print(f"Downloading {code}.png")
        urllib.request.urlretrieve(URL.format(code=code), path)
    print(f"{len(list(FLAGS_DIR.glob('*.png')))} flags in {FLAGS_DIR}")


if __name__ == "__main__":
    main()
