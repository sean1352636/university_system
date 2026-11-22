"""GUI for UCAS Extra, Clearing and Adjustment — the "Extra & Clearing" tab.

Three inner tabs: the cohort with what each application can open; the
routes that are open (and their choices); and the log of contacts with
university admissions offices.
"""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.sixth_form.domain.progression.university import (
    post_offer as data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.gui.progression import _record_tabs as rt

logger = logging.getLogger(__name__)


def _cycle(f: dict[str, str]) -> int:
    raw = f.get("cycle") or ""
    if not raw:
        return workflow_data.default_cycle_year()
    if not raw.isdigit():
        raise ValueError("Cycle must be a year")
    return int(raw)


_CYCLE = ("cycle", "Cycle (entry year)", "text", (), workflow_data.default_cycle_year())

_CHOICE_FIELDS = (
    ("university", "University", "text"), ("course_name", "Course", "text"),
    ("course_code", "Course code", "text"),
    ("entry_requirements", "Entry requirements", "text"),
    ("status", "Status", "choice", data.CHOICE_STATUSES),
    ("decision_date", "Decision date", "date"), ("notes", "Notes", "multiline"),
)
_CONTACT_FIELDS = (
    ("university", "University", "text"), ("contact_date", "Date", "date"),
    ("method", "Method", "choice", data.CONTACT_METHODS),
    ("contact_name", "Spoke to", "text"), ("summary", "Summary", "multiline"),
    ("outcome", "Outcome", "text"), ("follow_up_date", "Follow up on", "date"),
)


def build_tab(gui, parent: ttk.Frame) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    rt.notebook_tab(nb, "Cohort", _cohort)
    rt.notebook_tab(nb, "Routes", _routes)
    rt.notebook_tab(nb, "Contact log", _contacts)


# ── Cohort ──────────────────────────────────────────────────────────

def _cohort(parent: ttk.Frame) -> None:
    def load(f):
        return [r.as_row() for r in data.cohort(
            _cycle(f), only_actionable=f.get("show") == "Actionable only")]

    def explain(table):
        row = table.require()
        lines = [f"{row['student_name']} — application #{row['application_id']}", ""]
        for e in data.eligibility(row["application_id"]):
            lines.append(f"{e.route:<11} {'ELIGIBLE' if e.eligible else 'not eligible'}")
            lines.append(f"            {e.reason}")
        conf = data.get_confirmation(row["application_id"])
        if conf:
            lines += ["", f"Results day: {conf['outcome']}"
                      + ("  (conditions exceeded)" if conf["exceeded_conditions"] else "")]
        rt.show_text(table.parent, "Extra / Clearing / Adjustment", "\n".join(lines))

    def confirm_results(table):
        row = table.require()
        conf = data.get_confirmation(row["application_id"]) or {}
        rt.form_dialog(
            table.parent, "Results-day confirmation",
            [("outcome", "UCAS outcome", "choice", data.CONFIRMATION_OUTCOMES),
             ("exceeded", "Firm conditions exceeded", "bool"),
             ("confirmed_on", "Confirmed on", "date"),
             ("notes", "Notes", "multiline")],
            {"outcome": conf.get("outcome", ""), "exceeded": conf.get("exceeded_conditions"),
             "confirmed_on": conf.get("confirmed_on"), "notes": conf.get("notes")},
            lambda v: data.record_confirmation(
                row["application_id"], v["outcome"], exceeded_conditions=v["exceeded"],
                confirmed_on=v["confirmed_on"], notes=v["notes"]),
            table.refresh)

    def open_route(table):
        row = table.require()
        routes = data.eligible_routes(row["application_id"])
        if not routes:
            raise ValueError("Not eligible for any route yet — use 'Why?' for the reasons.")
        rt.form_dialog(
            table.parent, "Open route",
            [("route", "Route", "choice", routes), ("notes", "Notes", "multiline")],
            {"route": routes[0]},
            lambda v: data.open_route(row["application_id"], v["route"], notes=v["notes"]),
            table.refresh)

    def log_contact(table):
        row = table.require()
        routes = {f"{r['route']} (#{r['route_id']})": r["route_id"]
                  for r in data.list_routes(application_id=row["application_id"])}

        def save(v):
            v["route_id"] = routes.get(v.pop("route", ""), None)
            data.log_contact(row["application_id"], v)

        rt.form_dialog(table.parent, "Log contact with a university",
                       _CONTACT_FIELDS + (("route", "Route", "choice", list(routes)),),
                       {}, save)

    rt.RecordTable(
        parent,
        (("student_name", "Student", 180), ("student_id", "ID", 80),
         ("status", "Application", 100), ("confirmation", "Results day", 200),
         ("eligible", "Can open", 180), ("open_routes", "Open", 160)),
        load, key="application_id",
        filters=[_CYCLE, ("show", "Show", "choice", ("Actionable only",), "Actionable only")],
        note=("Eligibility is worked out from the choices and the results-day "
              "confirmation. Extra: all five choices used, no offers held. Clearing: "
              "from results day with no confirmed place, or after 30 June. "
              "Adjustment: Firm confirmed with conditions exceeded (now done by "
              "releasing the place into Clearing)."),
        tags=lambda r: "warn" if r["eligible"] != "—" else None,
        actions=[("Why?", explain), ("Record results day…", confirm_results),
                 ("Open route…", open_route), ("Log contact…", log_contact)],
        on_open=explain)


# ── Routes ──────────────────────────────────────────────────────────

def _routes(parent: ttk.Frame) -> None:
    def load(f):
        return data.list_routes(cycle_year=_cycle(f), route=f.get("route") or None,
                                status=f.get("status") or None)

    def choices(table):
        row = table.require()
        rows = data.list_choices(row["route_id"])
        lines = [f"{row['route']} — {row['student_name']} ({row['status']})", ""]
        for c in rows:
            lines.append(f"#{c['po_choice_id']}  {c['university']} — {c['course_name']}"
                         f"  [{c['status']}]"
                         + (f"  req: {c['entry_requirements']}" if c["entry_requirements"] else ""))
        if not rows:
            lines.append("(no choices yet)")
        rt.show_text(table.parent, "Route choices", "\n".join(lines))

    def add_choice(table):
        row = table.require()
        rt.form_dialog(table.parent, f"Add {row['route']} choice", _CHOICE_FIELDS,
                       {"status": "Considering"},
                       lambda v: data.add_choice(row["route_id"], v), table.refresh)

    def update_choice(table):
        row = table.require()
        rows = data.list_choices(row["route_id"])
        if not rows:
            raise ValueError("This route has no choices.")
        labels = [f"#{c['po_choice_id']} {c['university']} — {c['course_name']}" for c in rows]
        by = dict(zip(labels, rows))
        rt.form_dialog(
            table.parent, "Update a choice's status",
            [("choice", "Choice", "choice", labels),
             ("status", "New status", "choice", data.CHOICE_STATUSES),
             ("decision_date", "Decision date", "date")],
            {"choice": labels[0]},
            lambda v: data.update_choice(by[v["choice"]]["po_choice_id"],
                                         {"status": v["status"] or by[v["choice"]]["status"],
                                          "decision_date": v["decision_date"] or None}),
            table.refresh)

    def close(table):
        row = table.require()
        rows = data.list_choices(row["route_id"])
        labels = [f"#{c['po_choice_id']} {c['university']} — {c['course_name']}" for c in rows]
        by = dict(zip(labels, rows))
        rt.form_dialog(
            table.parent, f"Close {row['route']}",
            [("status", "Result", "choice", ("Placed", "Closed - not placed", "Withdrawn")),
             ("placed", "Placed on (if placed)", "choice", labels),
             ("outcome", "Outcome note", "text"), ("closed_on", "Closed on", "date")],
            {"status": "Placed" if labels else "Closed - not placed"},
            lambda v: data.close_route(
                row["route_id"], status=v["status"], outcome=v["outcome"],
                placed_po_choice_id=(by[v["placed"]]["po_choice_id"] if v["placed"] else None),
                closed_on=v["closed_on"]),
            table.refresh)

    rt.RecordTable(
        parent,
        (("route_id", "#", 50), ("route", "Route", 90), ("student_name", "Student", 170),
         ("status", "Status", 130), ("opened_on", "Opened", 90),
         ("n_choices", "Choices", 60), ("outcome", "Outcome", 280),
         ("eligible_reason", "Why eligible", 240)),
        load, key="route_id",
        filters=[_CYCLE, ("route", "Route", "choice", data.ROUTES),
                 ("status", "Status", "choice", data.ROUTE_STATUSES)],
        tags=lambda r: "good" if r["status"] == "Placed" else (
            "warn" if r["status"] == "Active" else "muted"),
        actions=[("Choices", choices), ("Add choice…", add_choice),
                 ("Update choice…", update_choice), ("Close route…", close)],
        on_open=choices)


# ── Contacts ────────────────────────────────────────────────────────

def _contacts(parent: ttk.Frame) -> None:
    import datetime as _dt

    def load(f):
        due = _dt.date.today().isoformat() if f.get("show") == "Follow-ups due" else None
        return data.list_contacts(follow_ups_due_by=due)

    def delete(table):
        row = table.require()
        if rt.confirm(table.parent, "Delete", "Delete this contact record?"):
            data.delete_contact(row["contact_id"])
            table.refresh()

    rt.RecordTable(
        parent,
        (("contact_date", "Date", 90), ("student_id", "Student", 80),
         ("university", "University", 180), ("route", "Route", 80),
         ("method", "Method", 80), ("contact_name", "Spoke to", 120),
         ("summary", "Summary", 300), ("outcome", "Outcome", 160),
         ("follow_up_date", "Follow up", 90)),
        load, key="contact_id",
        filters=[("show", "Show", "choice", ("Follow-ups due",))],
        note="Log new contacts from the Cohort tab (select the applicant first).",
        actions=[("Delete", delete)])


__all__ = ["build_tab"]
