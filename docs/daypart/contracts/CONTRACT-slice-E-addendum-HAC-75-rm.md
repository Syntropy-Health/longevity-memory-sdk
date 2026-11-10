# CONTRACT slice E addendum: question library, reward model, GRPO, inclinations (HAC-75)

Plan tasks 4.1 (Jev question library), 4.2 (reward model), 4.3 (GRPO). Board direction on HAC-74:
"Incorporate jev and GRPO by implementing a reward model that may provide interpretability on the
passport on inclinations." This file is the only surface shared between the test-author and the
implementer for this change. It **amends** slice E: E1.1's default `runs.yaml` table rows `grpo`,
`rm` and `jev` are no longer `not_run`, and G3 of slice G ("`grpo`, `rm`, `jev` stay `not_run`")
is superseded.

Python ≥3.12, numpy only (no new dependency), no network, no wall clock, every rng seeded.
Synthetic only (I1): nothing here may read a curated (`cur-`) profile.

## H1. Eval arms (amends E1.1 / E1.3)

- `ARM_KINDS` is unchanged. `EXTENSION_ARM_KINDS == {"escalation", "jev_library", "reward_model", "grpo_policy"}`.
- `ArmConfig` kind `grpo_policy` requires `n_scenarios >= 1`, non-empty unique `seeds`, `horizon >= 1`
  (else `ValidationError`). `jev_library` and `reward_model` need no extra fields.
- Default `runs.yaml`: arm names and order unchanged. `grpo` → `kind: grpo_policy`, `n_scenarios: 50`,
  `seeds: [0, 1, 2]`, `horizon: 14`; `rm` → `kind: reward_model`; `jev` → `kind: jev_library`.
  With the committed results, `run(load_runs(), root=engine)` reports every arm `ok`
  (`summary == {"ok": 12, "not_run": 0, "failed": 0}`).
- Every metrics dict of these three arms has `"data": "synthetic"` and a `"label"` containing
  `"not clinical evidence"`. Determinism (E1.3) holds: `dumps(run(cfg))` twice is byte-identical.
- `jev` metrics: `n_questions` (int ≥ 5), `question_ids` (list of str), `n_features` (int),
  `heldout_recovery` = `{"n_members", "axis_accuracy": {axis: float}, "chance_accuracy": {axis: float},
  "mood_mean_abs_error"}` with one key per categorical latents axis except `age_band`.
- `rm` metrics: `heldout` = `{"n_members", "n_rows", "log_loss", "brier", "auc", "base_rate_log_loss",
  "status_only_log_loss", "status_only_auc"}`; `attribution_recovery` = `{"lift_spearman",
  "lift_pearson", "top_message_agreement", "top_message_chance"}`; `train` = `{"n_members", "n_rows"}`.
  Held-out `auc` in (0.5, 1]; `log_loss < base_rate_log_loss`; `top_message_agreement > top_message_chance`.
- `grpo` metrics: the `env_baseline` shape (`policy`, `horizon`, `n_scenarios`, `per_seed[]` with the
  same keys and the **same `scenario_manifest_sha256` per seed as the `env_baseline` arms**,
  `mean_adherence`, `episode_violation_rate`, `seeds`), plus `heldout_members`, `message_mix`
  (one key per intent, values sum to 1 ± 1e-5) and `training`. `episode_violation_rate == 0.0`.
- I1: `daypart.ci.i1_check.BUILDERS` gains `"rm.train_members"`; `python -m daypart.ci.i1_check`
  prints `I1 ok   rm.train_members`.

## H2. `daypart.rm` public surface

