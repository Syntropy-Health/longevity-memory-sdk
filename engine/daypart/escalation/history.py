"""Track B — the observable history the escalation estimator sees (AIR-319 ``track-b-spec``).

The estimator never reads latents. Everything it sees goes through :func:`as_history`, which keeps
only observables (per-day state, adherence, check-in flag, sentiment, and any check-in text) and
refuses objects that carry latents (a ``Profile``, ``Latents`` or a whole ``Cohort``).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

#: Keys under which per-day or per-history check-in text may arrive.
_DAY_TEXT_KEYS = ("text", "journal", "checkin_text", "note_text")
_HISTORY_TEXT_KEYS = ("texts", "checkin_texts", "journals", "text")
_LATENT_TYPES = ("Profile", "Latents", "Cohort")


@dataclass(frozen=True)
class Day:
    """One observed day. ``state`` may be unknown (``None``) for a history built from text only."""

    adhered: bool
    checkin: bool = False
    state: str | None = None
    sentiment: float | None = None
    text: str | None = None


@dataclass(frozen=True)
class History:
    """A member's observables up to day *t*: the days so far plus free check-in texts."""

    days: tuple[Day, ...] = ()
    texts: tuple[str, ...] = ()

    def all_texts(self) -> tuple[str, ...]:
        return tuple(d.text for d in self.days if d.text) + tuple(t for t in self.texts if t)


def _refuse_latents(obj: Any) -> None:
    if type(obj).__name__ in _LATENT_TYPES or (isinstance(obj, Mapping) and "latents" in obj):
        raise TypeError(
            f"escalation sees observables only; got {type(obj).__name__} (latents are hidden, track-b-spec)"
        )


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_day(obj: Any) -> Day:
    if isinstance(obj, Day):
        return obj
    _refuse_latents(obj)
    adhered = _get(obj, "adhered")
    if adhered is None:
        raise ValueError(f"a history day needs 'adhered'; got {type(obj).__name__}")
    sentiment = _get(obj, "sentiment")
    if sentiment is not None:
        sentiment = float(sentiment)
        if not math.isfinite(sentiment):  # NaN would otherwise clamp to p = 0 ("stay silent")
            raise ValueError(f"sentiment must be finite, got {sentiment!r}")
    parts = [t for k in _DAY_TEXT_KEYS for t in _as_texts(_get(obj, k)) if t.strip()]
    text = "\n".join(parts) if parts else None  # every text field reaches the crisis gate
    state = _get(obj, "state")
    return Day(
        adhered=bool(adhered),
        checkin=bool(_get(obj, "checkin", False)) or text is not None,
        state=str(state) if state is not None else None,
        sentiment=sentiment,
        text=text,
    )


def _as_texts(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, Iterable):
        return tuple(t for item in raw for t in _as_texts(item))
    return (str(raw),)


def as_history(history: Any, texts: Iterable[str] | str | None = None) -> History:
    """Normalise ``history`` into a :class:`History` of observables.

    Accepts a :class:`History`, a ``Trajectory``, a sequence of ``DayRecord`` / day mappings /
    :class:`Day`, a mapping ``{"days": ..., "texts": ...}``, a ``(days, texts)`` pair, or a bare
    check-in string. ``texts`` adds free check-in text. Objects carrying latents raise ``TypeError``.
    """
    extra = _as_texts(texts)
    if isinstance(history, History):
        return History(history.days, history.texts + extra) if extra else history
    if history is None:
        return History((), extra)
    _refuse_latents(history)
    if isinstance(history, str):
        return History((), (history,) + extra)
    if isinstance(history, Mapping):
        if "days" not in history and "adhered" in history:
            return History((_as_day(history),), extra)
        raw_texts = tuple(t for k in _HISTORY_TEXT_KEYS for t in _as_texts(history.get(k)))
        base = as_history(history.get("days", ()))
        return History(base.days, base.texts + raw_texts + extra)
    days_attr = getattr(history, "days", None)
    if days_attr is not None and not isinstance(history, (list, tuple)):  # a Trajectory-like object
        attr_texts = tuple(t for k in _HISTORY_TEXT_KEYS for t in _as_texts(getattr(history, k, None)))
        return History(tuple(_as_day(d) for d in days_attr), attr_texts + extra)
    if isinstance(history, Sequence) and history and all(isinstance(t, str) for t in history):
        return History((), tuple(history) + extra)  # a list of check-in texts
    if isinstance(history, Sequence) and len(history) == 2 and _is_text_part(history[1]) and not _is_day(history[0]):
        base = as_history(history[0])
        return History(base.days, base.texts + _as_texts(history[1]) + extra)
    if isinstance(history, Iterable):
        return History(tuple(_as_day(d) for d in history), extra)
    raise TypeError(f"cannot read an escalation history from {type(history).__name__}")


def _is_day(obj: Any) -> bool:
    return isinstance(obj, Day) or _get(obj, "adhered") is not None


def _is_text_part(obj: Any) -> bool:
    if obj is None or isinstance(obj, str):
        return True
    return isinstance(obj, (list, tuple)) and all(isinstance(t, str) for t in obj)


def until(history: Any, t: int) -> History:
    """The history up to and including day ``t`` (the first ``t + 1`` days); free texts are kept."""
    if t < 0:
        raise ValueError("t must be >= 0")
    h = as_history(history)
    return History(h.days[: t + 1], h.texts)


def history_from(trajectory: Any, day: int, texts: Iterable[str] | str = ()) -> History:
    """The observables of ``trajectory`` for days ``0..day`` inclusive, plus check-in ``texts``
    (track-b-spec v1.1). The trajectory's latents are never seen: only its day records are read."""
    return until(as_history(trajectory, texts), day)


__all__ = ["Day", "History", "as_history", "history_from", "until"]
