# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.post_18.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.post_18.university_system.core.i18n import get_text as _t
from education_system.post_18.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction, foreign_keys_off
from education_system.post_18.university_system.core.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.post_18.university_system.modules.shared.gui.main.students.student_crud_gui")

try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

from .widgets import _DOBPicker, _safe_set_combobox, _safe_entry_insert

from education_system.post_18.university_system.modules.domain.academics.services.admissions_selection import (
    normalise_grade as _normalise_grade,
    enrol_student_in_curriculum as _enrol_student_in_curriculum,
    ensure_module_chat_rooms_and_join,
    get_course as _get_course,
)
from education_system.post_18.university_system.modules.shared.services.student_provisioning import (
    compute_age as _compute_age,
    default_student_password as _default_student_password,
    provision_student_login as _provision_student_login,
)


def _sixth_form_alevel_grades(student_id, subjects):
    """Best A-level grade per subject for a sixth-form student.

    Prefers achieved exam results, then falls back to teacher-predicted
    grades. Returns a ``{subject: grade}`` dict (subject keys exactly as
    stored in the sixth-form system). Best-effort: returns ``{}`` if the
    sixth-form assessment modules aren't importable or hold nothing for this
    student, so "grades if available" degrades gracefully to "no grades".
    """
    grades: dict[str, str] = {}
    try:
        from education_system.post_16.sixthform_system.modules.domain.assessment.exam_results import (
            exam_results as _exam_results,
        )
        for rr in _exam_results.results_for_student(student_id):
            if rr.subject and rr.result and rr.result.grade:
                grades.setdefault(rr.subject, rr.result.grade)
    except Exception:
        logger.debug(
            "Sixth-form exam results unavailable for %s", student_id,
            exc_info=True)
    try:
        from education_system.post_16.sixthform_system.modules.domain.assessment.predicted_grades import (
            predicted_grades as _predicted_grades,
        )
        for p in _predicted_grades.predictions_for_student(student_id):
            if p.subject and p.grade:
                grades.setdefault(p.subject, p.grade)
    except Exception:
        logger.debug(
            "Sixth-form predicted grades unavailable for %s", student_id,
            exc_info=True)
    return grades


