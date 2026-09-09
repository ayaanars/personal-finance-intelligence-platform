"""Request-local Isolation Forest support. No scores leave this adapter."""

from collections import Counter
from decimal import Decimal
from statistics import median
from typing import Literal

from ledgerx.modules.analytics.intelligence import Observation

MLState = Literal["active", "insufficient_history", "unavailable", "no_activity"]


def ml_support(
    history: list[Observation], current: list[Observation], months: int
) -> tuple[MLState, set[str]]:
    if months < 3 or len(history) < 100:
        return "insufficient_history", set()
    if not current:
        return "no_activity", set()
    if len({r.currency for r in history + current}) != 1:
        raise ValueError("ML requires a single currency")
    # Stable bounded training sample, no shared fitted state or current-month training.
    history = sorted(history, key=lambda r: (r.day, r.identifier))[-2000:]
    typical = median([-r.amount for r in history])
    counts = Counter(r.day for r in history + current)

    def features(rows: list[Observation]) -> list[list[float]]:
        # Only dimensionless ratios become floats; financial calculations stay Decimal.
        return [
            [
                float(min(-r.amount / typical, Decimal(1000))),
                float(r.day.day) / 31,
                float(r.day.weekday() >= 5),
                float(min(counts[r.day], 1000)),
            ]
            for r in rows
        ]

    try:
        from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]

        model = IsolationForest(
            n_estimators=64,
            max_samples=min(256, len(history)),
            contamination="auto",
            random_state=14,
            n_jobs=1,
        )
        model.fit(features(history))
        predictions = model.predict(features(current))
    except (ImportError, OSError, ValueError, RuntimeError):
        return "unavailable", set()
    return "active", {
        r.identifier for r, label in zip(current, predictions, strict=True) if label == -1
    }
