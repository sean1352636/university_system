"""Year 9 Options screen.

The old Options Process window is the Rounds tab: New round, Edit round, Set
status, Manage subjects, Submit choices, Summary, Delete round and Refresh,
with the old columns and the "Selected round" panel. The old Manage subjects
window (In round / Active catalogue, Add / Remove) and the old Submit choices
and Summary windows are kept. Added: the rules on a round, the Choices tab
(every pupil's choices, who hasn't chosen, reminders to families, export) and
the Blocks tab (option blocks, suggested blocks, allocation, placing pupils by
hand, finalising, results to families and Year 10 groups).
Rules live in :mod:`modules.curriculum.domain.options`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
    simpledialog,
)
from education_system.systems.secondary.modules.curriculum.domain import options as OP
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.core.permissions.access import OPTIONS_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
NONE = "(none)"
STATUS_BG = {"Draft": "#eeeeee", "Open": "#e6f2ff", "Closed": "#fff6d5",
             "Finalised": "#e7f6ea", "override": "#fff6d5", "stuck": "#fde2e2"}
_ERRORS = (OP.ValidationError, OP.PermissionDenied, OP.NotFound)


_problems = W.problems


def _tree(parent, columns, height: int = 10, *, multi: bool = False) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select="extended" if multi else "browse",
                  stretch={"name", "pupil", "choices", "why", "subjects"}, tags=STATUS_BG)


def _deliver(owner, principal: Principal, ids: list[int], title: str) -> None:
    """Deliver queued e-mails one after another, off the Tk thread."""
    from education_system.systems.secondary.modules.communication.gui import email_views
    pending = list(ids)

    def next_one(_report=None, error=None) -> None:
        if error:
            messagebox.showwarning(title, f"Saved in the outbox but not all sent yet: {error}",
                                   parent=owner)
            return
        if pending:
            email_views.deliver_in_background(owner, pending.pop(0), principal, next_one)
    next_one()


_ROUND_COLS = (("id", "ID", 45), ("name", "Name", 240), ("year", "Year", 50),
               ("status", "Status", 80), ("opens", "Opens", 95), ("closes", "Closes", 95),
               ("picks", "Picks", 55), ("reserves", "Reserves", 70))


class OptionsPage:
    TABS = ("Rounds", "Choices", "Blocks")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = principal.role in OPTIONS_EDITORS
        activity_log.record("options.view")
        ttk.Label(parent, text="Year 9 Options", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(anchor="w",
                                                                                 pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_rounds(self.tabs["Rounds"])
        self.book.select(self.TABS.index(state.get("tab", "Rounds")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── shared ───────────────────────────────────────────────────────

    @property
    def round(self) -> OP.Round | None:
        rid = self.state.get("round_id")
        if rid is None:
            rounds = OP.list_rounds()
            if not rounds:
                return None
            rid = self.state["round_id"] = rounds[0].round_id
        try:
            return OP.get_round(rid)
        except OP.NotFound:
            self.state.pop("round_id", None)
            return None

    def _round_bar(self, tab: ttk.Frame) -> OP.Round | None:
        """The round picker at the top of the Choices and Blocks tabs."""
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        rounds = {f"{r.name} ({r.status})": r for r in OP.list_rounds()}
        ttk.Label(bar, text="Round:").pack(side="left", padx=(0, 4))
        cb = ttk.Combobox(bar, values=list(rounds), state="readonly", width=44)
        cb.pack(side="left")
        current = self.round
        if current:
            cb.set(next((k for k, r in rounds.items() if r.round_id == current.round_id), ""))

        def pick(_e=None) -> None:
            self.state["round_id"] = rounds[cb.get()].round_id
            self._on_tab()
        cb.bind("<<ComboboxSelected>>", pick)
        if current is None:
            ttk.Label(tab, text="No options rounds yet - create one on the Rounds tab.",
                      foreground="#888").pack(anchor="w")
        return current

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name == "Rounds":
            self.refresh()
            return
        tab = self.tabs[name]
        for w in tab.winfo_children():
            w.destroy()
        try:
            {"Choices": self._draw_choices, "Blocks": self._draw_blocks}[name](tab)
        except Exception:
            logger.exception("Options tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    def _error(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self.parent)

    # ── Rounds tab (old window) ──────────────────────────────────────

    def _build_rounds(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in (("New round", self.new_round), ("Edit round", self.edit_round),
                          ("Set status", self.set_status),
                          ("Manage subjects", self.manage_subjects),
                          ("Submit choices", self.submit_choices), ("Summary", self.summary),
                          ("Delete round", self.delete_round), ("Refresh", self.refresh)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        ttk.Button(bar, text="History", command=self.history).pack(side="right")
        self.tree = _tree(tab, _ROUND_COLS, height=12)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._detail())
        self.tree.bind("<Double-1>", lambda _e: self.edit_round())
        box = ttk.LabelFrame(tab, text="Selected round", padding=8)
        box.pack(fill="x", pady=(8, 0))
        self.detail_var = tk.StringVar(value="(select a round)")
        ttk.Label(box, textvariable=self.detail_var, justify="left",
                  wraplength=1100).pack(anchor="w")
        self.rows: dict[str, OP.Round] = {}

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for r in OP.list_rounds():
            iid = str(r.round_id)
            self.rows[iid] = r
            self.tree.insert("", "end", iid=iid, tags=(r.status,), values=(
                r.round_id, r.name, r.year_group, r.status, r.opens_on or "",
                r.closes_on or "", r.choices_required, r.reserves_required))
        sel = str(self.state.get("round_id", ""))
        if sel not in self.rows and self.rows:
            sel = next(iter(self.rows))       # newest round
        if sel in self.rows:
            self.tree.selection_set(sel)
        open_now = [r for r in self.rows.values() if r.status == "Open"]
        self.summary_var.set(f"{len(self.rows)} round(s)"
                             + (f" · open: {', '.join(r.name for r in open_now)}"
                                if open_now else ""))
        self._detail()

    def _selected(self, quiet: bool = False) -> OP.Round | None:
        sel = self.tree.selection()
        if not sel:
            if not quiet:
                messagebox.showinfo("Options", "Select a round first.", parent=self.parent)
            return None
        self.state["round_id"] = int(sel[0])
        return self.rows.get(sel[0])

    def _detail(self) -> None:
        r = self._selected(quiet=True)
        if r is None:
            self.detail_var.set("(select a round)")
            return
        s = OP.summary(r.round_id)
        subjects = ", ".join(x["code"] for x in s["subject_picks"]) or "none yet"
        rules = "; ".join(x.label for x in OP.list_rules(r.round_id)) or "none"
        lines = [f"{r.name} · Year {r.year_group} choosing for Year {r.next_year} · {r.status}"
                 + (f" · opens {r.opens_on}" if r.opens_on else "")
                 + (f" · closes {r.closes_on}" if r.closes_on else ""),
                 f"{r.choices_required} choices + {r.reserves_required} reserve(s) · "
                 f"{r.blocks} blocks · classes of {r.class_size}",
                 f"Subjects: {subjects}", f"Rules: {rules}",
                 f"Chosen: {s['pupils_submitted']} of {s['cohort']} pupils"
                 + (f" ({s['overrides']} accepted against the rules)" if s["overrides"]
                    else "")]
        if r.notes:
            lines.append(f"Notes: {r.notes}")
        self.detail_var.set("\n".join(lines))

    def new_round(self) -> None:
        round_dialog(self.parent, self.principal, None, self.refresh)

    def edit_round(self) -> None:
        r = self._selected()
        if r:
            round_dialog(self.parent, self.principal, r, self.refresh)

    def set_status(self) -> None:
        r = self._selected()
        if r:
            status_dialog(self.parent, self.principal, r, self.refresh)

    def manage_subjects(self) -> None:
        r = self._selected()
        if r:
            SubjectsWindow(self.parent, self.principal, r, on_close=self.refresh)

    def submit_choices(self) -> None:
        r = self._selected()
        if r:
            choices_dialog(self.parent, self.principal, r, None, self.refresh)

    def summary(self) -> None:
        r = self._selected()
        if r:
            summary_window(self.parent, r)

    def delete_round(self) -> None:
        r = self._selected()
        if not r or not messagebox.askyesno(
                "Delete round", f"Delete '{r.name}' with its subjects and every pupil's "
                "choices?", parent=self.parent):
            return
        try:
            OP.delete_round(r.round_id, actor=self.principal)
        except _ERRORS as e:
            self._error("Delete round", e)
            return
        self.state.pop("round_id", None)
        self.refresh()

    def history(self) -> None:
        r = self._selected()
        if not r:
            return
        text = "\n".join(f"{h['at']}  {h['actor']:<12} {h['action']:<16} "
                         f"{', '.join(f'{k}={v}' for k, v in h['detail'].items())}"
                         for h in OP.history(r.round_id)) or "No changes recorded."
        _text_window(self.parent, f"History - {r.name}", text)

    # ── Choices tab ──────────────────────────────────────────────────

    def _draw_choices(self, tab: ttk.Frame) -> None:
        r = self._round_bar(tab)
        if r is None:
            return
        s = OP.summary(r.round_id)
        ttk.Label(tab, text=f"{s['pupils_submitted']} of {s['cohort']} Year {r.year_group} "
                            f"pupils have chosen · {r.status}"
                            + (f" · closes {r.closes_on}" if r.closes_on else ""),
                  font=("", 10, "bold")).pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)
        show = tk.StringVar(value=self.state.get("choices_show", "chosen"))
        ttk.Radiobutton(bar, text="Chosen", variable=show, value="chosen",
                        command=lambda: self._redraw("choices_show", show.get())).pack(
            side="left")
        ttk.Radiobutton(bar, text="Not chosen yet", variable=show, value="missing",
                        command=lambda: self._redraw("choices_show", show.get())).pack(
            side="left", padx=6)
        missing = show.get() == "missing"
        if missing:
            cols = (("pupil", "Pupil", 200), ("adm", "Adm no", 90), ("form", "Form", 60))
        else:
            cols = (("pupil", "Pupil", 200), ("adm", "Adm no", 90), ("form", "Form", 60),
                    ("choices", "Choices (reserves)", 360), ("by", "Entered by", 90),
                    ("at", "Entered", 130))
        tree = _tree(tab, cols, height=16)
        rows: dict[str, int] = {}
        if missing:
            for p in OP.not_submitted(r.round_id):
                rows[str(p.pupil_id)] = p.pupil_id
                tree.insert("", "end", iid=str(p.pupil_id), values=(
                    f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}",
                    p.admission_no, p.form_group or ""))
        else:
            for x in OP.list_choices(r.round_id):
                rows[str(x.pupil_id)] = x.pupil_id
                tree.insert("", "end", iid=str(x.pupil_id), values=(
                    x.pupil_name, x.admission_no, x.form_group or "", x.label,
                    x.submitted_by or "", x.submitted_at),
                    tags=("override",) if x.override_reason else ())

        def chosen() -> int | None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Choices", "Select a pupil first.", parent=self.parent)
                return None
            return rows[sel[0]]

        def enter() -> None:
            pid = chosen()
            if pid is not None:
                choices_dialog(self.parent, self.principal, r, pid, self._on_tab)

        def clear() -> None:
            pid = chosen()
            if pid is None or not messagebox.askyesno("Clear choices", "Remove this pupil's "
                                                      "choices?", parent=self.parent):
                return
            try:
                OP.clear_choices(r.round_id, pid, actor=self.principal)
            except _ERRORS as e:
                self._error("Clear choices", e)
                return
            self._on_tab()
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(6, 0))
        for text, cmd in (("Enter / change choices…", enter), ("Clear", clear),
                          ("Remind families…", lambda: self._remind(r)),
                          ("Export…", lambda: self._export(r))):
            ttk.Button(bar2, text=text, command=cmd).pack(side="left", padx=2)
        if self.open_pupil:
            ttk.Button(bar2, text="Open pupil", command=lambda: (
                (pid := chosen()) is not None and self.open_pupil(pid))).pack(side="left",
                                                                            padx=2)
        tree.bind("<Double-1>", lambda _e: enter())

    def _redraw(self, key: str, value) -> None:
        self.state[key] = value
        self._on_tab()

    def _remind(self, r: OP.Round) -> None:
        missing = OP.not_submitted(r.round_id)
        if not missing:
            messagebox.showinfo("Remind families", "Every pupil has chosen.", parent=self.parent)
            return
        body = simpledialog.askstring(
            "Remind families", f"E-mail the families of {len(missing)} pupil(s) who haven't "
            "chosen?\n\nEdit the first line of the message if you like (the rest is "
            "standard):", initialvalue=OP.reminder_body(r).split("\n\n")[1],
            parent=self.parent)
        if body is None:
            return
        parts = OP.reminder_body(r).split("\n\n")
        parts[1] = body
        try:
            result = OP.remind_families(r.round_id, actor=self.principal,
                                        body="\n\n".join(parts))
        except _ERRORS as e:
            self._error("Remind families", e)
            return
        _deliver(self.parent, self.principal, [result.message_id], "Remind families")
        no = result.pupils_without_email
        messagebox.showinfo("Remind families", f"E-mail to {result.recipients} contact(s) is on "
                            "its way (see Email for delivery)."
                            + (f"\n\nNo e-mail address for {len(no)} pupil(s): "
                               + ", ".join(p.display_name for p in no[:20]) if no else ""),
                            parent=self.parent)

    def _export(self, r: OP.Round) -> None:
        path = filedialog.asksaveasfilename(parent=self.parent, defaultextension=".csv",
                                            initialfile=f"options-{r.round_id}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = OP.export_choices(r.round_id, path, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            self._error("Export", e)
            return
        messagebox.showinfo("Export", f"Saved {n} pupil(s) to {path}.", parent=self.parent)

    # ── Blocks tab ───────────────────────────────────────────────────

    def _draw_blocks(self, tab: ttk.Frame) -> None:
        r = self._round_bar(tab)
        if r is None:
            return
        st = OP.allocation_status(r.round_id)
        classes = st["classes"]
        top = ttk.Frame(tab)
        top.pack(fill="x")
        ttk.Label(top, text=f"{r.status} · {len(classes)} class(es) in {r.blocks} blocks · "
                            f"{st['allocated']} pupil(s) allocated, "
                            f"{len(st['unresolved'])} still to place"
                            + (f" · {st['all_first_choices']} got all their first choices"
                               if st["allocated"] else ""),
                  font=("", 10, "bold")).pack(side="left")
        grid = ttk.LabelFrame(tab, text="Option blocks (pupils / class size)", padding=6)
        grid.pack(fill="x", pady=(6, 0))
        for i, b in enumerate(r.block_names):
            ttk.Label(grid, text=f"Block {b}", font=("", 10, "bold")).grid(
                row=0, column=i, sticky="w", padx=(0, 18))
            here = [c for c in classes if c["block"] == b]
            for j, c in enumerate(here, 1):
                full = c["pupils"] > c["capacity"]
                ttk.Label(grid, text=f"{c['code']}  {c['pupils']}/{c['capacity']}",
                          foreground="#a00" if full else "").grid(row=j, column=i, sticky="w",
                                                                  padx=(0, 18))
            if not here:
                ttk.Label(grid, text="(empty)", foreground="#888").grid(row=1, column=i,
                                                                        sticky="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=6)
        steps = (("Edit blocks…", lambda: BlocksWindow(self.parent, self.principal, r,
                                                        on_close=self._on_tab)),
                 ("Allocate subjects", lambda: self._allocate(r)),
                 ("Finalise", lambda: self._finalise(r)),
                 ("E-mail results…", lambda: self._results(r)),
                 ("Create Year 10 groups", lambda: self._groups(r)))
        for text, cmd in steps:
            btn = ttk.Button(bar, text=text, command=cmd)
            btn.pack(side="left", padx=2)
            if not self.editor:
                btn.state(["disabled"])
        ttk.Label(tab, text="Pupils still to place (double-click to place by hand):").pack(
            anchor="w", pady=(6, 0))
        tree = _tree(tab, (("pupil", "Pupil", 200), ("adm", "Adm no", 90),
                           ("choices", "Choices (reserves)", 300),
                           ("why", "Why", 360)), height=8)
        why = {u["pupil_id"]: u["why"] for u in self.state.get("last_unresolved", [])
               if self.state.get("last_round") == r.round_id}
        for x in st["unresolved"]:
            tree.insert("", "end", iid=str(x.pupil_id), tags=("stuck",), values=(
                x.pupil_name, x.admission_no, x.label, why.get(x.pupil_id, "")))

        def place(_e=None) -> None:
            sel = tree.selection()
            if sel and self.editor:
                place_dialog(self.parent, self.principal, r, int(sel[0]), self._on_tab)
        tree.bind("<Double-1>", place)
        ttk.Button(tab, text="Change a pupil's placement…", command=lambda: self._place_any(
            r)).pack(anchor="w", pady=(6, 0))

    def _allocate(self, r: OP.Round) -> None:
        try:
            rep = OP.allocate(r.round_id, actor=self.principal)
        except _ERRORS as e:
            self._error("Allocate", e)
            return
        self.state.update(last_unresolved=rep["unresolved"], last_round=r.round_id)
        messagebox.showinfo("Allocate", f"{rep['placed']} pupil(s) placed"
                            + (f", {rep['manual']} kept as placed by hand" if rep["manual"]
                               else "")
                            + (f"; {rep['reserves_used']} reserve(s) used" if
                               rep["reserves_used"] else "")
                            + (f".\n\n{len(rep['unresolved'])} pupil(s) need placing by hand."
                               if rep["unresolved"] else "."), parent=self.parent)
        self._on_tab()

    def _finalise(self, r: OP.Round) -> None:
        if not messagebox.askyesno("Finalise", "Finalise the round? Choices and placements "
                                   "can't change afterwards.", parent=self.parent):
            return
        try:
            OP.set_status(r.round_id, "Finalised", actor=self.principal)
        except _ERRORS as e:
            self._error("Finalise", e)
            return
        self._on_tab()

    def _results(self, r: OP.Round) -> None:
        if not messagebox.askyesno("E-mail results", "E-mail every family their child's "
                                   "subjects?", parent=self.parent):
            return
        try:
            ids, no_email = OP.email_results(r.round_id, actor=self.principal)
        except _ERRORS as e:
            self._error("E-mail results", e)
            return
        _deliver(self.parent, self.principal, ids, "E-mail results")
        messagebox.showinfo("E-mail results", f"{len(ids)} e-mail(s) on their way (see "
                            "Email for delivery)."
                            + (f"\n\nNo e-mail address for {len(no_email)} pupil(s): "
                               + ", ".join(no_email[:20]) if no_email else ""),
                            parent=self.parent)

    def _groups(self, r: OP.Round) -> None:
        try:
            rep = OP.create_groups(r.round_id, actor=self.principal)
        except _ERRORS as e:
            self._error("Create Year 10 groups", e)
            return
        lines = [f"Created {len(rep['created'])} group(s)"
                 + (f": {', '.join(rep['created'])}" if rep["created"] else ""),
                 f"Added {rep['added']} pupil place(s)."]
        if rep["refused"]:
            lines += ["", "Not added:"] + [f"• {c}: {adm} - {why}"
                                           for c, adm, why in rep["refused"][:30]]
        messagebox.showinfo("Create Year 10 groups", "\n".join(lines), parent=self.parent)

    def _place_any(self, r: OP.Round) -> None:
        rows = {f"{x.pupil_name} ({x.admission_no})": x.pupil_id
                for x in OP.list_choices(r.round_id)}
        if not rows:
            messagebox.showinfo("Place", "Nobody has chosen yet.", parent=self.parent)
            return
        win = make_toplevel(self.parent.winfo_toplevel())
        win.title("Choose a pupil")
        frm = ttk.Frame(win, padding=12)
        frm.pack()
        cb = ttk.Combobox(frm, values=list(rows), state="readonly", width=40)
        cb.pack()

        def go() -> None:
            if cb.get():
                win.destroy()
                place_dialog(self.parent, self.principal, r, rows[cb.get()], self._on_tab)
        ttk.Button(frm, text="Place…", command=go).pack(pady=(8, 0))


def draw_options(parent: ttk.Frame, *, principal: Principal, state: dict | None = None,
                 open_pupil: Callable[[int], None] | None = None) -> OptionsPage:
    return OptionsPage(parent, principal=principal, state=state if state is not None else {},
                       open_pupil=open_pupil)


# ── Windows and dialogs ──────────────────────────────────────────────

def _text_window(owner, title: str, text: str) -> None:
    W.text_window(owner, title, text, size="760x460")


def _grid_rows(frm, rows, start: int = 0) -> None:
    for i, (text, w) in enumerate(rows, start):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)


def _buttons(frm, row: int, win, save, label: str = "Save") -> ttk.Frame:
    bar = ttk.Frame(frm)
    bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text=label, command=save).pack(side="right", padx=(0, 6))
    return bar


def round_dialog(owner, principal: Principal, r: OP.Round | None,
                 after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Edit round" if r else "New round")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    entries: dict[str, ttk.Entry] = {}
    fields = (("name", "Name *", 40), ("opens_on", "Opens on (YYYY-MM-DD)", 12),
              ("closes_on", "Closes on (YYYY-MM-DD)", 12), ("choices_required", "Choices", 5),
              ("reserves_required", "Reserves", 5), ("blocks", "Option blocks", 5),
              ("class_size", "Class size", 5))
    year = ttk.Combobox(frm, values=("7", "8", "9", "10"), state="readonly", width=5)
    year.set(str(r.year_group if r else 9))
    rows = []
    for key, label, width in fields:
        e = ttk.Entry(frm, width=width)
        value = getattr(r, key) if r else {"choices_required": 4, "reserves_required": 1,
                                            "class_size": OP.DEFAULT_CLASS_SIZE}.get(key)
        e.insert(0, "" if value is None else str(value))
        entries[key] = e
        rows.append((label, e))
        if key == "name":
            rows.append(("Year group choosing", year))
    notes = tk.Text(frm, width=48, height=3, wrap="word")
    notes.insert("1.0", (r.notes if r else "") or "")
    rows.append(("Notes", notes))
    _grid_rows(frm, rows)
    ttk.Label(frm, text="Blocks blank = one per choice.", foreground="#888").grid(
        row=len(rows), column=1, sticky="w")

    def save() -> None:
        data = {k: e.get() for k, e in entries.items()}
        data.update(year_group=year.get(), notes=notes.get("1.0", "end"))
        try:
            if r is None:
                OP.create_round(data, actor=principal)
            else:
                OP.update_round(r.round_id, data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Options round", _problems(e), parent=win)
            return
        win.destroy()
        after()
    _buttons(frm, len(rows) + 1, win, save)


def status_dialog(owner, principal: Principal, r: OP.Round,
                  after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Set status")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{r.name} - now {r.status}").grid(row=0, column=0, columnspan=2,
                                                           sticky="w")
    var = tk.StringVar(value=r.status)
    help_text = {"Draft": "being set up", "Open": "staff can enter pupils' choices",
                 "Closed": "no more choices; blocks and allocation",
                 "Finalised": "subjects confirmed - nothing can change"}
    for i, s in enumerate(OP.STATUSES, 1):
        ttk.Radiobutton(frm, text=f"{s} - {help_text[s]}", variable=var, value=s).grid(
            row=i, column=0, columnspan=2, sticky="w")

    def save() -> None:
        try:
            OP.set_status(r.round_id, var.get(), actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Set status", _problems(e), parent=win)
            return
        win.destroy()
        after()
    _buttons(frm, 6, win, save)


class SubjectsWindow:
    """The old Manage subjects window, with the round's rules underneath."""

    def __init__(self, owner, principal: Principal, r: OP.Round, *,
                 on_close: Callable[[], None]) -> None:
        self.principal, self.r, self.on_close = principal, r, on_close
        self.win = win = make_toplevel(owner.winfo_toplevel())
        win.title(f"Subjects - {r.name}")
        win.geometry("860x560")
        win.protocol("WM_DELETE_WINDOW", self.close)
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="In round", foreground="#444").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Active catalogue (taught in Year "
                            f"{r.next_year}, not core)", foreground="#444").grid(
            row=0, column=2, sticky="w")
        self.in_round = ttk.Treeview(frm, columns=("code", "name", "cat"), show="headings",
                                     height=12)
        for c, h, w in (("code", "Code", 70), ("name", "Name", 170), ("cat", "Category", 90)):
            self.in_round.heading(c, text=h)
            self.in_round.column(c, width=w, anchor="w")
        self.in_round.grid(row=1, column=0, sticky="nsew")
        col = ttk.Frame(frm)
        col.grid(row=1, column=1, padx=8)
        ttk.Button(col, text="◀ Add", command=self.add).pack(pady=4)
        ttk.Button(col, text="Remove ▶", command=self.remove).pack(pady=4)
        self.available = ttk.Treeview(frm, columns=("code", "name", "qual"), show="headings",
                                      height=12)
        for c, h, w in (("code", "Code", 70), ("name", "Name", 170),
                        ("qual", "Qualification", 90)):
            self.available.heading(c, text=h)
            self.available.column(c, width=w, anchor="w")
        self.available.grid(row=1, column=2, sticky="nsew")
        rules = ttk.LabelFrame(frm, text="Rules on each pupil's choices", padding=6)
        rules.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.rules = tk.Listbox(rules, height=4)
        self.rules.pack(fill="x")
        rbar = ttk.Frame(rules)
        rbar.pack(fill="x", pady=(4, 0))
        ttk.Label(rbar, text="At least").pack(side="left")
        self.rule_n = ttk.Spinbox(rbar, from_=1, to=8, width=3)
        self.rule_n.set("1")
        self.rule_n.pack(side="left", padx=4)
        ttk.Label(rbar, text="from").pack(side="left")
        self.rule_cats = {c: tk.BooleanVar() for c in S.EBACC_CATEGORIES}
        for c, v in self.rule_cats.items():
            ttk.Checkbutton(rbar, text=c, variable=v).pack(side="left", padx=2)
        ttk.Button(rbar, text="Add rule", command=self.add_rule).pack(side="left", padx=8)
        ttk.Button(rbar, text="Remove selected", command=self.remove_rule).pack(side="left")
        bottom = ttk.Frame(frm)
        bottom.grid(row=3, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(bottom, text="Close", command=self.close).pack(side="right")
        frm.columnconfigure(0, weight=1)
        frm.columnconfigure(2, weight=1)
        frm.rowconfigure(1, weight=1)
        self.rule_ids: list[int] = []
        self.refresh()

    def close(self) -> None:
        self.win.destroy()
        self.on_close()

    def refresh(self) -> None:
        for t in (self.in_round, self.available):
            t.delete(*t.get_children())
        for s in OP.list_round_subjects(self.r.round_id):
            self.in_round.insert("", "end", iid=str(s.subject_id),
                                 values=(s.code, s.name, s.ebacc_category or ""))
        for s in OP.available_subjects(self.r.round_id):
            self.available.insert("", "end", iid=str(s.subject_id),
                                  values=(s.code, s.name, s.qualification))
        self.rules.delete(0, "end")
        self.rule_ids = []
        for rule in OP.list_rules(self.r.round_id):
            self.rules.insert("end", rule.label)
            self.rule_ids.append(rule.rule_id)

    def _do(self, title: str, fn) -> None:
        try:
            fn()
        except _ERRORS as e:
            messagebox.showerror(title, _problems(e), parent=self.win)
        self.refresh()

    def add(self) -> None:
        for sid in self.available.selection():
            self._do("Add subject", lambda s=sid: OP.add_round_subject(
                self.r.round_id, int(s), actor=self.principal))

    def remove(self) -> None:
        for sid in self.in_round.selection():
            self._do("Remove subject", lambda s=sid: OP.remove_round_subject(
                self.r.round_id, int(s), actor=self.principal))

    def add_rule(self) -> None:
        cats = [c for c, v in self.rule_cats.items() if v.get()]
        self._do("Add rule", lambda: OP.add_rule(self.r.round_id, cats, self.rule_n.get(),
                                                 actor=self.principal))

    def remove_rule(self) -> None:
        sel = self.rules.curselection()
        if sel:
            self._do("Remove rule", lambda: OP.remove_rule(self.rule_ids[sel[0]],
                                                           actor=self.principal))


def choices_dialog(owner, principal: Principal, r: OP.Round, pupil_id: int | None,
                   after: Callable[[], None]) -> None:
    """The old Submit choices: pupil, primary choices in order, reserves."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Choices - {r.name}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    pupils = {f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name} "
              f"({p.admission_no})": p.pupil_id for p in OP.cohort(r.round_id)}
    subjects = {f"{s.name} ({s.code})": s.subject_id for s in OP.list_round_subjects(r.round_id)}
    names = [NONE, *subjects]
    pupil_cb = ttk.Combobox(frm, values=list(pupils), state="readonly", width=40)
    pupil_cb.grid(row=0, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Pupil").grid(row=0, column=0, sticky="w", padx=(0, 8))
    ttk.Label(frm, text="Primary choices:", font=("", 10, "bold")).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(8, 2))
    prim = []
    for i in range(r.choices_required):
        ttk.Label(frm, text=f"  {i + 1}.").grid(row=2 + i, column=0, sticky="e")
        cb = ttk.Combobox(frm, values=names, state="readonly", width=36)
        cb.set(NONE)
        cb.grid(row=2 + i, column=1, sticky="w", pady=1)
        prim.append(cb)
    row = 2 + r.choices_required
    res = []
    if r.reserves_required:
        ttk.Label(frm, text="Reserves:", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(8, 2))
        row += 1
        for i in range(r.reserves_required):
            ttk.Label(frm, text=f"  R{i + 1}.").grid(row=row, column=0, sticky="e")
            cb = ttk.Combobox(frm, values=names, state="readonly", width=36)
            cb.set(NONE)
            cb.grid(row=row, column=1, sticky="w", pady=1)
            res.append(cb)
            row += 1
    rules = OP.list_rules(r.round_id)
    if rules:
        ttk.Label(frm, text="Rules: " + "; ".join(x.label for x in rules),
                  foreground="#555", wraplength=380).grid(row=row, column=0, columnspan=2,
                                                          sticky="w", pady=(6, 0))
        row += 1
    reason = ttk.Entry(frm, width=40)
    if principal.role in OPTIONS_EDITORS:
        ttk.Label(frm, text="Accept against the rules because").grid(row=row, column=0,
                                                                    sticky="w", pady=(6, 0))
        reason.grid(row=row, column=1, sticky="w", pady=(6, 0))
        row += 1
    notes = ttk.Entry(frm, width=40)
    ttk.Label(frm, text="Notes").grid(row=row, column=0, sticky="w")
    notes.grid(row=row, column=1, sticky="w")
    row += 1
    by_id = {v: k for k, v in subjects.items()}

    def load(_e=None) -> None:
        pid = pupils.get(pupil_cb.get())
        x = OP.get_choices(r.round_id, pid) if pid else None
        for cb in prim + res:
            cb.set(NONE)
        reason.delete(0, "end")
        notes.delete(0, "end")
        if x:
            for cb, c in zip(prim, x.primary):
                cb.set(by_id.get(c.subject_id, NONE))
            for cb, c in zip(res, x.reserves):
                cb.set(by_id.get(c.subject_id, NONE))
            reason.insert(0, x.override_reason or "")
            notes.insert(0, x.notes or "")
    pupil_cb.bind("<<ComboboxSelected>>", load)
    if pupil_id is not None:
        pupil_cb.set(next((k for k, v in pupils.items() if v == pupil_id), ""))
        load()

    def save() -> None:
        pid = pupils.get(pupil_cb.get())
        if pid is None:
            messagebox.showerror("Choices", "Choose the pupil.", parent=win)
            return
        try:
            OP.submit_choices(r.round_id, pid,
                              [subjects[cb.get()] for cb in prim if cb.get() in subjects],
                              [subjects[cb.get()] for cb in res if cb.get() in subjects],
                              actor=principal, override_reason=reason.get() or None,
                              notes=notes.get() or None)
        except _ERRORS as e:
            messagebox.showerror("Choices", _problems(e), parent=win)
            return
        win.destroy()
        after()

    def clear_all() -> None:
        pid = pupils.get(pupil_cb.get())
        if pid is None:
            for cb in prim + res:
                cb.set(NONE)
            return
        if not messagebox.askyesno("Clear all", "Remove this pupil's choices?", parent=win):
            return
        try:
            OP.clear_choices(r.round_id, pid, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Choices", _problems(e), parent=win)
            return
        win.destroy()
        after()
    bar = _buttons(frm, row, win, save)
    ttk.Button(bar, text="Clear all", command=clear_all).pack(side="left")


def summary_window(owner, r: OP.Round) -> None:
    """The old Summary: who has chosen, and each subject's demand."""
    s = OP.summary(r.round_id)
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Summary - {r.name}")
    win.geometry("720x480")
    frm = ttk.Frame(win, padding=10)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Pupils submitted: {s['pupils_submitted']} of {s['cohort']}    "
                        f"Complete: {s['pupils_complete']}    "
                        f"Partial: {s['pupils_partial']}    "
                        f"Accepted against the rules: {s['overrides']}",
              foreground="#444").pack(anchor="w", pady=(0, 10))
    t = _tree(frm, (("code", "Code", 70), ("name", "Name", 220), ("primary", "Primary", 70),
                    ("first", "1st choice", 75), ("reserve", "Reserve", 70),
                    ("groups", "Classes needed", 100), ("places", "Places in blocks", 110)),
              height=14)
    for x in s["subject_picks"]:
        t.insert("", "end", values=(x["code"], x["name"], x["primary"], x["first"],
                                    x["reserve"], x["groups"],
                                    "" if x["places"] is None else x["places"]))
    ttk.Button(frm, text="Close", command=win.destroy).pack(pady=(8, 0))


