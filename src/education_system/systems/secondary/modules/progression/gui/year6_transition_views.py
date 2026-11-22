"""Year 6 Transition screen: planning the whole incoming Year 7 cohort.

Heading with the intake year (drop-down), a summary line and Sync. Tabs:

* **Cohort** - everyone expected (platform transfers from primary and Year 7
  admissions offers): feeder, status, KS2, flags (as permitted), enhanced,
  form, checklist progress. Pupil details…, Transition report…, Edit…,
  Liaison note…, Start in September…, Start everyone…, Open pupil, Export.
* **Feeder Schools & Liaison** - feeder primaries with counts and the last
  contact; visits / calls and per-child notes (Record…, Edit…, Delete).
* **Events** - induction / taster days, new-parents' evening, summer
  school, enhanced visits; invitations and attendance; register export.
* **Friendships** - friendship requests and keep-aparts (prefilled from
  the transition reports); Add…, Link name…, Remove.
* **Form Allocation** - Year 7 forms with balance figures, the children
  and their form; Auto-suggest…, Move…, Take out, Publish / Unlock…,
  warnings, form lists export.
* **Enhanced Transition** - vulnerable children with their plan.

Dates are picked with the platform DatePicker and every fixed list, time
and person is a read-only drop-down. Rules are in
:mod:`modules.progression.domain.year6_transition`.
"""

from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.date_picker import DatePicker, recent_years
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.modules.progression.domain import year6_allocation as YA
from education_system.systems.secondary.modules.progression.domain import year6_events as YE
from education_system.systems.secondary.modules.progression.domain import year6_transition as Y6
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.ui.gui.components import widgets as W

_ERRORS = (*W.ERRORS, P.DuplicatePupil)
_YEARS = recent_years(ahead=2, back=2)


def _yn(v: Any) -> str:
    return "" if v is None else "Yes" if v else "No"


def _staff_choices() -> list[str]:
    try:
        from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
        return [""] + SD.choices()
    except Exception:  # noqa: BLE001 - the staff list is a convenience
        return [""]


