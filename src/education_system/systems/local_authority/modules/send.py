"""SEND: EHC needs assessments, EHC plans, tribunal appeals and high-needs
top-up funding (SEND Code of Practice 0-25, 2015).

Timescales from the request for an assessment:

* 6 weeks to decide whether to assess (and tell the parent if not);
* 16 weeks to tell the parent if, after assessing, no plan will be issued;
* 20 weeks to issue the final EHC plan; the parent has 15 days to comment
  on the draft before it's finalised.

EHC plans: reviewed at least every 12 months; at a phase transfer the
amended plan naming the new school must be final by 15 February of the
transfer year (31 March for a move into post-16). Ceasing a plan needs a
reason. Issuing a final plan from an assessment opens the plan, and the
child's SEN status follows the request and the plan.

Tribunals: an appeal is lodged within two months of the decision, or one
month of a mediation certificate if that's later; a mediation certificate is
needed unless the appeal is only about the school or setting named.

Top-ups: one live top-up per child at a time, for an open setting, ending
after it starts.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.local_authority.core import dates
from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.local_authority.infrastructure import database as db
from education_system.systems.local_authority.modules import children, schools

DECIDE_WEEKS, NO_PLAN_WEEKS, FINAL_WEEKS = 6, 16, 20
COMMENT_DAYS = 15
REQUESTERS = ("Parent", "Young person", "School / college", "Early years setting",
              "Health", "Social care", "Other")
ASSESS = ("Pending", "Agreed to assess", "Refused to assess")
PLAN_DECISIONS = ("Pending", "Issue a plan", "No plan - SEN support")
NEEDS = ("Specific learning difficulty", "Moderate learning difficulty",
         "Severe learning difficulty", "Profound and multiple learning difficulty",
         "Social, emotional and mental health", "Speech, language and communication needs",
         "Hearing impairment", "Vision impairment", "Multi-sensory impairment",
         "Physical disability", "Autistic spectrum disorder", "Other difficulty / disability")


def _weeks(row: dict, n: int) -> date | None:
    got = r.to_date(row.get("received_on"))
    return got + timedelta(weeks=n) if got else None


def request_next_step(row: dict) -> tuple[str, date | None]:
    """(what's next, by when) for an open request; ("", None) when done."""
    if row.get("status") == "Closed":
        return "", None
    if row.get("assess_decision") in (None, "", "Pending"):
        return "Decide whether to assess", _weeks(row, DECIDE_WEEKS)
    if row["assess_decision"] == "Refused to assess":
        return "", None
    if row.get("plan_decision") in (None, "", "Pending"):
        return "Decide whether to issue a plan", _weeks(row, NO_PLAN_WEEKS)
    if row["plan_decision"] == "Issue a plan" and not row.get("final_issued_on"):
        return "Issue the final EHC plan", _weeks(row, FINAL_WEEKS)
    return "", None


def _check_request(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    got = r.to_date(merged.get("received_on"))
    if got and got > date.today():
        raise ValidationError("A request can't be received in the future.")
    for key in ("decided_on", "draft_issued_on", "final_issued_on"):
        d = r.to_date(merged.get(key))
        if d and got and d < got:
            raise ValidationError("Decisions and plans come after the request.")
        if d and d > date.today():
            raise ValidationError("Those dates can't be in the future.")
    if merged.get("assess_decision") not in (None, "", "Pending") and \
            not merged.get("decided_on"):
        values["decided_on"] = date.today().isoformat()
    if merged.get("assess_decision") != "Agreed to assess" and \
            merged.get("plan_decision") not in (None, "", "Pending"):
        raise ValidationError("The plan decision follows an agreement to assess.")
    final = r.to_date(merged.get("final_issued_on"))
    draft = r.to_date(merged.get("draft_issued_on"))
    if final:
        if merged.get("plan_decision") != "Issue a plan":
            raise ValidationError("A final plan needs the decision to issue a plan.")
        if not draft:
            raise ValidationError("A draft plan comes first (the parent has 15 days to "
                                  "comment).")
        if final < draft + timedelta(days=COMMENT_DAYS):
            raise ValidationError(f"The parent has {COMMENT_DAYS} days to comment on the "
                                  f"draft: the final plan can't be issued before "
                                  f"{dates.uk(draft + timedelta(days=COMMENT_DAYS))}.")
        if not merged.get("setting_id"):
            raise ValidationError("A final plan names the school or setting (section I).")
    done = (merged.get("assess_decision") == "Refused to assess"
            or merged.get("plan_decision") == "No plan - SEN support" or final)
    values["status"] = "Closed" if done else "Open"


def _after_request(conn, row: dict, old: dict | None) -> None:
    lid = row["learner_id"]
    if old is None:
        conn.execute("UPDATE learners SET sen_status = 'EHC needs assessment' WHERE id = ? "
                     "AND sen_status IN ('No SEN', 'SEN Support')", (lid,))
    if row.get("final_issued_on") and not (old or {}).get("final_issued_on"):
        issued = date.fromisoformat(row["final_issued_on"])
        conn.execute("INSERT INTO ehc_plans (learner_id, request_id, issued_on, setting_id, "
                     "primary_need, next_review, status) VALUES (?, ?, ?, ?, ?, ?, 'Active')",
                     (lid, row["id"], issued.isoformat(), row.get("setting_id"),
                      row.get("primary_need"), dates.add_months(issued, 12).isoformat()))
        conn.execute("UPDATE learners SET sen_status = 'EHC plan' WHERE id = ?", (lid,))
        conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, action, "
                     "summary) VALUES ('system', 'ehc_plans', last_insert_rowid(), ?, "
                     "'added', 'EHC plan issued')", (lid,))
    elif row["status"] == "Closed" and (old or {}).get("status") != "Closed" and \
            not row.get("final_issued_on"):
        conn.execute("UPDATE learners SET sen_status = 'SEN Support' WHERE id = ? AND "
                     "sen_status = 'EHC needs assessment'", (lid,))


def _next(row: dict) -> str:
    what, due = request_next_step(row)
    if not what:
        return ""
    return f"{what} by {dates.uk(due)}" + (" - OVERDUE" if due and due < date.today() else "")


def _weeks_taken(row: dict) -> str:
    got, final = r.to_date(row.get("received_on")), r.to_date(row.get("final_issued_on"))
    if not (got and final):
        return ""
    weeks = (final - got).days / 7
    return f"{weeks:.1f}" + (" (late)" if weeks > FINAL_WEEKS else "")


EHC_REQUESTS = RecordType(
    after_commit=children.platform_hook("ehc_request_saved"),
    key="ehc_requests", title="EHC Needs Assessments", singular="assessment request",
    order_by="received_on DESC, id DESC", check=_check_request, after_save=_after_request,
    filters=("assess_decision", "status"),
    describe=lambda row: f"EHC request: {children.child_name(row.get('learner_id'))}",
    computed=(("Next step", _next), ("Weeks to final plan", _weeks_taken)),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("received_on", "Request received", "date", required=True),
        Field("requested_by", "Requested by", "choice", REQUESTERS, required=True),
        Field("assess_decision", "Assessment decision", "choice", ASSESS, required=True,
              default="Pending"),
        Field("decided_on", "Decided", "date", listed=False),
        Field("plan_decision", "Plan decision", "choice", PLAN_DECISIONS, default="Pending",
              listed=False),
        Field("primary_need", "Primary need", "choice", NEEDS, listed=False),
        Field("draft_issued_on", "Draft plan issued", "date", listed=False),
        Field("final_issued_on", "Final plan issued", "date", listed=False),
        Field("setting_id", "School / setting named", "ref", ref="schools",
              on_delete="SET NULL", listed=False),
        Field("caseworker", "Caseworker"),
        Field("status", "Status", "choice", ("Open", "Closed"), form=False),
        Field("notes", "Notes", "long", listed=False),
        # Set by the platform for a notification from a linked school.
        Field("source_system", "Notified by (platform)", form=False, listed=False),
        Field("transition_id", "Platform notification", form=False, listed=False),
    ),
)


