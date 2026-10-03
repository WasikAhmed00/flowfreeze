"""Validation-fitted one-vs-rest Platt calibration for multiclass scores."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression


def _logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(clipped / (1 - clipped))


def fit_multiclass_calibrators(
    raw_probabilities: Any,
    y_true: Any,
    classes: list[str],
    *,
    seed: int = 42,
) -> dict[str, LogisticRegression]:
    raw = np.asarray(raw_probabilities, dtype=float)
    labels = np.asarray(y_true, dtype=str)
    if raw.ndim != 2 or raw.shape[1] != len(classes) or raw.shape[0] != len(labels):
        raise ValueError("Calibration scores, labels, and classes have inconsistent shapes.")
    calibrators: dict[str, LogisticRegression] = {}
    logits = _logit(raw)
    for index, label in enumerate(classes):
        binary = (labels == label).astype(int)
        if len(np.unique(binary)) != 2:
            raise ValueError(f"Validation split must contain both outcomes for class {label!r}.")
        calibrator = LogisticRegression(C=1e6, max_iter=1000, random_state=seed, solver="lbfgs")
        calibrator.fit(logits[:, [index]], binary)
        calibrators[label] = calibrator
    return calibrators


def apply_multiclass_calibrators(
    raw_probabilities: Any,
    classes: list[str],
    calibrators: dict[str, Any],
    *,
    raw_blend: float = 0.5,
) -> np.ndarray:
    raw = np.asarray(raw_probabilities, dtype=float)
    if raw.ndim != 2 or raw.shape[1] != len(classes):
        raise ValueError("Prediction score columns do not match calibration classes.")
    if not 0 <= raw_blend <= 1:
        raise ValueError("raw_blend must be between 0 and 1.")
    logits = _logit(raw)
    corrected = np.column_stack([
        calibrators[label].predict_proba(logits[:, [index]])[:, 1]
        for index, label in enumerate(classes)
    ])
    totals = corrected.sum(axis=1, keepdims=True)
    calibrated = np.divide(corrected, totals, out=np.full_like(corrected, 1 / len(classes)), where=totals > 0)
    blended = raw_blend * raw + (1 - raw_blend) * calibrated
    blend_totals = blended.sum(axis=1, keepdims=True)
    return np.divide(blended, blend_totals, out=np.full_like(blended, 1 / len(classes)), where=blend_totals > 0)
