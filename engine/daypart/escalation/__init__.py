"""escalation — Track B calibrated escalation, a standalone fallback (AIR-319 ``track-b-spec``).

For one synthetic member at day *t*: how likely is a clinician hand-off, and should the engine
escalate, stay silent or abstain? The estimator sees observables only; ground truth is the
simulator's hidden ``escalation_trigger`` and is not clinically validated.
"""

from daypart.escalation.features import CRISIS_FEATURE, FEATURE_NAMES, MODEL_FEATURES, features
from daypart.escalation.history import Day, History, as_history, until
from daypart.escalation.model import (
    CALIBRATOR_KIND,
    DECISION_RULE_VERSION,
    TAU_HIGH,
    TAU_LOW,
    TRAIN_HISTORY_DAYS,
    Assessment,
    Calibrator,
    CuratedMemberError,
    assess,
    decide,
    fit,
    training_rows,
)

__all__ = [
    "CALIBRATOR_KIND",
    "CRISIS_FEATURE",
    "DECISION_RULE_VERSION",
    "FEATURE_NAMES",
    "MODEL_FEATURES",
    "TAU_HIGH",
    "TAU_LOW",
    "TRAIN_HISTORY_DAYS",
    "Assessment",
    "Calibrator",
    "CuratedMemberError",
    "Day",
    "History",
    "as_history",
    "assess",
    "decide",
    "features",
    "fit",
    "training_rows",
    "until",
]