# ── EHC plans ───────────────────────────────────────────────────────

PLAN_STATUSES = ("Active", "Ceased", "Transferred out")
CEASE_REASONS = ("No longer needed", "Moved to another authority", "Left education / "
                 "employment (16-25)", "Reached 25", "Other")


def phase_transfer_deadline(row: dict, on: date | None = None) -> date | None:
    """When the amended plan for the next phase must be final, if this child
    moves phase at the end of the current school year."""
    child = r.get(children.CHILDREN, row["learner_id"]) if row.get("learner_id") else None
    if child is None:
        return None
    on = on or date.today()
    year = children.year_group(r.to_date(child["dob"]), on)
    nxt = dates.school_year_start(on).year + 1
    if year in ("Year 2", "Year 6", "Year 9"):   # infant/junior, primary/secondary, middle
        return date(nxt, 2, 15)
    if year == "Year 11":
        return date(nxt, 3, 31)
    return None


def _check_plan(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    issued = r.to_date(merged.get("issued_on"))
    if issued and issued > date.today():
        raise ValidationError("A plan can't be issued in the future.")
    last = r.to_date(merged.get("last_review")) or issued
    if r.to_date(merged.get("last_review")) and issued and \
            r.to_date(merged["last_review"]) < issued:
        raise ValidationError("A review can't be before the plan was issued.")
    if last:
        limit = dates.add_months(last, 12)
        current = r.to_date(merged.get("next_review"))
        if current is None or current > limit or "last_review" in values and \
                values["last_review"] != (old or {}).get("last_review"):
            values["next_review"] = limit.isoformat()
    if merged.get("status") == "Ceased" and not merged.get("cease_reason"):
        raise ValidationError("Give the reason the plan is ceasing.")
    if merged.get("status") == "Active":
        with db.connect() as conn:
            dupe = conn.execute("SELECT 1 FROM ehc_plans WHERE learner_id = ? AND status = "
                                "'Active' AND id IS NOT ?",
                                (merged["learner_id"], (old or {}).get("id"))).fetchone()
        if dupe:
            raise ValidationError("The child already has an active EHC plan: amend that one.")


def _after_plan(conn, row: dict, old: dict | None) -> None:
    status = "EHC plan" if row["status"] == "Active" else "SEN Support"
    if old is None or old.get("status") != row["status"]:
        conn.execute("UPDATE learners SET sen_status = ? WHERE id = ?",
                     (status, row["learner_id"]))


def _plan_flag(row: dict) -> str:
    if row.get("status") != "Active":
        return ""
    out = []
    nxt = r.to_date(row.get("next_review"))
    if nxt:
        out.append(f"Review {dates.uk(nxt)}" + (" OVERDUE" if nxt < date.today() else ""))
    pt = phase_transfer_deadline(row)
    if pt:
        out.append(f"Phase transfer final by {dates.uk(pt)}")
    return " · ".join(out)


EHC_PLANS = RecordType(
    after_commit=children.platform_hook("ehc_plan_saved"),
    key="ehc_plans", title="EHC Plans", singular="EHC plan",
    order_by="next_review, id", check=_check_plan, after_save=_after_plan,
    filters=("primary_need", "status"),
    describe=lambda row: f"EHC plan: {children.child_name(row.get('learner_id'))}",
    computed=(("Setting", lambda row: schools.school_name(row.get("setting_id"))),
              ("Due", _plan_flag)),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("request_id", "From assessment", "ref", ref="ehc_requests",
              on_delete="SET NULL", form=False, listed=False),
        Field("issued_on", "Issued", "date", required=True),
        Field("setting_id", "School / setting (section I)", "ref", ref="schools",
              on_delete="SET NULL", listed=False),
        Field("primary_need", "Primary need", "choice", NEEDS),
        Field("last_review", "Last annual review", "date", listed=False),
        Field("next_review", "Next review", "date", listed=False),
        Field("personal_budget", "Personal budget", "money", listed=False),
        Field("caseworker", "Caseworker", listed=False),
        Field("status", "Status", "choice", PLAN_STATUSES, required=True, default="Active"),
        Field("cease_reason", "Reason ceased", "choice", CEASE_REASONS, listed=False),
    ),
)


