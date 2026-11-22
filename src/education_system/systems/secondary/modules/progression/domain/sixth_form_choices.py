"""Year 11 A-level choices for the sixth form.

Each Year 11 pupil picks **three A-levels** from the sixth form's course
list, in the pupil portal or with a member of staff (the head of year /
an administrator, :data:`SIXTH_FORM_SENDERS`). Parents can see the choices
but not change them. The choices go with the pupil when they are sent to
the sixth form (:mod:`modules.progression.domain.sixth_form_progression`), and a change made
after that is passed on to the open application.

Whether a pupil can study a course is the **sixth form's** rule, not the
school's: its admissions entry requirements (a college-wide minimum and
each course's own - "5 GCSEs at 4+", "GCSE Mathematics 7"). The school
asks the sixth form, through the platform adapter registry, to check the
pupil's released GCSE results against them (``course_options``); nothing
here copies the rules.

Results day
    Until the pupil's results are in (any exam entry still awaited, or the
    series still under embargo), each choice shows what it needs. Once they
    are in, each choice is Met, Near miss (one grade short - the sixth form
    may still take them) or Not met. A pupil with a choice they no longer
    meet is shown the courses they **can** choose from; from then on every
    course they pick must have requirements their results meet. Staff may
    also choose a near-miss course (the sixth form decides).

Option blocks
    The sixth form timetables its courses in option blocks (one course per
    block) with a number of places on each. Once it has set up the blocks
    for the coming year, the three choices must sit in different blocks
    and a newly chosen course must have places left (``blocks_check`` asks
    the sixth form). A full course drops out of the courses a pupil can
    choose from; a course the pupil already had is kept.

Nothing here imports the sixth form.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

CHOICES = 3
#: Outcomes a pupil may switch to once results are in (staff also Near miss).
PUPIL_OK = frozenset({"Met"})
STAFF_OK = frozenset({"Met", "Near miss"})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sixth_form_choices (
    pupil_id    INTEGER PRIMARY KEY REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    choice_1    TEXT NOT NULL,
    choice_2    TEXT NOT NULL,
    choice_3    TEXT NOT NULL,
    chosen_by   TEXT NOT NULL,
    chosen_as   TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sixth_form_choices_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id  INTEGER NOT NULL,
    detail    TEXT,
    actor     TEXT NOT NULL,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("sixth_form_choices", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class Choices:
    pupil_id: int
    courses: tuple[str, ...]
    chosen_by: str
    chosen_as: str
    updated_at: str


def _sfp():
    from education_system.systems.secondary.modules.progression.domain import (
        sixth_form_progression as SFP,
    )
    return SFP


# ── Reading ──────────────────────────────────────────────────────────

def get(pupil_id: int) -> Choices | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM sixth_form_choices WHERE pupil_id = ?",
                         (int(pupil_id),)).fetchone()
    if r is None:
        return None
    return Choices(r["pupil_id"], (r["choice_1"], r["choice_2"], r["choice_3"]),
                   r["chosen_by"], r["chosen_as"], r["updated_at"])


def courses_for(pupil_id: int) -> list[str]:
    c = get(pupil_id)
    return list(c.courses) if c else []


def all_choices() -> dict[int, Choices]:
    with database.connect() as conn:
        return {r["pupil_id"]: Choices(r["pupil_id"], (r["choice_1"], r["choice_2"],
                                                        r["choice_3"]), r["chosen_by"],
                                       r["chosen_as"], r["updated_at"])
                for r in conn.execute("SELECT * FROM sixth_form_choices")}


def history(pupil_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute("SELECT * FROM sixth_form_choices_audit WHERE pupil_id = ?"
                                      " ORDER BY audit_id DESC", (int(pupil_id),))]


# ── What the sixth form says ─────────────────────────────────────────

def _adapter():
    """The sixth form's adapter, found the way the post-16 board finds it."""
    SFP = _sfp()
    return SFP._post16()._destination_adapter(SFP.DESTINATION)


