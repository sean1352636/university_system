"""GUI panels for Sixth Form Personal Statements.

Three tabs:

* Directory  — filterable list of drafts (filter by student / status),
  plus the statements that live on a student's UCAS application and
  were never drafted here, highlighted and importable.
* Review     — the statement, read-only, with its char / word / line
  counters against the UCAS limits, and the review controls that *are*
  editable: status, reviewer, feedback. Save review / Email feedback /
  Push to UCAS / Delete.
* Per-student — counts per student + latest status.

The body is read-only for an existing statement. These are the
student's own words going to UCAS under their name; a reviewer changes
a statement by asking for the change in the feedback, which can now be
emailed rather than left in a column nobody reads.
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable
from education_system.systems.sixth_form.domain.progression.university import statements as personal_statements
from education_system.systems.sixth_form.domain.progression.university import statements as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.progression.university import ucas as ucas_data
from education_system.systems.sixth_form.domain.progression.university.statements import (
    DEFAULT_STATUS,
    MAX_CHARS,
    MAX_LINES,
    PersonalStatement,
    STATUSES,
    StudentSummary,
    ValidationError,
    compute_counts,
    compute_three_counts,
    FORMAT_LABELS,
    FORMAT_SINGLE,
    FORMAT_THREE,
    MIN_ANSWER_CHARS,
    QUESTIONS,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _current_reviewer(gui) -> str:
    """Who is signed in, for the Reviewer field.

    A reviewer typing their own name into every draft they open is a
    field that gets left blank, or filled with three different spellings
    of the same person. The session already knows who they are.

    Falls back through the several shapes the GUI shell has used for
    this, and finally to "" — an empty box is the old behaviour, which
    is the right thing to degrade to when nobody is signed in.
    """
    auth = getattr(gui, "auth", None)
    cu = getattr(auth, "current_user", None) if auth is not None else None
    if isinstance(cu, dict):
        for key in ("display_name", "username"):
            value = cu.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for attr in ("current_username", "username"):
        value = getattr(gui, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    var = getattr(gui, "current_user_var", None)
    if var is not None:
        try:
            value = var.get()
        except Exception:
            value = ""
        if isinstance(value, str) and value.strip() and value.strip() != "—":
            return value.strip()
    return ""


#: Prefix marking a Treeview row that is a statement on a UCAS
#: application rather than a draft in this table. Draft rows use the
#: bare statement_id, so the two can never be confused for each other.
_UCAS_IID = "ucas:"


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Personal Statements")

    nb = SidebarBook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    editor_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(editor_tab,  text="Review")
    nb.add(summary_tab, text="Per-student summary")

    _build_directory_tab(gui, dir_tab)
    _build_editor_tab(gui, editor_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    status_var = tk.StringVar()

    ttk.Label(filt, text="Student ID:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["", *STATUSES], state="readonly", width=12
                 ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(parent)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()
        try:
            rows = data.list_statements(
                student_id=sid_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_statements failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        # Statements that live on a UCAS application and were never
        # drafted here. Without these the screen looks empty for a
        # student whose statement was written in the UCAS applications
        # dialog — the data is fine, it is just in the other table.
        # A status filter is about *draft* status, which these do not
        # have, so applying one hides them rather than showing a row
        # whose status column is a guess.
        ucas_rows: list = []
        if not status_var.get().strip():
            try:
                ucas_rows = data.ucas_only_statements(
                    student_id=sid_var.get().strip() or None)
            except Exception:
                logger.exception("ucas_only_statements failed")

        cols = ("statement_id", "student", "title", "status",
                "chars", "lines", "reviewer", "updated_at")
        headings = {
            "statement_id": ("#",        50),
            "student":      ("Student", 110),
            "title":        ("Title",   200),
            "status":       ("Status",  100),
            "chars":        ("Chars",    60),
            "lines":        ("Lines",    50),
            "reviewer":     ("Reviewer", 130),
            "updated_at":   ("Updated",  140),
        }
        tree = ttk.Treeview(table_holder, columns=cols,
                            show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        tree.tag_configure("on_application", background="#eef3fb",
                            foreground="#1a3f8c")

        for s in rows:
            tree.insert("", "end", iid=str(s.statement_id), values=(
                s.statement_id, s.student_id, s.title or "—",
                s.status, s.char_count, s.line_count,
                s.reviewer or "—", s.updated_at,
            ))
        for u in ucas_rows:
            tree.insert("", "end", iid=f"{_UCAS_IID}{u.application_id}",
                        values=(
                            f"app #{u.application_id}", u.student_id,
                            f"On UCAS application (cycle {u.cycle_year})",
                            f"— {u.app_status}",
                            u.char_count, u.line_count, "—", u.updated_at,
                        ),
                        tags=("on_application",))
        summary.configure(
            text=f"{len(rows)} draft(s)"
                 + (f", {len(ucas_rows)} on a UCAS application only "
                    "(highlighted — use Import as draft to review one)"
                    if ucas_rows else "."))

        def _selected() -> str | None:
            sel = tree.selection()
            return sel[0] if sel else None

        def _require() -> str | None:
            iid = _selected()
            if iid is None:
                messagebox.showinfo("No selection",
                                    "Pick a statement first.",
                                    parent=gui.root)
            return iid

        def _require_draft() -> int | None:
            """A selection that is a real draft, not an application row."""
            iid = _require()
            if iid is None:
                return None
            if iid.startswith(_UCAS_IID):
                messagebox.showinfo(
                    "On a UCAS application",
                    "This statement lives on the student's UCAS "
                    "application, not as a draft here.\n\n"
                    "Use Import as draft first — then it can be "
                    "reviewed, given feedback and pushed back.",
                    parent=gui.root)
                return None
            return int(iid)

        def _open() -> None:
            iid = _require()
            if iid is None:
                return
            if iid.startswith(_UCAS_IID):
                _view_ucas_statement(
                    gui, int(iid[len(_UCAS_IID):]), on_changed=refresh)
                return
            open_editor(gui, statement_id=int(iid))

        def _import() -> None:
            iid = _require()
            if iid is None:
                return
            if not iid.startswith(_UCAS_IID):
                messagebox.showinfo(
                    "Already a draft",
                    "That row is already a draft here — Import as draft "
                    "is for the highlighted rows that only exist on a "
                    "UCAS application.",
                    parent=gui.root)
                return
            _import_ucas_statement(
                gui, int(iid[len(_UCAS_IID):]), on_changed=refresh)

        def _delete() -> None:
            sid = _require_draft()
            if sid is None:
                return
            s = data.get_statement(sid)
            if s is None:
                return
            if not messagebox.askyesno(
                "Delete statement",
                f"Delete personal statement #{sid} ({s.student_id})?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_statement(sid)
            except Exception as e:
                logger.exception("delete_statement crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        def _push() -> None:
            sid = _require_draft()
            if sid is None:
                return
            s = data.get_statement(sid)
            if s is None:
                return
            if not messagebox.askyesno(
                "Push to UCAS",
                f"Copy this draft to {s.student_id}'s UCAS application?\n\n"
                f"(The draft will be marked as Submitted.)",
                parent=gui.root,
            ):
                return
            try:
                aid = data.push_to_ucas(sid)
            except ValidationError as e:
                messagebox.showerror("Cannot push", str(e), parent=gui.root)
                return
            except Exception as e:
                logger.exception("push_to_ucas crashed")
                messagebox.showerror("Error", f"Unexpected: {e}",
                                     parent=gui.root)
                return
            messagebox.showinfo(
                "Pushed",
                f"Copied to UCAS application #{aid}.",
                parent=gui.root,
            )
            refresh()

        ttk.Button(actions_holder, text="Open",
                   command=_open).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Import as draft",
                   command=_import).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Push to UCAS",
                   command=_push).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_editor(gui, statement_id=None)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _open())
        gui.status_var.set(f"Personal statements: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), status_var.set(""),
                                refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Statements that live on a UCAS application ─────────────────────

def _ucas_statement(application_id: int):
    """The application-only statement for *application_id*, or None."""
    for u in data.ucas_only_statements():
        if u.application_id == application_id:
            return u
    return None


def _view_ucas_statement(gui, application_id: int, *,
                         on_changed: Callable[[], None]) -> None:
    """Read-only look at a statement that is not a draft here.

    Read-only in the strong sense: this text belongs to the UCAS
    application and the way to work on it is to import it, which is the
    button this window offers rather than an edit box that would write
    to the wrong place.
    """
    u = _ucas_statement(application_id)
    if u is None:
        messagebox.showinfo(
            "Not found",
            f"UCAS application #{application_id} no longer has a "
            "personal statement that is missing from here.",
            parent=gui.root)
        on_changed()
        return

    win = tk.Toplevel(gui.root)
    win.title(f"Personal statement on UCAS application #{application_id}")
    win.transient(gui.root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=f"{u.student_id}  ·  cycle {u.cycle_year}  ·  "
                        f"application {u.app_status}",
              font=("", 11, "bold")).pack(anchor="w")
    ttk.Label(frm,
              text="This statement is on the student's UCAS application. "
                   "It is not a draft here, so it has no review history, "
                   "reviewer or feedback until it is imported.",
              foreground="#555", wraplength=620, justify="left").pack(
        anchor="w", pady=(2, 8))

    body = tk.Text(frm, wrap="word", width=82, height=20,
                   font=("TkFixedFont", 10))
    vs = ttk.Scrollbar(frm, orient="vertical", command=body.yview)
    body.configure(yscrollcommand=vs.set)
    body.pack(side="top", fill="both", expand=True)
    body.insert("1.0", u.body)
    body.configure(state="disabled")

    ttk.Label(frm, text=_counter_text(u.word_count, u.char_count,
                                       u.line_count),
              foreground="#555").pack(anchor="w", pady=(4, 8))

    bar = ttk.Frame(frm)
    bar.pack(anchor="w")
    ttk.Button(bar, text="Import as draft",
               command=lambda: (win.destroy(),
                                _import_ucas_statement(
                                    gui, application_id,
                                    on_changed=on_changed))
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="left")


def _import_ucas_statement(gui, application_id: int, *,
                           on_changed: Callable[[], None]) -> None:
    """Adopt an application's statement as a reviewable draft."""
    u = _ucas_statement(application_id)
    if u is None:
        on_changed()
        return
    if not messagebox.askyesno(
        "Import as draft",
        f"Import {u.student_id}'s statement from UCAS application "
        f"#{application_id} (cycle {u.cycle_year}) as a draft here?\n\n"
        "The application keeps its own copy — this makes a reviewable "
        "draft alongside it, so it can be given feedback and pushed "
        "back when it is ready.",
        parent=gui.root,
    ):
        return
    try:
        created = data.import_from_ucas(application_id)
    except ValidationError as e:
        messagebox.showerror("Cannot import", str(e), parent=gui.root)
        return
    except Exception as e:
        logger.exception("import_from_ucas crashed")
        messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
        return
    gui.status_var.set(
        f"Imported UCAS application #{application_id} as draft "
        f"#{created.statement_id}")
    on_changed()
    open_editor(gui, statement_id=created.statement_id)


