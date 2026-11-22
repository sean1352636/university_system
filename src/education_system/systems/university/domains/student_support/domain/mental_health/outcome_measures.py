"""Standardised outcome measures used by the counselling service.

Three questionnaires, scored item by item exactly as published:

* **PHQ-9** (depression): nine items scored 0–3, total 0–27. Bands 0–4
  minimal, 5–9 mild, 10–14 moderate, 15–19 moderately severe, 20–27 severe.
  Caseness ≥ 10. Item 9 (thoughts of being better off dead or of hurting
  yourself) above 0 is a risk flag whatever the total.
* **GAD-7** (anxiety): seven items 0–3, total 0–21. Bands 0–4 minimal, 5–9
  mild, 10–14 moderate, 15–21 severe. Caseness ≥ 8 (the NHS Talking
  Therapies cut-off).
* **CORE-10** (general psychological distress): ten items 0–4, total 0–40.
  Items 2 ("I have felt I have someone to turn to for support when needed")
  and 3 ("I have felt able to cope when things go wrong") are positively
  worded and reverse-scored (4 − answer). Bands 0–5 healthy, 6–10 low
  level, 11–14 mild, 15–19 moderate, 20–24 moderately severe, 25–40 severe;
  clinical cut-off 11. Item 6 ("I made plans to end my life") above 0 is a
  risk flag.

Change between a first and a last score is judged with the reliable change
thresholds (PHQ-9 6, GAD-7 4, CORE-10 6 points); *recovery* is moving from
at or above caseness to below it, and *reliable recovery* is recovery with
reliable improvement.
"""

from __future__ import annotations

from dataclasses import dataclass

STAGES = ("first", "review", "last")


@dataclass(frozen=True)
class Measure:
    code: str
    title: str
    items: tuple[str, ...]
    max_item: int
    answers: tuple[str, ...]
    bands: tuple[tuple[int, str], ...]      # (lowest total, band), ascending
    caseness: int
    reliable_change: int
    reverse_items: tuple[int, ...] = ()     # 1-based item numbers
    risk_item: int | None = None            # 1-based

    @property
    def max_total(self) -> int:
        return self.max_item * len(self.items)


_PHQ_GAD_ANSWERS = ("Not at all", "Several days", "More than half the days",
                    "Nearly every day")

PHQ9 = Measure(
    code="PHQ-9", title="Patient Health Questionnaire (PHQ-9)",
    items=(
        "Little interest or pleasure in doing things",
        "Feeling down, depressed, or hopeless",
        "Trouble falling or staying asleep, or sleeping too much",
        "Feeling tired or having little energy",
        "Poor appetite or overeating",
        "Feeling bad about yourself — or that you are a failure or have let yourself "
        "or your family down",
        "Trouble concentrating on things, such as reading or watching television",
        "Moving or speaking so slowly that other people could have noticed, or the "
        "opposite — being so fidgety or restless that you have been moving around a "
        "lot more than usual",
        "Thoughts that you would be better off dead, or of hurting yourself in some way",
    ),
    max_item=3, answers=_PHQ_GAD_ANSWERS,
    bands=((0, "Minimal"), (5, "Mild"), (10, "Moderate"), (15, "Moderately severe"),
           (20, "Severe")),
    caseness=10, reliable_change=6, risk_item=9)

GAD7 = Measure(
    code="GAD-7", title="Generalised Anxiety Disorder Assessment (GAD-7)",
    items=(
        "Feeling nervous, anxious or on edge",
        "Not being able to stop or control worrying",
        "Worrying too much about different things",
        "Trouble relaxing",
        "Being so restless that it is hard to sit still",
        "Becoming easily annoyed or irritable",
        "Feeling afraid as if something awful might happen",
    ),
    max_item=3, answers=_PHQ_GAD_ANSWERS,
    bands=((0, "Minimal"), (5, "Mild"), (10, "Moderate"), (15, "Severe")),
    caseness=8, reliable_change=4)