def course_options(gcse_results: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Every sixth form course checked against *gcse_results* by the sixth
    form's entry requirements; None when the sixth form can't be asked."""
    try:
        fn = getattr(_adapter(), "course_options", None)
        return list(fn(gcse_results)) if fn else None
    except Exception:  # noqa: BLE001 - the sixth form isn't installed / reachable
        import logging
        logging.getLogger(__name__).exception("Couldn't ask the sixth form about courses")
        return None


def blocks_check(pupil_id: int, courses: list[str],
                 app: dict | None = None) -> dict[str, Any] | None:
    """Whether *courses* fit the sixth form's option blocks for the coming
    intake with places left, as the sixth form checks it (its
    ``option_blocks``: ``published``, ``blocks``, ``courses`` {course:
    {blocks, capacity, taken, full}}, ``placement``, ``full``,
    ``clashes``). The pupil's own application doesn't count against the
    places. None when the sixth form can't be asked."""
    try:
        fn = getattr(_adapter(), "option_blocks", None)
        if fn is None:
            return None
        if app is None:
            app = _sfp().application_for(int(pupil_id))
        return dict(fn(list(courses), (app or {}).get("journey_id")))
    except Exception:  # noqa: BLE001 - the sixth form isn't installed / reachable
        import logging
        logging.getLogger(__name__).exception("Couldn't ask the sixth form about option blocks")
        return None


def block_lines(blocks: dict[str, Any] | None) -> list[str]:
    """"Block A: Biology, Maths (full)" lines for showing the blocks; empty
    when the sixth form hasn't set them up."""
    if not blocks or not blocks.get("published"):
        return []
    full = {c for c, v in blocks["courses"].items() if v["full"]}
    return [f"Block {b}: " + ", ".join(f"{c} (full)" if c in full else c for c in subs)
            for b, subs in sorted(blocks["blocks"].items())]


def _full(blocks: dict[str, Any] | None, course: str) -> bool:
    if not blocks or not blocks.get("published"):
        return False
    c = {k.lower(): v for k, v in blocks["courses"].items()}.get(course.lower())
    return bool(c and c["full"])


def _with_blocks(o: dict[str, Any], blocks: dict[str, Any] | None) -> dict[str, Any]:
    """A course option with its ``blocks`` (letters) and ``full`` flag."""
    c = ({k.lower(): v for k, v in blocks["courses"].items()}.get(o["course"].lower())
         if blocks and blocks.get("published") else None)
    return {**o, "blocks": list(c["blocks"]) if c else [], "full": bool(c and c["full"]),
            "places": (None if not c or c["capacity"] is None
                       else max(c["capacity"] - c["taken"], 0))}


def results_known(pupil_id: int, states: dict | None = None,
                  results: list[dict] | None = None) -> bool:
    """The pupil's results are in: no exam entry still awaited (or under
    embargo) and at least one GCSE result to go on."""
    from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
    from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
    n = (states if states is not None else ER.result_states()).get(int(pupil_id), {})
    if n.get("awaited"):
        return False
    return bool(results if results is not None else G.handover_list(int(pupil_id)))


def status(pupil_id: int, *, states: dict | None = None) -> dict[str, Any]:
    """Everything the portal and the staff screens show about a pupil's
    choices: ``choices``, ``results_known``, ``options`` (every course, as
    the sixth form checked it - None if it can't be asked), ``chosen`` (the
    options for the three choices), ``all_met`` (None until results are
    in), ``can_choose_from`` (courses met, not already chosen),
    ``near_miss``, ``stage`` (the sixth form application) and ``locked``
    (why choices can't change, or None)."""
    from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    choices = courses_for(p.pupil_id)
    if p.year_group != P.YEAR_GROUPS[-1] and not choices:
        # Not choosing yet: nothing to ask the sixth form about.
        return {"pupil": p, "choices": [], "results_known": False, "results": [],
                "options": [], "chosen": [], "all_met": None, "eligible": [], "blocks": None,
                "can_choose_from": [],
                "near_miss": [], "stage": "Not sent", "locked": _locked(p, None)}
    results = G.handover_list(p.pupil_id)
    known = results_known(p.pupil_id, states, results)
    options = course_options(results)
    app = _sfp().application_for(p.pupil_id)
    blocks = blocks_check(p.pupil_id, choices, app) if options is not None else None
    if options is not None:
        options = [_with_blocks(o, blocks) for o in options]
    by_course = {o["course"].lower(): o for o in options or []}
    chosen = [by_course.get(c.lower(), {"course": c, "outcome": "Unknown",
                                        "requirements": [], "checks": []}) for c in choices]
    all_met = (all(c["outcome"] == "Met" for c in chosen) if known and chosen else None)
    picked = {c.lower() for c in choices}
    # A full course can't be newly chosen; one the pupil already has stays.
    open_ = [o for o in options or [] if not o["full"] or o["course"].lower() in picked]
    return {
        "pupil": p, "choices": choices, "results_known": known, "results": results,
        "options": options, "chosen": chosen, "all_met": all_met, "blocks": blocks,
        "eligible": [o["course"] for o in open_ if known and o["outcome"] == "Met"],
        "can_choose_from": [o["course"] for o in open_ if known
                            and o["outcome"] == "Met" and o["course"].lower() not in picked],
        "near_miss": [o["course"] for o in open_ if known
                      and o["outcome"] == "Near miss" and o["course"].lower() not in picked],
        "stage": app["stage"] if app else "Not sent", "locked": _locked(p, app),
    }


def cohort(*, show: str = "all", search: str | None = None) -> list[dict[str, Any]]:
    """:func:`status` for every Year 11 pupil on roll. *show*: ``all``,
    ``not chosen`` or ``needs new choices`` (results in, a choice not met)."""
    from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
    states = ER.result_states()
    out = []
    for p in P.list_pupils(year_group=P.YEAR_GROUPS[-1], search=search):
        st = status(p.pupil_id, states=states)
        st["summary"] = summary(st)
        if show == "not chosen" and st["choices"]:
            continue
        if show == "needs new choices" and st["all_met"] is not False:
            continue
        out.append(st)
    return out


def summary(st: dict[str, Any]) -> str:
    """One line for lists: "All met", "1 not met", "Results awaited"..."""
    if not st["choices"]:
        return "Not chosen"
    if st["options"] is None:
        return "Sixth form unavailable"
    clash = ", block clash" if (st.get("blocks") or {}).get("clashes") else ""
    if not st["results_known"]:
        return "Results awaited" + clash
    bad = [c for c in st["chosen"] if c["outcome"] != "Met"]
    if not bad:
        return "All met" + clash
    near = sum(1 for c in bad if c["outcome"] == "Near miss")
    return ", ".join(x for x in (f"{len(bad) - near} not met" if len(bad) > near else "",
                                 f"{near} near miss" if near else "") if x) + clash


def _locked(p: P.Pupil, app: dict | None) -> str | None:
    if app and app["stage"] == "Enrolled / On Programme":
        return "You're enrolled at the sixth form - talk to them about changing courses."
    if p.roll_status != "on_roll":
        return f"{p.display_name} is not on roll"
    if p.year_group != P.YEAR_GROUPS[-1]:
        return f"A-level choices are made in Year {P.YEAR_GROUPS[-1]}"
    return None


# ── Choosing ─────────────────────────────────────────────────────────

def can_choose(actor: Principal, pupil_id: int) -> bool:
    """The pupil themselves (in the portal) or a sender (staff); not parents."""
    if actor.is_student:
        from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
        try:
            PA.require_pupil(actor, pupil_id, "pupil")
            return True
        except PA.PermissionDenied:
            return False
    return _sfp().is_sender(actor)


def save(pupil_id: int, courses: list[str], *, actor: Principal) -> dict[str, Any]:
    """Choose (or change) the pupil's three A-levels. Returns {'choices',
    'sixth_form': 'updated' / 'not sent yet' / why it wasn't passed on}."""
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    if not can_choose(actor, p.pupil_id):
        activity_log.record("sixthform.choices", target=p.admission_no, outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only the pupil, their head of year or an administrator can "
                               "choose their A-levels.")
    st = status(p.pupil_id)
    problems: list[str] = []
    if st["locked"]:
        problems.append(st["locked"])
    picked = [str(c or "").strip() for c in courses or []]
    picked = [c for c in picked if c]
    if len(picked) != CHOICES:
        problems.append(f"Choose {CHOICES} A-levels")
    if len({c.lower() for c in picked}) != len(picked):
        problems.append("Each A-level must be different")
    options = st["options"]
    if options is None:
        problems.append("The sixth form's course list isn't available just now - try again "
                        "later")
    else:
        by_course = {o["course"].lower(): o for o in options}
        allowed = STAFF_OK if not actor.is_student else PUPIL_OK
        canon = []
        for c in picked:
            o = by_course.get(c.lower())
            if o is None:
                problems.append(f"{c} isn't a course the sixth form offers")
                continue
            canon.append(o["course"])
            if st["results_known"] and o["outcome"] not in allowed:
                need = "; ".join(x["requirement"] for x in o["checks"]
                                 if x["outcome"] != "Met")
                problems.append(f"Your results don't meet the entry requirements for "
                                f"{o['course']}" + (f" ({need})" if need else ""))
        picked = canon if len(canon) == len(picked) else picked
        if not problems:
            problems.extend(_block_problems(p.pupil_id, picked, st["choices"]))
    if problems:
        activity_log.record("sixthform.choices", target=p.admission_no, outcome="invalid",
                            principal=actor, problems=len(problems))
        raise ValidationError(problems)
    if [c.lower() for c in picked] == [c.lower() for c in st["choices"]]:
        return {"choices": st["choices"], "sixth_form": "unchanged"}
    role = "pupil" if actor.is_student else "staff"
    with database.connect() as conn:
        conn.execute(
            "INSERT INTO sixth_form_choices (pupil_id, choice_1, choice_2, choice_3, chosen_by,"
            " chosen_as) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (pupil_id) DO UPDATE SET "
            "choice_1 = excluded.choice_1, choice_2 = excluded.choice_2, choice_3 = "
            "excluded.choice_3, chosen_by = excluded.chosen_by, chosen_as = excluded.chosen_as, "
            "updated_at = datetime('now')",
            (p.pupil_id, *picked, actor.username or "unknown", role))
        conn.execute("INSERT INTO sixth_form_choices_audit (pupil_id, detail, actor) VALUES "
                     "(?, ?, ?)", (p.pupil_id, json.dumps({"from": st["choices"],
                                                           "to": picked, "as": role}),
                                   actor.username or "unknown"))
    activity_log.record("sixthform.choices", target=p.admission_no, principal=actor,
                        chosen_as=role)
    return {"choices": picked, "sixth_form": _pass_on(p.pupil_id, picked)}


def _block_problems(pupil_id: int, picked: list[str], had: list[str]) -> list[str]:
    """The sixth form's option blocks: the three must be in different
    blocks, and a newly chosen course must have places left (one the pupil
    already had is kept even if it has filled since). Nothing to check if
    the sixth form hasn't set up blocks for the coming year."""
    check = blocks_check(pupil_id, picked)
    if not check or not check.get("published"):
        return []
    kept = {c.lower() for c in had}
    out = [f"{c} is full - there are no places left (choose another course)"
           for c in check.get("full", []) if c.lower() not in kept]
    if check.get("clashes"):
        blocks = {c: "/".join(v["blocks"]) for c, v in check["courses"].items()}
        where = ", ".join(f"{c} (block {blocks[c]})" for c in picked if c in blocks)
        out.extend(check["clashes"])
        if where:
            out.append(f"Choose one course from each block: {where}")
    return out


def _pass_on(pupil_id: int, picked: list[str]) -> str:
    """Give an open sixth form application the new choices (best effort)."""
    SFP = _sfp()
    app = SFP.application_for(pupil_id)
    if app is None or app["stage"] in SFP.CLOSED_STAGES:
        return "not sent yet"
    try:
        SFP._post16().update_choices(str(pupil_id), SFP.DESTINATION, subjects=picked)
        return "updated"
    except Exception as exc:  # noqa: BLE001 - the choice is kept here either way
        import logging
        logging.getLogger(__name__).exception("Couldn't pass choices on to the sixth form")
        return f"not passed on ({exc})"
