"""Enrolment import / export / print: directory CSV, progression list,
PDF summaries (one enrolment, a tutor group roster), clipboard copy and
CSV import with a validated preview."""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    DEFAULT_STATUS,
    Enrolment,
)
from education_system.systems.sixth_form.domain.learners.students import students as student_data

from .enrolment_common import (
    _clear,
    _default_academic_year,
    _heading,
    _report_bulk,
    _student_name_map,
    back_to_directory,
    describe_error,
)

logger = logging.getLogger(__name__)


# ── Import / export / print (features 29–35) ────────────────────────

_CSV_HEADERS = ("enrolment_id", "student_id", "name", "academic_year",
                "year_group", "tutor_group", "start_date", "status", "notes")


def export_directory_csv(gui, rows: list[Enrolment], names: dict[str, str]) -> None:
    """Feature #29 — export the current (filtered) view to CSV."""
    import csv
    from education_system.platform.delivery.gui.parented_dialogs import filedialog
    path = filedialog.asksaveasfilename(
        parent=gui.root, defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialfile="enrolments.csv", title="Export enrolments to CSV")
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(_CSV_HEADERS)
            for e in rows:
                w.writerow([
                    e.enrolment_id, e.student_id, names.get(e.student_id, ""),
                    e.academic_year, e.year_group, e.tutor_group or "",
                    e.start_date or "", e.status, (e.notes or "").replace("\n", " ")])
    except Exception as exc:
        logger.exception("CSV export failed")
        messagebox.showerror("Export failed", str(exc), parent=gui.root)
        return
    messagebox.showinfo("Exported", f"Wrote {len(rows)} row(s) to:\n{path}",
                        parent=gui.root)
    gui.status_var.set(f"Exported {len(rows)} enrolment(s)")


def export_progression_list(gui) -> None:
    """Feature #35 — CSV of who is progressing (Y12 Enrolled) vs leaving
    (Y13 Enrolled) for the current academic year."""
    import csv
    from education_system.platform.delivery.gui.parented_dialogs import filedialog
    year = _default_academic_year()
    try:
        rows = data.list_enrolments(academic_year=year, status="Enrolled")
    except Exception as exc:
        messagebox.showerror("Error", str(exc), parent=gui.root)
        return
    names = _student_name_map()
    path = filedialog.asksaveasfilename(
        parent=gui.root, defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        initialfile=f"progression_{year.replace('/', '-')}.csv",
        title="Export progression list")
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(("student_id", "name", "year_group", "outcome"))
            for e in rows:
                outcome = "Progressing to Y13" if e.year_group == 12 else \
                          ("Leaving (Y13)" if e.year_group == 13 else "—")
                w.writerow((e.student_id, names.get(e.student_id, ""),
                            e.year_group, outcome))
    except Exception as exc:
        logger.exception("Progression export failed")
        messagebox.showerror("Export failed", str(exc), parent=gui.root)
        return
    messagebox.showinfo("Exported", f"Wrote {len(rows)} row(s) to:\n{path}",
                        parent=gui.root)
    gui.status_var.set("Exported progression list")


def _write_simple_pdf(path: str, title: str, lines: list[str]) -> None:
    """Render a plain, one-column text PDF via reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _canvas
    c = _canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, title)
    y -= 30
    c.setFont("Helvetica", 10)
    for line in lines:
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 50
        c.drawString(50, y, line[:110])
        y -= 16
    c.save()


def export_enrolment_pdf(gui, enrolment_id: int) -> None:
    """Feature #30 — the printable enrolment confirmation and learner
    agreement (``enrolment_day.confirmation_text``) as a PDF."""
    from .enrolment_day_views import confirmation_pdf
    path = confirmation_pdf(gui, enrolment_id)
    if path:
        messagebox.showinfo("Exported", f"Saved PDF to:\n{path}", parent=gui.root)
        gui.status_var.set(f"Exported PDF for #{enrolment_id}")


def export_tutor_group_pdf(gui, tutor_group: str) -> None:
    """Feature #33 — printable tutor-group roster PDF."""
    from education_system.platform.delivery.gui.parented_dialogs import filedialog
    names = _student_name_map()
    rows = sorted(
        (e for e in data.list_enrolments()
         if (e.tutor_group or "").lower() == tutor_group.lower()),
        key=lambda r: names.get(r.student_id, ""))
    path = filedialog.asksaveasfilename(
        parent=gui.root, defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")],
        initialfile=f"roster_{tutor_group}.pdf",
        title="Export roster PDF")
    if not path:
        return
    lines = [f"Tutor group: {tutor_group}    ({len(rows)} students)", ""]
    lines += [f"{i + 1:>2}. {e.student_id:<10} {names.get(e.student_id, '—'):<28} "
              f"{e.academic_year}  {e.status}"
              for i, e in enumerate(rows)]
    try:
        _write_simple_pdf(path, "Tutor Group Roster", lines)
    except Exception as exc:
        logger.exception("Roster PDF export failed")
        messagebox.showerror("Export failed", str(exc), parent=gui.root)
        return
    messagebox.showinfo("Exported", f"Saved roster to:\n{path}", parent=gui.root)
    gui.status_var.set(f"Exported roster {tutor_group}")


