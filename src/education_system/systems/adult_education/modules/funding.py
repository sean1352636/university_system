"""Adult Skills Fund eligibility: which funding a course would attract.

:func:`evaluate` is a pure rule function (no database), carried over from the
old Adult Education system; saving an assessment records its outcome and
reasons. The rules are a simplified model of England's adult funding:

1. **Age** - 19 or over on 31 August before the academic year starts;
   younger learners are 16-19 funded (sixth form / FE).
2. **Residency** - UK/EEA for three years, settled status, refugee /
   humanitarian protection, or an asylum seeker waiting 6 months+.
3. **Level 4 and above** - not grant funded: Advanced Learner Loan.
4. **Level 3** - a first full Level 3 is fully funded for a learner without a
   Level 3 or on a low wage (Free Courses for Jobs); otherwise a loan.
5. **English and maths** (up to Level 2) - fully funded without a GCSE grade
   4/C in that subject; otherwise co-funded.
6. **Essential digital skills** (up to Level 1) - fully funded.
7. **ESOL** (up to Level 2) - fully funded for the unemployed or those on
   benefits; otherwise co-funded.
8. **Other courses up to Level 2** - fully funded for the unemployed, those on
   benefits, a low wage (under :data:`LOW_WAGE_THRESHOLD`), a first full Level 2
   at 19-23 without one, or Entry/Level 1 study below Level 2; else co-funded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from education_system.systems.adult_education.core import dates
from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.core.records import Field, RecordType, ValidationError
from education_system.systems.adult_education.modules import learners
from education_system.systems.adult_education.modules.learners import LEVEL_RANK, LEVELS

LOW_WAGE_THRESHOLD = 25_000
RESIDENCY = ("Lived in the UK/EEA for the last 3 years", "Settled or pre-settled status",
             "Refugee or humanitarian protection",
             "Asylum seeker (6 months+ awaiting decision)", "None of these")
ELIGIBLE_RESIDENCY = frozenset(RESIDENCY[:4])
COURSE_TYPES = ("General course", "English or maths", "ESOL", "Essential digital skills")
#: Highest level each course type can be funded at.
MAX_LEVEL = {"English or maths": "Level 2", "ESOL": "Level 2",
             "Essential digital skills": "Level 1"}
OUTCOMES = ("Fully funded", "Co-funded (learner pays part)", "Advanced Learner Loan",
            "Not eligible for funding")
FULLY, CO, LOAN, NONE = OUTCOMES
NOT_WORKING = frozenset({"Unemployed (looking for work)", "Not working and not looking"})


@dataclass
class Result:
    outcome: str
    reasons: list[str] = field(default_factory=list)
    age: int | None = None


def academic_year_start(on: date) -> date:
    """1 August that starts the academic year *on* falls in."""
    return date(on.year if on.month >= 8 else on.year - 1, 8, 1)


def evaluate(*, dob: date, year_start: date, residency: str, employment: str,
             course_type: str, course_level: str, annual_income: float | None = None,
             on_benefits: bool = False, highest_level: str | None = None,
             gcse_english: bool = False, gcse_maths: bool = False,
             first_full_level: bool = False) -> Result:
    age = dates.age_on(dob, date(year_start.year, 8, 31))
    res = Result(NONE, age=age)
    why = res.reasons
    if age < 19:
        why.append(f"Aged {age} on 31 August {year_start.year}: under 19, so 16-19 funding "
                   "applies (refer to a sixth form or FE college).")
        return res
    why.append(f"Aged {age} on 31 August {year_start.year} (19 or over).")
    if residency not in ELIGIBLE_RESIDENCY:
        why.append("Doesn't meet the residency rules for public funding.")
        return res
    why.append(f"Residency: {residency}.")
    no_work = employment in NOT_WORKING or bool(on_benefits)
    low_wage = (employment in ("Employed", "Self-employed") and annual_income is not None
                and annual_income < LOW_WAGE_THRESHOLD)
    highest = LEVEL_RANK.get(highest_level or "", -1)
    rank = LEVEL_RANK[course_level]

    if rank >= LEVEL_RANK["Level 4"]:
        res.outcome = LOAN
        why.append(f"{course_level} isn't grant funded; an Advanced Learner Loan can cover "
                   "the fees.")
    elif rank == LEVEL_RANK["Level 3"]:
        if first_full_level and (highest < LEVEL_RANK["Level 3"] or low_wage):
            res.outcome = FULLY
            why.append("First full Level 3 for a learner " +
                       ("without a Level 3." if highest < LEVEL_RANK["Level 3"]
                        else f"earning under £{LOW_WAGE_THRESHOLD:,}."))
        else:
            res.outcome = LOAN
            why.append("Level 3 that isn't a first full Level 3 (or the learner already "
                       "holds one): Advanced Learner Loan.")
    elif course_type == "English or maths":
        if not (gcse_english and gcse_maths):
            res.outcome = FULLY
            missing = [s for s, held in (("English", gcse_english), ("maths", gcse_maths))
                       if not held]
            why.append("Legal entitlement: no GCSE grade 4/C in " + " or ".join(missing) + ".")
        else:
            res.outcome = CO
            why.append("Already holds GCSE grade 4/C in English and maths.")
    elif course_type == "Essential digital skills":
        res.outcome = FULLY
        why.append("Legal entitlement: essential digital skills.")
    elif course_type == "ESOL":
        res.outcome = FULLY if no_work else CO
        why.append("ESOL for a learner who isn't working or is on benefits." if no_work
                   else "ESOL for a learner in work: co-funded.")
    elif no_work:
        res.outcome = FULLY
        why.append("Unemployed, not working or on benefits.")
    elif low_wage:
        res.outcome = FULLY
        why.append(f"Earning under £{LOW_WAGE_THRESHOLD:,} a year (low wage).")
    elif (first_full_level and rank == LEVEL_RANK["Level 2"] and age <= 23
          and highest < LEVEL_RANK["Level 2"]):
        res.outcome = FULLY
        why.append("First full Level 2, aged 19-23 without a Level 2.")
    elif rank <= LEVEL_RANK["Level 1"] and highest < LEVEL_RANK["Level 2"]:
        res.outcome = FULLY
        why.append(f"{course_level} study for a learner below Level 2.")
    else:
        res.outcome = CO
        why.append("No full-funding rule applies: co-funded (the learner pays part).")
    return res


def _check(values: dict, old: dict | None) -> None:
    if old is not None:
        raise ValidationError("A funding assessment is a record of a decision and can't be "
                              "edited. Make a new assessment instead.")
    learner = r.get(learners.LEARNERS, int(values["learner_id"]))
    if learner is None:
        raise ValidationError("Choose the learner.")
    if learner["status"] == "Archived":
        raise ValidationError("This learner is archived. Restore them before assessing.")
    course_type, level = values["course_type"], values["course_level"]
    cap = MAX_LEVEL.get(course_type)
    if cap and LEVEL_RANK[level] > LEVEL_RANK[cap]:
        raise ValidationError(f"{course_type} is funded up to {cap} only.")
    prior = learners.prior_summary(learner["id"])   # fill gaps from prior qualifications
    if not values.get("highest_prior_level"):
        values["highest_prior_level"] = prior["highest_level"]
    values["gcse_english"] = 1 if (values.get("gcse_english") or prior["gcse_english"]) else 0
    values["gcse_maths"] = 1 if (values.get("gcse_maths") or prior["gcse_maths"]) else 0
    start = r.to_date(r.parse_date(values.get("year_start"))) or academic_year_start(date.today())
    values["year_start"] = start.isoformat()
    res = evaluate(dob=date.fromisoformat(learner["dob"]), year_start=start,
                   residency=values["residency"], employment=values["employment"],
                   course_type=course_type, course_level=level,
                   annual_income=values.get("annual_income"),
                   on_benefits=bool(values.get("on_benefits")),
                   highest_level=values.get("highest_prior_level"),
                   gcse_english=bool(values["gcse_english"]),
                   gcse_maths=bool(values["gcse_maths"]),
                   first_full_level=bool(values.get("first_full_level")))
    values.update(outcome=res.outcome, reasons="\n".join(res.reasons), age_at_31_august=res.age,
                  assessed_on=date.today().isoformat())


ELIGIBILITY = RecordType(
    key="eligibility", title="Funding Eligibility", singular="funding assessment",
    order_by="assessed_on DESC, id DESC", check=_check, filters=("outcome", "course_type"),
    describe=lambda row: f"{row.get('outcome')} - {row.get('course_level')} "
                         f"{row.get('course_type')} ({row.get('assessed_on')})",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("course_type", "Course type", "choice", COURSE_TYPES, required=True),
        Field("course_level", "Course level", "choice", LEVELS, required=True),
        Field("first_full_level", "First full level", "bool", listed=False,
              help="Would this be the learner's first full Level 2 / Level 3?"),
        Field("residency", "Residency", "choice", RESIDENCY, required=True, listed=False),
        Field("employment", "Employment", "choice", learners.EMPLOYMENT, required=True,
              listed=False),
        Field("annual_income", "Annual income", "money", listed=False),
        Field("on_benefits", "On benefits", "bool", listed=False),
        Field("highest_prior_level", "Highest level held", "choice", LEVELS, listed=False,
              help="Left blank: taken from Prior Qualifications"),
        Field("gcse_english", "GCSE English 4/C+", "bool", listed=False,
              help="Also ticked automatically from Prior Qualifications"),
        Field("gcse_maths", "GCSE maths 4/C+", "bool", listed=False),
        Field("year_start", "Academic year starts", "date", listed=False,
              help="Left blank: this academic year (1 August)"),
        Field("assessed_by", "Assessed by"),
        Field("outcome", "Outcome", form=False),
        Field("reasons", "Reasons", "long", form=False),
        Field("age_at_31_august", "Age at 31 Aug", "int", form=False, listed=False),
        Field("assessed_on", "Assessed", "date", form=False),
    ),
)


def latest_outcome(learner_id: int) -> str | None:
    rows = r.list_records(ELIGIBILITY, learner_id=learner_id, limit=1)
    return rows[0]["outcome"] if rows else None