CORE10 = Measure(
    code="CORE-10", title="Clinical Outcomes in Routine Evaluation (CORE-10)",
    items=(
        "I have felt tense, anxious or nervous",
        "I have felt I have someone to turn to for support when needed",
        "I have felt able to cope when things go wrong",
        "Talking to people has felt too much for me",
        "I have felt panic or terror",
        "I made plans to end my life",
        "I have had difficulty getting to sleep or staying asleep",
        "I have felt despairing or hopeless",
        "I have felt unhappy",
        "Unwanted images or memories have been distressing me",
    ),
    max_item=4,
    answers=("Not at all", "Only occasionally", "Sometimes", "Often",
             "Most or all of the time"),
    bands=((0, "Healthy"), (6, "Low level"), (11, "Mild"), (15, "Moderate"),
           (20, "Moderately severe"), (25, "Severe")),
    caseness=11, reliable_change=6, reverse_items=(2, 3), risk_item=6)

MEASURES: dict[str, Measure] = {m.code: m for m in (CORE10, PHQ9, GAD7)}


def get(code) -> Measure:
    measure = MEASURES.get(str(code or "").strip().upper())
    if measure is None:
        raise ValueError(f"Unknown outcome measure {code!r}; use one of "
                         f"{', '.join(MEASURES)}.")
    return measure


def validate(measure: Measure, answers) -> list[int]:
    """The answers as integers, or ``ValueError`` naming the bad item."""
    answers = list(answers or [])
    if len(answers) != len(measure.items):
        raise ValueError(f"{measure.code} has {len(measure.items)} items; "
                         f"{len(answers)} answered.")
    clean = []
    for number, value in enumerate(answers, start=1):
        try:
            score = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{measure.code} item {number} is not answered.") from None
        if not 0 <= score <= measure.max_item:
            raise ValueError(f"{measure.code} item {number} must be 0–{measure.max_item}.")
        clean.append(score)
    return clean


def band(measure: Measure, total: int) -> str:
    label = measure.bands[0][1]
    for lowest, name in measure.bands:
        if total >= lowest:
            label = name
    return label


def score(code, answers) -> dict:
    """``{'measure', 'items', 'scored_items', 'total', 'max_total', 'band',
    'clinical', 'risk_flag', 'risk_item_score'}`` for one completed form.

    ``items`` are the answers as given; ``scored_items`` after reverse
    scoring (CORE-10 items 2 and 3)."""
    measure = get(code)
    raw = validate(measure, answers)
    scored = [measure.max_item - value if number in measure.reverse_items else value
              for number, value in enumerate(raw, start=1)]
    total = sum(scored)
    risk_score = raw[measure.risk_item - 1] if measure.risk_item else 0
    return {"measure": measure.code, "items": raw, "scored_items": scored, "total": total,
            "max_total": measure.max_total, "band": band(measure, total),
            "clinical": total >= measure.caseness, "risk_flag": risk_score > 0,
            "risk_item_score": risk_score}


def change(code, first_total: int, last_total: int) -> dict:
    """Reliable change and recovery between two totals (lower is better).

    ``category`` is ``'reliably improved'``, ``'reliably deteriorated'`` or
    ``'no reliable change'``; ``recovered`` needs the first score at or
    above caseness and the last below it; ``reliable_recovery`` needs both
    recovery and reliable improvement."""
    measure = get(code)
    first_total, last_total = int(first_total), int(last_total)
    delta = last_total - first_total
    if delta <= -measure.reliable_change:
        category = "reliably improved"
    elif delta >= measure.reliable_change:
        category = "reliably deteriorated"
    else:
        category = "no reliable change"
    case_at_start = first_total >= measure.caseness
    recovered = case_at_start and last_total < measure.caseness
    return {"measure": measure.code, "first": first_total, "last": last_total,
            "change": delta, "category": category, "case_at_start": case_at_start,
            "recovered": recovered,
            "reliable_recovery": recovered and category == "reliably improved"}
