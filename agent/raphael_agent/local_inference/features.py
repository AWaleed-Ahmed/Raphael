"""Inference-only text and numeric feature transformations."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix, hstack


def stable_text(record: dict[str, Any], fields: Sequence[str]) -> str:
    """Convert selected structured fields into stable, auditable text tokens."""
    parts: list[str] = []
    for field in fields:
        value = record.get(field)
        if value is None:
            rendered = "__missing__"
        elif isinstance(value, list):
            rendered = " ".join(str(item) for item in value)
        elif isinstance(value, dict):
            rendered = " ".join(f"{key}:{value[key]}" for key in sorted(value))
        else:
            rendered = str(value)
        parts.append(f"{field}={rendered}")
    return " | ".join(parts)


def as_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def numeric_matrix(
    rows: Sequence[dict[str, Any]],
    fields: Sequence[str],
    means: Sequence[float],
    scales: Sequence[float],
) -> csr_matrix:
    raw = np.asarray(
        [[as_number(row.get(field)) for field in fields] for row in rows],
        dtype=np.float32,
    )
    if not fields:
        return csr_matrix((len(rows), 0), dtype=np.float32)
    normalized = (raw - np.asarray(means, dtype=np.float32)) / np.asarray(
        scales, dtype=np.float32
    )
    return csr_matrix(normalized, dtype=np.float32)


def feature_matrix(
    *,
    rows: Sequence[dict[str, Any]],
    text_fields: Sequence[str],
    numeric_fields: Sequence[str],
    vectorizer: Any,
    means: Sequence[float],
    scales: Sequence[float],
) -> csr_matrix:
    texts = [stable_text(row, text_fields) for row in rows]
    text_features = vectorizer.transform(texts)
    numbers = numeric_matrix(rows, numeric_fields, means, scales)
    return hstack((text_features, numbers), format="csr", dtype=np.float32)