def copy_enrolment_to_clipboard(gui, enrolment_id: int) -> None:
    """Feature #34 — copy a formatted enrolment summary to the clipboard."""
    e = data.get_enrolment(enrolment_id)
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
        return
    student = student_data.get_student(e.student_id)
    text = (
        f"Enrolment #{e.enrolment_id}\n"
        f"Student: {e.student_id} — {student.full_name if student else '(deleted)'}\n"
        f"Year: {e.academic_year} · Year {e.year_group}\n"
        f"Tutor: {e.tutor_group or '—'} · Start: {e.start_date or '—'}\n"
        f"Status: {e.status}")
    try:
        gui.root.clipboard_clear()
        gui.root.clipboard_append(text)
    except Exception as exc:
        messagebox.showerror("Copy failed", str(exc), parent=gui.root)
        return
    gui.status_var.set(f"Copied enrolment #{enrolment_id} to clipboard")


def _preview_import_diff(gui, parent, records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Feature #32 — classify parsed CSV rows as new / duplicate / invalid and
    render the preview. Returns the subset that is safe to import (new)."""
    existing = {(e.student_id, e.academic_year) for e in data.list_enrolments()}
    all_students = {s.student_id: s for s in student_data.list_students()}
    importable: list[dict[str, str]] = []

    tree = ttk.Treeview(parent, columns=("sid", "year", "yg", "verdict"),
                        show="headings", height=10)
    for col, (text, w) in {
        "sid": ("Student", 100), "year": ("Year", 90),
        "yg": ("YG", 50), "verdict": ("Verdict", 220),
    }.items():
        tree.heading(col, text=text)
        tree.column(col, width=w)
    tree.tag_configure("new", foreground="#2a7d2a")
    tree.tag_configure("dupe", foreground="#b8860b")
    tree.tag_configure("bad", foreground="#a33333")
    tree.pack(anchor="w", fill="x")

    for rec in records:
        sid = (rec.get("student_id") or "").strip()
        year = (rec.get("academic_year") or "").strip()
        yg = (rec.get("year_group") or "").strip()
        if sid not in all_students:
            verdict, tag = "unknown student — skipped", "bad"
        elif not all_students[sid].on_roll:
            verdict, tag = f"not on roll ({all_students[sid].status}) — skipped", "bad"
        elif not enrolments._ACADEMIC_YEAR_RE.match(year):
            verdict, tag = "bad academic year — skipped", "bad"
        elif (sid, year) in existing:
            verdict, tag = "duplicate (student+year) — skipped", "dupe"
        else:
            verdict, tag = "new — will import", "new"
            importable.append(rec)
        tree.insert("", "end", tags=(tag,), values=(sid, year, yg, verdict))
    return importable


def import_enrolments_csv(gui) -> None:
    """Feature #31 — bulk-import enrolments from CSV with a validated preview."""
    import csv
    from education_system.platform.delivery.gui.parented_dialogs import filedialog
    path = filedialog.askopenfilename(
        parent=gui.root, filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        title="Import enrolments from CSV")
    if not path:
        return
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            records = list(csv.DictReader(fh))
    except Exception as exc:
        logger.exception("CSV import read failed")
        messagebox.showerror("Import failed", f"Could not read file: {exc}",
                             parent=gui.root)
        return

    frame = _clear(gui)
    _heading(frame, "Import Enrolments — Preview")
    ttk.Label(frame, text=f"{len(records)} row(s) read from {path}",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    preview_holder = ttk.Frame(frame)
    preview_holder.pack(anchor="w", fill="x")
    importable = _preview_import_diff(gui, preview_holder, records)

    def do_import() -> None:
        ok: list[str] = []
        fail: list[str] = []
        for rec in importable:
            try:
                data.create_enrolment({
                    "student_id": rec.get("student_id", "").strip(),
                    "academic_year": rec.get("academic_year", "").strip(),
                    "year_group": rec.get("year_group", "").strip(),
                    "tutor_group": (rec.get("tutor_group") or "").strip() or None,
                    "start_date": (rec.get("start_date") or "").strip() or None,
                    "status": (rec.get("status") or DEFAULT_STATUS).strip(),
                    "notes": (rec.get("notes") or "").strip() or None,
                })
                ok.append(rec.get("student_id", "?"))
            except Exception as exc:  # reported per row
                fail.append(f"{rec.get('student_id', '?')}: {describe_error(exc)}")
        _report_bulk(gui, "CSV import", ok, fail)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))
    ttk.Button(bar, text=f"Import {len(importable)} new row(s)",
               command=do_import,
               state=("normal" if importable else "disabled")
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel",
               command=lambda: back_to_directory(gui)).pack(side="left")
    gui.status_var.set(f"Import preview: {len(importable)} importable")
