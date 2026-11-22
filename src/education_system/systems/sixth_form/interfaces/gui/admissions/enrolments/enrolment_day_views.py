"""Enrolment day: the cohort board (Ready / Outstanding per learner), one
learner's status, the enrolment confirmation (print / PDF), the learner
ID card (print / PDF, with photo), and the confirmation template editor
with its version history."""

from __future__ import annotations

import logging
import os
import tempfile
import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolment_day as day,
)

from . import enrolment_page_kit as kit
from .enrolment_common import _default_academic_year, describe_error, show_error

logger = logging.getLogger(__name__)

TICK = {True: "✓", False: "✗", None: "ℹ"}


def _open_file(path: str) -> None:
    from education_system.systems.sixth_form.interfaces.gui.admissions._common import (
        _open_path,
    )
    _open_path(path)


# ── Board ───────────────────────────────────────────────────────────

BOARD_COLS = [("sid", "Student", 90), ("name", "Name", 180), ("yg", "YG", 40),
              ("tutor", "Tutor", 70), ("overall", "Overall", 90), ("done", "Done", 60),
              ("todo", "Outstanding", 520)]
ITEM_COLS = [("mark", "", 30), ("name", "Item", 220), ("detail", "Detail", 640)]


def open_enrolment_day_board(gui, academic_year: str | None = None,
                             year_group: int | None = None) -> None:
    year = academic_year or _default_academic_year()
    frame, bar = kit.page(gui, "Enrolment Day Board")
    top = ttk.Frame(frame)
    top.pack(anchor="w", fill="x")
    yg_var = tk.StringVar(value=str(year_group or ""))
    year_var = kit.year_picker(top, year)
    ttk.Label(top, text="Year group:").pack(side="left")
    ttk.Combobox(top, textvariable=yg_var, values=("", "12", "13"), state="readonly",
                 width=4).pack(side="left", padx=(4, 8))
    ttk.Button(top, text="Apply", command=lambda: open_enrolment_day_board(
        gui, year_var.get(), int(yg_var.get()) if yg_var.get() else None)).pack(side="left")
    try:
        rows = day.cohort_board(year, year_group)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Enrolment day board", exc)
        rows = []
    ready = sum(1 for r in rows if r.overall == day.READY)
    kit.note(frame, f"{len(rows)} learner(s): {ready} ready, {len(rows) - ready} "
             "outstanding. Select a learner to see each item; double-click for "
             "their full status.")
    holder = ttk.Frame(frame)
    holder.pack(fill="both", expand=True)
    tree = kit.table(holder, BOARD_COLS, [
        (r.student_id, r.name, r.year_group, r.tutor_group, r.overall,
         "{}/{}".format(*r.done_count), ", ".join(i.name for i in r.outstanding))
        for r in rows], iids=[r.student_id for r in rows], height=12)
    tree.tag_configure("out", foreground="#a33")
    for r in rows:
        if r.overall != day.READY:
            tree.item(r.student_id, tags=("out",))
    detail = kit.table(holder, ITEM_COLS, [], height=7, expand=False)
    by_sid = {r.student_id: r for r in rows}

    def show_items(_e=None) -> None:
        for i in detail.get_children():
            detail.delete(i)
        sel = tree.selection()
        if sel and sel[0] in by_sid:
            for it in by_sid[sel[0]].items:
                detail.insert("", "end", values=(TICK[it.done], it.name, it.detail))

    tree.bind("<<TreeviewSelect>>", show_items)
    tree.bind("<Double-1>", lambda _e: tree.selection() and open_learner_status(
        gui, tree.selection()[0], year))
    kit.button(bar, "Open Status", lambda: (lambda s: s and open_learner_status(gui, s, year))(
        kit.selected(tree, "Enrolment day", "a learner")))
    kit.csv_button(bar, gui, lambda: [
        {"student_id": r.student_id, "name": r.name, "year_group": r.year_group,
         "tutor_group": r.tutor_group, "overall": r.overall,
         "outstanding": "; ".join(f"{i.name}: {i.detail}" for i in r.outstanding)}
        for r in rows], f"enrolment_day_{year.replace('/', '-')}.csv")
    gui.status_var.set(f"Enrolment day {year}: {ready}/{len(rows)} ready")