```python
# daypart.rm.jev
LIBRARY_VERSION = "jev-v1"
QUESTIONS: tuple[Question, ...]          # every categorical question's options cover exactly its axis levels
QUESTION_IDS: tuple[str, ...]
FEATURE_NAMES: tuple[str, ...]           # "<group>.<level>" ..., then "mood"
def simulate_answers(latents, member_id: str, seed: int = 0) -> dict[str, str]   # deterministic
def answers_for(profile, seed: int = 0) -> dict[str, str]
def validate_answers(answers) -> None    # ValueError: unanswered / unknown question / unknown option
def features(answers) -> numpy.ndarray   # shape (len(FEATURE_NAMES),), validates first
def infer_latents(answers) -> dict[str, str]
def recovery(profiles, seed: int = 0) -> dict   # ValueError on empty

# daypart.rm.model
OFF_TRACK = ("strained", "lapsed", "recovering")
MESSAGE_INTENTS: tuple[str, ...]          # INTENTS without "none"
def split(cohort) -> tuple[tuple[Profile, ...], tuple[Profile, ...]]   # (train, held-out), disjoint, syn- only
def rollouts(profiles, *, cohort_seed=0, seeds=None, horizon=14) -> Rollouts   # ValueError on a curated profile
def trained(cohort_seed: int = 0) -> RewardModel                       # cached, deterministic
class RewardModel:
    def attribution(self, feats, state, intent) -> tuple[Component, ...]   # ValueError on unknown state/intent
    def logit(self, feats, state, intent) -> float   # == sum(c.value for c in attribution(...)) (exact to 1e-9)
    def prob(self, feats, state, intent) -> float    # in (0, 1)
    def lift(self, feats, intent, states=OFF_TRACK) -> float
class Component:  name: str; part: "member" | "message"; value: float
# attribution always contains components named "base" and "status"; "message" iff intent != "none".
def evaluate(cohort_seed: int = 0) -> dict        # the rm arm's metrics

# daypart.rm.grpo
def train_policy(rm, profiles, *, cohort_seed=0, steps=300, seed=4300) -> tuple[Policy, dict]
    # ValueError on empty profiles or any non-synthetic profile; deterministic
class Policy:
    def probs(self, feats, state) -> numpy.ndarray   # shape (len(INTENTS),), sums to 1
    def act(self, feats, state) -> str               # an intent in INTENTS
def evaluate_env(cohort_seed, seeds, n_scenarios, horizon) -> dict   # the grpo arm's metrics

# daypart.rm.inclinations
def inclinations(rm, answers) -> Inclinations
class Inclinations:   # frozen, extra="forbid"
    title: "Inclinations"; data: "synthetic"; rm_version: str; jev_version: str
    drivers: tuple[Driver, ...]; insights: tuple[Insight, ...]; note: str
class Driver:  driver_id (a FEATURE_NAMES entry), label, direction: "helps" | "makes_harder", weight: "strong" | "moderate" | "slight", question_ids
class Insight: insight_id ("insight:<intent>"), title, action, reason (starts "Why: "), driver, strength: "clear" | "moderate" | "small"
```

Invariants (`ValidationError` on construction otherwise): every `Insight.driver` is the `driver_id` of a
driver in the same `Inclinations`; at most 3 insights; every member-facing string (driver label,
insight title/action/reason, note) passes `assert_narration_safe` and `dsl.check(...).passed`.
For every synthetic member of `generate(0)`, `inclinations(trained(0), answers_for(p))` has 1–3
insights, drivers listed heaviest first. No member-facing inclinations string contains a digit, and
the model carries no float: word tiers only, so nothing can be mistaken for a registry bound (T6.5).

## H3. Passport (amends E2 for the Health Clone Passport only)

`HealthClonePassport` gains `inclinations: Inclinations | None = None`. `GET
/api/journals/{id}/passport` returns it for a `syn-` member journal and for the `persona-v1` journal
(drivers and 1–3 insights, each insight linked to a shown driver). If building it raises, the field
is `null` and the rest of the passport is unchanged (fail closed, never partial). The research
`Passport` model of E2 (`/api/members/{id}/passport`) is unchanged. No member-facing inclinations
string contains the words logit, reward, GRPO, feature, intent, model, weight, policy or latent.
