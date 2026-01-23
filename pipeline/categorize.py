"""
Categorization via rules first, then optional ML (TF-IDF + LogisticRegression).
"""
from __future__ import annotations
import os, pickle, yaml
import pandas as pd
from typing import Optional, List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "category_model.pkl")
RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "category_rules.yml")

def load_rules() -> dict:
    if os.path.exists(RULES_PATH):
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            y = yaml.safe_load(f)
        return y.get("rules", {})
    return {}

def rule_based_category(text: str, rules: dict) -> Optional[str]:
    t = (text or "").lower()
    for cat, patterns in rules.items():
        for pat in patterns:
            if pat.lower() in t:
                return cat
    return None

def _load_model():
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            obj = pickle.load(f)
        return obj
    return None

def categorize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply rules, then ML model if available. Adds 'category' column.
    """
    out = df.copy()
    rules = load_rules()
    model_bundle = _load_model()

    categories: List[Optional[str]] = []
    if "description" not in out.columns:
        out["description"] = ""

    for desc in out["description"].astype(str):
        cat = rule_based_category(desc, rules)
        if cat is None and model_bundle is not None:
            vectorizer = model_bundle["vectorizer"]
            clf = model_bundle["clf"]
            X = vectorizer.transform([desc])
            cat = clf.predict(X)[0]
        categories.append(cat if cat is not None else "Uncategorized")

    out["category"] = categories
    return out

def train_classifier(labeled_csv: str, model_out: str = MODEL_PATH):
    """
    Train a simple TF-IDF + LogisticRegression classifier.
    labeled_csv must have columns: description, category
    """
    df = pd.read_csv(labeled_csv)
    df = df.dropna(subset=["description", "category"])
    df["description"] = df["description"].astype(str)

    vectorizer = TfidfVectorizer(ngram_range=(1,2), min_df=2, max_features=20000)
    X = vectorizer.fit_transform(df["description"])
    y = df["category"].astype(str)

    clf = LogisticRegression(max_iter=200, n_jobs=None)
    clf.fit(X, y)

    bundle = {"vectorizer": vectorizer, "clf": clf, "labels": sorted(y.unique().tolist())}
    os.makedirs(os.path.dirname(model_out), exist_ok=True)
    with open(model_out, "wb") as f:
        pickle.dump(bundle, f)
    return model_out