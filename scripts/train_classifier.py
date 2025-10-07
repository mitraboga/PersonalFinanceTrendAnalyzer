"""
Train the NLP category classifier from a labeled CSV (columns: description, category).

Usage:
  python scripts/train_classifier.py --input data/labeled_samples.csv
  # Optional custom output path:
  python scripts/train_classifier.py --input data/labeled_samples.csv --out models/my_category_model.pkl
"""
from __future__ import annotations
import argparse
from pipeline.categorize import train_classifier


def main():
    ap = argparse.ArgumentParser(description="Train TF-IDF + LogisticRegression category classifier")
    ap.add_argument("--input", required=True, help="CSV with columns: description,category")
    ap.add_argument("--out", default=None, help="Optional model output path (.pkl). Defaults to models/category_model.pkl")
    args = ap.parse_args()

    out = train_classifier(args.input, model_out=args.out) if args.out else train_classifier(args.input)
    print(f"[OK] Saved model to: {out}")


if __name__ == "__main__":
    main()