def open_learner_status(gui, student_id: str, academic_year: str | None = None) -> None:
    frame, bar = kit.page(gui, f"Enrolment Day — {student_id}",
                          back=lambda: open_enrolment_day_board(gui, academic_year),
                          back_text="Back to Board")
    try:
        st = day.learner_status(student_id, academic_year)
    except Exception as exc:  # noqa: BLE001
        kit.note(frame, f"Status not read: {describe_error(exc)}", colour="#a33")
        return
    done, total = st.done_count
    kit.note(frame, f"{st.name} · {st.academic_year} · Year {st.year_group or '—'} · "
             f"tutor {st.tutor_group or '—'} — {st.overall} ({done}/{total} done)",
             colour="#2e7d32" if st.overall == day.READY else "#a33")
    kit.table(frame, ITEM_COLS, [(TICK[i.done], i.name, i.detail) for i in st.items],
              height=16)
    eid = st.enrolment_id
    from .enrolment_agreements_views import open_agreements
    from .enrolment_views import open_profile
    kit.button(bar, "Open Enrolment", lambda: open_profile(gui, eid), enabled=bool(eid))
    kit.button(bar, "Agreements", lambda: open_agreements(gui, eid), enabled=bool(eid))
    kit.button(bar, "Confirmation…", lambda: show_confirmation(gui, eid), enabled=bool(eid))
    kit.button(bar, "ID Card…", lambda: open_id_card(gui, student_id))
    kit.button(bar, "Photo & ID checks", lambda: _identity(gui, student_id))
    gui.status_var.set(f"{student_id}: {st.overall}")


def _identity(gui, student_id: str) -> None:
    from .identity_checks_views import open_identity_checks_window
    open_identity_checks_window(gui.root, student_id=student_id)


# ── Confirmation ────────────────────────────────────────────────────

def write_text_pdf(path: str, title: str, text: str) -> None:
    from .enrolment_io_views import _write_simple_pdf
    _write_simple_pdf(path, title, text.splitlines())


def confirmation_pdf(gui, enrolment_id: int, path: str | None = None) -> str | None:
    """The confirmation + learner agreement as a PDF (asks where when no
    path is given)."""
    try:
        text = day.confirmation_text(enrolment_id)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Enrolment confirmation", exc)
        return None
    if path is None:
        path = filedialog.asksaveasfilename(
            parent=gui.root, defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")],
            initialfile=f"enrolment_{enrolment_id}.pdf", title="Save enrolment confirmation")
        if not path:
            return None
    try:
        write_text_pdf(path, "Sixth Form Enrolment Confirmation", text)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Export failed", exc)
        return None
    gui.status_var.set(f"Saved confirmation for #{enrolment_id}")
    return path


def print_confirmation(gui, enrolment_id: int) -> None:
    """Write the confirmation to a temporary PDF and open it to print."""
    fd, path = tempfile.mkstemp(prefix=f"enrolment_{enrolment_id}_", suffix=".pdf")
    os.close(fd)
    if confirmation_pdf(gui, enrolment_id, path):
        _open_file(path)


def show_confirmation(gui, enrolment_id: int) -> None:
    try:
        text = day.confirmation_text(enrolment_id)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Enrolment confirmation", exc)
        return
    win = make_toplevel(gui.root)
    win.title(f"Enrolment confirmation — #{enrolment_id}")
    bar = ttk.Frame(win, padding=(8, 8, 8, 0))
    bar.pack(fill="x")
    ttk.Button(bar, text="Print…", command=lambda: print_confirmation(gui, enrolment_id)
               ).pack(side="left")
    ttk.Button(bar, text="Save PDF…", command=lambda: confirmation_pdf(gui, enrolment_id)
               ).pack(side="left", padx=6)
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="left")
    t = tk.Text(win, width=84, height=34, wrap="word")
    t.pack(fill="both", expand=True, padx=8, pady=8)
    t.insert("1.0", text)
    t.configure(state="disabled")


# ── ID card ─────────────────────────────────────────────────────────

CARD_W, CARD_H = 242.6, 153.0   # ISO ID-1 card in points (85.6 × 54 mm)


def card_lines(card) -> list[str]:
    return [card.name + (f" ({card.preferred_name})" if card.preferred_name else ""),
            f"Student {card.student_id}",
            f"{card.academic_year or ''}  Year {card.year_group or '—'}  "
            f"Tutor {card.tutor_group or '—'}",
            f"Valid until {card.valid_until or '—'}",
            f"Card {card.card_number}" if card.card_number else ""]


def id_card_pdf(card, path: str) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _canvas
    c = _canvas.Canvas(path, pagesize=A4)
    _w, h = A4
    x, y = 60, h - 60 - CARD_H
    c.roundRect(x, y, CARD_W, CARD_H, 8)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 10, y + CARD_H - 20, "Sixth Form College")
    text_x = x + 10
    if card.photo_path:
        try:
            c.drawImage(card.photo_path, x + 10, y + 12, width=70, height=90,
                        preserveAspectRatio=True, mask="auto")
            text_x = x + 90
        except Exception:  # noqa: BLE001 — the card prints without it
            logger.warning("Photo not drawn on ID card for %s", card.student_id)
    c.setFont("Helvetica", 9)
    ty = y + CARD_H - 42
    for line in card_lines(card):
        if line:
            c.drawString(text_x, ty, line[:40])
            ty -= 14
    c.showPage()
    c.save()


