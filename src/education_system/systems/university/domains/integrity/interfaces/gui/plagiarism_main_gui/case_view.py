"""Pieces of a case shared by the officer's, the referring member of
staff's and the student's case screens: the statements and evidence
sections, opening or saving an evidence file, adding evidence and sending
a statement. Rules are in ``application/integrity/evidence``."""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404 - opens a stored evidence file with the desktop's viewer
import sys
from tkinter import filedialog

from education_system.systems.university.application.integrity import evidence
from education_system.systems.university.infrastructure.ui.record_screens import (
    Field, ask, ask_text, call, confirm, info, nice,
)

EVIDENCE_KIND_CHOICES = [("note", "Note"), ("meeting_record", "Meeting record"),
                         ("file", "File")]


def statement_lines(record) -> list[str]:
    return [f"{s['submitted_at'][:16]}: {s['statement']}" for s in record.get("statements") or []]


def evidence_lines(record) -> list[str]:
    lines = []
    for e in record.get("evidence") or []:
        marks = []
        if e.get("removed_at"):
            marks.append("withdrawn")
        if not e.get("visible_to_student"):
            marks.append("internal")
        if e.get("file_name"):
            marks.append(f"file {e['file_name']}")
        head = f"#{e['evidence_id']} {e['added_at'][:10]} {nice(e['kind'])}: {e['title']}"
        if marks:
            head += f" [{', '.join(marks)}]"
        lines.append(head + (f" — {e['detail']}" if e.get("detail") else ""))
    return lines


def case_sections(record) -> list:
    """Statement deadline, statements and evidence, for ``Detail.show``."""
    return [("Student's account", [("Statement due by", record.get("response_due"))]
             + (statement_lines(record) or ["No statement yet."])),
            ("Evidence", evidence_lines(record) or ["None"])]


def file_items(record, include_withdrawn=False) -> list[dict]:
    return [e for e in record.get("evidence") or []
            if e.get("file_name") and (include_withdrawn or not e.get("removed_at"))]


def _choose(parent, items, title):
    if not items:
        info(parent, "There is no evidence file on this case.")
        return None
    if len(items) == 1:
        return items[0]
    values = ask(parent, title, [Field("id", "Evidence", "combo",
                                       [(e["evidence_id"], f"#{e['evidence_id']} "
                                         f"{e['file_name']}") for e in items], required=True)])
    if not values:
        return None
    return next((e for e in items if str(e["evidence_id"]) == str(values["id"])), None)


def _open_path(path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]  # nosec B606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])  # nosec B603 B607
    else:
        subprocess.Popen(["xdg-open", path])  # nosec B603 B607


def open_evidence(parent, who, record, save=False) -> None:
    """Open (or save a copy of) one of the case's evidence files."""
    item = _choose(parent, file_items(record), "Save evidence" if save else "Open evidence")
    if item is None:
        return
    found = call(parent, evidence.evidence_file, who, item["evidence_id"], write=True)
    if found is None:
        return
    if not found["intact"] and not confirm(parent, "This file no longer matches the copy that was "
                                                   "attached (its fingerprint differs). Open it "
                                                   "anyway?"):
        return
    if save:
        target = filedialog.asksaveasfilename(parent=parent, initialfile=found["name"])
        if target:
            shutil.copyfile(found["path"], target)
            info(parent, f"Saved {found['name']}.")
        return
    try:
        _open_path(found["path"])
    except OSError as exc:
        info(parent, f"Could not open the file: {exc}")


def add_evidence(tab, record, officer) -> None:
    """Add a note, meeting record or file (``tab`` is a RecordTab)."""
    fields = [Field("kind", "Kind", "combo", EVIDENCE_KIND_CHOICES, required=True),
              Field("title", "Title", required=True),
              Field("detail", "Note / record (for a file: what it shows)", "multiline")]
    if officer:
        fields += [Field("visible", "The student can see this", "check"),
                   Field("reason", "If not, why (e.g. a third party's personal data)")]
    values = ask(tab, f"Add evidence to case {record['id']}", fields,
                 {"kind": "note", "visible": True})
    if not values:
        return
    path = None
    if values["kind"] == "file":
        path = filedialog.askopenfilename(parent=tab, title="Choose the evidence file")
        if not path:
            return
    tab.write(evidence.add_evidence, tab.who, record["id"], kind=values["kind"],
              title=values["title"], detail=values["detail"], file_path=path,
              visible_to_student=values.get("visible", True),
              internal_reason=values.get("reason", ""), done="Evidence added.")


def withdraw_evidence(tab, record) -> None:
    items = [e for e in record.get("evidence") or [] if not e.get("removed_at")]
    if not items:
        info(tab, "There is no evidence to withdraw.")
        return
    values = ask(tab, "Withdraw evidence", [
        Field("id", "Evidence", "combo", [(e["evidence_id"], f"#{e['evidence_id']} {e['title']}")
                                          for e in items], required=True),
        Field("reason", "Why it is withdrawn", "multiline", required=True)])
    if values:
        tab.write(evidence.withdraw_evidence, tab.who, int(values["id"]), values["reason"],
                  done="Evidence withdrawn (it stays on the record).")


def change_deadline(tab, record) -> None:
    values = ask(tab, f"Statement deadline, case {record['id']}", [
        Field("date", "New deadline", "datepick", required=True),
        Field("reason", "Reason (sent to the student)", "multiline", required=True)],
        {"date": record.get("response_due")})
    if values:
        tab.write(evidence.set_response_due, tab.who, record["id"], values["date"],
                  values["reason"], done="Deadline changed and the student told.")


def send_statement(tab, record) -> None:
    text = ask_text(tab, f"Your statement, case {record['id']}",
                    "Your account of what happened (the integrity officer reads it before "
                    "anything is decided)")
    if text:
        tab.write(evidence.submit_statement, tab.who, record["id"], text,
                  done="Your statement has been sent.")
