"""Education, Health and Care plans: the statutory timeline and annual reviews.

Statutory timescales (SEND Code of Practice 2015), all from the request date
unless stated:

* decision whether to assess - 6 weeks;
* final plan issued - 20 weeks (the draft must leave the family 15 days to
  comment, so :data:`DRAFT_TARGET_WEEKS` is the local target for the draft);
* annual review - within 12 months of the plan being issued, then of the
  last review;
* after a review meeting, the report goes out within 2 weeks and the LA
  decides within 4 weeks of the meeting.

Rules: one open EHCP per learner; a stage that needs a date can't be saved
without it; issuing the final plan sets the learner's SEN status to EHCP and
ceasing it returns them to SEN Support.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.special_education.core import dates
from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.core.records import Field, RecordType, ValidationError
from education_system.systems.special_education.infrastructure import database as db
from education_system.systems.special_education.modules import learners

DECISION_WEEKS = 6
DRAFT_TARGET_WEEKS = 16
FINAL_WEEKS = 20
REPORT_WEEKS = 2
LA_DECISION_WEEKS = 4

STAGES = ("Requested", "Assessing", "Refused to assess", "Draft issued", "Final issued",
          "Not issued", "Ceased")
CLOSED = frozenset({"Refused to assess", "Not issued", "Ceased"})
#: The date each stage needs before it can be saved.
_STAGE_DATE = {"Assessing": "decision_date", "Refused to assess": "decision_date",
               "Not issued": "decision_date", "Draft issued": "draft_date",
               "Final issued": "final_date", "Ceased": "cease_date"}


def _today() -> str:
    return date.today().isoformat()


@dataclass(frozen=True)
class Deadline:
    what: str
    due: date
    done: date | None

    @property
    def overdue(self) -> bool:
        return self.done is None and self.due < date.today()

    @property
    def late(self) -> bool:
        """Met, but after the deadline."""
        return self.done is not None and self.done > self.due


def deadlines(row: dict) -> list[Deadline]:
    """The plan's statutory deadlines, met or not, in date order."""
    req = r.to_date(row.get("request_date"))
    out: list[Deadline] = []
    if req is None:
        return out
    decision = r.to_date(row.get("decision_date"))
    out.append(Deadline("Decision to assess", dates.add_weeks(req, DECISION_WEEKS), decision))
    if row.get("stage") in ("Refused to assess",):
        return out
    out.append(Deadline("Draft plan (local target)", dates.add_weeks(req, DRAFT_TARGET_WEEKS),
                        r.to_date(row.get("draft_date"))))
    final = r.to_date(row.get("final_date"))
    if row.get("stage") != "Not issued":
        out.append(Deadline("Final plan", dates.add_weeks(req, FINAL_WEEKS), final))
    if final and row.get("stage") != "Ceased":
        last = r.to_date(row.get("last_review_date"))
        base = max(d for d in (final, last) if d)
        out.append(Deadline("Annual review", dates.add_months(base, 12), None))
    return out


def next_deadline(row: dict) -> Deadline | None:
    if row.get("stage") in CLOSED:
        return None
    pending = [d for d in deadlines(row) if d.done is None]
    return min(pending, key=lambda d: d.due) if pending else None


def _next_label(row: dict) -> str:
    d = next_deadline(row)
    if d is None:
        return ""
    days = (d.due - date.today()).days
    when = f"overdue {-days}d" if days < 0 else f"in {days}d"
    return f"{d.what} {dates.uk(d.due)} ({when})"


def _week(row: dict) -> str:
    req = r.to_date(row.get("request_date"))
    if not req or row.get("final_date") or row.get("stage") in CLOSED:
        return ""
    return f"Week {(date.today() - req).days // 7 + 1}"