# ── tribunals ───────────────────────────────────────────────────────

APPEAL_TYPES = ("Refusal to assess", "Refusal to issue a plan",
                "Contents of the plan (sections B, F and I)",
                "School or setting named only (section I)", "Decision to cease the plan")
TRIBUNAL_OUTCOMES = ("Pending", "Conceded by LA", "Withdrawn", "Upheld", "Partly upheld",
                     "Dismissed")


def lodge_by(row: dict) -> date | None:
    decided = r.to_date(row.get("decision_on"))
    if decided is None:
        return None
    by = dates.add_months(decided, 2)
    cert = r.to_date(row.get("mediation_certificate_on"))
    return max(by, dates.add_months(cert, 1)) if cert else by


def _check_tribunal(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    decided = r.to_date(merged.get("decision_on"))
    lodged = r.to_date(merged.get("lodged_on"))
    if merged.get("appeal_type") != APPEAL_TYPES[3] and not merged.get(
            "mediation_certificate_on"):
        raise ValidationError("A mediation certificate is needed unless the appeal is only "
                              "about the school or setting named.")
    if lodged and decided and lodged < decided:
        raise ValidationError("An appeal is lodged after the decision.")
    hearing = r.to_date(merged.get("hearing_on"))
    if merged.get("outcome") in ("Upheld", "Partly upheld", "Dismissed") and \
            (hearing is None or hearing > date.today()):
        raise ValidationError("Give the date of the hearing that decided it.")


TRIBUNALS = RecordType(
    key="tribunals", title="SEND Tribunal Appeals", singular="tribunal appeal",
    order_by="lodged_on DESC, id DESC", check=_check_tribunal, filters=("appeal_type",
                                                                        "outcome"),
    describe=lambda row: f"Tribunal: {children.child_name(row.get('learner_id'))}",
    computed=(("Lodge by", lambda row: dates.uk(lodge_by(row))),),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("appeal_type", "Appeal about", "choice", APPEAL_TYPES, required=True),
        Field("decision_on", "LA decision letter", "date", required=True),
        Field("mediation_certificate_on", "Mediation certificate", "date", listed=False),
        Field("lodged_on", "Lodged", "date"),
        Field("hearing_on", "Hearing", "date"),
        Field("outcome", "Outcome", "choice", TRIBUNAL_OUTCOMES, required=True,
              default="Pending"),
        Field("notes", "Notes", "long", listed=False),
    ),
)


