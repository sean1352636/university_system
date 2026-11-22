"""Education welfare: attendance casework, penalty notices, children missing
education (CME) and elective home education (EHE).

Attendance cases (Working together to improve school attendance, 2024):
support first, then formal steps; persistent absence is under 90%
attendance and severe absence under 50%; a case is reviewed at least every
six weeks and closes with an outcome.

Penalty notices (national framework from August 2024):

* for unauthorised absence (incl. term-time holiday) the threshold is 10
  sessions in a rolling 10 school weeks; for an excluded child seen in a
  public place, within the first five days of the exclusion;
* £80 if paid within 21 days, £160 if paid within 28 days; a second notice
  to the same parent for the same child within three years is £160 with no
  reduced rate; a third within three years can't be issued (consider other
  action);
* unpaid after 28 days: prosecute for the offence, or withdraw.

CME: an open case records the enquiries made; closing it needs the outcome
and date, and a child found on roll / home educated / moved updates the
child's record.

EHE: a child with an EHC plan at a special school arranged by the authority
can't be taken off roll to home educate without the authority's consent;
the arrangements are reviewed at least yearly; a school attendance order
follows only where education is found not to be suitable.
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

# ── attendance casework ─────────────────────────────────────────────

STAGES = ("Support (early help)", "Attendance contract", "Notice to improve",
          "Education supervision order", "Penalty notice", "Prosecution")
PERSISTENT, SEVERE = 90.0, 50.0
REVIEW_WEEKS = 6


def absence_band(pct) -> str:
    if pct is None:
        return ""
    pct = float(pct)
    return "Severe" if pct < SEVERE else "Persistent" if pct < PERSISTENT else ""


def _check_case(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    pct = merged.get("attendance_pct")
    if pct is not None and not 0 <= float(pct) <= 100:
        raise ValidationError("Attendance is a percentage, 0-100.")
    got = r.to_date(merged.get("referred_on"))
    if got and got > date.today():
        raise ValidationError("A referral can't be dated in the future.")
    if merged.get("status") == "Closed":
        if not merged.get("outcome"):
            raise ValidationError("Record the outcome before closing the case.")
    else:
        with db.connect() as conn:
            dupe = conn.execute("SELECT 1 FROM attendance_cases WHERE learner_id = ? AND "
                                "status = 'Open' AND id IS NOT ?",
                                (merged["learner_id"], (old or {}).get("id"))).fetchone()
        if dupe:
            raise ValidationError("The child already has an open attendance case.")
    if merged.get("stage") in ("Penalty notice", "Prosecution") and not merged.get("school_id"):
        raise ValidationError("Formal action needs the school whose register shows the absence.")
    last = r.to_date(merged.get("last_reviewed_on")) or got
    if last and (merged.get("next_review") in (None, "") or "last_reviewed_on" in values
                 and values.get("last_reviewed_on") != (old or {}).get("last_reviewed_on")):
        values["next_review"] = dates.add_weeks(last, REVIEW_WEEKS).isoformat()
    nxt = r.to_date(values.get("next_review", merged.get("next_review")))
    if last and nxt and nxt > dates.add_weeks(last, REVIEW_WEEKS):
        raise ValidationError(f"Review at least every {REVIEW_WEEKS} weeks.")


ATTENDANCE_CASES = RecordType(
    after_commit=children.platform_hook("attendance_saved"),
    key="attendance_cases", title="Attendance Cases", singular="attendance case",
    order_by="referred_on DESC, id DESC", check=_check_case, filters=("stage", "status"),
    describe=lambda row: f"Attendance case: {children.child_name(row.get('learner_id'))}",
    computed=(("School", lambda row: schools.school_name(row.get("school_id"))),
              ("Band", lambda row: absence_band(row.get("attendance_pct")))),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("school_id", "School", "ref", ref="schools", on_delete="SET NULL",
              listed=False),
        Field("referred_on", "Referred", "date", required=True),
        Field("attendance_pct", "Attendance %", "number"),
        Field("stage", "Stage", "choice", STAGES, required=True, default=STAGES[0]),
        Field("officer", "Attendance officer"),
        Field("barriers", "Barriers / support offered", "long", listed=False),
        Field("last_reviewed_on", "Last reviewed", "date", listed=False),
        Field("next_review", "Next review", "date"),
        Field("status", "Status", "choice", ("Open", "Closed"), required=True,
              default="Open"),
        Field("outcome", "Outcome", "long", listed=False),
        # Set by the platform for a notification from a linked school.
        Field("source_system", "Notified by (platform)", form=False, listed=False),
        Field("transition_id", "Platform notification", form=False, listed=False),
    ),
)


# ── penalty notices ─────────────────────────────────────────────────

PN_REASONS = ("Unauthorised absence", "Term-time holiday", "Excluded child in a public place")
PN_STATUSES = ("Issued", "Paid", "Withdrawn", "Prosecution")
PN_LOW, PN_HIGH = 80.0, 160.0
PN_THRESHOLD = 10
PN_YEARS = 3


def _prior_notices(row: dict, conn) -> int:
    issued = r.to_date(row.get("issued_on")) or date.today()
    since = date(issued.year - PN_YEARS, issued.month, min(issued.day, 28)).isoformat()
    return conn.execute(
        "SELECT COUNT(*) FROM penalty_notices WHERE learner_id = ? AND parent_id = ? AND "
        "status != 'Withdrawn' AND issued_on >= ? AND issued_on <= ? AND id IS NOT ?",
        (row["learner_id"], row["parent_id"], since, issued.isoformat(),
         row.get("id"))).fetchone()[0]


def amount_due(row: dict, paid_on: date | None = None) -> float:
    issued = r.to_date(row.get("issued_on"))
    if row.get("second_notice") or issued is None:
        return PN_HIGH
    paid_on = paid_on or date.today()
    return PN_LOW if (paid_on - issued).days <= 21 else PN_HIGH


def _check_notice(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    parent = r.get(children.CONTACTS, int(merged["parent_id"])) if merged.get("parent_id") \
        else None
    if parent is None or parent["learner_id"] != int(merged["learner_id"]):
        raise ValidationError("Choose the parent from the child's parents and carers.")
    if not parent.get("parental_responsibility"):
        raise ValidationError(f"{parent['name']} isn't recorded as having parental "
                              "responsibility.")
    issued = r.to_date(merged.get("issued_on"))
    if issued and issued > date.today():
        raise ValidationError("A notice can't be issued in the future.")
    if merged.get("reason") in PN_REASONS[:2]:
        if int(merged.get("sessions_missed") or 0) < PN_THRESHOLD:
            raise ValidationError(f"The threshold is {PN_THRESHOLD} sessions of unauthorised "
                                  "absence in 10 school weeks.")
    if old is None or "parent_id" in values and values["parent_id"] != old.get("parent_id"):
        with db.connect() as conn:
            prior = _prior_notices({**merged, "id": (old or {}).get("id")}, conn)
        if prior >= 2:
            raise ValidationError("This parent has had two notices for this child in the last "
                                  "three years: a third can't be issued - consider other "
                                  "action (e.g. prosecution or a parenting order).")
        values["second_notice"] = 1 if prior == 1 else 0
    status = merged.get("status")
    if status == "Paid":
        paid = r.to_date(merged.get("paid_on")) or date.today()
        if issued and (paid - issued).days > 28:
            raise ValidationError("A notice can only be paid within 28 days; after that it's "
                                  "prosecution or withdrawal.")
        values["paid_on"] = paid.isoformat()
        values["amount_paid"] = amount_due({**merged, **values}, paid)
    else:
        values["paid_on"] = None
        values["amount_paid"] = None
    if status in ("Withdrawn", "Prosecution") and not merged.get("notes"):
        raise ValidationError(f"Record why ({status.lower()}) in the notes.")


def _pn_flag(row: dict) -> str:
    issued = r.to_date(row.get("issued_on"))
    if row.get("status") != "Issued" or issued is None:
        return ""
    end = issued + timedelta(days=28)
    return f"Pay by {dates.uk(end)}" + (" - UNPAID" if end < date.today() else "")


PENALTY_NOTICES = RecordType(
    after_commit=children.platform_hook("penalty_notice_saved"),
    key="penalty_notices", title="Penalty Notices", singular="penalty notice",
    order_by="issued_on DESC, id DESC", check=_check_notice, filters=("reason", "status"),
    describe=lambda row: f"Penalty notice: {children.child_name(row.get('learner_id'))}",
    computed=(("Rate", lambda row: "£160 (second notice)" if row.get("second_notice")
               else "£80 / £160"), ("Payment", _pn_flag)),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("parent_id", "Parent", "ref", ref="contacts", required=True, listed=False),
        Field("school_id", "School", "ref", ref="schools", on_delete="SET NULL",
              listed=False),
        Field("reason", "Reason", "choice", PN_REASONS, required=True),
        Field("sessions_missed", "Unauthorised sessions (10 weeks)", "int", listed=False),
        Field("issued_on", "Issued", "date", required=True),
        Field("second_notice", "Second notice in 3 years", "bool", form=False,
              listed=False),
        Field("status", "Status", "choice", PN_STATUSES, required=True, default="Issued"),
        Field("paid_on", "Paid on", "date", listed=False),
        Field("amount_paid", "Amount paid", "money", form=False),
        Field("notes", "Notes", "long", listed=False),
    ),
)


# ── children missing education ──────────────────────────────────────

CME_SOURCES = ("School (removed from roll)", "School (unexplained absence)",
               "Admissions", "Health", "Police", "Social care", "Housing", "Neighbour / public",
               "Other")
CME_OUTCOMES = ("Open", "Found - on a school roll", "Found - home educated",
                "Moved to another authority", "Moved abroad", "Closed - other")


def _check_cme(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    got = r.to_date(merged.get("reported_on"))
    if got and got > date.today():
        raise ValidationError("A report can't be dated in the future.")
    outcome = merged.get("status")
    if outcome != "Open":
        if not merged.get("enquiries"):
            raise ValidationError("Record the enquiries made before closing the case.")
        if not merged.get("closed_on"):
            values["closed_on"] = date.today().isoformat()
        if outcome == CME_OUTCOMES[1] and not merged.get("found_school_id"):
            raise ValidationError("Choose the school the child was found on roll at.")
    else:
        values["closed_on"] = None


def _after_cme(conn, row: dict, old: dict | None) -> None:
    if row["status"] == (old or {}).get("status"):
        return
    sql = {
        CME_OUTCOMES[1]: ("UPDATE learners SET education = 'At school', school_id = ? "
                          "WHERE id = ?", (row.get("found_school_id"), row["learner_id"])),
        CME_OUTCOMES[2]: ("UPDATE learners SET education = 'Elective home education', "
                          "school_id = NULL WHERE id = ?", (row["learner_id"],)),
        CME_OUTCOMES[3]: ("UPDATE learners SET status = 'Moved out of area' WHERE id = ?",
                          (row["learner_id"],)),
        CME_OUTCOMES[4]: ("UPDATE learners SET status = 'Moved out of area' WHERE id = ?",
                          (row["learner_id"],)),
    }.get(row["status"])
    if row["status"] == "Open":
        sql = ("UPDATE learners SET education = 'Not in education', school_id = NULL "
               "WHERE id = ? AND education IN ('At school', 'Alternative provision')",
               (row["learner_id"],))
    if sql:
        conn.execute(sql[0], sql[1])


def _cme_open(row: dict) -> str:
    got = r.to_date(row.get("reported_on"))
    if row.get("status") != "Open" or got is None:
        return ""
    return f"{dates.weekdays_between(got, date.today())} school days"


CME = RecordType(
    after_commit=children.platform_hook("cme_saved"),
    key="cme", title="Children Missing Education", singular="CME case",
    order_by="reported_on DESC, id DESC", check=_check_cme, after_save=_after_cme,
    filters=("status",),
    describe=lambda row: f"CME: {children.child_name(row.get('learner_id'))}",
    computed=(("Open for", _cme_open),),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("reported_on", "Reported", "date", required=True),
        Field("source", "Reported by", "choice", CME_SOURCES, required=True),
        Field("last_school_id", "Last school", "ref", ref="schools", on_delete="SET NULL",
              listed=False),
        Field("enquiries", "Enquiries made", "long", listed=False,
              help="Home visit, school, health, housing, other LAs, police ..."),
        Field("status", "Outcome", "choice", CME_OUTCOMES, required=True, default="Open"),
        Field("found_school_id", "Found on roll at", "ref", ref="schools",
              on_delete="SET NULL", listed=False),
        Field("closed_on", "Closed", "date"),
        # Set by the platform for a notification from a linked school.
        Field("source_system", "Notified by (platform)", form=False, listed=False),
        Field("transition_id", "Platform notification", form=False, listed=False),
    ),
)


# ── elective home education ─────────────────────────────────────────

SUITABILITY = ("Not yet assessed", "Suitable", "Concerns", "Not suitable")
SAO_STAGES = ("None", "Notice served", "School attendance order issued", "Order revoked")
EHE_STATUSES = ("Active", "Returned to school", "Moved away", "Over compulsory school age")
CONSENT = ("Not needed", "Requested", "Given", "Refused")


def _needs_consent(merged: dict) -> bool:
    child = r.get(children.CHILDREN, int(merged["learner_id"]))
    school = r.get(schools.SCHOOLS, int(merged["from_school_id"])) \
        if merged.get("from_school_id") else None
    return bool(child and child["sen_status"] == "EHC plan" and school
                and school["phase"] == "Special")


def _check_ehe(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    got = r.to_date(merged.get("notified_on"))
    if got and got > date.today():
        raise ValidationError("A notification can't be dated in the future.")
    if _needs_consent(merged):
        if merged.get("consent") in (None, "", "Not needed"):
            values["consent"] = "Requested"
        if merged.get("status") == "Active" and \
                values.get("consent", merged.get("consent")) != "Given":
            raise ValidationError("The child has an EHC plan and attends a special school the "
                                  "authority arranged: they can't come off roll to be home "
                                  "educated until the authority consents.")
    elif merged.get("consent") in (None, ""):
        values["consent"] = "Not needed"
    if merged.get("sao_stage") not in (None, "None", "Order revoked") and \
            merged.get("suitability") != "Not suitable":
        raise ValidationError("A school attendance order follows only where the education "
                              "isn't suitable.")
    last = r.to_date(merged.get("last_review")) or r.to_date(merged.get("first_contact_on"))
    if last:
        nxt = dates.add_months(last, 12)
        current = r.to_date(merged.get("next_review"))
        if current is None or current > nxt or "last_review" in values:
            values["next_review"] = nxt.isoformat()


def _after_ehe(conn, row: dict, old: dict | None) -> None:
    if row["status"] == "Active" and (old or {}).get("status") != "Active":
        conn.execute("UPDATE learners SET education = 'Elective home education', "
                     "school_id = NULL, updated_at = datetime('now') WHERE id = ?",
                     (row["learner_id"],))


EHE = RecordType(
    after_commit=children.platform_hook("ehe_saved"),
    key="ehe", title="Elective Home Education", singular="EHE record",
    order_by="notified_on DESC, id DESC", check=_check_ehe, after_save=_after_ehe,
    filters=("suitability", "status"),
    describe=lambda row: f"EHE: {children.child_name(row.get('learner_id'))}",
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("notified_on", "Notified", "date", required=True),
        Field("from_school_id", "Came off roll at", "ref", ref="schools",
              on_delete="SET NULL", listed=False),
        Field("consent", "LA consent to deregister", "choice", CONSENT, listed=False,
              help="Needed for a child with an EHC plan at a special school"),
        Field("first_contact_on", "First contact", "date", listed=False),
        Field("last_review", "Last review", "date", listed=False),
        Field("next_review", "Next review", "date"),
        Field("suitability", "Education suitable?", "choice", SUITABILITY, required=True,
              default=SUITABILITY[0]),
        Field("sao_stage", "School attendance order", "choice", SAO_STAGES, default="None",
              listed=False),
        Field("status", "Status", "choice", EHE_STATUSES, required=True, default="Active"),
        Field("notes", "Notes", "long", listed=False),
        # Set by the platform for a notification from a linked school.
        Field("source_system", "Notified by (platform)", form=False, listed=False),
        Field("transition_id", "Platform notification", form=False, listed=False),
    ),
)
