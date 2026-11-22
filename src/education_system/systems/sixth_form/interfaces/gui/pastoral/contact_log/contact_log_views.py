"""Tkinter window: Contact Log.

Tabs: Contact Log (filterable, full CRUD), Follow-ups and Summary.
What each user sees is decided in ``contact_log`` (own entries, PASTORAL
for others', SAFEGUARDING for restricted ones).
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.contact_log import (
    contact_log as data,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._pastoral_ui import (
    ReportTab, counts_block, make_window,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form,
)

_TAGS = {"overdue": ("#ffd1d1", "#8c0d0d"), "open": ("#fff7e6", "#7a5800"),
         "restricted": ("#ede6ff", "#3b1a8c")}

_COLUMNS = (
    ("#", lambda c: c.contact_id, 50),
    ("Date", lambda c: c.contact_date, 90),
    ("Student", lambda c: c.student_id, 90),
    ("With", lambda c: c.contact_with, 120),
    ("Name", lambda c: c.contact_name, 130),
    ("Method", lambda c: c.method, 80),
    ("Dir.", lambda c: "In" if c.direction == "Incoming" else "Out", 40),
    ("Reason", lambda c: c.reason, 130),
    ("Summary", lambda c: c.summary, 320),
    ("Follow up by", lambda c: c.follow_up_by if c.follow_up_open else
     (f"done {c.follow_up_done_on}" if c.follow_up_done_on else ""), 110),
    ("Recorded by", lambda c: c.recorded_by, 130),
)


def _tag(c: Any) -> str | None:
    if c.follow_up_overdue:
        return "overdue"
    if c.follow_up_open:
        return "open"
    return "restricted" if c.restricted else None


def _done(tab: RecordTab, c: Any) -> None:
    ask_form(tab.frame, f"Follow-up done — contact #{c.contact_id}",
             (Col("on", "Followed up on", "date", default=today),
              Col("notes", "Notes", "multiline")),
             on_save=lambda v: data.complete_follow_up(
                 c.contact_id, on=v["on"] or None, notes=v["notes"]))


def open_contact_log_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Contact Log")

    RecordTab(
        nb, "Contact Log", data.SPEC,
        load=lambda f: data.list_contacts(
            student_id=f.get("student_id") or None,
            reason=f.get("reason") or None, method=f.get("method") or None,
            date_from=f.get("from") or None, date_to=f.get("to") or None,
            mine_only=bool(f.get("mine"))),
        create=data.log_contact, update=data.update_contact,
        delete=data.delete_contact, columns=_COLUMNS,
        filters=(Col("student_id", "Student", "student"),
                 Col("reason", "Reason", "choice", choices=data.REASONS),
                 Col("method", "Method", "choice", choices=data.METHODS),
                 Col("from", "From", "date"), Col("to", "To", "date"),
                 Col("mine", "Mine only", "bool")),
        actions=(("Follow-up Done", _done, True),),
        row_tag=_tag, tag_colours=_TAGS,
        intro=("Calls, e-mails, meetings and letters with learners, "
               "parents / carers and agencies. Safeguarding concerns still "
               "go to Safeguarding: contacts with reason 'Safeguarding' or "
               "marked confidential are restricted (purple) to you and the "
               "DSL team. Amber = follow-up open, red = overdue."))

    RecordTab(
        nb, "Follow-ups", data.SPEC,
        load=lambda f: data.list_contacts(
            follow_up_open_only=True,
            follow_up_overdue_only=bool(f.get("overdue")),
            mine_only=bool(f.get("mine"))),
        update=data.update_contact, columns=_COLUMNS,
        filters=(Col("overdue", "Overdue only", "bool"),
                 Col("mine", "Mine only", "bool")),
        actions=(("Follow-up Done", _done, True),),
        row_tag=_tag, tag_colours=_TAGS)

    def render(f: dict[str, str]) -> list[str]:
        s = data.summary(date_from=f.get("from") or None,
                         date_to=f.get("to") or None)
        lines = [f"Contacts {s.date_from} to {s.date_to} (those you can see)",
                 "", f"  Contacts:            {s.total}",
                 f"  Students contacted:  {s.students}",
                 f"  Outgoing / incoming: {s.outgoing} / {s.incoming}",
                 f"  Follow-ups open:     {s.follow_ups_open} "
                 f"({s.follow_ups_overdue} overdue)", ""]
        lines += counts_block("By reason", s.by_reason)
        lines += counts_block("By method", s.by_method)
        lines += counts_block("Contact with", s.by_with)
        lines.append("  Most contacted students:")
        lines += [f"    {sid:<10} {name:<30} {n:>4}"
                  for sid, name, n in s.top_students] or ["    (none)"]
        return lines

    month_ago = (_dt.date.today() - _dt.timedelta(days=30)).isoformat()
    ReportTab(nb, "Summary", render,
              filters=(("from", "From", month_ago), ("to", "To", today())))