class BlocksWindow:
    """Edit the option blocks: each block's subjects and class sizes."""

    def __init__(self, owner, principal: Principal, r: OP.Round, *,
                 on_close: Callable[[], None]) -> None:
        self.principal, self.r, self.on_close = principal, r, on_close
        self.win = win = make_toplevel(owner.winfo_toplevel())
        win.title(f"Option blocks - {r.name}")
        win.geometry("640x520")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="A subject can run in more than one block (more classes). "
                            "Saving clears the automatic allocation - run it again.",
                  foreground="#555", wraplength=600).pack(anchor="w")
        self.tree = _tree(frm, (("block", "Block", 60), ("code", "Code", 70),
                                ("name", "Subject", 220), ("size", "Class size", 80)),
                          height=14, multi=True)
        self.subjects = {f"{s.name} ({s.code})": s for s in
                         OP.list_round_subjects(r.round_id)}
        add = ttk.Frame(frm)
        add.pack(fill="x", pady=6)
        self.block_cb = ttk.Combobox(add, values=r.block_names, state="readonly", width=4)
        self.block_cb.set(r.block_names[0])
        self.subj_cb = ttk.Combobox(add, values=list(self.subjects), state="readonly",
                                    width=30)
        self.size_e = ttk.Entry(add, width=5)
        self.size_e.insert(0, str(r.class_size))
        for label, w in (("Block", self.block_cb), ("Subject", self.subj_cb),
                         ("Size", self.size_e)):
            ttk.Label(add, text=label).pack(side="left", padx=(0, 4))
            w.pack(side="left", padx=(0, 8))
        ttk.Button(add, text="Add", command=self.add).pack(side="left")
        bar = ttk.Frame(frm)
        bar.pack(fill="x")
        ttk.Button(bar, text="Remove selected", command=self.remove).pack(side="left")
        ttk.Button(bar, text="Suggest from choices", command=self.suggest).pack(side="left",
                                                                                padx=6)
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
        ttk.Button(bar, text="Save", command=self.save).pack(side="right", padx=6)
        self.entries: list[tuple[str, int, int]] = [
            (b["block"], b["subject_id"], b["capacity"]) for b in OP.list_blocks(r.round_id)]
        self.draw()

    def draw(self) -> None:
        self.tree.delete(*self.tree.get_children())
        names = {s.subject_id: s for s in self.subjects.values()}
        for i, (b, sid, size) in enumerate(sorted(self.entries)):
            s = names.get(sid)
            self.tree.insert("", "end", iid=str(i), values=(
                b, s.code if s else sid, s.name if s else "", size))
        self.entries.sort()

    def add(self) -> None:
        s = self.subjects.get(self.subj_cb.get())
        if s is None:
            return
        try:
            size = int(self.size_e.get())
        except ValueError:
            messagebox.showerror("Blocks", "Class size must be a number.", parent=self.win)
            return
        self.entries = [e for e in self.entries
                        if not (e[0] == self.block_cb.get() and e[1] == s.subject_id)]
        self.entries.append((self.block_cb.get(), s.subject_id, size))
        self.draw()

    def remove(self) -> None:
        drop = {int(i) for i in self.tree.selection()}
        self.entries = [e for i, e in enumerate(self.entries) if i not in drop]
        self.draw()

    def suggest(self) -> None:
        plan = OP.suggest_blocks(self.r.round_id)
        if not any(plan.values()):
            messagebox.showinfo("Suggest", "Nobody has chosen yet.", parent=self.win)
            return
        self.entries = [(b, sid, size) for b, items in plan.items() for sid, size in items]
        self.draw()

    def save(self) -> None:
        blocks: dict[str, list[tuple[int, int | None]]] = {b: [] for b in self.r.block_names}
        for b, sid, size in self.entries:
            blocks.setdefault(b, []).append((sid, size))
        try:
            OP.set_blocks(self.r.round_id, blocks, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Blocks", _problems(e), parent=self.win)
            return
        self.win.destroy()
        self.on_close()


def place_dialog(owner, principal: Principal, r: OP.Round, pupil_id: int,
                 after: Callable[[], None]) -> None:
    """Place one pupil by hand: a subject for each block."""
    x = OP.get_choices(r.round_id, pupil_id)
    if x is None:
        messagebox.showinfo("Place", "That pupil hasn't chosen.", parent=owner)
        return
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Place {x.pupil_name}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{x.pupil_name} chose {x.label}", wraplength=420).grid(
        row=0, column=0, columnspan=2, sticky="w")
    if x.notes:
        ttk.Label(frm, text=f"Notes: {x.notes}", foreground="#555").grid(
            row=1, column=0, columnspan=2, sticky="w")
    current = {a.block: a.subject_id for a in OP.allocations(r.round_id, pupil_id)}
    status = OP.allocation_status(r.round_id)
    boxes: dict[str, tuple[ttk.Combobox, dict[str, int]]] = {}
    for i, b in enumerate(r.block_names, 2):
        options = {f"{c['code']} ({c['pupils']}/{c['capacity']})": c["subject_id"]
                   for c in status["classes"] if c["block"] == b}
        cb = ttk.Combobox(frm, values=[NONE, *options], state="readonly", width=24)
        cb.set(next((k for k, v in options.items() if v == current.get(b)), NONE))
        ttk.Label(frm, text=f"Block {b}").grid(row=i, column=0, sticky="w", padx=(0, 8))
        cb.grid(row=i, column=1, sticky="w", pady=1)
        boxes[b] = (cb, options)

    def save() -> None:
        placements = {b: opts[cb.get()] for b, (cb, opts) in boxes.items() if cb.get() in opts}
        try:
            _a, warnings = OP.place_by_hand(r.round_id, pupil_id, placements, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Place", _problems(e), parent=win)
            return
        win.destroy()
        if warnings:
            messagebox.showwarning("Place", "Saved. Note:\n" + "\n".join(
                f"• {w}" for w in warnings), parent=owner)
        after()
    _buttons(frm, len(r.block_names) + 3, win, save)