# ── high-needs top-ups ──────────────────────────────────────────────

def _check_topup(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    start, end = r.to_date(merged.get("start_date")), r.to_date(merged.get("end_date"))
    if start and end and end <= start:
        raise ValidationError("A top-up ends after it starts.")
    if float(merged.get("annual_amount") or 0) <= 0:
        raise ValidationError("The annual amount must be above zero.")
    setting = r.get(schools.SCHOOLS, int(merged["setting_id"]))
    if (old is None or "setting_id" in values and values["setting_id"] != old.get(
            "setting_id")) and setting["status"] == "Closed":
        raise ValidationError(f"{setting['name']} is closed.")
    with db.connect() as conn:
        clash = conn.execute(
            "SELECT 1 FROM topups WHERE learner_id = ? AND id IS NOT ? AND "
            "start_date <= COALESCE(?, '9999-12-31') AND COALESCE(end_date, '9999-12-31') >= ?",
            (merged["learner_id"], (old or {}).get("id"),
             end.isoformat() if end else None, start.isoformat())).fetchone()
    if clash:
        raise ValidationError("That overlaps another top-up for the child: end it first.")


def live_topups(on: date | None = None) -> list[dict]:
    on = on or date.today()
    return [t for t in r.list_records(TOPUPS)
            if (r.to_date(t["start_date"]) or on) <= on
            and (r.to_date(t.get("end_date")) is None or r.to_date(t["end_date"]) >= on)]


TOPUPS = RecordType(
    key="topups", title="High Needs Top-ups", singular="top-up",
    order_by="start_date DESC, id DESC", check=_check_topup,
    describe=lambda row: f"Top-up: {children.child_name(row.get('learner_id'))}",
    computed=(("Setting", lambda row: schools.school_name(row.get("setting_id"))),
              ("Monthly", lambda row: f"£{float(row.get('annual_amount') or 0) / 12:,.2f}")),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("setting_id", "Setting", "ref", ref="schools", required=True, listed=False),
        Field("start_date", "From", "date", required=True),
        Field("end_date", "To", "date"),
        Field("annual_amount", "Annual top-up", "money", required=True),
        Field("band", "Band / element", listed=False),
    ),
)
