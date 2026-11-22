"""Medical screen.

The old First Aid window is the "First aid" tab, with its toolbar (Severity
filter, RIDDOR only, Hospital only; Apply, New, Edit, Delete, Refresh), its
columns (ID, Date, Time, Pupil, Yr, Injury, Severity, Outcome, P, H, R) and
its incident dialog. The old Emergency & Drills window is the "Emergencies &
drills" tab (Kind, Type and Status filters, Outstanding only; Apply, New,
Edit, Close, Delete, Refresh; ID, Date, Kind, Type, Min, Pups, Miss, Inj,
Outcome, Status). Added to first aid: staff and visitor accidents, Parents
told, E-mail family, RIDDOR reported (with the 10-day deadline), Summary,
View and Export.

New tabs: Who has what (every member of staff: conditions, allergies, where
the emergency medication is and what to do), Conditions (with healthcare plans
and their reviews), Allergies (and the trip / kitchen list), Medicines (stored
in school, consent, expiry, stock, return, ask the family to replace),
Medicines given (the log), Due and Reports. Rules are in
:mod:`modules.medical.domain.medical`.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any, Callable

from education_system.systems.secondary.modules.medical.domain import medical as M
from education_system.systems.secondary.modules.send.gui.send_page import (
    YEARS,
    Table,
    TabbedPage,
    changed,
    filled,
    num,
)
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log

_SEV_TAGS = {"sev_Life-threatening": "#ffcccc", "sev_Severe": "#ffe0b3",
             "sev_Critical": "#ffcccc", "sev_Moderate": "#ffffb3"}


def _getter(obj: Any) -> Callable[..., Any]:
    return (lambda k, d="": getattr(obj, k) if obj is not None and getattr(obj, k) is not None
            else d)


def _who(obj: Any) -> str:
    return f"{obj.pupil_name} ({obj.admission_no})" if getattr(obj, "pupil_id", None) else ""


def _bools(v: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: v[k] for k in keys if k in v}


def _incident_fields(i: M.Incident | None) -> list:
    g = _getter(i)
    head = [] if i else [
        ("person_type", "Person", "Pupil", list(M.PERSON_TYPES)),
        ("pupil_id", "Pupil ID / admission no. (pupils)", "", None),
        ("person_name", "Name (staff / visitor)", "", None)]
    return head + [
        ("incident_date", "Date (blank = today)", g("incident_date"), None),
        ("incident_time", "Time (HH:MM)", g("incident_time"), None),
        ("location", "Location", g("location"), None),
        ("injury_type", "Injury type", g("injury_type", M.INJURY_TYPES[0]),
         list(M.INJURY_TYPES)),
        ("severity", "Severity", g("severity", M.SEVERITIES[0]), list(M.SEVERITIES)),
        ("body_part", "Body part", g("body_part"), None),
        ("description", "Description", g("description"), "text"),
        ("treatment", "Treatment", g("treatment"), "text"),
        ("treated_by", "Treated by", g("treated_by"), None),
        ("outcome", "Outcome", g("outcome", M.OUTCOMES[0]), list(M.OUTCOMES)),
        ("parent_contacted", "Parent contacted", bool(i and i.parent_contacted), "check"),
        ("parent_contact_time", "Parent contact time", g("parent_contact_time"), None),
        ("hospital_referral", "Hospital referral", bool(i and i.hospital_referral), "check"),
        ("accident_book_ref", "Accident book ref", g("accident_book_ref"), None),
        ("riddor_reportable", "RIDDOR reportable", bool(i and i.riddor_reportable), "check"),
        ("follow_up", "Follow-up", g("follow_up"), "text"),
        ("notes", "Notes", g("notes"), "text"),
    ]


_INCIDENT_BOOLS = ("parent_contacted", "hospital_referral", "riddor_reportable")


def _event_fields(e: M.Emergency | None) -> list:
    g = _getter(e)
    return [
        ("kind", "Kind", g("kind", M.EVENT_KINDS[0]), list(M.EVENT_KINDS)),
        ("event_type", "Type", g("event_type", M.EMERGENCY_TYPES[0]), list(M.EMERGENCY_TYPES)),
        ("event_date", "Date (blank = today)", g("event_date"), None),
        ("start_time", "Start (HH:MM)", g("start_time"), None),
        ("end_time", "End (HH:MM)", g("end_time"), None),
        ("duration_min", "Duration min (blank = from times)", g("duration_min"), None),
        ("location", "Location", g("location"), None),
        ("trigger", "Trigger", g("trigger"), None),
        ("reported_by", "Reported by", g("reported_by"), None),
        ("incident_commander", "Incident commander", g("incident_commander"), None),
        ("pupils_evacuated", "Pupils evacuated", g("pupils_evacuated"), None),
        ("staff_evacuated", "Staff evacuated", g("staff_evacuated"), None),
        ("missing_count", "Missing", g("missing_count", 0), None),
        ("injuries_count", "Injuries", g("injuries_count", 0), None),
        ("emergency_services", "Emergency services called", bool(e and e.emergency_services),
         "check"),
        ("services_attended", "Services attended", g("services_attended"), None),
        ("outcome", "Outcome", g("outcome", M.EVENT_OUTCOMES[0]), list(M.EVENT_OUTCOMES)),
        ("status", "Status", g("status", M.EVENT_STATUSES[0]), list(M.EVENT_STATUSES)),
        ("lessons_learned", "Lessons learned", g("lessons_learned"), "text"),
        ("follow_up_actions", "Follow-up actions", g("follow_up_actions"), "text"),
        ("notes", "Notes", g("notes"), "text"),
    ]


def _condition_fields(c: M.Condition | None) -> list:
    g = _getter(c)
    head = [] if c else [("pupil_id", "Pupil ID / admission no.", "", None)]
    return head + [
        ("condition", "Condition", g("condition"), ("edit", M.CONDITIONS)),
        ("severity", "Severity", g("severity", M.CONDITION_SEVERITIES[0]),
         list(M.CONDITION_SEVERITIES)),
        ("symptoms", "Symptoms", g("symptoms"), "text"),
        ("triggers", "Triggers", g("triggers"), "text"),
        ("what_to_do", "What to do", g("what_to_do"), "text"),
        ("emergency_medication", "Emergency medication", g("emergency_medication"), None),
        ("medication_location", "Where it's kept", g("medication_location"), None),
        ("has_ihp", "Individual healthcare plan", bool(c and c.has_ihp), "check"),
        ("ihp_agreed_on", "IHP agreed on", g("ihp_agreed_on"), None),
        ("ihp_review_date", "IHP review date (blank = 12 months)", g("ihp_review_date"), None),
        ("diagnosed_by", "Diagnosed by", g("diagnosed_by"), None),
        ("status", "Status", g("status", M.CONDITION_STATUSES[0]), list(M.CONDITION_STATUSES)),
        ("notes", "Notes", g("notes"), "text"),
    ]


def _allergy_fields(a: M.Allergy | None) -> list:
    g = _getter(a)
    head = [] if a else [("pupil_id", "Pupil ID / admission no.", "", None)]
    return head + [
        ("allergen", "Allergen", g("allergen"), None),
        ("kind", "Kind", g("kind", M.ALLERGY_KINDS[0]), list(M.ALLERGY_KINDS)),
        ("reaction", "Reaction", g("reaction"), "text"),
        ("severity", "Severity", g("severity", M.CONDITION_SEVERITIES[1]),
         list(M.CONDITION_SEVERITIES)),
        ("anaphylaxis", "Anaphylaxis", bool(a and a.anaphylaxis), "check"),
        ("auto_injector", "Carries an auto-injector", bool(a and a.auto_injector), "check"),
        ("dietary", "Catering note (blank = No <allergen>)", g("dietary"), None),
        ("action", "What to do", g("action"), "text"),
        ("status", "Status", g("status", M.CONDITION_STATUSES[0]), list(M.CONDITION_STATUSES)),
        ("notes", "Notes", g("notes"), "text"),
    ]


def _medicine_fields(m: M.Medicine | None) -> list:
    g = _getter(m)
    head = [] if m else [("pupil_id", "Pupil ID / admission no.", "", None)]
    return head + [
        ("name", "Medicine", g("name"), None),
        ("form", "Form", g("form", M.MEDICINE_FORMS[0]), list(M.MEDICINE_FORMS)),
        ("strength", "Strength", g("strength"), None),
        ("dose", "Dose", g("dose"), None),
        ("frequency", "When", g("frequency"), None),
        ("purpose", "What for", g("purpose"), None),
        ("emergency", "Emergency medication", bool(m and m.emergency), "check"),
        ("controlled", "Controlled drug", bool(m and m.controlled), "check"),
        ("prescribed", "Prescribed", bool(m.prescribed) if m else True, "check"),
        ("location", "Where it's kept", g("location"), None),
        ("quantity", "Quantity", g("quantity"), None),
        ("expiry_date", "Expiry date", g("expiry_date"), None),
        ("batch", "Batch", g("batch"), None),
        ("consent_on", "Consent form date", g("consent_on"), None),
        ("consent_by", "Consent given by", g("consent_by"), None),
        ("notes", "Notes", g("notes"), "text"),
    ]


_MED_BOOLS = ("emergency", "controlled", "prescribed")


class MedicalPage(TabbedPage):
    TITLE = "Medical"
    TABS = ("Who has what", "Conditions", "Allergies", "Medicines", "Medicines given",
            "First aid", "Emergencies & drills", "Due", "Reports")

    def __init__(self, parent, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        activity_log.record("medical.view")
        super().__init__(parent, principal=principal, state=state, open_pupil=open_pupil,
                         editor=M.is_editor(principal))
        self._summary()

    def _summary(self) -> None:
        try:
            s = M.summary()
        except M.PermissionDenied:
            return
        self.summary_var.set(f"Conditions: {s['conditions']} ({s['pupils_with_conditions']} "
                             f"pupils, {s['ihps']} IHPs)    Allergies: {s['allergies']} "
                             f"({s['anaphylaxis']} anaphylaxis)    Medicines in school: "
                             f"{s['medicines']} ({s['expiring']} expiring)    Doses today: "
                             f"{s['doses_today']}")

    def refresh_all(self) -> None:
        super().refresh_all()
        self._summary()

    # ── Who has what (every member of staff) ─────────────────────────

    def _tab_who_has_what(self, tab):
        self.note(tab, "Every pupil with a medical condition or allergy: what it is, where "
                       "their emergency medication is kept and what to do.")
        bar = self.bar(tab)
        run = lambda: self._run("Who has what")  # noqa: E731
        self.cl_year = self.combo(bar, "Year:", "cl_year", ["", *YEARS], run, 5)
        self.cl_form = self.entry(bar, "Form:", "cl_form", run, 8)
        self.cl_serious = self.check(bar, "Severe / life-threatening only", "cl_serious", run)
        self.buttons(bar, (("Refresh", run), ("What to do", self.what_to_do),
                           ("Open pupil", lambda: self.open_selected(self.care)),
                           ("Export CSV…", lambda: self.save_csv(
                               "care_list.csv", lambda p: M.export_care_list(
                                   p, actor=self.principal), "pupil"))))
        self.care = Table(tab, [("pupil", "Pupil", 190), ("yr", "Yr", 35),
                                ("worst", "Severity", 110), ("cond", "Conditions", 200),
                                ("allergy", "Allergies", 170), ("med", "Medication", 200),
                                ("ihp", "IHP", 40), ("do", "What to do", 320)], height=18,
                          stretch={"do", "cond"}, tags=_SEV_TAGS)
        self.care.on_double(self.what_to_do)

        def refresh() -> None:
            self.care.fill(M.care_list(actor=self.principal,
                                       year_group=self.cl_year.get() or None,
                                       form_group=self.cl_form.get() or None,
                                       serious_only=self.cl_serious.get()),
                           lambda r: r["pupil_id"], lambda r: (
                f"{r['pupil_name']} ({r['admission_no']})", r["year_group"], r["worst"],
                "; ".join(r["conditions"]), "; ".join(r["allergies"]),
                "; ".join(r["medication"]), "yes" if r["ihp"] else "",
                " | ".join(r["what_to_do"])), lambda r: f"sev_{r['worst']}")
        return refresh

    def what_to_do(self) -> None:
        r = self.pick(self.care, "What to do")
        if r is None:
            return
        lines = [f"{r['pupil_name']} ({r['admission_no']}), Year {r['year_group']}",
                 f"Most serious: {r['worst']}" + ("  ·  ANAPHYLAXIS" if r["anaphylaxis"] else "")
                 + ("  ·  has an IHP" if r["ihp"] else ""), ""]
        for label, key in (("Conditions", "conditions"), ("Allergies", "allergies"),
                           ("Medication (where kept)", "medication")):
            lines += [f"{label}:"] + [f"  {x}" for x in r[key]] + [""]
        lines += ["What to do:"] + [f"  • {x}" for x in r["what_to_do"]]
        self.text("What to do", "\n".join(lines))

    # ── Conditions ───────────────────────────────────────────────────

    def _tab_conditions(self, tab):
        bar = self.bar(tab)
        run = lambda: self._run("Conditions")  # noqa: E731
        self.co_year = self.combo(bar, "Year:", "co_year", ["", *YEARS], run, 5)
        self.co_sev = self.combo(bar, "Severity:", "co_sev", ["", *M.CONDITION_SEVERITIES],
                                 run, 15)
        self.co_status = self.combo(bar, "Status:", "co_status", ["", *M.CONDITION_STATUSES],
                                    run, 10)
        self.buttons(bar, (("New", self.new_condition, True),
                           ("Edit", self.edit_condition, True),
                           ("IHP reviewed…", self.ihp_reviewed, True),
                           ("Delete", self.delete_condition, True),
                           ("View", self.view_condition), ("History", lambda: self.history(
                               self.cond, "condition", "condition_id")),
                           ("Open pupil", lambda: self.open_selected(self.cond))))
        self.cond = Table(tab, [("id", "ID", 50), ("pupil", "Pupil", 190), ("yr", "Yr", 35),
                                ("cond", "Condition", 180), ("sev", "Severity", 110),
                                ("med", "Emergency medication", 170),
                                ("where", "Kept", 120), ("ihp", "IHP review", 90),
                                ("status", "Status", 70)], stretch={"pupil", "cond"},
                          tags=_SEV_TAGS)
        self.cond.on_double(self.view_condition)

        def refresh() -> None:
            today = M._today().isoformat()
            self.cond.fill(M.list_conditions(year_group=self.co_year.get() or None,
                                             severity=self.co_sev.get() or None,
                                             status=self.co_status.get() or None),
                           lambda c: c.condition_id, lambda c: (
                c.condition_id, _who(c), c.pupil_year, c.condition, c.severity,
                c.emergency_medication or "", c.medication_location or "",
                c.ihp_review_date or "", c.status),
                lambda c: "bad" if c.has_ihp and c.ihp_review_date and c.ihp_review_date
                < today else f"sev_{c.severity}")
        return refresh

    def new_condition(self) -> None:
        self.form("New condition", _condition_fields(None),
                  lambda v: M.add_condition(filled(v) | _bools(v, ("has_ihp",)),
                                            actor=self.principal),
                  note="Severe and life-threatening conditions need what to do; emergency "
                       "medication needs where it's kept.")

    def edit_condition(self) -> None:
        c = self.pick(self.cond, "Edit condition")
        if c:
            self.form(f"Condition #{c.condition_id} - {c.pupil_name}", _condition_fields(c),
                      lambda v: M.update_condition(c.condition_id, changed(c, v),
                                                   actor=self.principal))

    def ihp_reviewed(self) -> None:
        c = self.pick(self.cond, "IHP reviewed")
        if c:
            self.form(f"Healthcare plan reviewed - {c.pupil_name}", [
                ("on", "Reviewed on (blank = today)", "", None),
                ("next", "Next review (blank = 12 months)", "", None),
                ("note", "Note", "", "text")],
                lambda v: M.review_ihp(c.condition_id, actor=self.principal,
                                       reviewed_on=v["on"] or None,
                                       next_review=v["next"] or None, note=v["note"]))

    def delete_condition(self) -> None:
        c = self.pick(self.cond, "Delete condition")
        if c and self.ask("Delete", f"Delete {c.condition} for {c.pupil_name}?"):
            M.delete_condition(c.condition_id, actor=self.principal)
            self.refresh_all()

    def view_condition(self) -> None:
        c = self.pick(self.cond, "View")
        if c:
            self._view(f"Condition #{c.condition_id}", c, _condition_fields(c))

    def _view(self, title: str, obj: Any, fields: list) -> None:
        lines = [_who(obj), ""] if getattr(obj, "pupil_id", None) else []
        for key, label, *_r in fields:
            v = getattr(obj, key, None)
            if v not in (None, "", False):
                lines.append(f"{label.split(' (')[0]}: {'yes' if v is True else v}")
        self.text(title, "\n".join(lines))

    def history(self, table: Table, item: str, id_attr: str) -> None:
        x = table.selected()
        rows = M.history(x.pupil_id if x else None, item=item if x else None,
                         item_id=getattr(x, id_attr) if x else None)
        self.text("History", self.history_text(rows))

    # ── Allergies ────────────────────────────────────────────────────

    def _tab_allergies(self, tab):
        bar = self.bar(tab)
        run = lambda: self._run("Allergies")  # noqa: E731
        self.al_year = self.combo(bar, "Year:", "al_year", ["", *YEARS], run, 5)
        self.al_kind = self.combo(bar, "Kind:", "al_kind", ["", *M.ALLERGY_KINDS], run, 14)
        self.buttons(bar, (("New", self.new_allergy, True), ("Edit", self.edit_allergy, True),
                           ("Delete", self.delete_allergy, True),
                           ("Trip / kitchen list…", self.trip_list),
                           ("History", lambda: self.history(self.alg, "allergy",
                                                            "allergy_id")),
                           ("Open pupil", lambda: self.open_selected(self.alg)),
                           ("Export CSV…", lambda: self.save_csv(
                               "allergy_list.csv", lambda p: M.export_allergy_list(
                                   p, actor=self.principal), "allergy"))))
        self.alg = Table(tab, [("id", "ID", 50), ("pupil", "Pupil", 190), ("yr", "Yr", 35),
                               ("allergen", "Allergen", 140), ("kind", "Kind", 110),
                               ("sev", "Severity", 110), ("ana", "Anaphylaxis", 80),
                               ("pen", "Pen", 40), ("diet", "Catering", 150),
                               ("do", "What to do", 220)], stretch={"pupil", "do"},
                         tags=_SEV_TAGS)
        self.alg.on_double(self.edit_allergy)

        def refresh() -> None:
            self.alg.fill(M.list_allergies(year_group=self.al_year.get() or None,
                                           kind=self.al_kind.get() or None),
                          lambda a: a.allergy_id, lambda a: (
                a.allergy_id, _who(a), a.pupil_year, a.allergen, a.kind, a.severity,
                "YES" if a.anaphylaxis else "", "yes" if a.auto_injector else "",
                a.dietary or "", a.action or ""), lambda a: f"sev_{a.severity}")
        return refresh

    def new_allergy(self) -> None:
        self.form("New allergy", _allergy_fields(None),
                  lambda v: M.add_allergy(filled(v) | _bools(v, ("anaphylaxis",
                                                                 "auto_injector")),
                                          actor=self.principal),
                  note="Anaphylaxis makes it life-threatening and needs what to do.")

    def edit_allergy(self) -> None:
        a = self.pick(self.alg, "Edit allergy")
        if a:
            self.form(f"Allergy #{a.allergy_id} - {a.pupil_name}", _allergy_fields(a),
                      lambda v: M.update_allergy(a.allergy_id, changed(a, v),
                                                 actor=self.principal))

    def delete_allergy(self) -> None:
        a = self.pick(self.alg, "Delete allergy")
        if a and self.ask("Delete", f"Delete the {a.allergen} allergy for {a.pupil_name}?"):
            M.delete_allergy(a.allergy_id, actor=self.principal)
            self.refresh_all()

    def trip_list(self) -> None:
        pupils = [(p.pupil_id, f"{p.display_name} ({p.admission_no}) Yr{p.year_group}")
                  for p in P.list_pupils()]

        def save(v):
            rows = M.allergy_list(actor=self.principal, pupil_ids=v["ids"] or None,
                                  year_group=v["year"] or None)
            self.text("Allergy list", "\n".join(
                f"{r['pupil_name']} ({r['admission_no']}) Yr{r['year_group']}: "
                f"{r['allergen']} - {r['severity']}"
                + (" - ANAPHYLAXIS" if r["anaphylaxis"] else "")
                + (", carries a pen" if r["auto_injector"] else "")
                + (f"\n    Catering: {r['dietary']}" if r["dietary"] else "")
                + (f"\n    What to do: {r['action']}" if r["action"] else "")
                for r in rows) or "No allergies recorded for these pupils.",
                save_name="allergy_list.txt")
        self.form("Trip / kitchen allergy list", [
            ("ids", "Pupils on the trip (none = all)", [], ("pupils", pupils)),
            ("year", "or a year group", "", ["", *YEARS])], save)

    # ── Medicines ────────────────────────────────────────────────────

    def _tab_medicines(self, tab):
        bar = self.bar(tab)
        run = lambda: self._run("Medicines")  # noqa: E731
        self.me_year = self.combo(bar, "Year:", "me_year", ["", *YEARS], run, 5)
        self.me_status = self.combo(bar, "Status:", "me_status", list(M.MEDICINE_STATUSES),
                                    run, 13, "In school")
        self.me_emerg = self.check(bar, "Emergency only", "me_emerg", run)
        self.buttons(bar, (("New", self.new_medicine, True), ("Edit", self.edit_medicine, True),
                           ("Give a dose…", self.give, True),
                           ("Return / dispose…", self.return_medicine, True),
                           ("Ask family to replace…", self.replace, True),
                           ("Delete", self.delete_medicine, True)))
        bar2 = self.bar(tab)
        self.buttons(bar2, (("View", self.view_medicine),
                            ("History", lambda: self.history(self.med, "medicine",
                                                             "medicine_id")),
                            ("Open pupil", lambda: self.open_selected(self.med))))
        self.med = Table(tab, [("id", "ID", 50), ("pupil", "Pupil", 180), ("yr", "Yr", 35),
                               ("med", "Medicine", 180), ("dose", "Dose", 100),
                               ("when", "When", 100), ("where", "Kept", 140),
                               ("qty", "Qty", 45), ("expiry", "Expiry", 90),
                               ("flags", "", 120)], stretch={"pupil", "med"})
        self.med.on_double(self.give)

        def refresh() -> None:
            self.med.fill(M.list_medicines(year_group=self.me_year.get() or None,
                                           status=self.me_status.get() or None,
                                           emergency=True if self.me_emerg.get() else None),
                          lambda m: m.medicine_id, lambda m: (
                m.medicine_id, _who(m), m.pupil_year, m.label, m.dose, m.frequency or "",
                m.location, num(m.quantity), m.expiry_date,
                " ".join(x for x in ("EXPIRED" if m.expired else "",
                                     "expiring" if m.expiring and not m.expired else "",
                                     "emergency" if m.emergency else "",
                                     "CD" if m.controlled else "") if x)),
                lambda m: "bad" if m.expired else ("warn" if m.expiring or (
                    m.quantity is not None and m.quantity <= M.LOW_STOCK) else None))
        return refresh

    def new_medicine(self) -> None:
        self.form("New medicine in school", _medicine_fields(None),
                  lambda v: M.add_medicine(filled(v) | _bools(v, _MED_BOOLS),
                                           actor=self.principal),
                  note="Needs the parent's written consent. Controlled drugs are kept locked.")

    def edit_medicine(self) -> None:
        m = self.pick(self.med, "Edit medicine")
        if m:
            self.form(f"Medicine #{m.medicine_id} - {m.pupil_name}", _medicine_fields(m),
                      lambda v: M.update_medicine(m.medicine_id, changed(m, v),
                                                  actor=self.principal))

    def view_medicine(self) -> None:
        m = self.pick(self.med, "View")
        if m:
            self._view(f"Medicine #{m.medicine_id}", m, _medicine_fields(m)
                       + [("status", "Status", None, None)])

    def give(self) -> None:
        m = self.med.selected() if hasattr(self, "med") else None
        if m is not None and m.status != "In school":
            m = None
        given = M.doses_today(m.pupil_id, m.medicine_id) if m else []
        note = (f"{m.pupil_name}: {m.label}, {m.dose} {m.frequency or ''}" if m else
                "Not held in school (e.g. a one-off with a parent's verbal consent): give the "
                "pupil and the medicine.")
        if given:
            note += "\n\nAlready given today at " + ", ".join(d.given_at[11:16] for d in given)
        head = [] if m else [("pupil_id", "Pupil ID / admission no.", "", None),
                             ("medicine_name", "Medicine", "", None)]

        def save(v):
            data = filled(v) | _bools(v, ("consent_checked", "refused", "emergency",
                                          "parent_informed"))
            if m:
                data["medicine_id"] = m.medicine_id
            M.give_dose(data, actor=self.principal)
        self.form("Give a medicine", head + [
            ("dose", "Dose (blank = usual)", m.dose if m else "", None),
            ("given_at", "Given at (blank = now)", "", None),
            ("given_by", "Given by", self.principal.username, None),
            ("witnessed_by", "Witnessed by (controlled drugs)", "", None),
            ("reason", "Reason", "", None),
            ("consent_checked", "Consent, name, dose and expiry checked", False, "check"),
            ("refused", "Refused", False, "check"),
            ("emergency", "Emergency use", False, "check"),
            ("parent_informed", "Parent informed", False, "check"),
            ("notes", "Notes", "", "text")], save, note=note)

    def return_medicine(self) -> None:
        m = self.pick(self.med, "Return medicine")
        if m:
            self.form(f"Return / dispose - {m.label}", [
                ("disposed", "Disposed of (not sent home)", False, "check"),
                ("note", "Note", "", "text")],
                lambda v: M.return_medicine(m.medicine_id, actor=self.principal,
                                            disposed=v["disposed"], note=v["note"]))

    def replace(self) -> None:
        m = self.pick(self.med, "Ask to replace")
        if m:
            self.form(f"Ask the family to replace {m.label}", [
                ("note", "Message (optional)", "", "text")],
                lambda v: self.deliver("Ask to replace", M.ask_for_replacement(
                    m.medicine_id, actor=self.principal, note=v["note"])),
                note=f"Expires {m.expiry_date}. E-mailed to contacts with parental "
                     "responsibility.")

    def delete_medicine(self) -> None:
        m = self.pick(self.med, "Delete medicine")
        if m and self.ask("Delete", f"Delete {m.label} for {m.pupil_name}? (Only if entered "
                                    "by mistake - use Return / dispose otherwise.)"):
            M.delete_medicine(m.medicine_id, actor=self.principal)
            self.refresh_all()

    # ── Medicines given ──────────────────────────────────────────────

    def _tab_medicines_given(self, tab):
        bar = self.bar(tab)
        run = lambda: self._run("Medicines given")  # noqa: E731
        self.do_from = self.entry(bar, "From:", "do_from", run, 11)
        self.do_to = self.entry(bar, "To:", "do_to", run, 11)
        self.do_year = self.combo(bar, "Year:", "do_year", ["", *YEARS], run, 5)
        self.buttons(bar, (("Apply", run), ("Give a dose…", self.give, True),
                           ("Delete (entered in error)…", self.delete_dose, True),
                           ("Open pupil", lambda: self.open_selected(self.doses))))
        self.doses = Table(tab, [("id", "ID", 55), ("at", "Given at", 130),
                                 ("pupil", "Pupil", 180), ("yr", "Yr", 35),
                                 ("med", "Medicine", 160), ("dose", "Dose", 90),
                                 ("by", "Given by", 100), ("wit", "Witness", 90),
                                 ("chk", "Consent", 60), ("flags", "", 140)],
                           height=16, stretch={"pupil", "med"})

        def refresh() -> None:
            self.doses.fill(M.list_doses(from_date=self.do_from.get() or None,
                                         to_date=self.do_to.get() or None,
                                         year_group=self.do_year.get() or None, limit=500),
                            lambda d: d.dose_id, lambda d: (
                d.dose_id, d.given_at, _who(d), d.pupil_year, d.medicine_name, d.dose,
                d.given_by, d.witnessed_by or "", "yes" if d.consent_checked else "",
                " ".join(x for x in ("REFUSED" if d.refused else "",
                                     "EMERGENCY" if d.emergency else "",
                                     "parent told" if d.parent_informed else "") if x)),
                lambda d: "bad" if d.refused or d.emergency else None)
        return refresh

    def delete_dose(self) -> None:
        d = self.pick(self.doses, "Delete dose")
        if d:
            self.form(f"Delete dose #{d.dose_id}", [("reason", "Why (required)", "", "text")],
                      lambda v: M.delete_dose(d.dose_id, actor=self.principal,
                                              reason=v["reason"]),
                      note="The stock is put back.")

    # ── First aid (the old First Aid window) ─────────────────────────

    def _tab_first_aid(self, tab):
        bar = self.bar(tab)
        run = lambda: self._run("First aid")  # noqa: E731
        self.fa_sev = self.combo(bar, "Severity:", "fa_sev", ["", *M.SEVERITIES], run, 10)
        self.fa_riddor = self.check(bar, "RIDDOR only", "fa_riddor", run)
        self.fa_hosp = self.check(bar, "Hospital only", "fa_hosp", run)
        self.buttons(bar, (("Apply", run), ("New", self.new_incident, True),
                           ("Edit", self.edit_incident, True),
                           ("Delete", self.delete_incident, True), ("Refresh", run)))
        bar2 = self.bar(tab)
        self.fa_who = self.combo(bar2, "Person:", "fa_who", ["", *M.PERSON_TYPES], run, 9)
        self.fa_from = self.entry(bar2, "From:", "fa_from", run, 11)
        self.fa_to = self.entry(bar2, "To:", "fa_to", run, 11)
        self.buttons(bar2, (("View", self.view_incident),
                            ("Parents told…", self.parents_told, True),
                            ("E-mail family…", self.notify, True),
                            ("RIDDOR reported…", self.riddor, True),
                            ("Summary", self.fa_summary),
                            ("Open pupil", lambda: self.open_selected(self.fa)),
                            ("Export CSV…", lambda: self.save_csv(
                                "first_aid.csv", lambda p: M.export_first_aid(
                                    p, actor=self.principal), "incident"))))
        self.fa = Table(tab, [("id", "ID", 50), ("date", "Date", 90), ("time", "Time", 50),
                              ("pupil", "Pupil", 190), ("yr", "Yr", 35),
                              ("injury", "Injury", 140), ("sev", "Severity", 80),
                              ("outcome", "Outcome", 160), ("p", "P", 25), ("h", "H", 25),
                              ("r", "R", 25)], stretch={"pupil", "outcome"},
                        tags={"sev_Severe": "#ffe0b3", "sev_Critical": "#ffcccc"})
        self.fa.on_double(self.view_incident)

        def refresh() -> None:
            self.fa.fill(M.list_incidents(severity=self.fa_sev.get() or None,
                                          riddor_only=self.fa_riddor.get(),
                                          hospital_only=self.fa_hosp.get(),
                                          person_type=self.fa_who.get() or None,
                                          from_date=self.fa_from.get() or None,
                                          to_date=self.fa_to.get() or None),
                         lambda i: i.incident_id, lambda i: (
                i.incident_id, i.incident_date, i.incident_time or "", i.who,
                i.pupil_year or "", i.injury_type, i.severity, i.outcome,
                "Y" if i.parent_contacted else "", "Y" if i.hospital_referral else "",
                ("Y" if i.riddor_reported_on else "!") if i.riddor_reportable else ""),
                lambda i: "bad" if i.riddor_reportable and not i.riddor_reported_on
                else f"sev_{i.severity}")
        return refresh

    def _check_incident(self, data: dict[str, Any]) -> None:
        warnings = M.check_incident(data)
        if warnings and not self.ask("First aid", "\n\n".join(warnings) + "\n\nSave anyway?"):
            raise M.ValidationError(["Not saved yet - change the details, or Save again and "
                                     "answer Yes"])

    def new_incident(self) -> None:
        def save(v):
            data = filled(v) | _bools(v, _INCIDENT_BOOLS)
            self._check_incident(data)
            i = M.create_incident(data, actor=self.principal)
            if i.pupil_id and not i.parent_contacted and self.ask(
                    "First aid", f"Incident #{i.incident_id} saved.\n\nE-mail the family now?"):
                self.deliver("E-mail family", M.notify_parents(i.incident_id,
                                                               actor=self.principal))
        self.form("New first aid incident", _incident_fields(None), save,
                  note="Head injuries, hospital visits and ambulances: tell the parents the "
                       "same day.")

    def edit_incident(self) -> None:
        i = self.pick(self.fa, "Edit incident")
        if i:
            self.form(f"Incident #{i.incident_id} - {i.who}", _incident_fields(i),
                      lambda v: M.update_incident(i.incident_id, changed(i, v),
                                                  actor=self.principal))

    def view_incident(self) -> None:
        i = self.pick(self.fa, "View")
        if i:
            fields = _incident_fields(i) + [
                ("parent_contact_how", "Parents told how", None, None),
                ("riddor_reported_on", "RIDDOR reported on", None, None),
                ("riddor_reference", "HSE reference", None, None),
                ("created_by", "Recorded by", None, None)]
            self.text(f"Incident #{i.incident_id}", "\n".join(
                [i.who, ""] + [f"{label.split(' (')[0]}: {'yes' if v is True else v}"
                               for key, label, *_r in fields
                               if (v := getattr(i, key, None)) not in (None, "", False)]
                + ([f"RIDDOR due by: {i.riddor_due}"] if i.riddor_due and
                   not i.riddor_reported_on else [])))

    def delete_incident(self) -> None:
        i = self.pick(self.fa, "Delete incident")
        if i:
            self.form(f"Delete incident #{i.incident_id}",
                      [("reason", "Why (required)", "", "text")],
                      lambda v: M.delete_incident(i.incident_id, actor=self.principal,
                                                  reason=v["reason"]))

    def parents_told(self) -> None:
        i = self.pick(self.fa, "Parents told")
        if i:
            self.form(f"Parents told - incident #{i.incident_id}", [
                ("how", "How", "Phone call", list(M.TOLD_HOW)),
                ("when", "When (blank = now)", "", None)],
                lambda v: M.record_parents_told(i.incident_id, actor=self.principal,
                                                how=v["how"], when=v["when"] or None))

    def notify(self) -> None:
        i = self.pick(self.fa, "E-mail family")
        if i:
            self.form(f"E-mail the family - incident #{i.incident_id}", [
                ("note", "Message (optional)", "", "text")],
                lambda v: self.deliver("E-mail family", M.notify_parents(
                    i.incident_id, actor=self.principal, note=v["note"])))

    def riddor(self) -> None:
        i = self.pick(self.fa, "RIDDOR")
        if i:
            self.form(f"RIDDOR reported - incident #{i.incident_id}", [
                ("on", "Reported on (blank = today)", "", None),
                ("ref", "HSE reference (required)", i.riddor_reference or "", None)],
                lambda v: M.record_riddor(i.incident_id, actor=self.principal,
                                          reported_on=v["on"] or None, reference=v["ref"]),
                note=f"Report to the HSE within {M.RIDDOR_DAYS} days"
                     + (f" (by {i.riddor_due})." if i.riddor_due else "."))

    def fa_summary(self) -> None:
        s = M.first_aid_summary(from_date=self.fa_from.get() or None,
                                to_date=self.fa_to.get() or None)
        self.text("First aid summary", "\n".join((
            f"Total: {s['total']}   Pupils: {s['pupils']}   Parents contacted: "
            f"{s['parent_contacted']}   Hospital: {s['hospital']}   RIDDOR: {s['riddor']} "
            f"({s['riddor_outstanding']} still to report)", "",
            "By severity: " + self.counts(s["by_severity"]),
            "By injury: " + self.counts(s["by_injury"]),
            "By outcome: " + self.counts(s["by_outcome"]),
            "By location: " + self.counts(s["by_location"]),
            "By month: " + self.counts(s["by_month"]))), save_name="first_aid_summary.txt")

    # ── Emergencies & drills (the old Emergency & Drills window) ─────

    def _tab_emergencies_drills(self, tab):
        bar = self.bar(tab)
        run = lambda: self._run("Emergencies & drills")  # noqa: E731
        self.em_kind = self.combo(bar, "Kind:", "em_kind", ["", *M.EVENT_KINDS], run, 9)
        self.em_type = self.combo(bar, "Type:", "em_type", ["", *M.EMERGENCY_TYPES], run, 16)
        self.em_status = self.combo(bar, "Status:", "em_status", ["", *M.EVENT_STATUSES], run,
                                    16)
        self.em_out = self.check(bar, "Outstanding only", "em_out", run)
        self.buttons(bar, (("Apply", run), ("New", self.new_event, True),
                           ("Edit", self.edit_event, True), ("Close", self.close_event, True),
                           ("Delete", self.delete_event, True), ("Refresh", run)))
        bar2 = self.bar(tab)
        self.buttons(bar2, (("View", self.view_event),
                            ("Set status…", self.event_status, True),
                            ("Summary", self.em_summary)))
        self.drill_var = ttk.Label(bar2, foreground="#555")
        self.drill_var.pack(side="left", padx=8)
        self.em = Table(tab, [("id", "ID", 50), ("date", "Date", 90), ("kind", "Kind", 70),
                              ("type", "Type", 130), ("min", "Min", 45), ("pups", "Pups", 55),
                              ("miss", "Miss", 45), ("inj", "Inj", 40),
                              ("outcome", "Outcome", 170), ("status", "Status", 130)],
                        stretch={"outcome"})
        self.em.on_double(self.view_event)

        def refresh() -> None:
            self.em.fill(M.list_emergencies(kind=self.em_kind.get() or None,
                                            event_type=self.em_type.get() or None,
                                            status=self.em_status.get() or None,
                                            outstanding_only=self.em_out.get()),
                         lambda e: e.event_id, lambda e: (
                e.event_id, e.event_date, e.kind, e.event_type, num(e.duration_min),
                num(e.pupils_evacuated), e.missing_count, e.injuries_count, e.outcome,
                e.status), lambda e: "bad" if e.missing_count else (
                    "warn" if e.status != "Closed" else None))
            d = M.drills_this_term()
            self.drill_var.configure(text="Fire drill this term: " + (
                f"yes ({d['last']})" if d["this_term"] else
                f"NOT YET (last {d['last'] or 'never'})"))
        return refresh

    def new_event(self) -> None:
        self.form("New emergency / drill", _event_fields(None),
                  lambda v: M.create_emergency(filled(v) | _bools(v, ("emergency_services",)),
                                               actor=self.principal),
                  note="It can't be closed while anyone is missing; Actions outstanding needs "
                       "the follow-up actions.")

    def edit_event(self) -> None:
        e = self.pick(self.em, "Edit event")
        if e:
            self.form(f"Event #{e.event_id}", _event_fields(e),
                      lambda v: M.update_emergency(e.event_id, changed(e, v),
                                                   actor=self.principal))

    def view_event(self) -> None:
        e = self.pick(self.em, "View")
        if e:
            self._view(f"Event #{e.event_id}", e, _event_fields(e))

    def event_status(self) -> None:
        e = self.pick(self.em, "Status")
        if e:
            self.form(f"Status - event #{e.event_id}", [
                ("status", "Status", e.status, list(M.EVENT_STATUSES))],
                lambda v: M.set_emergency_status(e.event_id, v["status"],
                                                 actor=self.principal))

    def close_event(self) -> None:
        e = self.pick(self.em, "Close event")
        if e and self.ask("Close event", f"Close event #{e.event_id}?"):
            M.close_emergency(e.event_id, actor=self.principal)
            self.refresh_all()

    def delete_event(self) -> None:
        e = self.pick(self.em, "Delete event")
        if e and self.ask("Delete event", f"Delete event #{e.event_id}?"):
            M.delete_emergency(e.event_id, actor=self.principal)
            self.refresh_all()

    def em_summary(self) -> None:
        s = M.emergency_summary()
        self.text("Emergency summary", "\n".join((
            f"Total: {s['total']}   Drills: {s['drills']}   Real: {s['real']}   Outstanding: "
            f"{s['outstanding']}", f"Missing: {s['total_missing']}   Injuries: "
            f"{s['total_injuries']}   Emergency services called: {s['services_called']}   "
            f"Average minutes: {num(s['avg_duration_min'])}", "",
            "By type: " + self.counts(s["by_type"]),
            "By outcome: " + self.counts(s["by_outcome"]),
            "By status: " + self.counts(s["by_status"]))))

    # ── Due ──────────────────────────────────────────────────────────

    def _tab_due(self, tab):
        self.note(tab, f"Healthcare plan reviews, medicines expiring in the next "
                       f"{M.EXPIRY_WARNING_DAYS} days or running low, RIDDOR reports, "
                       "outstanding emergency actions and a missing fire drill.")
        self.buttons(self.bar(tab), (("Refresh", lambda: self._run("Due")),
                                     ("Open pupil", lambda: self.open_selected(self.due))))
        self.due = Table(tab, [("due", "Due", 90), ("flag", "", 75), ("who", "Who", 220),
                               ("item", "What", 460)], height=18, stretch={"item"})

        def refresh() -> None:
            self.due.fill(M.due(), None, lambda d: (
                d["due"] or "", "OVERDUE" if d["overdue"] else "", d["who"], d["item"]),
                lambda d: "bad" if d["overdue"] else None)
        return refresh

    # ── Reports ──────────────────────────────────────────────────────

    def _tab_reports(self, tab):
        self.buttons(self.bar(tab), (("Refresh", lambda: self._run("Reports")),))
        self.heading(tab, "Conditions")
        self.rep_cond = Table(tab, [("what", "Condition", 280), ("n", "Pupils", 80)], height=6)
        self.heading(tab, "Medicines given")
        self.rep_dose = Table(tab, [("med", "Medicine", 260), ("doses", "Doses", 70),
                                    ("refused", "Refused", 70), ("emerg", "Emergency", 80),
                                    ("pupils", "Pupils", 70)], height=6)
        self.heading(tab, "First aid this year")
        self.rep_fa = Table(tab, [("what", "Group", 280), ("n", "Incidents", 80)], height=6)

        def refresh() -> None:
            s = M.summary()
            self.rep_cond.fill(sorted(s["by_condition"].items(), key=lambda x: -x[1]), None,
                               lambda x: x)
            self.rep_dose.fill(M.dose_report(), None, lambda r: (
                r["medicine"], r["doses"], r["refused"], r["emergency"], r["pupils"]))
            fa = M.first_aid_summary(
                from_date=P.academic_year_start(M._today()).isoformat())
            self.rep_fa.fill([(f"Severity: {k}", v) for k, v in fa["by_severity"].items()]
                             + [(f"Injury: {k}", v) for k, v in fa["by_injury"].items()]
                             + [(f"Outcome: {k}", v) for k, v in fa["by_outcome"].items()],
                             None, lambda x: x)
        return refresh


def draw_medical(parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> MedicalPage:
    return MedicalPage(parent, principal=principal, state=state, open_pupil=open_pupil)