def _open_sixth_form_import_dialog(parent_dialog, fields):
    """Modal picker showing Year 13 students from the sixth-form system.

    On confirm, pre-fills the parent create-student dialog's title,
    first/middle/last name, gender, and date-of-birth fields, plus the three
    A-level subjects the student studies and their grades where available
    (achieved exam results first, otherwise teacher-predicted grades). The
    UCAS tariff recomputes from the filled grades; course assignment and visa
    details are intentionally left to the user.

    Errors are surfaced via messagebox and logged; the parent dialog
    is left untouched if anything goes wrong.
    """
    try:
        from education_system.post_16.sixthform_system.modules.domain.students.students import (
            students as sf_students,
        )
    except Exception:
        logger.exception("Sixth-form module not importable")
        messagebox.showerror(
            "Import from Sixth Form System",
            "Could not load the sixth-form student module. "
            "Make sure the sixth-form system is installed alongside "
            "the university system.",
            parent=parent_dialog,
        )
        return

    try:
        rows = sf_students.list_year_13_students()
    except Exception as e:
        logger.exception("list_year_13_students failed")
        messagebox.showerror(
            "Import from Sixth Form System",
            f"Could not load Year 13 students: {e}",
            parent=parent_dialog,
        )
        return

    if not rows:
        messagebox.showinfo(
            "Import from Sixth Form System",
            "No active Year 13 students were found in the sixth-form "
            "database. (Looking for enrolments with year_group=13 and "
            "status='Enrolled'.)",
            parent=parent_dialog,
        )
        return

    picker = tk.Toplevel(parent_dialog)
    picker.title("Import from Sixth Form System — Year 13")
    picker.geometry("820x520")
    picker.transient(parent_dialog)
    try:
        picker.grab_set()
    except tk.TclError:
        pass

    header = ttk.Frame(picker, padding=(12, 10, 12, 4))
    header.pack(fill=tk.X)
    ttk.Label(
        header,
        text=("Year 13 students in the sixth-form database. "
              "Pick one and click Import to pre-fill the form."),
        font=('Arial', 10),
    ).pack(side=tk.LEFT)

    body = ttk.Frame(picker, padding=(12, 4, 12, 12))
    body.pack(fill=tk.BOTH, expand=True)

    cols = ("student_id", "name", "title", "gender", "dob")
    headings = {
        "student_id": "Student ID",
        "name":       "Name",
        "title":      "Title",
        "gender":     "Gender",
        "dob":        "Date of birth",
    }
    widths = {"student_id": 110, "name": 260,
              "title": 80, "gender": 90, "dob": 120}

    tree = ttk.Treeview(body, columns=cols, show='headings',
                         selectmode='browse')
    for c in cols:
        tree.heading(c, text=headings[c])
        tree.column(c, width=widths[c],
                     anchor=tk.W if c in ('student_id', 'name')
                                  else tk.CENTER)
    vsb = ttk.Scrollbar(body, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    for s in rows:
        tree.insert(
            "", "end", iid=s.student_id,
            values=(s.student_id, s.full_name,
                      s.title or "—",
                      s.gender or "—",
                      s.date_of_birth or "—"),
        )

    footer = ttk.Frame(picker, padding=(12, 0, 12, 12))
    footer.pack(fill=tk.X)
    info = ttk.Label(footer, text="", foreground="#666")
    info.pack(side=tk.LEFT)

    def _do_import():
        sel = tree.selection()
        if not sel:
            info.config(text="Select a student first.")
            return
        sid = sel[0]
        student = next((s for s in rows if s.student_id == sid), None)
        if student is None:
            info.config(text="Selection lost — refresh the list.")
            return
        # Remember the origin id on the parent dialog so the eventual
        # Save handler can call mark_transferred() against the right
        # sixth-form row.
        try:
            parent_dialog._sixth_form_origin_id = student.student_id
        except Exception:
            logger.exception(
                "Could not stash sixth-form origin id on dialog")
        try:
            # Pre-fill the parent form. Use _safe_entry_insert helper
            # for entries; combobox uses .set() which is safe.
            if student.title and 'title' in fields:
                _safe_set_combobox(fields['title'], student.title)
            if 'first_name' in fields:
                fields['first_name'].delete(0, tk.END)
                _safe_entry_insert(fields['first_name'],
                                     student.first_name or "")
            if 'middle_name' in fields:
                fields['middle_name'].delete(0, tk.END)
                _safe_entry_insert(fields['middle_name'],
                                     student.middle_name or "")
            if 'last_name' in fields:
                fields['last_name'].delete(0, tk.END)
                _safe_entry_insert(fields['last_name'],
                                     student.last_name or "")
            if student.gender and 'gender' in fields:
                _safe_set_combobox(fields['gender'], student.gender)
            if student.date_of_birth and 'dob' in fields:
                # The DOB widget is now a _DOBPicker; use its set()
                # rather than delete/insert on a plain Entry.
                try:
                    fields['dob'].set(student.date_of_birth)
                except Exception:
                    # Fallback for the legacy Entry just in case.
                    fields['dob'].delete(0, tk.END)
                    _safe_entry_insert(fields['dob'],
                                         student.date_of_birth)
        except Exception as e:
            logger.exception(
                "Pre-filling form from sixth-form student %s failed", sid)
            messagebox.showerror(
                "Import from Sixth Form System",
                f"Could not pre-fill the form: {e}",
                parent=picker,
            )
            return

        # Pre-fill the three A-level subjects + grades (where available) from
        # the sixth-form record so the UCAS tariff / course eligibility come
        # from the student's real results rather than being re-keyed. Subjects
        # with no grade on record are left blank for the user to complete.
        filled_grades = 0
        sf_subjects = list(getattr(student, "subjects", []) or [])
        try:
            grade_by_subject = _sixth_form_alevel_grades(
                student.student_id, sf_subjects)
            norm_grades = {
                (subj or "").strip().lower(): grade
                for subj, grade in grade_by_subject.items()
            }
            for i in range(1, 4):
                subj = sf_subjects[i - 1] if i - 1 < len(sf_subjects) else ""
                if f"alevel_subj_{i}" in fields:
                    fields[f"alevel_subj_{i}"].delete(0, tk.END)
                    _safe_entry_insert(fields[f"alevel_subj_{i}"], subj or "")
                if f"alevel_grade_{i}" in fields:
                    grade = _normalise_grade(
                        norm_grades.get((subj or "").strip().lower(), ""))
                    fields[f"alevel_grade_{i}"].set(grade)
                    if grade:
                        filled_grades += 1
            # ``.set()`` doesn't fire <<ComboboxSelected>>, so nudge the tariff
            # label to recompute from the freshly filled grades.
            if "alevel_grade_3" in fields:
                try:
                    fields["alevel_grade_3"].event_generate(
                        "<<ComboboxSelected>>")
                except Exception:
                    pass
        except Exception:
            logger.exception(
                "Pre-filling A-levels from sixth-form student %s failed", sid)

        logger.info(
            "Imported sixth-form student %s (%s) into university "
            "create-student dialog (fields pre-filled: title=%s, "
            "gender=%s, dob=%s, a_levels=%d/%d subjects, grades=%d)",
            student.student_id, student.full_name,
            bool(student.title), bool(student.gender),
            bool(student.date_of_birth),
            len(sf_subjects), 3, filled_grades,
        )
        if sf_subjects and filled_grades < len(sf_subjects):
            messagebox.showinfo(
                "Import from Sixth Form System",
                "Imported the student's A-level subjects, but "
                f"{len(sf_subjects) - filled_grades} grade(s) were not on "
                "record in the sixth-form system. Please complete the missing "
                "A-level grade(s) before saving.",
                parent=parent_dialog,
            )
        picker.destroy()

    btns = ttk.Frame(footer)
    btns.pack(side=tk.RIGHT)
    ttk.Button(btns, text="Cancel",
                command=picker.destroy).pack(side=tk.RIGHT, padx=4)
    ttk.Button(btns, text="Import",
                command=_do_import).pack(side=tk.RIGHT, padx=4)

    tree.bind("<Double-Button-1>", lambda _e: _do_import())


def _open_bulk_csv_import_dialog(self, parent_dialog):
    """Bulk-create university students from a CSV file.

    Expected columns (case-insensitive, any subset is fine):
        first_name, middle_name, last_name, gender, dob, title

    For each well-formed row the function does a direct INSERT into
    ``students`` using the same fields the per-student create dialog
    produces, plus the same random course assignment + random module
    enrolment as the singleton create path. Per-row errors are
    collected and shown in a summary panel after the run — they do
    not abort the rest of the import.
    """
    win = tk.Toplevel(parent_dialog)
    win.title("Bulk import students from CSV")
    win.geometry("900x680")
    try:
        win.transient(parent_dialog)
        win.grab_set()
    except tk.TclError:
        pass

    # File picker row
    top = ttk.Frame(win, padding=(12, 10))
    top.pack(fill=tk.X)
    ttk.Label(top, text="CSV file:").pack(side=tk.LEFT)
    path_var = tk.StringVar()
    ttk.Entry(top, textvariable=path_var, width=70).pack(
        side=tk.LEFT, padx=(8, 8), fill=tk.X, expand=True)

    def _browse():
        p = filedialog.askopenfilename(
            parent=win,
            title="Choose CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if p:
            path_var.set(p)
            _refresh_preview()

    ttk.Button(top, text="Browse…",
                command=_browse).pack(side=tk.LEFT)

    # Preview area (column → field mapping + first few rows)
    body = ttk.Frame(win, padding=(12, 0))
    body.pack(fill=tk.BOTH, expand=True)

    map_frame = ttk.LabelFrame(body, text="Column mapping", padding=10)
    map_frame.pack(fill=tk.X, pady=(8, 6))
    map_widgets: dict[str, ttk.Combobox] = {}
    expected = ("first_name", "middle_name", "last_name",
                "gender", "dob", "title",
                "student_id", "email", "course", "registration_date",
                "module_1", "module_2", "module_3",
                "module_4", "module_5", "module_6")
    for i, field in enumerate(expected):
        ttk.Label(map_frame, text=f"{field}:").grid(
            row=i // 3, column=(i % 3) * 2,
            sticky=tk.W, padx=(0, 6), pady=2)
        cb = ttk.Combobox(map_frame, values=[""], state="readonly",
                            width=22)
        cb.grid(row=i // 3, column=(i % 3) * 2 + 1,
                  sticky=tk.W, padx=(0, 16), pady=2)
        map_widgets[field] = cb

    preview_lbl = ttk.LabelFrame(body, text="Preview (first 5 rows)",
                                    padding=10)
    preview_lbl.pack(fill=tk.BOTH, expand=True, pady=6)
    preview_text = scrolledtext.ScrolledText(
        preview_lbl, height=8, wrap=tk.NONE, font=("Courier", 9))
    preview_text.pack(fill=tk.BOTH, expand=True)

    # Status / summary at the bottom
    bottom = ttk.Frame(win, padding=(12, 6, 12, 12))
    bottom.pack(fill=tk.X)
    status_lbl = ttk.Label(bottom, text="", foreground="#666")
    status_lbl.pack(side=tk.LEFT)
    btns = ttk.Frame(bottom)
    btns.pack(side=tk.RIGHT)

    csv_rows: list[dict] = []
    csv_headers: list[str] = []

    def _refresh_preview():
        nonlocal csv_rows, csv_headers
        csv_rows = []
        csv_headers = []
        preview_text.configure(state="normal")
        preview_text.delete("1.0", tk.END)
        p = path_var.get().strip()
        if not p:
            preview_text.configure(state="disabled")
            return
        try:
            with open(p, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                csv_headers = reader.fieldnames or []
                for row in reader:
                    csv_rows.append(row)
        except Exception as e:
            status_lbl.config(text=f"Could not read CSV: {e}",
                                foreground="red")
            preview_text.configure(state="disabled")
            return
        # Populate combobox values
        for cb in map_widgets.values():
            cb.configure(values=[""] + csv_headers)
        # Auto-map by normalised name (case/space/underscore/hyphen-insensitive)
        def _norm(s: str) -> str:
            return "".join(ch for ch in s.lower() if ch.isalnum())
        norm_headers = {_norm(h): h for h in csv_headers}
        aliases = {
            "first_name":  ("firstname", "givenname", "forename"),
            "middle_name": ("middlename",),
            "last_name":   ("lastname", "surname", "familyname"),
            "gender":      ("sex",),
            "dob":         ("dateofbirth", "birthdate", "birthday"),
            "title":       ("salutation", "honorific"),
            "student_id":  ("studentid", "id", "studentnumber"),
            "email":       ("emailaddress", "emailaddr"),
            "course":      ("coursecode", "programme", "program"),
            "registration_date": ("registrationdate", "regdate",
                                  "enrolmentdate", "enrollmentdate"),
            "module_1":    ("module1", "mod1"),
            "module_2":    ("module2", "mod2"),
            "module_3":    ("module3", "mod3"),
            "module_4":    ("module4", "mod4"),
            "module_5":    ("module5", "mod5"),
            "module_6":    ("module6", "mod6"),
        }
        for field, cb in map_widgets.items():
            candidates = (field, *aliases.get(field, ()))
            match = ""
            for cand in candidates:
                if _norm(cand) in norm_headers:
                    match = norm_headers[_norm(cand)]
                    break
            cb.set(match)
        # Preview
        head = "  ".join(f"{h:<16}" for h in csv_headers)
        preview_text.insert("1.0", head + "\n" + "-" * len(head) + "\n")
        for row in csv_rows[:5]:
            line = "  ".join(
                f"{(row.get(h) or ''):<16}" for h in csv_headers)
            preview_text.insert(tk.END, line + "\n")
        preview_text.configure(state="disabled")
        status_lbl.config(
            text=f"{len(csv_rows)} row(s) loaded.  "
                  f"Map columns then click Import.",
            foreground="#444")

    def _import_rows():
        if not csv_rows:
            status_lbl.config(text="No rows to import.",
                                foreground="red")
            return
        mapping = {f: w.get() for f, w in map_widgets.items()}
        missing = [f for f in ("first_name", "last_name")
                    if not mapping.get(f)]
        if missing:
            status_lbl.config(
                text="Missing required column mapping: "
                      + ", ".join(missing),
                foreground="red")
            return

        ok_rows: list[str] = []
        err_rows: list[tuple[int, str]] = []

        def _cell(key: str) -> str:
            col = mapping.get(key, "")
            if not col:
                return ""
            return (row.get(col, "") or "").strip()

        def _module_code(raw: str) -> str:
            # Export writes "CODE - Module Name"; accept either form.
            raw = (raw or "").strip()
            if " - " in raw:
                raw = raw.split(" - ", 1)[0]
            return raw.strip()

        for idx, row in enumerate(csv_rows, start=2):  # 1=header line
            try:
                first_name = _cell("first_name")
                last_name  = _cell("last_name")
                gender_raw = _cell("gender").lower()
                dob_text   = _cell("dob")
                middle     = _cell("middle_name")
                title      = _cell("title") or None

                csv_student_id = _cell("student_id")
                csv_email      = _cell("email")
                csv_course     = _cell("course").upper()
                csv_reg_date   = _cell("registration_date")
                csv_modules    = [
                    _module_code(_cell(f"module_{i}"))
                    for i in range(1, 7)
                ]
                csv_modules = [m for m in csv_modules if m]

                if not first_name or not last_name:
                    raise ValueError(
                        "first_name and last_name are required")
                if not gender_raw:
                    gender_raw = "other"
                elif gender_raw not in ("male", "female", "other"):
                    raise ValueError(
                        "gender must be male / female / other")
                if not dob_text:
                    dob_text = "2000-01-01"
                try:
                    dob = datetime.strptime(dob_text, "%Y-%m-%d")
                except ValueError:
                    raise ValueError("dob must be YYYY-MM-DD")
                age = _compute_age(dob)

                # Validate the course against the live catalogue: accept any
                # real course code, fail fast on an unknown one, and only fall
                # back to a random default when the CSV left it blank.
                if csv_course:
                    if not _get_course(csv_course):
                        raise ValueError(f"unknown course code {csv_course!r}")
                    course = csv_course
                else:
                    course = random.choice(['CS', 'DS'])
                if not title:
                    title = "Mr" if gender_raw == "male" else "Ms"

                student_id = csv_student_id or str(
                    secrets.randbelow(9000000) + 1000000).zfill(7)
                email_address = csv_email or f"C{student_id}@tees.ac.uk"
                if csv_reg_date:
                    # Accept date-only or full timestamp.
                    reg_time = csv_reg_date if " " in csv_reg_date \
                        else f"{csv_reg_date} 00:00:00"
                else:
                    reg_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                temp_password = _default_student_password(first_name, student_id)

                enrolled_modules: list[str] = []
                conn = get_db_connection()
                if not conn:
                    raise RuntimeError("DB connection failed")
                try:
                    cur = conn.cursor()
                    # Reject a duplicate id; for an auto-generated id, regenerate
                    # on the rare clash instead of failing the row.
                    if csv_student_id:
                        cur.execute(
                            "SELECT 1 FROM students WHERE student_id = ?",
                            (student_id,))
                        if cur.fetchone():
                            raise ValueError(
                                f"student_id {student_id} already exists")
                    else:
                        for _ in range(25):
                            cur.execute(
                                "SELECT 1 FROM students WHERE student_id = ?",
                                (student_id,))
                            if cur.fetchone() is None:
                                break
                            student_id = str(
                                secrets.randbelow(9000000) + 1000000).zfill(7)
                            if not csv_email:
                                email_address = f"C{student_id}@tees.ac.uk"
                    # Email must be unique regardless of where the id came from.
                    cur.execute(
                        "SELECT 1 FROM students WHERE email_address = ?",
                        (email_address,))
                    if cur.fetchone():
                        raise ValueError(
                            f"email {email_address} already in use")
                    # FK checks off so module rows can be written before their
                    # catalog entries; the context manager restores enforcement
                    # even if the body raises.
                    with foreign_keys_off(conn):
                        cur.execute(
                            """INSERT INTO students
                                   (student_id, email_address, title,
                                    first_name, middle_name, last_name,
                                    gender, dob, age, course,
                                    registration_datetime, status,
                                    enrollment_date)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                       ?, 'Active', ?)""",
                            (student_id, email_address, title,
                             first_name, middle or None, last_name,
                             gender_raw, dob.strftime("%Y-%m-%d"),
                             age, course, reg_time, reg_time),
                        )
                        # Enrol in the course's full 18-module curriculum
                        # (6/year x 3) — the same set the single-create and CLI
                        # paths use, not only the modules the CSV listed.
                        curriculum = _enrol_student_in_curriculum(
                            cur, student_id, course, course)
                        enrolled_modules = [m["module_code"] for m in curriculum]
                        # Honour any explicit module codes from the CSV as extras.
                        extra = [m for m in csv_modules
                                 if m and m not in enrolled_modules]
                        if extra:
                            cur.executemany(
                                "INSERT OR IGNORE INTO student_modules "
                                "(student_id, module_code) VALUES (?, ?)",
                                [(student_id, m) for m in extra],
                            )
                            enrolled_modules.extend(extra)
                        cur.execute(
                            "UPDATE courses SET current_enrollment = "
                            "current_enrollment + 1 "
                            "WHERE course_code = ? AND status = 'active'",
                            (course,),
                        )
                    conn.commit()
                finally:
                    conn.close()

                # Provision the login in both auth stores (legacy
                # student_records.db user + central shared-auth) so the student
                # can sign in and be resolved for chat-room membership. The
                # bulk path previously created only the shared-auth row.
                _provision_student_login(
                    getattr(self, "auth", None),
                    username=student_id, password=temp_password,
                    email=email_address, first_name=first_name,
                    last_name=last_name,
                )

                # Auto-join the student to one chat room per enrolled module
                # (creating any missing room), matching the other create
                # paths. Best-effort.
                try:
                    ensure_module_chat_rooms_and_join(student_id, enrolled_modules)
                except Exception as exc:
                    logger.debug(
                        "Chat-room auto-join failed for %s during CSV "
                        "import: %s", student_id, exc)

                ok_rows.append(student_id)
            except Exception as e:
                err_rows.append((idx, str(e)))

        # Show summary
        summary = (
            f"Bulk import finished.\n\n"
            f"  Imported   : {len(ok_rows)} row(s)\n"
            f"  Skipped    : {len(err_rows)} row(s)\n\n"
        )
        if err_rows:
            summary += "Errors (line # — message):\n"
            for ln, msg in err_rows[:30]:
                summary += f"  line {ln}: {msg}\n"
            if len(err_rows) > 30:
                summary += f"  …plus {len(err_rows) - 30} more\n"
        messagebox.showinfo("CSV import", summary, parent=win)

        # Refresh the parent views
        try:
            if hasattr(self, "view_students"):
                self.view_students()
            self.refresh_advanced_search()
        except Exception:
            pass
        if ok_rows and not err_rows:
            win.destroy()

    ttk.Button(btns, text="Cancel",
                command=win.destroy).pack(side=tk.RIGHT, padx=4)
    ttk.Button(btns, text="Import",
                command=_import_rows).pack(side=tk.RIGHT, padx=4)