def _check(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    d = {k: r.to_date(r.parse_date(merged.get(k))) for k in
         ("request_date", "decision_date", "draft_date", "final_date", "last_review_date",
          "cease_date")}
    # A later date implies the stage: entering the final date issues the plan.
    stage = merged.get("stage") or "Requested"
    order = {s: i for i, s in enumerate(STAGES)}
    implied = ("Final issued" if d["final_date"] else "Draft issued" if d["draft_date"]
               else None)
    if implied and stage not in CLOSED and order[stage] < order[implied]:
        values["stage"] = stage = implied
    need = _STAGE_DATE.get(stage)
    if need and not d[need]:
        label = EHCPS.fields_by_name[need].label
        raise ValidationError(f"'{stage}' needs the {label.lower()}.")
    chain = [("request_date", "decision_date"), ("decision_date", "draft_date"),
             ("draft_date", "final_date"), ("request_date", "final_date"),
             ("final_date", "last_review_date"), ("request_date", "cease_date")]
    for first, second in chain:
        if d[first] and d[second] and d[second] < d[first]:
            f1, f2 = EHCPS.fields_by_name[first].label, EHCPS.fields_by_name[second].label
            raise ValidationError(f"{f2} can't be before {f1.lower()}.")
    if d["draft_date"] and d["final_date"] and (d["final_date"] - d["draft_date"]).days < 15:
        raise ValidationError("The family must get at least 15 days to comment on the draft "
                              "before the final plan is issued.")
    if stage not in CLOSED:
        with db.connect() as conn:
            other = conn.execute(
                "SELECT stage FROM ehcps WHERE learner_id = ? AND id IS NOT ? AND stage NOT IN "
                f"({', '.join('?' for _ in CLOSED)})",
                (merged.get("learner_id"), (old or {}).get("id"), *sorted(CLOSED))).fetchone()
        if other:
            raise ValidationError(f"This learner already has an open EHCP ({other[0]}).")


def _after(conn, row: dict, old: dict | None) -> None:
    was = (old or {}).get("stage")
    if row["stage"] == "Final issued" and was != "Final issued":
        learners.set_sen_status(conn, row["learner_id"], "EHCP")
    elif row["stage"] == "Ceased" and was != "Ceased":
        learners.set_sen_status(conn, row["learner_id"], "SEN Support", only_if="EHCP")


EHCPS = RecordType(
    key="ehcps", title="EHCP Tracker", singular="EHCP", order_by="request_date DESC",
    check=_check, after_save=_after, filters=("stage",),
    after_commit=learners.platform_hook("ehcp_saved"),
    describe=lambda row: (f"{row.get('learner_name') or 'EHCP'} - requested "
                          f"{dates.uk(r.to_date(row.get('request_date')))} ({row.get('stage')})"),
    computed=(("Week", _week), ("Next deadline", _next_label)),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("local_authority", "Local authority"),
        Field("request_date", "Request received", "date", required=True, default=_today),
        Field("requested_by", "Requested by", "choice",
              ("Parent/carer", "School/setting", "Young person", "Health/social care", "Other"),
              listed=False),
        Field("stage", "Stage", "choice", STAGES, required=True, default="Requested"),
        Field("decision_date", "Decision to assess", "date", listed=False),
        Field("draft_date", "Draft issued", "date", listed=False),
        Field("final_date", "Final issued", "date"),
        Field("last_review_date", "Last annual review", "date", listed=False,
              help="Filled in from Annual Reviews"),
        Field("cease_date", "Ceased on", "date", listed=False),
        Field("caseworker", "LA caseworker", listed=False),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def _ehcp_learner(values: dict, old: dict | None) -> dict:
    ehcp_id = values.get("ehcp_id") or (old or {}).get("ehcp_id")
    plan = r.get(EHCPS, int(ehcp_id)) if ehcp_id else None
    if plan is None:
        raise ValidationError("Choose the EHCP.")
    values["learner_id"] = plan["learner_id"]
    return plan


def _check_advice(values: dict, old: dict | None) -> None:
    _ehcp_learner(values, old)
    merged = {**(old or {}), **values}
    asked = r.to_date(r.parse_date(merged.get("requested_on")))
    if asked and not merged.get("due_on"):
        values["due_on"] = dates.add_weeks(asked, 6).isoformat()
    got = r.to_date(r.parse_date(merged.get("received_on")))
    if asked and got and got < asked:
        raise ValidationError("Advice can't be received before it was requested.")


ADVICE = RecordType(
    key="ehcp_advice", title="Advice & Information", singular="advice request",
    order_by="due_on", check=_check_advice, filters=("advice_type",),
    computed=(("Late", lambda row: "Overdue" if (not row.get("received_on") and row.get("due_on")
                                                 and row["due_on"] < _today()) else ""),),
    describe=lambda row: f"{row.get('advice_type')} advice",
    fields=(
        Field("ehcp_id", "EHCP", "ref", ref="ehcps", required=True, on_delete="CASCADE"),
        Field("learner_id", "Learner", "learner", form=False),
        Field("advice_type", "Advice", "choice",
              ("Educational", "Educational psychology", "Health", "Social care",
               "Parent/carer", "Young person", "Other"), required=True),
        Field("adviser", "From"),
        Field("requested_on", "Requested", "date", required=True, default=_today),
        Field("due_on", "Due", "date", help="Left blank: 6 weeks after the request"),
        Field("received_on", "Received", "date"),
        Field("summary", "Summary", "long", listed=False),
    ),
)


def _check_review(values: dict, old: dict | None) -> None:
    plan = _ehcp_learner(values, old)
    if not plan.get("final_date"):
        raise ValidationError("Annual reviews are for issued plans - this EHCP has no final "
                              "plan date yet.")
    merged = {**(old or {}), **values}
    meeting = r.to_date(r.parse_date(merged.get("meeting_date")))
    if meeting and meeting < date.fromisoformat(plan["final_date"]):
        raise ValidationError("The review meeting can't be before the plan was issued.")
    for k in ("report_sent", "la_decision"):
        got = r.to_date(r.parse_date(merged.get(k)))
        if meeting and got and got < meeting:
            raise ValidationError(f"{REVIEWS.fields_by_name[k].label} can't be before the meeting.")


def _after_review(conn, row: dict, _old: dict | None) -> None:
    latest = conn.execute("SELECT MAX(meeting_date) FROM annual_reviews WHERE ehcp_id = ?",
                          (row["ehcp_id"],)).fetchone()[0]
    conn.execute("UPDATE ehcps SET last_review_date = ?, updated_at = datetime('now') "
                 "WHERE id = ?", (latest, row["ehcp_id"]))


def _review_due(row: dict, key: str, weeks: int) -> str:
    meeting = r.to_date(row.get("meeting_date"))
    if not meeting or row.get(key):
        return ""
    due = dates.add_weeks(meeting, weeks)
    return f"{dates.uk(due)}{' OVERDUE' if due < date.today() else ''}"


REVIEWS = RecordType(
    key="annual_reviews", title="Annual Reviews", singular="annual review",
    order_by="meeting_date DESC", check=_check_review, after_save=_after_review,
    after_commit=learners.platform_hook("review_saved"),
    filters=("outcome",),
    describe=lambda row: f"Annual review {dates.uk(r.to_date(row.get('meeting_date')))}",
    computed=(("Report due", lambda row: _review_due(row, "report_sent", REPORT_WEEKS)),
              ("LA decision due", lambda row: _review_due(row, "la_decision", LA_DECISION_WEEKS))),
    fields=(
        Field("ehcp_id", "EHCP", "ref", ref="ehcps", required=True, on_delete="CASCADE"),
        Field("learner_id", "Learner", "learner", form=False),
        Field("meeting_date", "Meeting", "date", required=True, default=_today),
        Field("attendees", "Who attended", listed=False),
        Field("recommendation", "Recommendation", "choice", ("Maintain", "Amend", "Cease")),
        Field("report_sent", "Report sent to LA", "date"),
        Field("la_decision", "LA decision", "date"),
        Field("outcome", "LA decided", "choice", ("Maintain", "Amend", "Cease", "Pending"),
              default="Pending"),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def _check_dispute(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if merged.get("status") != "Open" and not merged.get("closed_on"):
        values["closed_on"] = _today()
    raised = r.to_date(r.parse_date(merged.get("raised_on")))
    closed = r.to_date(r.parse_date(values.get("closed_on") or merged.get("closed_on")))
    if raised and closed and closed < raised:
        raise ValidationError("It can't be closed before it was raised.")


DISPUTES = RecordType(
    key="disputes", title="Complaints, Mediation & Tribunals", singular="case",
    order_by="status DESC, raised_on DESC", check=_check_dispute, filters=("kind", "status"),
    describe=lambda row: f"{row.get('kind')}: {row.get('about')}",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("kind", "Type", "choice",
              ("Complaint", "Disagreement resolution", "Mediation", "Tribunal appeal"),
              required=True),
        Field("about", "About", required=True),
        Field("raised_on", "Raised", "date", required=True, default=_today),
        Field("hearing_date", "Hearing / meeting", "date"),
        Field("status", "Status", "choice",
              ("Open", "Resolved", "Upheld", "Not upheld", "Withdrawn"), required=True,
              default="Open"),
        Field("closed_on", "Closed", "date", listed=False),
        Field("outcome", "Outcome", "long", listed=False),
    ),
)


def open_plans() -> list[dict]:
    return [row for row in r.list_records(EHCPS) if row["stage"] not in CLOSED]


def timeliness() -> dict:
    """20-week performance for plans issued: count, on time, late, and the
    open requests already past 20 weeks."""
    rows = r.list_records(EHCPS)
    issued = [x for x in rows if x.get("final_date")]
    on_time = [x for x in issued
               if date.fromisoformat(x["final_date"]) <=
               dates.add_weeks(date.fromisoformat(x["request_date"]), FINAL_WEEKS)]
    overdue = [x for x in rows if x["stage"] not in CLOSED and not x.get("final_date")
               and dates.add_weeks(date.fromisoformat(x["request_date"]), FINAL_WEEKS)
               < date.today()]
    return {"issued": len(issued), "on_time": len(on_time),
            "percent": round(100 * len(on_time) / len(issued)) if issued else None,
            "overdue_open": overdue}