def _counter_text(words: int, chars: int, lines: int) -> str:
    """The shared counter line, so the viewer and editor read alike."""
    text = (f"  {words} words  ·  {chars}/{MAX_CHARS} chars  "
            f"({MAX_CHARS - chars} left)  ·  "
            f"{lines}/{MAX_LINES} lines ({MAX_LINES - lines} left)")
    warn = []
    if chars > MAX_CHARS:
        warn.append(f"⚠ {chars - MAX_CHARS} over char limit")
    elif chars > MAX_CHARS - 200:
        warn.append("⚠ near char limit")
    if lines > MAX_LINES:
        warn.append(f"⚠ {lines - MAX_LINES} over line limit")
    return text + ("   " + " · ".join(warn) if warn else "")


# ─── Editor tab ─────────────────────────────────────────────────────

def _build_editor_tab(gui, parent: ttk.Frame) -> None:
    """Default editor tab — open the most recent draft or a blank one."""
    rows = data.list_statements()
    if rows:
        _render_editor(gui, parent, rows[0].statement_id)
    else:
        ttk.Label(
            parent,
            text=("No personal statements yet. "
                  "Use Directory → New to start one."),
            foreground="#555",
        ).pack(anchor="w", pady=8)


def open_editor(gui, *, statement_id: int | None) -> None:
    """Standalone full-page editor."""
    frame = _clear(gui)
    _heading(frame,
             f"Personal Statement #{statement_id}"
             if statement_id else "New Personal Statement")
    _render_editor(gui, frame, statement_id)
    ttk.Button(frame, text="Back to Personal Statements",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_editor(
    gui, parent: ttk.Frame, statement_id: int | None,
) -> None:
    existing = data.get_statement(statement_id) if statement_id else None

    # Header
    head = ttk.Frame(parent)
    head.pack(anchor="w", fill="x", pady=(0, 8))

    students = student_data.list_students()
    student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
    student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                        for s in students}

    if existing:
        ttk.Label(
            head,
            text=f"Student: {existing.student_id}",
            font=("", 11, "bold"),
        ).pack(side="left", padx=(0, 12))
        student_var = tk.StringVar(value=existing.student_id)
    else:
        ttk.Label(head, text="Student:",
                  font=("", 11, "bold")).pack(side="left")
        student_var = tk.StringVar(
            value=student_labels[0] if student_labels else "")
        ttk.Combobox(head, textvariable=student_var,
                     values=student_labels,
                     state="readonly", width=36
                     ).pack(side="left", padx=(4, 12))

    title_var = tk.StringVar(
        value=(existing.title or "") if existing else "")
    ttk.Label(head, text="Title:").pack(side="left")
    ttk.Entry(head, textvariable=title_var, width=24
              ).pack(side="left", padx=(4, 12))

    status_var = tk.StringVar(
        value=existing.status if existing else DEFAULT_STATUS)
    ttk.Label(head, text="Status:").pack(side="left")
    ttk.Combobox(head, textvariable=status_var, values=list(STATUSES),
                 state="readonly", width=12
                 ).pack(side="left", padx=(4, 12))

    # Format: three questions from 2026 entry, one statement before. An
    # existing statement keeps the format it was written in.
    label_to_format = {v: k for k, v in FORMAT_LABELS.items()}
    format_var = tk.StringVar(value=FORMAT_LABELS[
        existing.format if existing else data.default_format()])
    ttk.Label(head, text="Format:").pack(side="left")
    if existing:
        ttk.Label(head, textvariable=format_var).pack(side="left", padx=(4, 0))
    else:
        ttk.Combobox(head, textvariable=format_var,
                     values=list(FORMAT_LABELS.values()), state="readonly",
                     width=34).pack(side="left", padx=(4, 0))

    def _format() -> str:
        return label_to_format.get(format_var.get(), FORMAT_SINGLE)

    # Body — single statement
    body_frame = ttk.Frame(parent)
    body_text = tk.Text(body_frame, wrap="word", width=82, height=22,
                        font=("TkFixedFont", 10))
    vs = ttk.Scrollbar(body_frame, orient="vertical",
                        command=body_text.yview)
    body_text.configure(yscrollcommand=vs.set)
    body_text.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    if existing and existing.body and not existing.is_three_question:
        body_text.insert("1.0", existing.body)

    # Body — three questions, one box each
    three_frame = ttk.Frame(parent)
    answer_boxes: list[tk.Text] = []
    for i, question in enumerate(QUESTIONS, 1):
        ttk.Label(three_frame, text=f"{i}. {question}",
                  font=("", 10, "bold"), wraplength=900,
                  justify="left").pack(anchor="w", pady=(4, 0))
        box = tk.Text(three_frame, wrap="word", width=82, height=6,
                      font=("TkFixedFont", 10))
        box.pack(fill="both", expand=True)
        if existing and existing.is_three_question:
            box.insert("1.0", existing.answers[i - 1])
        answer_boxes.append(box)

    def _answers() -> tuple[str, str, str]:
        return tuple(b.get("1.0", "end-1c") for b in answer_boxes)  # type: ignore[return-value]

    def _show_format(*_a) -> None:
        body_frame.pack_forget()
        three_frame.pack_forget()
        target = three_frame if _format() == FORMAT_THREE else body_frame
        target.pack(fill="both", expand=True, pady=(0, 8), before=counter_label)
        _update_counter()

    # An existing statement is read, not rewritten. These are the
    # student's own words going to UCAS under their name, and a review
    # screen that silently lets a reviewer retype them is how a student
    # ends up submitting a sentence they never wrote. Feedback below is
    # how a reviewer changes a statement — by asking for the change.
    #
    # A *new* statement still needs a typeable box, because otherwise
    # there is no way to enter one at all.
    if existing:
        body_text.configure(state="disabled")
        for box in answer_boxes:
            box.configure(state="disabled")

    # Counter line (updates live while a new draft is being typed)
    counter_var = tk.StringVar(value="")
    counter_label = ttk.Label(parent, textvariable=counter_var,
                              foreground="#555")
    counter_label.pack(anchor="w")

    def _update_counter(*_a) -> None:
        short: list[str] = []
        if _format() == FORMAT_THREE:
            answers = _answers()
            words, chars, lines = compute_three_counts(answers)
            short = [f"Q{i} {len(a)}/{MIN_ANSWER_CHARS} min"
                     for i, a in enumerate(answers, 1)
                     if len(a.strip()) < MIN_ANSWER_CHARS]
        else:
            body = body_text.get("1.0", "end-1c")
            words, chars, lines = compute_counts(body)
        counter_var.set(_counter_text(words, chars, lines)
                        + (("   ⚠ " + ", ".join(short)) if short else ""))
        counter_label.configure(
            foreground=("#a33"
                        if chars > MAX_CHARS or lines > MAX_LINES
                        else ("#7a5800" if short else "#555")))

    if not existing:
        body_text.bind("<KeyRelease>", _update_counter)
        for box in answer_boxes:
            box.bind("<KeyRelease>", _update_counter)
        format_var.trace_add("write", _show_format)
    _show_format()

    if existing:
        ttk.Label(
            parent,
            text="Read-only — the statement is the student's to change. "
                 "Use Feedback below to tell them what to change.",
            foreground="#777").pack(anchor="w", pady=(2, 0))

    # Reviewer / feedback
    rev_frame = ttk.Frame(parent)
    rev_frame.pack(anchor="w", fill="x", pady=(8, 0))
    # Prefilled with whoever is signed in, so reviewing a draft does not
    # start with typing your own name. An existing reviewer wins: that
    # records who actually reviewed it, which is not necessarily whoever
    # opened it next.
    reviewer_var = tk.StringVar(
        value=((existing.reviewer if existing else None)
               or _current_reviewer(gui)))
    ttk.Label(rev_frame, text="Reviewer:").pack(side="left")
    ttk.Entry(rev_frame, textvariable=reviewer_var, width=28
              ).pack(side="left", padx=(4, 12))

    ttk.Label(parent, text="Feedback:").pack(anchor="w", pady=(8, 2))
    feedback_text = tk.Text(parent, wrap="word", width=82, height=4)
    feedback_text.pack(anchor="w")
    if existing and existing.feedback:
        feedback_text.insert("1.0", existing.feedback)

    # Actions
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(12, 0))

    def _save() -> dict[str, Any] | None:
        if existing:
            sid = existing.student_id
        else:
            sid = student_by_label.get(student_var.get())
            if not sid:
                messagebox.showerror("Cannot save",
                                     "Pick a student.", parent=gui.root)
                return None
        payload = {
            "student_id": sid,
            "title":      title_var.get(),
            "status":     status_var.get(),
            "reviewer":   reviewer_var.get(),
            "feedback":   feedback_text.get("1.0", "end-1c").strip(),
        }
        # The body is only ever sent for a new draft. Omitting the key on
        # an update leaves the stored text exactly as it is, which is the
        # same guarantee the read-only box makes — enforced here too, so
        # it does not depend on a widget state to hold.
        if not existing:
            payload["format"] = _format()
            if _format() == FORMAT_THREE:
                for i, answer in enumerate(_answers(), 1):
                    payload[f"answer_{i}"] = answer
            else:
                payload["body"] = body_text.get("1.0", "end-1c")
        try:
            if existing:
                saved = data.update_statement(existing.statement_id, payload)
            else:
                saved = data.create_statement(payload)
        except ValidationError as e:
            logger.warning("save statement rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return None
        except Exception as e:
            logger.exception("save statement crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return None
        gui.status_var.set(f"Saved personal statement #{saved.statement_id}")
        return {"id": saved.statement_id}

    def save() -> None:
        result = _save()
        if not result:
            return
        messagebox.showinfo("Saved",
                            f"Saved statement #{result['id']}.",
                            parent=gui.root)
        # Re-render with the new id so subsequent saves are updates.
        open_editor(gui, statement_id=result["id"])

    def save_and_push() -> None:
        result = _save()
        if not result:
            return
        if not messagebox.askyesno(
            "Push to UCAS",
            f"Push this statement to "
            f"{student_var.get().split(' — ')[0]}'s UCAS application?",
            parent=gui.root,
        ):
            return
        try:
            aid = data.push_to_ucas(result["id"])
        except ValidationError as e:
            messagebox.showerror("Cannot push", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("push_to_ucas crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        messagebox.showinfo(
            "Pushed",
            f"Saved and pushed to UCAS application #{aid}.",
            parent=gui.root,
        )
        open_editor(gui, statement_id=result["id"])

    def delete() -> None:
        if not existing:
            return
        if not messagebox.askyesno(
            "Delete statement",
            f"Delete personal statement #{existing.statement_id}?",
            parent=gui.root,
        ):
            return
        try:
            data.delete_statement(existing.statement_id)
        except Exception as e:
            logger.exception("delete_statement crashed")
            messagebox.showerror("Error", f"Could not delete: {e}",
                                 parent=gui.root)
            return
        gui.status_var.set("Deleted statement")
        open_directory(gui)

    def email_feedback() -> None:
        """Save the review, then send the feedback to the student."""
        if not existing:
            messagebox.showinfo(
                "Save first",
                "Save this statement before emailing feedback on it.",
                parent=gui.root)
            return
        if not feedback_text.get("1.0", "end-1c").strip():
            messagebox.showwarning(
                "No feedback",
                "Write the feedback first — the email carries what is in "
                "the Feedback box.",
                parent=gui.root)
            return
        # Saved before sending, so the student never receives feedback
        # that differs from what this screen shows the next reviewer.
        result = _save()
        if not result:
            return
        saved = data.get_statement(result["id"])
        if saved is None:
            return
        student = student_data.get_student(saved.student_id)
        to = (student.email if student else "") or "(no address on file)"
        if not messagebox.askyesno(
            "Email feedback",
            f"Send this feedback to {saved.student_id} at {to}?\n\n"
            f"The email also carries the draft's status ({saved.status}) "
            f"and its {saved.char_count}/{MAX_CHARS} character position.",
            parent=gui.root,
        ):
            return
        from education_system.systems.sixth_form.domain.progression.university import feedback_notice
        msg = feedback_notice.send_feedback_email(
            saved, reviewer=reviewer_var.get().strip() or None)
        if msg is None:
            # Never raises and logs the reason; the review is saved
            # either way, so this is a notice rather than a failure the
            # reviewer has to resolve here.
            messagebox.showwarning(
                "Not sent",
                "The review was saved, but the feedback email could not "
                "be sent — the student may have no email address on "
                "file. See the log for the reason.",
                parent=gui.root)
            gui.status_var.set(
                f"Statement #{saved.statement_id} saved; feedback email "
                "not sent")
            return
        gui.status_var.set(
            f"Emailed feedback on statement #{saved.statement_id} to "
            f"{saved.student_id}")
        messagebox.showinfo(
            "Feedback sent",
            f"Feedback emailed to {saved.student_id} as message "
            f"#{msg.message_id}.",
            parent=gui.root)
        open_editor(gui, statement_id=saved.statement_id)

    ttk.Button(actions, text="Save review" if existing else "Save",
               command=save).pack(side="left", padx=(0, 6))
    if existing:
        ttk.Button(actions, text="Email feedback to student",
                   command=email_feedback).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Save & push to UCAS",
               command=save_and_push).pack(side="left", padx=(0, 6))
    if existing:
        ttk.Button(actions, text="Delete",
                   command=delete).pack(side="left", padx=(0, 6))


# ─── Per-student summary tab ────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            rows = data.per_student_summary()
        except Exception as e:
            logger.exception("per_student_summary failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return
        if not rows:
            ttk.Label(holder, text="No personal statements yet.",
                      foreground="#555").pack(anchor="w")
            return

        cols = ("student_id", "drafts", "latest_status",
                "latest_chars", "latest_lines", "submitted")
        headings = {
            "student_id":    ("Student",    110),
            "drafts":        ("Drafts",      60),
            "latest_status": ("Latest",     110),
            "latest_chars":  ("Chars",       70),
            "latest_lines":  ("Lines",       60),
            "submitted":     ("Submitted?", 100),
        }
        tree = ttk.Treeview(holder, columns=cols,
                            show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for s in rows:
            tree.insert("", "end", iid=s.student_id, values=(
                s.student_id, s.drafts,
                s.latest_status or "—",
                s.latest_chars, s.latest_lines,
                "Yes" if s.has_submitted else "No",
            ))
        gui.status_var.set(f"PS summary: {len(rows)} student(s)")

    refresh_bar = ttk.Frame(parent)
    refresh_bar.pack(anchor="w", pady=(0, 8))
    ttk.Button(refresh_bar, text="Refresh", command=render
               ).pack(side="left")
    render()
