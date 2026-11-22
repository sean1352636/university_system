"""The HESA Data Futures builder: reference period, validation report, SIDs and
coding frames. Everything goes through ``application/statutory``; this system
writes the upload file but never submits it.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

from education_system.systems.university.application.statutory import access as sa
from education_system.systems.university.application.statutory import hesa_codes, hesa_return

TITLE = "HESA Data Futures"


def current_academic_year(today: date | None = None) -> str:
    """The HESA year holding ``today``: it runs 1 August to 31 July."""
    today = today or date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}/{(start + 1) % 100:02d}"


def _tree(master, columns, height=12) -> ttk.Treeview:
    frame = ttk.Frame(master)
    frame.pack(fill=tk.BOTH, expand=True)
    view = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height,
                        selectmode="browse")
    for key, heading, width in columns:
        view.heading(key, text=heading)
        view.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
    view.configure(yscrollcommand=bar.set)
    view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    bar.pack(side=tk.LEFT, fill=tk.Y)
    return view


def _fill(view, rows, columns) -> dict:
    view.delete(*view.get_children())
    return {view.insert("", tk.END, values=["" if row.get(c[0]) is None else row.get(c[0])
                                            for c in columns]): row for row in rows}


class HesaPanel(ttk.Frame):
    """``user`` is a callable returning the signed-in session dict; ``on_change``
    runs after a build so the host can refresh its list of returns."""

    ISSUES = (("level", "Level", 70), ("student_id", "Student", 100), ("entity", "Entity", 170),
              ("field", "Field", 130), ("message", "Message", 560))
    MISSING = (("student_id", "Student", 120), ("name", "Name", 300))
    CODES = (("code", "Code", 90), ("label", "Label", 480), ("active", "Active", 60),
             ("notes", "Source", 90))

    def __init__(self, master, user=None, on_change=None):
        super().__init__(master, padding=8)
        self._user = user if callable(user) else (lambda: user)
        self.on_change = on_change
        self.periods: dict[str, dict] = {}
        self.return_id: int | None = None
        book = ttk.Notebook(self)
        book.pack(fill=tk.BOTH, expand=True)
        self._build_tab(book)
        self._sids_tab(book)
        self._codes_tab(book)
        self._load_periods(quiet=True)

    def _run(self, fn, *args, **kwargs):
        """``fn(*args, **kwargs)``, showing any refusal or failure; ``None`` then."""
        try:
            return fn(*args, **kwargs)
        except (PermissionError, ValueError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self)
        except Exception as exc:
            messagebox.showerror(TITLE, f"That didn't work: {exc}", parent=self)
        return None

    # ---------------------------------------------------------------- build
    def _build_tab(self, book):
        tab = ttk.Frame(book, padding=8)
        book.add(tab, text="Build & Validate")
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Academic year:").pack(side=tk.LEFT)
        self.year = tk.StringVar(value=current_academic_year())
        year = ttk.Entry(bar, textvariable=self.year, width=9)
        year.pack(side=tk.LEFT, padx=4)
        year.bind("<FocusOut>", lambda _e: self._load_periods(quiet=True))
        ttk.Label(bar, text="Reference period:").pack(side=tk.LEFT, padx=(10, 4))
        self.period = tk.StringVar()
        self.period_box = ttk.Combobox(bar, textvariable=self.period, state="readonly", width=44)
        self.period_box.pack(side=tk.LEFT)
        ttk.Button(bar, text="Build return", command=self._build).pack(side=tk.LEFT, padx=8)
        ttk.Button(bar, text="Save issues as CSV…", command=self._save_csv).pack(side=tk.LEFT)
        self.status = tk.StringVar(value="Build a return to see its validation report.")
        ttk.Label(tab, textvariable=self.status, wraplength=1100, justify=tk.LEFT).pack(
            anchor="w", pady=6)
        self.issue_view = _tree(tab, self.ISSUES)

    def _load_periods(self, quiet=False):
        try:
            periods = hesa_return.reference_periods(self.year.get())
        except Exception as exc:
            if not quiet:
                messagebox.showerror(TITLE, str(exc), parent=self)
            periods = []
        self.periods = {p["label"]: p for p in periods}
        self.period_box.configure(values=list(self.periods))
        self.period.set(next(iter(self.periods), ""))

    def _build(self):
        self._load_periods()
        period = self.periods.get(self.period.get())
        if not period:
            return
        built = self._run(hesa_return.build, self._user(), self.year.get(),
                          period_start=period["start"], period_end=period["end"],
                          reference_period=period["label"])
        if built is None:
            return
        self.return_id = built["return_id"]
        _fill(self.issue_view, built["issues"], self.ISSUES)
        counts = ", ".join(f"{v} {k}" for k, v in built["counts"].items())
        where = (f"Upload file: {built['output_path']}" if built["output_path"]
                 else "No upload file: fix the errors and build again.")
        self.status.set(f"Return #{built['return_id']} ({built['status']}): {counts}. "
                        f"{built['errors']} error(s), {built['warnings']} warning(s). {where}")
        if self.on_change:
            self.on_change()

    def _save_csv(self):
        if self.return_id is None:
            messagebox.showinfo(TITLE, "Build a return first.", parent=self)
            return
        text = self._run(hesa_return.report_csv, self._user(), self.return_id)
        if text is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"hesa_return_{self.return_id}_issues.csv")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as out:
                out.write(text)
        except OSError as exc:
            messagebox.showerror(TITLE, f"Could not save: {exc}", parent=self)

    # ---------------------------------------------------------------- SIDs
    def _sids_tab(self, book):
        tab = ttk.Frame(book, padding=8)
        book.add(tab, text="Student identifiers (SID)")
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(bar, text="List students with no SID",
                   command=self._list_missing).pack(side=tk.LEFT)
        ttk.Button(bar, text="Import CSV…", command=self._import_sids).pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="(columns student_id, sid)", foreground="#777777").pack(side=tk.LEFT)
        form = ttk.Frame(tab)
        form.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        ttk.Label(form, text="Student:").pack(side=tk.LEFT)
        self.sid_student = tk.StringVar()
        ttk.Entry(form, textvariable=self.sid_student, width=14).pack(side=tk.LEFT, padx=4)
        ttk.Label(form, text="SID (13 digits):").pack(side=tk.LEFT, padx=(8, 4))
        self.sid_value = tk.StringVar()
        ttk.Entry(form, textvariable=self.sid_value, width=18).pack(side=tk.LEFT)
        ttk.Button(form, text="Save SID", command=self._save_sid).pack(side=tk.LEFT, padx=8)
        self.missing_view = _tree(tab, self.MISSING)
        self.missing_view.bind("<<TreeviewSelect>>", self._pick_missing)
        self.missing_rows = {}

    def _list_missing(self):
        rows = self._run(hesa_return.missing_sids, self._user(), self.year.get())
        if rows is not None:
            self.missing_rows = _fill(self.missing_view, rows, self.MISSING)
            if not rows:
                messagebox.showinfo(TITLE, "Every student in this year's return has a SID.",
                                    parent=self)

    def _pick_missing(self, _event=None):
        sel = self.missing_view.selection()
        if sel and sel[0] in self.missing_rows:
            self.sid_student.set(self.missing_rows[sel[0]]["student_id"])

    def _save_sid(self):
        student = self.sid_student.get().strip()
        try:
            hesa_return.set_sid(self._user(), student, self.sid_value.get())
        except (PermissionError, ValueError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror(TITLE, f"That didn't work: {exc}", parent=self)
            return
        self.sid_value.set("")
        for iid, row in list(self.missing_rows.items()):
            if row["student_id"] == student:
                self.missing_view.delete(iid)
                del self.missing_rows[iid]

    def _import_sids(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig", newline="") as src:
                text = src.read()
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror(TITLE, f"Could not read the file: {exc}", parent=self)
            return
        result = self._run(hesa_return.import_sids, self._user(), text)
        if result is None:
            return
        lines = [f"{result['recorded']} SID(s) recorded, {len(result['refused'])} refused."]
        lines += [f"Line {r['line']}: {r['error']}" for r in result["refused"][:15]]
        messagebox.showinfo(TITLE, "\n".join(lines), parent=self)

    # --------------------------------------------------------------- codes
    def _codes_tab(self, book):
        tab = ttk.Frame(book, padding=8)
        book.add(tab, text="Coding frames")
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(bar, text="Field:").pack(side=tk.LEFT)
        self.code_field = tk.StringVar(value=hesa_codes.FIELDS[0] if hesa_codes.FIELDS else "")
        field = ttk.Combobox(bar, textvariable=self.code_field, values=hesa_codes.FIELDS,
                             state="readonly", width=20)
        field.pack(side=tk.LEFT, padx=4)
        field.bind("<<ComboboxSelected>>", lambda _e: self._load_codes())
        ttk.Button(bar, text="Show", command=self._load_codes).pack(side=tk.LEFT)
        form = ttk.LabelFrame(tab, text="Add or edit a code", padding=8)
        form.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        ttk.Label(form, text="Code:").pack(side=tk.LEFT)
        self.code_value = tk.StringVar()
        ttk.Entry(form, textvariable=self.code_value, width=12).pack(side=tk.LEFT, padx=4)
        ttk.Label(form, text="Label:").pack(side=tk.LEFT, padx=(8, 4))
        self.code_label = tk.StringVar()
        ttk.Entry(form, textvariable=self.code_label, width=50).pack(side=tk.LEFT)
        self.code_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Active", variable=self.code_active).pack(side=tk.LEFT, padx=8)
        ttk.Button(form, text="Save code", command=self._save_code).pack(side=tk.LEFT)
        self.code_view = _tree(tab, self.CODES)
        self.code_view.bind("<<TreeviewSelect>>", self._pick_code)
        self.code_rows = {}

    def _read_codes(self, field):
        with sa.session() as conn:
            return hesa_codes.frame(conn, field)

    def _load_codes(self):
        if self._run(sa.officer, self._user()) is None:
            return
        rows = self._run(self._read_codes, self.code_field.get())
        if rows is not None:
            self.code_rows = _fill(self.code_view, rows, self.CODES)

    def _pick_code(self, _event=None):
        sel = self.code_view.selection()
        if sel and sel[0] in self.code_rows:
            row = self.code_rows[sel[0]]
            self.code_value.set(row["code"])
            self.code_label.set(row["label"])
            self.code_active.set(bool(row.get("active", 1)))

    def _save_code(self):
        try:
            hesa_codes.save_code(self._user(), self.code_field.get(), self.code_value.get(),
                                 self.code_label.get(), self.code_active.get())
        except (PermissionError, ValueError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror(TITLE, f"That didn't work: {exc}", parent=self)
            return
        self.code_value.set("")
        self.code_label.set("")
        self._load_codes()