def open_id_card(gui, student_id: str) -> tk.Toplevel | None:
    try:
        card = day.id_card_data(student_id)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "ID card", exc)
        return None
    win = make_toplevel(gui.root)
    win.title(f"ID card — {student_id}")
    body = ttk.Frame(win, padding=12, relief="groove")
    body.pack(padx=12, pady=12)
    if card.photo_path:
        try:
            from .identity_checks_views import _load_preview
            img = _load_preview(card.photo_path, (120, 160))
            lbl = ttk.Label(body, image=img)
            lbl.image = img  # type: ignore[attr-defined]
            lbl.grid(row=0, column=0, rowspan=6, padx=(0, 12))
        except (tk.TclError, OSError, ValueError) as exc:
            ttk.Label(body, text=f"(photo not shown: {exc})").grid(row=0, column=0, rowspan=6)
    else:
        ttk.Label(body, text="No photo\non file", foreground="#a33", width=14,
                  anchor="center").grid(row=0, column=0, rowspan=6, padx=(0, 12))
    for r, line in enumerate(card_lines(card)):
        ttk.Label(body, text=line, font=("", 11, "bold") if r == 0 else ("", 10)).grid(
            row=r, column=1, sticky="w")

    def save() -> None:
        path = filedialog.asksaveasfilename(
            parent=win, defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")],
            initialfile=f"id_card_{student_id}.pdf", title="Save ID card")
        if not path:
            return
        try:
            id_card_pdf(card, path)
        except Exception as exc:  # noqa: BLE001
            show_error(win, "ID card", exc)
            return
        gui.status_var.set(f"Saved ID card to {path}")

    def print_it() -> None:
        fd, path = tempfile.mkstemp(prefix=f"id_card_{student_id}_", suffix=".pdf")
        os.close(fd)
        try:
            id_card_pdf(card, path)
        except Exception as exc:  # noqa: BLE001
            show_error(win, "ID card", exc)
            return
        _open_file(path)

    bar = ttk.Frame(win)
    bar.pack(anchor="w", padx=12, pady=(0, 12))
    ttk.Button(bar, text="Print…", command=print_it).pack(side="left")
    ttk.Button(bar, text="Save PDF…", command=save).pack(side="left", padx=6)
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="left")
    return win


# ── Template editor ─────────────────────────────────────────────────

VERSION_COLS = [("id", "Version", 70), ("at", "Saved at", 150), ("by", "Saved by", 120),
                ("start", "Begins", 520)]


def open_confirmation_template(gui) -> None:
    frame, bar = kit.page(gui, "Enrolment Confirmation Wording")
    kit.note(frame, "The college expectations printed on every enrolment confirmation "
             "and signed as the learner agreement. Earlier versions are kept.")
    try:
        body = day.get_template()
        versions = day.template_versions()
    except Exception as exc:  # noqa: BLE001
        kit.note(frame, f"Not read: {describe_error(exc)}", colour="#a33")
        return
    text = tk.Text(frame, width=100, height=16, wrap="word")
    text.pack(fill="x")
    text.insert("1.0", body)
    write = kit.can_write()
    if not write:
        text.configure(state="disabled")
    kit.section(frame, "Versions")
    tree = kit.table(frame, VERSION_COLS, [
        (v["template_id"], v["saved_at"], v["saved_by"],
         (v["body"] or "").replace("\n", " ")[:90]) for v in versions],
        iids=[str(v["template_id"]) for v in versions], height=6)
    if not versions:
        kit.note(frame, "Never saved — the built-in wording is in use.", colour="#777")

    def save() -> None:
        if kit.attempt(gui, "Save wording",
                       lambda: day.save_template(text.get("1.0", "end"))) is not None:
            messagebox.showinfo("Saved", "The new wording is saved; earlier versions "
                                "are kept.", parent=gui.root)
            open_confirmation_template(gui)

    def load_version() -> None:
        iid = kit.selected(tree, "Versions", "a version")
        if iid:
            v = next(x for x in versions if str(x["template_id"]) == iid)
            text.delete("1.0", "end")
            text.insert("1.0", v["body"])
            gui.status_var.set(f"Loaded version {iid} — Save to make it current")

    kit.button(bar, "Save", save, enabled=write)
    kit.button(bar, "Load Selected Version", load_version, enabled=write)
    kit.button(bar, "Built-in Wording", lambda: (text.delete("1.0", "end"),
                                                 text.insert("1.0", day.DEFAULT_EXPECTATIONS)),
               enabled=write)
    frame.text = text  # type: ignore[attr-defined]  # for scripted checks
    gui.status_var.set("Confirmation wording")

