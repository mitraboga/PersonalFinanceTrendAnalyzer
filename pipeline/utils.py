"""
Utility helpers for the Personal Finance Trend Analyzer.
"""
from __future__ import annotations
import re
from typing import Dict, Iterable

def normalize_colname(name: str) -> str:
    """
    Lowercase, strip, and remove non-alphanumerics to standardize column names.
    """
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s

def first_present(mapping: Dict[str, str], candidates: Iterable[str]) -> str | None:
    """
    Return the first key in `mapping` that exists in `candidates`.
    """
    for c in candidates:
        if c in mapping:
            return c
    return None