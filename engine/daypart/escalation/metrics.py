"""Track B — calibration and decision metrics (Brier, 10-bin ECE, reliability, precision/recall)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

N_BINS = 10


def _r6(x: float) -> float:
    return round(float(x), 6)


def _check(p: Sequence[float], y: Sequence[bool]) -> None:
    if len(p) != len(y):
        raise ValueError("p and y must have the same length")
    if any(not (0.0 <= float(v) <= 1.0) for v in p):
        raise ValueError("probabilities must be within [0, 1]")


def brier(p: Sequence[float], y: Sequence[bool]) -> float | None:
    """Mean squared error of ``p`` against the 0/1 outcomes (``None`` when empty)."""
    _check(p, y)
    if not p:
        return None
    return sum((float(pi) - (1.0 if yi else 0.0)) ** 2 for pi, yi in zip(p, y)) / len(p)


def _bin(p: float, n_bins: int) -> int:
    return min(int(float(p) * n_bins), n_bins - 1)  # equal-width; p == 1.0 falls in the top bin


def reliability(p: Sequence[float], y: Sequence[bool], n_bins: int = N_BINS) -> list[dict[str, Any]]:
    """One row per equal-width bin: bounds, count, mean prediction and observed positive rate."""
    _check(p, y)
    rows = []
    for b in range(n_bins):
        idx = [i for i, pi in enumerate(p) if _bin(pi, n_bins) == b]
        n = len(idx)
        rows.append(
            {
                "bin": b,
                "lo": _r6(b / n_bins),
                "hi": _r6((b + 1) / n_bins),
                "n": n,
                "mean_p": _r6(sum(float(p[i]) for i in idx) / n) if n else None,
                "frac_positive": _r6(sum(1 for i in idx if y[i]) / n) if n else None,
            }
        )
    return rows


def ece(p: Sequence[float], y: Sequence[bool], n_bins: int = N_BINS) -> float | None:
    """Expected calibration error over ``n_bins`` equal-width bins (``None`` when empty)."""
    _check(p, y)
    if not p:
        return None
    total = 0.0
    for b in range(n_bins):
        idx = [i for i, pi in enumerate(p) if _bin(pi, n_bins) == b]
        if idx:
            conf = sum(float(p[i]) for i in idx) / len(idx)
            acc = sum(1 for i in idx if y[i]) / len(idx)
            total += len(idx) * abs(conf - acc)
    return total / len(p)


def decision_metrics(decisions: Sequence[str], y: Sequence[bool]) -> dict[str, Any]:
    """Abstention rate and precision/recall of ``escalate`` (abstain counts as not escalated).

    ``precision`` is ``None`` when nothing was escalated, ``recall`` when there are no positives.
    """
    if len(decisions) != len(y):
        raise ValueError("decisions and y must have the same length")
    n = len(decisions)
    esc = [d == "escalate" for d in decisions]
    tp = sum(1 for e, t in zip(esc, y) if e and t)
    n_esc = sum(esc)
    pos = sum(1 for t in y if t)
    return {
        "n": n,
        "n_escalate": n_esc,
        "n_no_escalation": sum(1 for d in decisions if d == "no_escalation"),
        "n_abstain": sum(1 for d in decisions if d == "abstain"),
        "abstention_rate": _r6(sum(1 for d in decisions if d == "abstain") / n) if n else None,
        "true_positives": tp,
        "precision": _r6(tp / n_esc) if n_esc else None,
        "recall": _r6(tp / pos) if pos else None,
    }


__all__ = ["N_BINS", "brier", "decision_metrics", "ece", "reliability"]
