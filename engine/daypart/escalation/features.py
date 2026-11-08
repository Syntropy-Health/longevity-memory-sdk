"""Track B — deterministic features from observables only (``track-b-spec`` interface).

``crisis_marker_hits`` counts check-in texts that hold a ``boundary-v1`` crisis marker or member
crisis language (:func:`daypart.checkin.crisis.is_crisis`, which matches the pack's
``crisis_markers`` through :mod:`daypart.membrane.dsl` normalisation). It drives the hard gate and
is not a model input; the simulator's histories carry no text, so a model could not learn it.
"""

from __future__ import annotations

from typing import Any

from daypart.escalation.history import as_history

#: Every feature :func:`features` returns, in order.
FEATURE_NAMES: tuple[str, ...] = (
    "days_observed",
    "adherence_rate",
    "recent_adherence_rate",
    "missed_days",
    "longest_miss_streak",
    "days_since_last_adherence",
    "lapsed_entries",
    "lapsed_fraction",
    "checkin_rate",
    "mean_sentiment",
    "min_sentiment",
    "crisis_marker_hits",
)

#: The hard-gate feature: any hit escalates whatever the model says.
CRISIS_FEATURE = "crisis_marker_hits"

#: The features the calibrator is fitted on (all but the hard-gate count).
MODEL_FEATURES: tuple[str, ...] = tuple(f for f in FEATURE_NAMES if f != CRISIS_FEATURE)

RECENT_DAYS = 7


def _crisis_hits(texts: tuple[str, ...]) -> int:
    if not texts:
        return 0
    from daypart.checkin.crisis import is_crisis  # lazy: checkin imports daypart.eval

    return sum(1 for t in texts if is_crisis(t))


def features(history: Any) -> dict[str, float]:
    """Deterministic ``FEATURE_NAMES`` -> float for ``history`` (observables only; see ``as_history``)."""
    h = as_history(history)
    days = h.days
    n = len(days)
    adhered = [d.adhered for d in days]
    missed = n - sum(adhered)

    longest = run = 0
    for a in adhered:
        run = 0 if a else run + 1
        longest = max(longest, run)
    last = max((i for i, a in enumerate(adhered) if a), default=None)
    since_last = float(n if last is None else n - 1 - last)

    states = [d.state for d in days]
    entries = sum(1 for i, s in enumerate(states) if s == "lapsed" and (i == 0 or states[i - 1] != "lapsed"))
    lapsed = sum(1 for s in states if s == "lapsed")

    recent = adhered[-RECENT_DAYS:]
    sentiments = [d.sentiment for d in days if d.sentiment is not None]
    checkins = sum(1 for d in days if d.checkin)

    out = {
        "days_observed": float(n),
        "adherence_rate": (n - missed) / n if n else 0.0,
        "recent_adherence_rate": sum(recent) / len(recent) if recent else 0.0,
        "missed_days": float(missed),
        "longest_miss_streak": float(longest),
        "days_since_last_adherence": since_last,
        "lapsed_entries": float(entries),
        "lapsed_fraction": lapsed / n if n else 0.0,
        "checkin_rate": checkins / n if n else 0.0,
        "mean_sentiment": sum(sentiments) / len(sentiments) if sentiments else 0.0,
        "min_sentiment": min(sentiments) if sentiments else 0.0,
        "crisis_marker_hits": float(_crisis_hits(h.all_texts())),
    }
    return {k: float(out[k]) for k in FEATURE_NAMES}


__all__ = ["CRISIS_FEATURE", "FEATURE_NAMES", "MODEL_FEATURES", "RECENT_DAYS", "features"]