def form(owner: tk.Misc, title: str, fields: list[tuple[str, str, Any, Any]],
         on_save: Callable[[dict[str, Any]], None], note: str | None = None) -> tk.Toplevel:
    """A pop-up form. Kinds: None (entry), "text", "check", "date"
    (DatePicker), a list (read-only drop-down), ("pick", [(value, label)])
    (read-only drop-down giving the value), ("edit", [choices]) (a drop-down
    you can also type in, for names outside a fixed list) or ("many", [(value, label)])
    (tick several)."""
    win, frm = W.dialog(owner, title)
    if note:
        ttk.Label(frm, text=note, foreground="#555", wraplength=480, justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
    get: dict[str, Callable[[], Any]] = {}
    for i, (key, label, initial, kind) in enumerate(fields, start=1):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw", padx=(0, 8), pady=2)
        init = "" if initial is None else str(initial)
        if kind == "text":
            t = tk.Text(frm, width=52, height=4, wrap="word")
            t.insert("1.0", init)
            t.grid(row=i, column=1, sticky="w", pady=2)
            get[key] = lambda t=t: t.get("1.0", "end").strip()
        elif kind == "check":
            bv = tk.BooleanVar(value=bool(initial))
            ttk.Checkbutton(frm, variable=bv).grid(row=i, column=1, sticky="w")
            get[key] = bv.get
        elif kind == "date":
            dp = DatePicker(frm, value=init or None, years=_YEARS)
            dp.grid(row=i, column=1, sticky="w", pady=2)
            get[key] = dp.get
        elif isinstance(kind, tuple) and kind[0] == "pick":
            labels = [lab for _v, lab in kind[1]]
            values = [v for v, _l in kind[1]]
            sv = tk.StringVar(value=next((lab for v, lab in kind[1] if v == initial), ""))
            ttk.Combobox(frm, textvariable=sv, values=labels, state="readonly",
                         width=44).grid(row=i, column=1, sticky="w")
            get[key] = lambda sv=sv, labels=labels, values=values: (
                values[labels.index(sv.get())] if sv.get() in labels else None)
        elif isinstance(kind, tuple) and kind[0] == "edit":
            sv = tk.StringVar(value=init)
            ttk.Combobox(frm, textvariable=sv, values=list(kind[1]), width=42).grid(
                row=i, column=1, sticky="w")
            get[key] = sv.get
        elif isinstance(kind, tuple) and kind[0] == "many":
            box = tk.Listbox(frm, selectmode="multiple", height=12, width=50,
                             exportselection=False)
            ids = [v for v, _l in kind[1]]
            for v, lab in kind[1]:
                box.insert("end", lab)
                if v in (initial or ()):
                    box.selection_set(ids.index(v))
            box.grid(row=i, column=1, sticky="w", pady=2)
            get[key] = lambda box=box, ids=ids: [ids[j] for j in box.curselection()]
        elif kind:
            sv = tk.StringVar(value=init)
            ttk.Combobox(frm, textvariable=sv, values=list(kind), state="readonly",
                         width=40).grid(row=i, column=1, sticky="w")
            get[key] = sv.get
        else:
            sv = tk.StringVar(value=init)
            ttk.Entry(frm, textvariable=sv, width=44).grid(row=i, column=1, sticky="w")
            get[key] = sv.get

    def save() -> None:
        try:
            on_save({k: g() for k, g in get.items()})
        except _ERRORS as e:
            messagebox.showerror(title, W.problems(e), parent=win)
            return
        win.destroy()

    bar = ttk.Frame(frm)
    bar.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(bar, text="Save", command=save).pack(side="right")
    return win


class Year6TransitionPage:
    TABS = ("Cohort", "Feeder Schools & Liaison", "Events", "Friendships", "Form Allocation",
            "Enhanced Transition")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = Y6.is_editor(principal)
        self.planner = self.editor or Y6.is_senco(principal)
        self.needs = Y6.can_see_needs(principal)
        self.lead = Y6.is_safeguarding_lead(principal)
        self.rows: dict[int, Y6.CohortRow] = {}
        activity_log.record("year6.open")
        head = ttk.Frame(parent)
        head.pack(fill="x")
        ttk.Label(head, text="Year 6 Transition", font=("", 16, "bold")).pack(side="left")
        ttk.Label(head, text="   Intake (September of):").pack(side="left")
        self.year_var = tk.StringVar(value=state.get("year") or Y6.default_intake())
        cb = ttk.Combobox(head, textvariable=self.year_var, values=Y6.intake_choices(),
                          state="readonly", width=9)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_all())
        b = ttk.Button(head, text="Sync from platform & admissions", command=self.sync)
        if not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=8)
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666",
                  wraplength=1100, justify="left").pack(anchor="w", pady=(2, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Cohort"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    @property
    def year(self) -> str:
        return self.year_var.get()

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _bar(self, tab, buttons) -> ttk.Frame:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd, who in buttons:
            b = ttk.Button(bar, text=text, command=cmd)
            if (who == "edit" and not self.editor) or (who == "plan" and not self.planner):
                b.state(["disabled"])
            b.pack(side="left", padx=2)
        return bar

    def _try(self, title: str, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except _ERRORS as e:
            self._err(title, e)
        except OSError as e:
            self._err(title, e)
        return None

    def _save_path(self, name: str) -> str:
        return filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            initialfile=name, filetypes=[("CSV", "*.csv")])

    def _pupil_choices(self, *, exclude: int | None = None) -> list[tuple[int, str]]:
        return [(r.cohort_id, f"{r.name} ({r.feeder_school or '-'})")
                for r in sorted(self.rows.values(), key=lambda r: r.name)
                if r.cohort_id != exclude and r.active]

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            {"Cohort": self._build_cohort, "Feeder Schools & Liaison": self._build_feeders,
             "Events": self._build_events, "Friendships": self._build_friends,
             "Form Allocation": self._build_forms,
             "Enhanced Transition": self._build_enhanced}[name](self.tabs[name])
        self.refresh_tab(name)

    def refresh_tab(self, name: str) -> None:
        self.state["year"] = self.year
        self._load_rows()
        {"Cohort": self.refresh_cohort, "Feeder Schools & Liaison": self.refresh_feeders,
         "Events": self.refresh_events, "Friendships": self.refresh_friends,
         "Form Allocation": self.refresh_forms,
         "Enhanced Transition": self.refresh_enhanced}[name]()

    def refresh_all(self) -> None:
        self.refresh_tab(self.TABS[self.book.index(self.book.select())])

    def _load_rows(self) -> None:
        try:
            rows = Y6.cohort(self.year, actor=self.principal, include_inactive=True)
            c = Y6.counts(self.year, actor=self.principal)
            pub = Y6.publication(self.year)
        except _ERRORS as e:
            self.summary_var.set(W.problems(e))
            self.rows = {}
            return
        self.rows = {r.cohort_id: r for r in rows}
        text = "    ".join(f"{k}: {v}" for k, v in c.items())
        if pub:
            text += f"    Forms published {pub['published_at'][:16]} by {pub['published_by']}"
        if not rows:
            text = ("Nobody in this intake yet." + (" Press Sync to read the platform queue "
                                                   "and admissions offers." if self.editor
                                                   else ""))
        self.summary_var.set(text)

    def sync(self) -> None:
        out = self._try("Sync", lambda: Y6.sync(self.year, actor=self.principal))
        if out is None:
            return
        self.refresh_all()
        self._info("Sync", f"From the platform: {out['platform']}\nFrom admissions: "
                           f"{out['admissions']}\nNew: {out['new']}\nFriendship / keep-apart "
                           f"names from reports: {out['report_names']} (matched "
                           f"{out['resolved']})" + ("\n\nSome handovers couldn't be read."
                                                    if out["unreadable"] else ""))

    # ── Cohort ───────────────────────────────────────────────────────

    def _build_cohort(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_var = tk.StringVar(value=self.state.get("search", ""))
        e = ttk.Entry(bar, textvariable=self.search_var, width=18)
        e.pack(side="left", padx=(4, 8))
        e.bind("<Return>", lambda _e: self.refresh_cohort())
        ttk.Label(bar, text="Feeder:").pack(side="left")
        self.feeder_var = tk.StringVar(value=self.state.get("feeder", ""))
        self.feeder_cb = ttk.Combobox(bar, textvariable=self.feeder_var, state="readonly",
                                      width=28)
        self.feeder_cb.pack(side="left", padx=(4, 8))
        self.feeder_cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_cohort())
        self.inactive_var = tk.BooleanVar(value=bool(self.state.get("inactive")))
        ttk.Checkbutton(bar, text="Include not coming", variable=self.inactive_var,
                        command=self.refresh_cohort).pack(side="left")
        self._bar(tab, (("Pupil details…", self.details, None),
                        ("Transition report…", self.report, None),
                        ("Edit details…", self.edit_row, "plan"),
                        ("Liaison note…", self.pupil_note, "edit"),
                        ("Start in September…", self.start_one, "edit"),
                        ("Start everyone…", self.start_everyone, "edit"),
                        ("Open pupil", self._open, None),
                        ("Export CSV…", self.export_cohort, None),
                        ("Refresh", self.refresh_all, None)))
        cols = [("name", "Child", 180), ("dob", "Born", 85), ("gender", "Gender", 60),
                ("feeder", "Feeder primary", 170), ("via", "Via", 110),
                ("status", "Status", 100), ("ks2", "KS2 R/M", 70), ("band", "KS2 band", 110),
                ("sen", "SEN", 40), ("pp", "PP", 40), ("enh", "Enhanced", 70),
                ("form", "Form", 60), ("prog", "Checklist", 70)]
        if self.lead:
            cols.append(("sg", "Safeguarding", 90))
        self.tree = W.tree(tab, cols, height=18, stretch={"feeder"}, tags=W.STANDARD_TAGS)
        self.tree.bind("<<TreeviewSelect>>", self._picked)
        self.tree.bind("<Double-1>", lambda _e: self.details())

    def _picked(self, _e=None) -> None:
        sel = self.tree.selection()
        if sel:
            self.state["cohort_id"] = int(sel[0])

    def _selected(self, title: str = "") -> Y6.CohortRow | None:
        cid = self.state.get("cohort_id")
        if "Cohort" in self._built and self.tree.selection():
            cid = int(self.tree.selection()[0])
        row = self.rows.get(cid) if cid is not None else None
        if row is None:
            self._info(title or "Year 6 Transition", "Select a child on the Cohort tab first.")
        return row

    def refresh_cohort(self) -> None:
        if "Cohort" not in self._built:
            return
        self.state.update(search=self.search_var.get().strip(), feeder=self.feeder_var.get(),
                          inactive=self.inactive_var.get())
        feeders = sorted({r.feeder_school or "" for r in self.rows.values()} - {""})
        self.feeder_cb.configure(values=[""] + feeders)
        terms = self.search_var.get().lower().split()
        self.tree.delete(*self.tree.get_children())
        for r in sorted(self.rows.values(), key=lambda r: r.name):
            if not r.active and not self.inactive_var.get():
                continue
            if self.feeder_var.get() and (r.feeder_school or "") != self.feeder_var.get():
                continue
            hay = f"{r.first_name} {r.last_name} {r.preferred_name or ''} {r.upn or ''}".lower()
            if any(t not in hay for t in terms):
                continue
            done, total = r.progress
            tag = "muted" if not r.active else "good" if total and done == total else \
                "warn" if r.enhanced else ""
            vals = [r.name, r.date_of_birth or "", r.gender or "", r.feeder_school or "",
                    r.source_label, r.status_label,
                    f"{r.ks2_reading or '-'}/{r.ks2_maths or '-'}", r.ks2_band,
                    r.sen_status or "", _yn(r.pupil_premium), "Yes" if r.enhanced else "",
                    r.form_name or "", r.progress_label]
            if self.lead:
                vals.append(_yn(r.safeguarding))
            self.tree.insert("", "end", iid=str(r.cohort_id), tags=(tag,) if tag else (),
                             values=vals)
        cid = self.state.get("cohort_id")
        if cid is not None and self.tree.exists(str(cid)):
            self.tree.selection_set(str(cid))
            self.tree.see(str(cid))

    def details(self, cohort_id: int | None = None) -> None:
        row = self.rows.get(cohort_id) if cohort_id is not None else \
            self._selected("Pupil details")
        if row is None:
            return
        text = self._try("Pupil details", lambda: Y6.pupil_text(row.cohort_id,
                                                                 actor=self.principal))
        if text is not None:
            W.text_window(self.parent, f"Year 6 transition — {row.name}", text, size="760x600")

    def report(self) -> None:
        row = self._selected("Transition report")
        if row is None:
            return
        if row.source != "platform":
            self._info("Transition report", f"{row.name} is coming from a school that isn't "
                                            "on the platform - record what their Year 6 "
                                            "teacher tells you with Liaison note….")
            return
        rep = self._try("Transition report", lambda: Y6.transition_report(
            row.cohort_id, actor=self.principal))
        W.text_window(self.parent, f"Transition report — {row.name}", Y6.report_text(rep),
                      size="680x560")

    def edit_row(self) -> None:
        row = self._selected("Edit details")
        if row is None:
            return
        fields: list[tuple[str, str, Any, Any]] = []
        if self.editor:
            fields += [("feeder_school", "Feeder primary", row.feeder_school, None),
                       ("gender", "Gender", row.gender or "", [""] + list(P.GENDERS)),
                       ("ks2_reading", "KS2 reading scaled score", row.ks2_reading or "",
                        [""] + [str(n) for n in range(80, 121)]),
                       ("ks2_maths", "KS2 maths scaled score", row.ks2_maths or "",
                        [""] + [str(n) for n in range(80, 121)]),
                       ("notes", "Notes", row.notes or "", "text")]
        if self.needs:
            fields += [("sen_status", "SEN status", row.sen_status or "",
                        [""] + list(P.SEN_STATUSES)),
                       ("pupil_premium", "Pupil premium", row.pupil_premium, "check"),
                       ("fsm", "Free school meals", row.fsm, "check"),
                       ("lac", "Looked after / previously looked after", row.lac, "check"),
                       ("eal", "EAL", row.eal, "check")]

        def save(v):
            Y6.update_row(row.cohort_id, v, actor=self.principal)
            self.refresh_all()
        form(self.parent, f"Edit — {row.name}", fields, save,
             note="Corrections made here are kept when the cohort is next synced.")

    def pupil_note(self) -> None:
        row = self._selected("Liaison note")
        if row is not None:
            self._liaison_form(row.feeder_school, cohort_id=row.cohort_id, who=row.name)

    def start_one(self) -> None:
        row = self._selected("Start in September")
        if row is None:
            return

        def save(v):
            notes = Y6.start_pupil(row.cohort_id, actor=self.principal,
                                   start_date=v["start"] or None)
            self.refresh_all()
            self._info("Start in September", f"{row.name}:\n\n" + "\n".join(
                f"• {n}" for n in notes))
        form(self.parent, f"Start in September — {row.name}",
             [("start", "First day", _dt.date.today().isoformat(), "date")], save,
             note="Makes sure there is a pupil record (matched, created from the handover or "
                  "admitted from the accepted offer), imports KS2, puts them in their "
                  "published form and completes the platform transfer.")

    def start_everyone(self) -> None:
        def save(v):
            out = Y6.start_all(self.year, actor=self.principal, start_date=v["start"] or None)
            self.refresh_all()
            W.text_window(self.parent, "September start", "\n\n".join(
                f"{name}\n" + "\n".join(f"  • {n}" for n in notes)
                for name, notes in out.items()) or "Nobody to start.", save_name="start.txt")
        form(self.parent, f"Start everyone — {self.year}",
             [("start", "First day", _dt.date.today().isoformat(), "date")], save,
             note="Runs Start in September for every child coming who hasn't started yet. "
                  "Children who can't start yet (offer not accepted, ...) are listed.")

    def _open(self) -> None:
        row = self._selected("Open pupil")
        if row is None:
            return
        if not row.pupil_id:
            self._info("Open pupil", f"{row.name} has no pupil record here yet.")
        elif self.open_pupil:
            self.open_pupil(row.pupil_id)

    def export_cohort(self) -> None:
        path = self._save_path(f"year6_cohort_{self.year.replace('/', '-')}.csv")
        if path:
            n = self._try("Export", lambda: Y6.export_cohort_csv(self.year, path,
                                                                 actor=self.principal))
            if n is not None:
                self._info("Export", f"Exported {n} child(ren) to\n{path}")

    # ── Feeder schools & liaison ─────────────────────────────────────

    def _build_feeders(self, tab) -> None:
        self._bar(tab, (("Record contact…", lambda: self._liaison_form(self._feeder()), "edit"),
                        ("Edit…", self.edit_liaison, "edit"),
                        ("Delete", self.delete_liaison, "edit"),
                        ("Refresh", self.refresh_all, None)))
        cols = [("school", "Feeder primary", 220), ("n", "Coming", 60),
                ("plat", "Platform", 70), ("adm", "Admissions", 80),
                ("enh", "Enhanced", 70)]
        if self.needs:
            cols += [("sen", "SEN", 50), ("pp", "PP", 50)]
        cols += [("contacts", "Contacts", 70), ("last", "Last contact", 100)]
        self.feeder_tree = W.tree(tab, cols, height=8, stretch={"school"})
        self.feeder_tree.bind("<<TreeviewSelect>>", lambda _e: self.refresh_liaison())
        ttk.Label(tab, text="Contacts and notes (for the school selected above, or all)",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        self.liaison_tree = W.tree(tab, [("date", "Date", 90), ("kind", "Kind", 150),
                                         ("school", "School", 170), ("pupil", "Child", 150),
                                         ("staff", "Our staff", 130),
                                         ("contact", "Their contact", 130),
                                         ("summary", "Summary", 300)],
                                   height=10, stretch={"summary"})
        self.liaison_tree.bind("<Double-1>", lambda _e: self.edit_liaison())

    def _feeder(self) -> str | None:
        sel = self.feeder_tree.selection() if "Feeder Schools & Liaison" in self._built else ()
        return sel[0] if sel else None

    def refresh_feeders(self) -> None:
        if "Feeder Schools & Liaison" not in self._built:
            return
        t = self.feeder_tree
        keep = self._feeder()
        t.delete(*t.get_children())
        rows = self._try("Feeder schools", lambda: Y6.feeder_schools(self.year,
                                                                      actor=self.principal))
        for d in rows or []:
            vals = [d["school"], d["expected"], d["platform"], d["admissions"], d["enhanced"]]
            if self.needs:
                vals += [d["sen"], d["pupil_premium"]]
            vals += [d["contacts"], d["last_contact"] or ""]
            t.insert("", "end", iid=d["school"], values=vals)
        if keep and t.exists(keep):
            t.selection_set(keep)
        self.refresh_liaison()

    def refresh_liaison(self) -> None:
        t = self.liaison_tree
        t.delete(*t.get_children())
        rows = self._try("Liaison", lambda: Y6.liaison(self.year, actor=self.principal,
                                                        school=self._feeder()))
        for r in rows or []:
            t.insert("", "end", iid=str(r["liaison_id"]), values=(
                r["held_on"], r["kind"], r["school"], r["pupil"], r.get("staff_name") or "",
                r.get("contact_name") or "", (r["summary"] or "").replace("\n", " ")))

    def _liaison_form(self, school: str | None, *, cohort_id: int | None = None,
                      who: str | None = None, record: dict | None = None) -> None:
        schools = sorted({r.feeder_school for r in self.rows.values() if r.feeder_school})
        rec = record or {}

        def save(v):
            if record:
                Y6.update_liaison(record["liaison_id"], v, actor=self.principal)
            else:
                Y6.add_liaison(self.year, v, actor=self.principal, cohort_id=cohort_id)
            self.refresh_all()
        kinds = list(Y6.LIAISON_KINDS)
        form(self.parent, ("Edit contact" if record else "Liaison note — " + who if who
                           else "Record contact with a primary"), [
            ("school", "Primary school", rec.get("school") or school or "",
             ("edit", schools)),
            ("kind", "Kind", rec.get("kind") or ("Y6 teacher conversation" if cohort_id
                                                 else "Visit to primary"), kinds),
            ("held_on", "Date", rec.get("held_on") or _dt.date.today().isoformat(), "date"),
            ("staff_name", "Our member of staff", rec.get("staff_name") or "",
             _staff_choices()),
            ("contact_name", "Their contact (e.g. Y6 teacher)", rec.get("contact_name") or "",
             None),
            ("summary", "What was discussed", rec.get("summary") or "", "text"),
            ("follow_up", "Follow-up", rec.get("follow_up") or "", "text")], save)

    def _liaison_selected(self) -> dict | None:
        sel = self.liaison_tree.selection()
        if not sel:
            self._info("Liaison", "Select a contact or note first.")
            return None
        rows = Y6.liaison(self.year, actor=self.principal)
        return next((r for r in rows if str(r["liaison_id"]) == sel[0]), None)

    def edit_liaison(self) -> None:
        rec = self._liaison_selected()
        if rec:
            self._liaison_form(rec["school"], record=rec, cohort_id=rec.get("cohort_id"))

    def delete_liaison(self) -> None:
        rec = self._liaison_selected()
        if rec and messagebox.askyesno("Delete", f"Delete the {rec['kind'].lower()} on "
                                                 f"{rec['held_on']}?", parent=self._top()):
            if self._try("Delete", lambda: Y6.delete_liaison(rec["liaison_id"],
                                                              actor=self.principal)) is None:
                self.refresh_all()

    # ── Events ───────────────────────────────────────────────────────

    def _build_events(self, tab) -> None:
        self._bar(tab, (("New event…", lambda: self._event_form(None), "edit"),
                        ("Edit…", self.edit_event, "edit"),
                        ("Delete", self.delete_event, "edit"),
                        ("Invite audience", self.invite_audience, "edit"),
                        ("Invite children…", self.invite_some, "edit"),
                        ("Refresh", self.refresh_all, None)))
        self.event_tree = W.tree(tab, [("date", "Date", 90), ("time", "Time", 100),
                                       ("title", "Event", 220), ("type", "Type", 170),
                                       ("aud", "Audience", 170), ("where", "Where", 120),
                                       ("inv", "Invited", 60), ("att", "Attended", 70)],
                                 height=8, stretch={"title"})
        self.event_tree.bind("<<TreeviewSelect>>", lambda _e: self.refresh_register())
        ttk.Label(tab, text="Register (for the event selected above)",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        self._bar(tab, (("Attended", lambda: self.mark("attended"), "edit"),
                        ("Absent", lambda: self.mark("absent"), "edit"),
                        ("Apologies", lambda: self.mark("apologies"), "edit"),
                        ("Back to invited", lambda: self.mark("invited"), "edit"),
                        ("Remove invitation", self.uninvite, "edit"),
                        ("Export register…", self.export_register, None)))
        self.reg_tree = W.tree(tab, [("name", "Child", 200), ("feeder", "Feeder", 180),
                                     ("form", "Form", 60), ("att", "Attendance", 100),
                                     ("by", "Marked by", 110), ("at", "When", 140)],
                               height=10, select="extended", stretch={"feeder"},
                               tags=W.STANDARD_TAGS)

    def _event(self, quiet: bool = False) -> dict | None:
        sel = self.event_tree.selection() if "Events" in self._built else ()
        if not sel:
            if not quiet:
                self._info("Events", "Select an event first.")
            return None
        return self._try("Events", lambda: YE.get_event(int(sel[0]), actor=self.principal))

    def refresh_events(self) -> None:
        if "Events" not in self._built:
            return
        t = self.event_tree
        keep = t.selection()
        t.delete(*t.get_children())
        for e in self._try("Events", lambda: YE.events(self.year, actor=self.principal)) or []:
            time = "–".join(x for x in (e.get("start_time"), e.get("end_time")) if x)
            t.insert("", "end", iid=str(e["event_id"]), values=(
                e["event_date"], time, e["title"], e["event_type"], e["audience"],
                e.get("location") or "", e["invited"], e["attended"]))
        if keep and t.exists(keep[0]):
            t.selection_set(keep[0])
        self.refresh_register()

    def refresh_register(self) -> None:
        t = self.reg_tree
        t.delete(*t.get_children())
        ev = self._event(quiet=True)
        if not ev:
            return
        for d in self._try("Register", lambda: YE.register(ev["event_id"],
                                                            actor=self.principal)) or []:
            r = d["row"]
            tag = {"attended": "good", "absent": "bad", "apologies": "warn"}.get(
                d["attendance"], "")
            t.insert("", "end", iid=str(r.cohort_id), tags=(tag,) if tag else (), values=(
                r.name, r.feeder_school or "", r.form_name or "",
                Y6.ATTENDANCE[d["attendance"]], d.get("marked_by") or "",
                d.get("marked_at") or ""))

    def _event_form(self, ev: dict | None) -> None:
        e = ev or {}

        def save(v):
            if ev:
                YE.update_event(ev["event_id"], v, actor=self.principal)
            else:
                YE.create_event(self.year, v, actor=self.principal)
            self.refresh_all()
        times = [""] + list(Y6.TIMES)
        form(self.parent, "Edit event" if ev else f"New transition event — {self.year}", [
            ("event_type", "Type", e.get("event_type") or "Induction day",
             list(Y6.EVENT_TYPES)),
            ("title", "Title (blank = the type)", e.get("title") or "", None),
            ("event_date", "Date", e.get("event_date") or "", "date"),
            ("start_time", "Starts", e.get("start_time") or "", times),
            ("end_time", "Ends", e.get("end_time") or "", times),
            ("audience", "For", e.get("audience") or "Whole cohort", list(Y6.AUDIENCES)),
            ("location", "Where", e.get("location") or "", None),
            ("notes", "Notes", e.get("notes") or "", "text")], save)

    def edit_event(self) -> None:
        ev = self._event()
        if ev:
            self._event_form(ev)

    def delete_event(self) -> None:
        ev = self._event()
        if ev and messagebox.askyesno("Delete event", f"Delete {ev['title']} on "
                                      f"{ev['event_date']}? Its register goes too.",
                                      parent=self._top()):
            if self._try("Delete", lambda: YE.delete_event(ev["event_id"],
                                                            actor=self.principal)) is None:
                self.refresh_all()

    def invite_audience(self) -> None:
        ev = self._event()
        if not ev:
            return
        n = self._try("Invite", lambda: YE.invite(ev["event_id"], actor=self.principal))
        if n is not None:
            self.refresh_events()
            self._info("Invite", f"{n} child(ren) invited ({ev['audience']}).")

    def invite_some(self) -> None:
        ev = self._event()
        if not ev:
            return

        def save(v):
            n = YE.invite(ev["event_id"], v["ids"], actor=self.principal)
            self.refresh_events()
            self._info("Invite", f"{n} child(ren) invited.")
        form(self.parent, f"Invite to {ev['title']}",
             [("ids", "Children", [], ("many", self._pupil_choices()))], save)

    def _reg_ids(self) -> list[int]:
        sel = self.reg_tree.selection()
        if not sel:
            self._info("Register", "Select one or more children in the register.")
        return [int(s) for s in sel]

    def mark(self, attendance: str) -> None:
        ev = self._event()
        ids = self._reg_ids() if ev else []
        if ids and self._try("Register", lambda: YE.mark(ev["event_id"], ids, attendance,
                                                         actor=self.principal)) is not None:
            self.refresh_events()

    def uninvite(self) -> None:
        ev = self._event()
        ids = self._reg_ids() if ev else []
        if ids and self._try("Register", lambda: YE.uninvite(ev["event_id"], ids,
                                                             actor=self.principal)) is not None:
            self.refresh_events()

    def export_register(self) -> None:
        ev = self._event()
        if not ev:
            return
        path = self._save_path(f"register_{ev['event_date']}.csv")
        if path:
            n = self._try("Export", lambda: YE.export_register(ev["event_id"], path,
                                                               actor=self.principal))
            if n is not None:
                self._info("Export", f"Exported {n} name(s) to\n{path}")

    # ── Friendships ──────────────────────────────────────────────────

    def _build_friends(self, tab) -> None:
        self._bar(tab, (("Add…", self.add_friend, "edit"),
                        ("Link name…", self.link_friend, "edit"),
                        ("Remove", self.remove_friend, "edit"),
                        ("Refresh", self.refresh_all, None)))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Show:").pack(side="left")
        self.kind_var = tk.StringVar(value=self.state.get("kind", "All"))
        cb = ttk.Combobox(bar, textvariable=self.kind_var, state="readonly", width=20,
                          values=["All", *Y6.RELATION_KINDS.values()])
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_friends())
        self.rel_tree = W.tree(tab, [("pupil", "Child", 180), ("kind", "Request", 130),
                                     ("other", "Other child", 200), ("src", "From", 100),
                                     ("f1", "Form", 60), ("f2", "Their form", 70),
                                     ("note", "Note", 240)], height=18, stretch={"note"},
                               tags=W.STANDARD_TAGS)

    def refresh_friends(self) -> None:
        if "Friendships" not in self._built:
            return
        self.state["kind"] = self.kind_var.get()
        kind = next((k for k, v in Y6.RELATION_KINDS.items() if v == self.kind_var.get()), None)
        t = self.rel_tree
        t.delete(*t.get_children())
        for r in self._try("Friendships", lambda: Y6.relationships(
                self.year, actor=self.principal, kind=kind)) or []:
            same = r.get("my_form") and r.get("my_form") == r.get("other_form")
            tag = ("bad" if same else "") if r["kind"] == "keep_apart" else \
                ("good" if same else "")
            if not r.get("other_cohort_id"):
                tag = "warn"
            t.insert("", "end", iid=str(r["rel_id"]), tags=(tag,) if tag else (), values=(
                r["pupil"], r["kind_label"], r["other_label"], r["source_label"],
                r.get("my_form") or "", r.get("other_form") or "", r.get("note") or ""))

    def add_friend(self) -> None:
        choices = self._pupil_choices()
        if not choices:
            self._info("Friendships", "Nobody in the cohort yet.")
            return

        def save(v):
            if v["who"] is None or v["other"] is None:
                raise Y6.ValidationError(["Choose both children"])
            kind = next(k for k, lab in Y6.RELATION_KINDS.items() if lab == v["kind"])
            Y6.add_relationship(v["who"], kind, actor=self.principal,
                                other_cohort_id=v["other"], note=v["note"])
            self.refresh_all()
        form(self.parent, "Friendship request / keep apart", [
            ("who", "Child", self.state.get("cohort_id"), ("pick", choices)),
            ("kind", "Request", "Friendship request", list(Y6.RELATION_KINDS.values())),
            ("other", "Other child", None, ("pick", choices)),
            ("note", "Note", "", "text")], save)

    def _rel(self) -> str | None:
        sel = self.rel_tree.selection()
        if not sel:
            self._info("Friendships", "Select a row first.")
        return sel[0] if sel else None

    def link_friend(self) -> None:
        rid = self._rel()
        if rid is None:
            return

        def save(v):
            if v["other"] is None:
                raise Y6.ValidationError(["Choose the child"])
            Y6.link_relationship(int(rid), v["other"], actor=self.principal)
            self.refresh_all()
        name = self.rel_tree.item(rid, "values")[2]
        form(self.parent, f"Link {name}", [("other", "Which child is it?", None,
                                            ("pick", self._pupil_choices()))], save,
             note="For a name in a primary's transition report that didn't match a child "
                  "in the cohort automatically.")

    def remove_friend(self) -> None:
        rid = self._rel()
        if rid and messagebox.askyesno("Remove", "Remove this request?", parent=self._top()):
            if self._try("Remove", lambda: Y6.remove_relationship(
                    int(rid), actor=self.principal)) is None:
                self.refresh_all()

    # ── Form allocation ──────────────────────────────────────────────

    def _build_forms(self, tab) -> None:
        self._bar(tab, (("Auto-suggest…", self.auto, "edit"),
                        ("Move to form…", self.move, "edit"),
                        ("Take out of form", lambda: self._move_to(None), "edit"),
                        ("Clear suggestions", self.clear, "edit"),
                        ("Publish", self.publish, "edit"),
                        ("Unlock…", self.unlock, "edit"),
                        ("Export form lists…", self.export_forms, None),
                        ("Refresh", self.refresh_all, None)))
        self.lock_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.lock_var, foreground="#a33").pack(anchor="w")
        cols = [("form", "Form", 90), ("tutor", "Tutor", 130), ("cap", "Places", 60),
                ("size", "Children", 70), ("f", "Girls", 50), ("m", "Boys", 50),
                ("o", "Other", 50),
                ("hi", "KS2 higher", 75), ("ex", "Expected", 70), ("wt", "Working tw.", 80),
                ("nk", "No KS2", 60)]
        if self.needs:
            cols.append(("sen", "SEN", 50))
        cols += [("feed", "Feeders", 60), ("enh", "Enhanced", 70)]
        self.form_tree = W.tree(tab, cols, height=6, stretch={"tutor"}, tags=W.STANDARD_TAGS)
        self.form_tree.bind("<<TreeviewSelect>>", lambda _e: self.refresh_alloc())
        pane = ttk.Frame(tab)
        pane.pack(fill="both", expand=True, pady=(6, 0))
        left = ttk.Frame(pane)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(pane)
        right.pack(side="left", fill="both", padx=(8, 0))
        ttk.Label(left, text="Children (in the form selected above, or all)",
                  font=("", 10, "bold")).pack(anchor="w")
        self.alloc_tree = W.tree(left, [("name", "Child", 180), ("g", "Gender", 60),
                                        ("feeder", "Feeder", 160), ("band", "KS2 band", 110),
                                        ("form", "Form", 60), ("how", "How", 60)],
                                 height=12, select="extended", stretch={"feeder"})
        ttk.Label(right, text="Warnings", font=("", 10, "bold")).pack(anchor="w")
        self.warn_tree = W.tree(right, [("w", "Warning", 380)], height=12,
                                tags=W.STANDARD_TAGS)

    def _form_sel(self) -> str | None:
        sel = self.form_tree.selection() if "Form Allocation" in self._built else ()
        return sel[0] if sel else None

    def refresh_forms(self) -> None:
        if "Form Allocation" not in self._built:
            return
        pub = self._try("Forms", lambda: Y6.publication(self.year))
        self.lock_var.set(f"Published {pub['published_at'][:16]} by {pub['published_by']} - "
                          "unlock to change." if pub else "")
        t = self.form_tree
        keep = self._form_sel()
        t.delete(*t.get_children())
        for f in self._try("Forms", lambda: YA.form_summary(self.year,
                                                            actor=self.principal)) or []:
            b = f["bands"]
            over = f["capacity"] is not None and f["size"] > f["capacity"]
            vals = [f["name"], f["tutor"] or "", f["capacity"] or "", f["size"], f["female"],
                    f["male"], f["other"], b["Higher"], b["Expected"], b["Working towards"], b["No KS2"]]
            if self.needs:
                vals.append(f["sen"])
            vals += [f["feeders"], f["enhanced"]]
            t.insert("", "end", iid=f["name"], tags=("bad",) if over else (), values=vals)
        if not t.get_children():
            self.lock_var.set("No Year 7 forms are set up - create them in Form Groups.")
        if keep and t.exists(keep):
            t.selection_set(keep)
        self.refresh_alloc()
        w = self.warn_tree
        w.delete(*w.get_children())
        for x in self._try("Warnings", lambda: YA.warnings(self.year,
                                                           actor=self.principal)) or []:
            w.insert("", "end", tags=({"bad": "bad", "warn": "warn"}.get(x["level"], ""),),
                     values=(x["text"],))

    def refresh_alloc(self) -> None:
        t = self.alloc_tree
        t.delete(*t.get_children())
        f = self._form_sel()
        for r in sorted(self.rows.values(), key=lambda r: r.name):
            if not r.active:
                continue
            if f and (r.form_name or "(not allocated)") != f:
                continue
            t.insert("", "end", iid=str(r.cohort_id), values=(
                r.name, r.gender or "", r.feeder_school or "", r.ks2_band, r.form_name or "",
                {"auto": "suggested", "manual": "by hand"}.get(r.form_how or "", "")))

    def auto(self) -> None:
        def save(v):
            s = YA.suggest(self.year, actor=self.principal, keep_manual=v["keep"])
            counts: dict[str, int] = {}
            for name in s.plan.values():
                counts[name] = counts.get(name, 0) + 1
            text = "\n".join(f"  {k}: {n}" for k, n in sorted(counts.items()))
            if not messagebox.askyesno(
                    "Auto-suggest", f"Suggested forms:\n{text}\n\n" + "\n".join(s.notes)
                    + "\n\nSave this allocation?", parent=self._top()):
                return
            YA.apply_plan(self.year, s.plan, actor=self.principal)
            self.refresh_all()
        form(self.parent, "Auto-suggest forms", [
            ("keep", "Keep children placed by hand", True, "check")], save,
             note="Balances form size, girls / boys, KS2 bands, SEN and feeder schools; "
                  "keeps every keep-apart and at least one friendship per child where it can.")

    def _alloc_ids(self) -> list[int]:
        sel = self.alloc_tree.selection()
        if not sel:
            self._info("Form allocation", "Select one or more children first.")
        return [int(s) for s in sel]

    def move(self) -> None:
        ids = self._alloc_ids()
        if not ids:
            return
        names = [f["name"] for f in YA.forms()]

        def save(v):
            for cid in ids:
                YA.move(cid, v["form"], actor=self.principal)
            self.refresh_all()
        form(self.parent, f"Move {len(ids)} child(ren)", [("form", "Form", "", names)], save)

    def _move_to(self, target: str | None) -> None:
        ids = self._alloc_ids()
        for cid in ids:
            if self._try("Form allocation", lambda cid=cid: YA.move(
                    cid, target, actor=self.principal)) is None:
                break
        self.refresh_all()

    def clear(self) -> None:
        if messagebox.askyesno("Clear", "Take out every suggested placement (children "
                                        "placed by hand stay)?", parent=self._top()):
            self._try("Clear", lambda: YA.clear_allocation(self.year, actor=self.principal))
            self.refresh_all()

    def publish(self) -> None:
        if not messagebox.askyesno("Publish", f"Publish the {self.year} form allocation? It "
                                   "is locked, and children with a pupil record here are put "
                                   "in their forms.", parent=self._top()):
            return
        notes = self._try("Publish", lambda: YA.publish(self.year, actor=self.principal))
        if notes is not None:
            self.refresh_all()
            self._info("Publish", "\n".join(f"• {n}" for n in notes))

    def unlock(self) -> None:
        def save(v):
            YA.unpublish(self.year, actor=self.principal, reason=v["reason"])
            self.refresh_all()
        form(self.parent, "Unlock the allocation", [("reason", "Why", "", "text")], save)

    def export_forms(self) -> None:
        path = self._save_path(f"year7_forms_{self.year.replace('/', '-')}.csv")
        if path:
            n = self._try("Export", lambda: Y6.export_form_lists(self.year, path,
                                                                 actor=self.principal))
            if n is not None:
                self._info("Export", f"Exported {n} child(ren) to\n{path}")

    # ── Enhanced transition ──────────────────────────────────────────

    def _build_enhanced(self, tab) -> None:
        self._bar(tab, (("Edit plan…", self.edit_plan, "plan"),
                        ("Add a child…", self.add_enhanced, "plan"),
                        ("Take off (added by hand)", self.remove_enhanced, "plan"),
                        ("Pupil details…", self._enh_details, None),
                        ("Refresh", self.refresh_all, None)))
        self.enh_tree = W.tree(tab, [("name", "Child", 170), ("feeder", "Feeder", 150),
                                     ("why", "Why", 260), ("status", "Status", 90),
                                     ("visits", "Extra visits", 80),
                                     ("att", "Visits attended", 95),
                                     ("adult", "Key adult", 140), ("story", "Social story", 85),
                                     ("form", "Form", 55)], height=18, stretch={"why"},
                               tags=W.STANDARD_TAGS)
        self.enh_tree.bind("<Double-1>", lambda _e: self.edit_plan())

    def refresh_enhanced(self) -> None:
        if "Enhanced Transition" not in self._built:
            return
        t = self.enh_tree
        t.delete(*t.get_children())
        self.enh_rows = {}
        for d in self._try("Enhanced", lambda: Y6.enhanced(self.year,
                                                           actor=self.principal)) or []:
            r = d["row"]
            self.enh_rows[r.cohort_id] = d
            tag = "good" if d["status"] == "Completed" else \
                "warn" if d["status"] == "Identified" else ""
            t.insert("", "end", iid=str(r.cohort_id), tags=(tag,) if tag else (), values=(
                r.name, r.feeder_school or "", "; ".join(r.enhanced_reasons), d["status"],
                d["extra_visits"], d["visits_attended"], d["key_adult"] or "",
                "Sent" if d["social_story_sent"] else "", r.form_name or ""))

    def _enh(self) -> dict | None:
        sel = self.enh_tree.selection()
        if not sel:
            self._info("Enhanced transition", "Select a child first.")
            return None
        return self.enh_rows.get(int(sel[0]))

    def _enh_details(self) -> None:
        d = self._enh()
        if d:
            self.details(d["row"].cohort_id)

    def edit_plan(self) -> None:
        d = self._enh()
        if d is None:
            return
        r = d["row"]

        def save(v):
            Y6.set_plan(r.cohort_id, v, actor=self.principal)
            self.refresh_all()
        form(self.parent, f"Enhanced transition plan — {r.name}", [
            ("status", "Status", d["status"], list(Y6.ENHANCED_STATUSES)),
            ("extra_visits", "Extra visits planned", d["extra_visits"],
             [str(n) for n in range(0, 11)]),
            ("key_adult", "Key adult", d["key_adult"] or "", _staff_choices()),
            ("social_story_sent", "Social story sent", d["social_story_sent"], "check"),
            ("plan", "Plan", d["plan"] or "", "text")], save,
             note="Why: " + ("; ".join(r.enhanced_reasons) or "-") + ". Book the visits as "
                  "'Enhanced transition visit' events and mark attendance there.")

    def add_enhanced(self) -> None:
        choices = [(c, lab) for c, lab in self._pupil_choices()
                   if not self.rows[c].enhanced]

        def save(v):
            if v["who"] is None:
                raise Y6.ValidationError(["Choose the child"])
            Y6.add_to_enhanced(v["who"], actor=self.principal, reason=v["reason"])
            self.refresh_all()
        form(self.parent, "Add to enhanced transition", [
            ("who", "Child", None, ("pick", choices)),
            ("reason", "Why", "", "text")], save)

    def remove_enhanced(self) -> None:
        d = self._enh()
        if d is None:
            return
        if not d["manual"]:
            self._info("Enhanced transition", f"{d['row'].name} is on the list by the rules "
                                              "(SEN / PP / looked after / the primary asked).")
            return
        self._try("Enhanced transition", lambda: Y6.remove_from_enhanced(
            d["row"].cohort_id, actor=self.principal))
        self.refresh_all()


def draw_year6_transition(parent: ttk.Frame, *, principal: Principal, state: dict,
                          open_pupil: Callable[[int], None] | None = None
                          ) -> Year6TransitionPage:
    return Year6TransitionPage(parent, principal=principal, state=state, open_pupil=open_pupil)
