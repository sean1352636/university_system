"""School admissions: applications and offers, admission appeals, and the
in-year fair access protocol (School Admissions Code 2021 and School
Admission Appeals Code 2022).

Applications:

* three rounds - Reception and Year 7 (the normal admissions round, by entry
  year) and in-year; one live application per child per round and year;
* the child must be the right age for the round (Reception: 4 by the 31
  August before entry; Year 7: 11), unless admission outside the normal age
  group has been agreed;
* up to three different, open preferences of the right phase;
* normal-round closing dates: 31 October before entry for Year 7, 15 January
  of the entry year for Reception; later is marked late;
* normal-round offers are made on national offer day (1 March for
  secondary, 16 April for primary, or the next working day) - not before;
  an in-year decision is due within 15 school days of the application;
* an offer names a school; the basis follows the preference it was (or an
  allocated nearest school with a place); a school can't be offered beyond
  its admission number for the round except by fair access or an appeal;
* Accepted / Declined only after an offer; an in-year application with no
  place is Refused (with a right of appeal).

Appeals: for a preference school that wasn't offered. Normal-round appeals
are lodged within 20 school days of the offer and heard within 40 school
days of that deadline; in-year appeals are heard within 30 school days of
lodging; the decision letter goes within 5 school days of the hearing. An
upheld appeal makes that school the offer.

Fair access: the panel aims to secure a place within 20 school days of the
referral; an allocation names an open school.
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

ROUNDS = ("Reception (normal round)", "Year 7 (normal round)", "In-year")
RECEPTION, YEAR7, IN_YEAR = ROUNDS
ROUND_YEAR = {RECEPTION: "Reception", YEAR7: "Year 7"}
ROUND_PHASES = {
    RECEPTION: {"Primary", "All-through", "Special"},
    YEAR7: {"Secondary", "All-through", "Middle", "Special"},
    IN_YEAR: {"Primary", "Middle", "Secondary", "All-through", "Special", "Post-16"},
}
BASES = ("1st preference", "2nd preference", "3rd preference",
         "Allocated - nearest school with a place", "Fair access", "Appeal upheld")
STATUSES = ("Received", "Offered", "Accepted", "Declined", "Refused", "Withdrawn")
LIVE = ("Received", "Offered", "Accepted")
OVER_PAN_BASES = frozenset({"Fair access", "Appeal upheld"})
IN_YEAR_DECISION_DAYS = 15


def _working_day(d: date) -> date:
    return dates.next_weekday(d)


def closing_date(round_: str, entry_year: int) -> date | None:
    if round_ == YEAR7:
        return date(entry_year - 1, 10, 31)
    if round_ == RECEPTION:
        return date(entry_year, 1, 15)
    return None


def offer_day(round_: str, entry_year: int) -> date | None:
    if round_ == YEAR7:
        return _working_day(date(entry_year, 3, 1))
    if round_ == RECEPTION:
        return _working_day(date(entry_year, 4, 16))
    return None


def decision_due(row: dict) -> date | None:
    if row.get("round") == IN_YEAR:
        got = r.to_date(row.get("received_on"))
        return dates.school_day(got, IN_YEAR_DECISION_DAYS) if got else None
    if row.get("entry_year"):
        return offer_day(row["round"], int(row["entry_year"]))
    return None


def offers_made(school_id: int, round_: str, entry_year: int | None,
                excluding: int | None = None) -> int:
    with db.connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM applications WHERE offered_school_id = ? AND round = ? "
            "AND entry_year IS ? AND status IN ('Offered', 'Accepted') AND id IS NOT ?",
            (school_id, round_, entry_year, excluding)).fetchone()[0]


def preferences(row: dict) -> list[int]:
    return [row[k] for k in ("pref1_id", "pref2_id", "pref3_id") if row.get(k)]


def _check_application(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    child = r.get(children.CHILDREN, int(merged["learner_id"]))
    round_ = merged.get("round")
    received = r.to_date(merged.get("received_on"))
    if received and received > date.today():
        raise ValidationError("An application can't be received in the future.")
    entry = merged.get("entry_year")
    if round_ == IN_YEAR:
        values["entry_year"] = entry = None
        values["late"] = 0
    else:
        if not entry:
            raise ValidationError("Give the year of entry (the September the child starts).")
        entry = int(entry)
        expected = ROUND_YEAR[round_]
        actual = children.year_group(r.to_date(child["dob"]), date(entry, 9, 1))
        if actual != expected and not merged.get("outside_age_group"):
            raise ValidationError(f"{children.child_name(child['id'])} would be in {actual} "
                                  f"in September {entry}, not {expected}. Tick 'admission "
                                  "outside the normal age group agreed' if that's been "
                                  "decided.")
        close = closing_date(round_, entry)
        values["late"] = 1 if received and close and received > close else 0
    prefs = preferences(merged)
    if not prefs:
        raise ValidationError("Give at least the first preference.")
    if len(set(prefs)) != len(prefs):
        raise ValidationError("Each preference must be a different school.")
    if old is None or any(k in values and values[k] != old.get(k)
                          for k in ("pref1_id", "pref2_id", "pref3_id", "round")):
        for sid in prefs:
            s = r.get(schools.SCHOOLS, sid)
            if s["status"] == "Closed":
                raise ValidationError(f"{s['name']} is closed.")
            if s["phase"] not in ROUND_PHASES[round_]:
                raise ValidationError(f"{s['name']} is a {s['phase'].lower()} school: it "
                                      f"doesn't admit for {round_}.")
    with db.connect() as conn:
        dupe = conn.execute(
            "SELECT id FROM applications WHERE learner_id = ? AND round = ? AND entry_year IS ? "
            "AND status IN ('Received', 'Offered', 'Accepted') AND id IS NOT ?",
            (child["id"], round_, entry, (old or {}).get("id"))).fetchone()
    status, was = merged.get("status"), (old or {}).get("status")
    if dupe and status in LIVE:
        raise ValidationError(f"There's already a live {round_} application for this child "
                              f"(#{dupe[0]}).")
    offered = merged.get("offered_school_id")
    if status == "Offered" or (offered and status in ("Accepted", "Declined")):
        if not offered:
            raise ValidationError("Choose the school offered.")
        offered = int(offered)
        basis = merged.get("offer_basis")
        if offered in prefs and basis not in OVER_PAN_BASES:
            basis = BASES[prefs.index(offered)]
        elif offered not in prefs and basis in BASES[:3]:
            basis = BASES[3]
        values["offer_basis"] = basis or BASES[3]
        on = r.to_date(merged.get("offered_on")) or date.today()
        values["offered_on"] = on.isoformat()
        if on > date.today():
            raise ValidationError("An offer can't be dated in the future.")
        nod = offer_day(round_, entry) if entry else None
        if nod and on < nod and (was != "Offered" or "offered_on" in values):
            raise ValidationError(f"Normal-round offers go out on national offer day "
                                  f"({dates.uk(nod)}), not before.")
        changed = old is None or old.get("offered_school_id") != offered or \
            was not in ("Offered", "Accepted")
        if changed:
            s = r.get(schools.SCHOOLS, offered)
            if s["status"] == "Closed":
                raise ValidationError(f"{s['name']} is closed.")
            if values["offer_basis"] not in OVER_PAN_BASES and s.get("pan") is not None and \
                    offers_made(offered, round_, entry, (old or {}).get("id")) >= int(s["pan"]):
                raise ValidationError(f"{s['name']} has offered all {s['pan']} places for this "
                                      "round. Offer another school, or place the child through "
                                      "fair access.")
    if status in ("Accepted", "Declined") and not offered:
        raise ValidationError("Only an offer can be accepted or declined.")
    if status == "Refused" and round_ != IN_YEAR:
        raise ValidationError("A normal-round applicant is offered a place (allocated if "
                              "need be), not refused.")
    if status in ("Received", "Refused", "Withdrawn"):
        values["offered_school_id"] = None
        values["offer_basis"] = None
        values["offered_on"] = None


def _school(row: dict, key: str) -> str:
    return schools.school_name(row.get(key))


APPLICATIONS = RecordType(
    after_commit=children.platform_hook("application_saved"),
    key="applications", title="Admission Applications", singular="application",
    order_by="received_on DESC, id DESC", check=_check_application,
    filters=("round", "status"),
    describe=lambda row: f"{children.child_name(row.get('learner_id'))} - {row.get('round')}"
                         + (f" {row['entry_year']}" if row.get("entry_year") else ""),
    computed=(("1st preference", lambda row: _school(row, "pref1_id")),
              ("Offered", lambda row: _school(row, "offered_school_id")),
              ("Decision due", lambda row: dates.uk(decision_due(row)))),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("round", "Round", "choice", ROUNDS, required=True, default=IN_YEAR),
        Field("entry_year", "Year of entry", "int",
              help="Normal round: the September the child starts, e.g. 2027"),
        Field("outside_age_group", "Admission outside the normal age group agreed", "bool",
              listed=False),
        Field("received_on", "Received", "date", required=True),
        Field("late", "Late", "bool", form=False),
        Field("pref1_id", "1st preference", "ref", ref="schools", required=True,
              listed=False),
        Field("pref2_id", "2nd preference", "ref", ref="schools", on_delete="SET NULL",
              listed=False),
        Field("pref3_id", "3rd preference", "ref", ref="schools", on_delete="SET NULL",
              listed=False),
        Field("sibling_school_id", "Sibling attends", "ref", ref="schools",
              on_delete="SET NULL", listed=False),
        Field("distance_miles", "Distance to 1st preference (miles)", "number", listed=False),
        Field("priority_notes", "Priority evidence (medical / social, faith ...)", "long",
              listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="Received"),
        Field("offered_school_id", "School offered", "ref", ref="schools", listed=False),
        Field("offer_basis", "Offer basis", "choice", BASES, listed=False,
              help="Worked out from the preferences when blank"),
        Field("offered_on", "Offered on", "date", listed=False),
        Field("notes", "Notes", "long", listed=False),
        # The school place handed to a school on this platform.
        Field("place_transition_id", "Platform place", form=False, listed=False),
    ),
)


# ── appeals ─────────────────────────────────────────────────────────

def lodge_deadline(app: dict) -> date | None:
    if app.get("round") == IN_YEAR:
        return None
    offered = r.to_date(app.get("offered_on"))
    return dates.school_day(offered + timedelta(days=1), 20) if offered else None


def hearing_due(row: dict, app: dict | None = None) -> date | None:
    app = app or r.get(APPLICATIONS, row["application_id"]) or {}
    lodged = r.to_date(row.get("lodged_on"))
    if lodged is None:
        return None
    if app.get("round") == IN_YEAR:
        return dates.school_day(lodged + timedelta(days=1), 30)
    deadline = lodge_deadline(app)
    base = max(deadline, lodged) if deadline else lodged
    return dates.school_day(base + timedelta(days=1), 40)


def _check_appeal(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    app = r.get(APPLICATIONS, int(merged["application_id"])) \
        if merged.get("application_id") else None
    if app is None:
        raise ValidationError("Choose the application.")
    values["learner_id"] = app["learner_id"]
    school = int(merged["school_id"])
    if school not in preferences(app):
        raise ValidationError("An appeal is for one of the schools the parent applied for.")
    if school == app.get("offered_school_id"):
        raise ValidationError("That school was offered - there's nothing to appeal.")
    if app["status"] not in ("Offered", "Accepted", "Declined", "Refused"):
        raise ValidationError("Appeals follow a decision: this application hasn't had one.")
    lodged = r.to_date(merged.get("lodged_on"))
    if lodged and lodged > date.today():
        raise ValidationError("An appeal can't be lodged in the future.")
    with db.connect() as conn:
        dupe = conn.execute("SELECT 1 FROM appeals WHERE application_id = ? AND school_id = ? "
                            "AND outcome IN ('Pending', 'Upheld') AND id IS NOT ?",
                            (app["id"], school, (old or {}).get("id"))).fetchone()
    if dupe:
        raise ValidationError("There's already an appeal for that school on this application.")
    deadline = lodge_deadline(app)
    values["late"] = 1 if lodged and deadline and lodged > deadline else 0
    hearing = r.to_date(merged.get("hearing_on"))
    if hearing and lodged and hearing < lodged:
        raise ValidationError("The hearing can't be before the appeal was lodged.")
    outcome = merged.get("outcome")
    if outcome in ("Upheld", "Dismissed"):
        if not hearing:
            raise ValidationError("An appeal is decided at a hearing: give the hearing date.")
        if hearing > date.today():
            raise ValidationError("The hearing hasn't happened yet.")


def _after_appeal(conn, row: dict, old: dict | None) -> None:
    if row["outcome"] == "Upheld" and (old or {}).get("outcome") != "Upheld":
        conn.execute("UPDATE applications SET offered_school_id = ?, offer_basis = "
                     "'Appeal upheld', offered_on = ?, status = 'Offered', "
                     "updated_at = datetime('now') WHERE id = ?",
                     (row["school_id"], row.get("hearing_on") or date.today().isoformat(),
                      row["application_id"]))
        conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, action, "
                     "summary) VALUES ('system', 'applications', ?, ?, 'updated', ?)",
                     (row["application_id"], row["learner_id"],
                      "Place offered after an upheld appeal: "
                      + schools.school_name(row["school_id"])))


def _letter_due(row: dict) -> str:
    hearing = r.to_date(row.get("hearing_on"))
    if not hearing or row.get("letter_sent_on") or row.get("outcome") in ("Pending",
                                                                        "Withdrawn"):
        return ""
    due = dates.school_day(hearing + timedelta(days=1), 5)
    return dates.uk(due) + (" - OVERDUE" if due < date.today() else "")


APPEALS = RecordType(
    key="appeals", title="Admission Appeals", singular="appeal",
    order_by="lodged_on DESC, id DESC", check=_check_appeal, after_save=_after_appeal,
    filters=("outcome",),
    describe=lambda row: f"Appeal: {children.child_name(row.get('learner_id'))} for "
                         f"{schools.school_name(row.get('school_id'))}",
    computed=(("School", lambda row: schools.school_name(row.get("school_id"))),
              ("Hear by", lambda row: dates.uk(hearing_due(row))),
              ("Decision letter due", _letter_due)),
    fields=(
        Field("learner_id", "Child", "learner", form=False),
        Field("application_id", "Application", "ref", ref="applications", required=True,
              listed=False),
        Field("school_id", "School appealed for", "ref", ref="schools", required=True,
              listed=False),
        Field("lodged_on", "Lodged", "date", required=True),
        Field("late", "Late", "bool", form=False, listed=False),
        Field("hearing_on", "Hearing", "date"),
        Field("outcome", "Outcome", "choice", ("Pending", "Upheld", "Dismissed", "Withdrawn"),
              required=True, default="Pending"),
        Field("letter_sent_on", "Decision letter sent", "date", listed=False),
        Field("grounds", "Grounds", "long", listed=False),
    ),
)


# ── fair access ─────────────────────────────────────────────────────

FAIR_ACCESS_CATEGORIES = (
    "Out of education for four weeks or more", "Permanently excluded / at risk",
    "Returning from the criminal justice system", "Gypsy, Roma or Traveller",
    "Refugee or asylum seeker", "Homeless", "Known to the police or youth justice",
    "Young carer", "SEN or disability (no EHC plan)", "Medical needs",
    "Previously looked after", "Other")
FAP_TARGET_DAYS = 20


def fap_target(row: dict) -> date | None:
    got = r.to_date(row.get("referred_on"))
    return dates.school_day(got, FAP_TARGET_DAYS) if got else None


def _check_fap(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    got = r.to_date(merged.get("referred_on"))
    if got and got > date.today():
        raise ValidationError("A referral can't be dated in the future.")
    decision = merged.get("decision")
    if decision == "Allocated":
        if not merged.get("school_id"):
            raise ValidationError("Choose the school allocated.")
        s = r.get(schools.SCHOOLS, int(merged["school_id"]))
        if s["status"] == "Closed":
            raise ValidationError(f"{s['name']} is closed.")
        if not merged.get("panel_on"):
            raise ValidationError("Give the date of the panel that allocated the place.")
    on_roll = r.to_date(merged.get("on_roll_on"))
    if on_roll and decision != "Allocated":
        raise ValidationError("Only an allocated child can be on roll.")
    if on_roll and on_roll > date.today():
        raise ValidationError("The on-roll date can't be in the future.")


def _after_fap(conn, row: dict, old: dict | None) -> None:
    if row.get("on_roll_on") and not (old or {}).get("on_roll_on"):
        conn.execute("UPDATE learners SET school_id = ?, education = 'At school', "
                     "updated_at = datetime('now') WHERE id = ?",
                     (row["school_id"], row["learner_id"]))


def _fap_flag(row: dict) -> str:
    target = fap_target(row)
    if row.get("on_roll_on") or row.get("decision") == "Not eligible" or target is None:
        return ""
    return dates.uk(target) + (" - OVERDUE" if target < date.today() else "")


FAIR_ACCESS = RecordType(
    after_commit=children.platform_hook("fair_access_saved"),
    key="fair_access", title="Fair Access Panel", singular="fair access referral",
    order_by="referred_on DESC, id DESC", check=_check_fap, after_save=_after_fap,
    filters=("category", "decision"),
    describe=lambda row: f"Fair access: {children.child_name(row.get('learner_id'))}",
    computed=(("School", lambda row: schools.school_name(row.get("school_id"))),
              ("Place by (target)", _fap_flag)),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("referred_on", "Referred", "date", required=True),
        Field("category", "Fair access category", "choice", FAIR_ACCESS_CATEGORIES,
              required=True),
        Field("panel_on", "Panel date", "date"),
        Field("decision", "Decision", "choice", ("Pending", "Allocated", "Not eligible"),
              required=True, default="Pending"),
        Field("school_id", "School allocated", "ref", ref="schools", on_delete="SET NULL",
              listed=False),
        Field("on_roll_on", "On roll from", "date", listed=False),
        Field("notes", "Notes", "long", listed=False),
        # The school place handed to a school on this platform.
        Field("place_transition_id", "Platform place", form=False, listed=False),
    ),
)
