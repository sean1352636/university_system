"""Enrolment & Leavers screens: overview, actions due, leavers, joiners, and
the record-leaver / leaving-details / reinstate dialogs. Rules live in
:mod:`modules.pupils.domain.enrolment`."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.date_picker import DatePicker, recent_years
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.secondary.modules.admissions.domain import admissions as A
from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W
from education_system.systems.secondary.ui.gui.layouts.scroll import scrolled_form

logger = logging.getLogger(__name__)

_ALL = "All"
_REASON_HINTS = {
    EN.MOVED_SCHOOL: "Give the new school. Send the Common Transfer File within 15 school "
                     "days.",
    EN.MOVED_AWAY: "If you don't know the new school, refer the pupil to the local authority "
                   "as a possible child missing education.",
    EN.EHE: "Notify the local authority that the pupil is being home educated.",
    EN.EXCLUSION: "Notify the local authority of the permanent exclusion.",
    EN.END_OF_Y11: "Record where the pupil is going next (post-16 destination).",
    EN.OTHER: "Explain the reason in the notes.",
}


def _tree(parent: tk.Misc, columns, height: int = 14) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, stretch={"name", "actions", "dest"})


def _destination(v: EN.LeaverView) -> str:
    lv = v.leaving
    if lv is None:
        return ""
    return lv.post16_destination or lv.destination_school or ""


# ── Page ─────────────────────────────────────────────────────────────

def draw_enrolment(parent: ttk.Frame, *, principal: Principal,
                   open_pupil: Callable[[int], None], state: dict | None = None) -> None:
    state = state if state is not None else {}
    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(0, 6))
    ttk.Label(head, text="Enrolment & Leavers", font=("", 16, "bold")).pack(side="left")
    year_var = tk.StringVar(value=state.get("year", A.current_academic_year()))
    ttk.Combobox(head, textvariable=year_var, values=A.academic_year_choices()[:3],
                 state="readonly", width=8).pack(side="right")
    ttk.Label(head, text="Academic year").pack(side="right", padx=(0, 4))

    book = ttk.Notebook(parent)
    book.pack(fill="both", expand=True)
    tabs = {name: ttk.Frame(book, padding=8) for name in
            ("Overview", "Actions due", "Leavers", "Joiners")}
    for name, frame in tabs.items():
        book.add(frame, text=name)

    def redraw() -> None:
        state["year"] = year_var.get()
        state["tab"] = book.index(book.select())
        for frame in tabs.values():
            for child in frame.winfo_children():
                child.destroy()
        _overview(tabs["Overview"], year_var.get())
        _actions_due(tabs["Actions due"], principal, open_pupil, redraw)
        _leavers(tabs["Leavers"], principal, year_var.get(), open_pupil, redraw, state)
        _joiners(tabs["Joiners"], year_var.get(), open_pupil)
        due = len(EN.list_leavers(actions_only=True))
        book.tab(tabs["Actions due"], text=f"Actions due ({due})" if due else "Actions due")

    year_var.trace_add("write", lambda *_a: redraw())
    book.bind("<<NotebookTabChanged>>", lambda _e: activity_log.record(
        "enrolment.tab", target=book.tab(book.select(), "text")))
    ttk.Button(head, text="Record a leaver…", command=lambda: record_leaver_dialog(
        parent, principal=principal, pupil=None, after=redraw)).pack(side="right", padx=8)
    redraw()
    try:
        book.select(state.get("tab", 0))
    except tk.TclError:
        pass


def _overview(tab: ttk.Frame, year: str) -> None:
    try:
        s = EN.roll_summary(year)
    except Exception as e:  # noqa: BLE001
        logger.exception("Roll summary failed")
        ttk.Label(tab, text=f"Couldn't load the summary: {e}", foreground="#a00").pack()
        return
    activity_log.record("enrolment.overview", target=year)
    tiles = ttk.Frame(tab)
    tiles.pack(fill="x")
    for i, (label, value, hint) in enumerate((
            ("On roll now", s.on_roll, " · ".join(f"Y{y} {n}"
                                                    for y, n in s.on_roll_by_year.items())),
            (f"Joined in {year}", s.joiners, "admitted during the year"),
            (f"Left in {year}", s.leavers, "taken off roll during the year"),
            ("Actions due", s.actions_due, "leavers with follow-up to do"))):
        tiles.columnconfigure(i, weight=1, uniform="t")
        box = ttk.LabelFrame(tiles, padding=10)
        box.grid(row=0, column=i, sticky="nsew", padx=4)
        ttk.Label(box, text=label, foreground="#666").pack(anchor="w")
        ttk.Label(box, text=str(value), font=("", 22, "bold")).pack(anchor="w")
        ttk.Label(box, text=hint, foreground="#888", font=("", 9)).pack(anchor="w")
    reasons = ttk.LabelFrame(tab, text=f"Leavers in {year} by reason", padding=10)
    reasons.pack(fill="x", pady=(12, 0), padx=4)
    if not s.leavers_by_reason:
        ttk.Label(reasons, text="Nobody has left this year.", foreground="#888").pack(anchor="w")
    for reason, n in sorted(s.leavers_by_reason.items(), key=lambda kv: -kv[1]):
        ttk.Label(reasons, text=f"{n:>4}  {reason}").pack(anchor="w")


def _actions_due(tab: ttk.Frame, principal: Principal, open_pupil, redraw) -> None:
    rows = EN.list_leavers(actions_only=True)
    ttk.Label(tab, text="Leavers with something still to do, newest first. Double-click to "
                        "record what's been done.", foreground="#666").pack(anchor="w",
                                                                           pady=(0, 6))
    tree = _tree(tab, (("adm", "Adm. no", 90), ("name", "Pupil", 170), ("left", "Left", 90),
                       ("reason", "Reason", 160), ("actions", "To do", 420)))
    for v in rows:
        tree.insert("", "end", iid=str(v.pupil.pupil_id), values=(
            v.pupil.admission_no, v.pupil.display_name, v.pupil.leaving_date or "",
            v.pupil.leaving_reason or "", "; ".join(v.actions())))
    if not rows:
        ttk.Label(tab, text="Nothing due.", foreground="#060").pack(anchor="w", pady=4)

    def open_details(_e=None) -> None:
        sel = tree.selection()
        if sel:
            details_dialog(tab, principal=principal, pupil_id=int(sel[0]), after=redraw)

    tree.bind("<Double-1>", open_details)
    bar = ttk.Frame(tab)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Record details…", command=open_details).pack(side="left")
    ttk.Button(bar, text="Open pupil", command=lambda: tree.selection() and open_pupil(
        int(tree.selection()[0]))).pack(side="left", padx=4)


def _leavers(tab: ttk.Frame, principal: Principal, year: str, open_pupil, redraw,
             state: dict) -> None:
    filters = ttk.Frame(tab)
    filters.pack(fill="x", pady=(0, 6))
    reason_var = tk.StringVar(value=state.get("reason", _ALL))
    search_var = tk.StringVar(value=state.get("search", ""))
    ttk.Label(filters, text="Reason").pack(side="left")
    ttk.Combobox(filters, textvariable=reason_var, values=[_ALL, *EN.REASONS],
                 state="readonly", width=24).pack(side="left", padx=(4, 12))
    ttk.Label(filters, text="Search").pack(side="left")
    ttk.Entry(filters, textvariable=search_var, width=22).pack(side="left", padx=4)
    tree = _tree(tab, (("adm", "Adm. no", 90), ("name", "Pupil", 170), ("yr", "Yr", 35),
                       ("left", "Left", 90), ("reason", "Reason", 160),
                       ("dest", "Destination", 200), ("actions", "To do", 220)))
    count = ttk.Label(tab, foreground="#666")
    count.pack(anchor="w", pady=(4, 0))

    def refresh(*_a) -> None:
        state.update(reason=reason_var.get(), search=search_var.get())
        tree.delete(*tree.get_children())
        reason = None if reason_var.get() == _ALL else reason_var.get()
        rows = EN.list_leavers(academic_year=year, reason=reason,
                               search=search_var.get().strip() or None)
        for v in rows:
            tree.insert("", "end", iid=str(v.pupil.pupil_id), values=(
                v.pupil.admission_no, v.pupil.display_name, v.pupil.year_group,
                v.pupil.leaving_date or "", v.pupil.leaving_reason or "", _destination(v),
                "; ".join(v.actions()) or "—"))
        count.configure(text=f"{len(rows)} leaver{'s' if len(rows) != 1 else ''} in {year}")

    def selected() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Leavers", "Select a pupil first.", parent=tab)
            return None
        return int(sel[0])

    def details(_e=None) -> None:
        pid = selected()
        if pid is not None:
            details_dialog(tab, principal=principal, pupil_id=pid, after=redraw)

    def back_on_roll() -> None:
        pid = selected()
        if pid is not None:
            reinstate_dialog(tab, principal=principal, pupil_id=pid, after=redraw)

    reason_var.trace_add("write", refresh)
    search_var.trace_add("write", refresh)
    tree.bind("<Double-1>", details)
    bar = ttk.Frame(tab)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Leaving details…", command=details).pack(side="left")
    ttk.Button(bar, text="Reinstate…", command=back_on_roll).pack(side="left", padx=4)
    ttk.Button(bar, text="Open pupil", command=lambda: (pid := selected()) is not None
               and open_pupil(pid)).pack(side="left")
    refresh()


def _joiners(tab: ttk.Frame, year: str, open_pupil) -> None:
    rows = EN.list_joiners(year)
    ttk.Label(tab, text=f"Pupils admitted during {year}, newest first.",
              foreground="#666").pack(anchor="w", pady=(0, 6))
    tree = _tree(tab, (("adm", "Adm. no", 90), ("name", "Pupil", 200), ("yr", "Yr", 35),
                       ("form", "Form", 60), ("joined", "Joined", 90), ("status", "Status", 90)))
    for p in rows:
        tree.insert("", "end", iid=str(p.pupil_id), values=(
            p.admission_no, p.display_name, p.year_group, p.form_group or "",
            p.admission_date, p.roll_status_label))
    tree.bind("<Double-1>", lambda _e: tree.selection() and open_pupil(
        int(tree.selection()[0])))


# ── Dialogs ──────────────────────────────────────────────────────────

def _detail_fields(body: ttk.Frame, start_row: int, current: dict,
                   reason_getter: Callable[[], str]) -> tuple[dict, Callable[[], None]]:
    """Destination / CTF / LA / post-16 / notes fields. Returns (widgets, sync)."""
    w: dict[str, tk.Misc] = {}

    def row(r: int, label: str, widget: tk.Misc) -> None:
        ttk.Label(body, text=label).grid(row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        widget.grid(row=r, column=1, sticky="w", pady=2)

    for i, (key, label, width) in enumerate((
            ("destination_school", "Destination school", 34),
            ("destination_urn", "Destination URN", 10),
            ("destination_la", "Destination local authority", 26))):
        e = ttk.Entry(body, width=width)
        e.insert(0, current.get(key) or "")
        row(start_row + i, label, e)
        w[key] = e
    post16 = ttk.Combobox(body, values=["", *EN.POST16_DESTINATIONS], state="readonly",
                          width=40)
    post16.set(current.get("post16_destination") or "")
    row(start_row + 3, "Post-16 destination", post16)
    w["post16_destination"] = post16
    for i, (key, label) in enumerate((("ctf_sent_date", "CTF sent on"),
                                      ("la_notified_date", "Local authority notified on"))):
        dp = DatePicker(body, value=current.get(key) or None, years=recent_years(ahead=0))
        row(start_row + 4 + i, label, dp)
        w[key] = dp
    ttk.Label(body, text="Notes").grid(row=start_row + 6, column=0, sticky="nw", pady=2)
    notes = tk.Text(body, width=44, height=4, wrap="word")
    notes.insert("1.0", current.get("notes") or "")
    notes.grid(row=start_row + 6, column=1, sticky="w", pady=2)
    w["notes"] = notes

    def sync() -> None:
        post16.configure(state="readonly" if reason_getter() == EN.END_OF_Y11 else "disabled")
        if reason_getter() != EN.END_OF_Y11:
            post16.set("")

    sync()
    return w, sync


def _collect(w: dict) -> dict:
    out = {}
    for key, widget in w.items():
        if isinstance(widget, tk.Text):
            out[key] = widget.get("1.0", "end").strip()
        else:
            out[key] = widget.get()  # type: ignore[attr-defined]
    return out


def record_leaver_dialog(owner: tk.Misc, *, principal: Principal, pupil: P.Pupil | None,
                         after: Callable[[], None]) -> None:
    if not principal.can_open(EN.MENU_LABEL):
        messagebox.showwarning("Leavers", principal.denied_message(EN.MENU_LABEL),
                               parent=owner)
        return
    activity_log.record("enrolment.leave.open", target=pupil.admission_no if pupil else "pick")
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Record a leaver")
    window_sizing.fit(win, "760x720", (640, 520))
    body, footer = scrolled_form(win)
    chosen: dict = {"pupil": pupil}

    pick = ttk.LabelFrame(body, text="Pupil", padding=8)
    pick.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    who = ttk.Label(pick, text=pupil.display_name if pupil else "Search for the pupil:",
                    font=("", 11, "bold"))
    who.pack(anchor="w")
    if pupil is None:
        search_var = tk.StringVar()
        ttk.Entry(pick, textvariable=search_var, width=40).pack(anchor="w", pady=4)
        results = tk.Listbox(pick, height=5, width=60, exportselection=False)
        results.pack(anchor="w")
        found: list[P.Pupil] = []

        def search(*_a) -> None:
            results.delete(0, "end")
            found.clear()
            text = search_var.get().strip()
            if text:
                for p in P.list_pupils(search=text)[:50]:
                    found.append(p)
                    results.insert("end", f"{p.display_name} · {p.admission_no} · "
                                          f"Y{p.year_group}")

        def choose(_e=None) -> None:
            sel = results.curselection()
            if sel:
                chosen["pupil"] = found[sel[0]]
                who.configure(text=f"{found[sel[0]].display_name} "
                                   f"({found[sel[0]].admission_no}, Year "
                                   f"{found[sel[0]].year_group})")

        search_var.trace_add("write", search)
        results.bind("<<ListboxSelect>>", choose)

    ttk.Label(body, text="Last day on roll *").grid(row=1, column=0, sticky="w", pady=2)
    date = DatePicker(body, years=recent_years(ahead=0))
    date.grid(row=1, column=1, sticky="w", pady=2)
    ttk.Label(body, text="Reason *").grid(row=2, column=0, sticky="w", pady=2)
    reason = ttk.Combobox(body, values=list(EN.REASONS), state="readonly", width=30)
    reason.grid(row=2, column=1, sticky="w", pady=2)
    hint = ttk.Label(body, text="", foreground="#a60", wraplength=520, justify="left")
    hint.grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 6))
    fields, sync = _detail_fields(body, 4, {}, reason.get)

    def on_reason(_e=None) -> None:
        hint.configure(text=_REASON_HINTS.get(reason.get(), ""))
        sync()

    reason.bind("<<ComboboxSelected>>", on_reason)
    error_var = tk.StringVar()
    ttk.Label(footer, textvariable=error_var, foreground="#a00", wraplength=700,
              justify="left").pack(anchor="w")

    def save() -> None:
        p = chosen["pupil"]
        if p is None:
            error_var.set("Choose the pupil who is leaving.")
            return
        if not messagebox.askyesno("Record leaver", f"Take {p.display_name} off roll?\n\n"
                                   "Their login will be closed.", parent=win):
            return
        try:
            view = EN.record_leaver(p.pupil_id, leaving_date=date.get(), reason=reason.get(),
                                    details=_collect(fields), actor=principal)
        except EN.ValidationError as e:
            error_var.set("Please fix:\n• " + "\n• ".join(e.problems))
            return
        except (EN.PermissionDenied, EN.NotFound) as e:
            messagebox.showerror("Record leaver", str(e), parent=win)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("Record leaver failed")
            messagebox.showerror("Record leaver", f"Something went wrong:\n{e}", parent=win)
            return
        win.destroy()
        todo = view.actions()
        messagebox.showinfo("Leaver recorded", f"{p.display_name} is now off roll."
                            + ("\n\nStill to do:\n• " + "\n• ".join(todo) if todo else ""),
                            parent=owner)
        after()

    def cancel() -> None:
        activity_log.record("enrolment.leave.cancel")
        win.destroy()

    bar = ttk.Frame(footer)
    bar.pack(anchor="e", pady=(4, 0))
    ttk.Button(bar, text="Cancel", command=cancel).pack(side="right")
    ttk.Button(bar, text="Record leaver", command=save).pack(side="right", padx=(0, 6))
    win.protocol("WM_DELETE_WINDOW", cancel)


def details_dialog(owner: tk.Misc, *, principal: Principal, pupil_id: int,
                   after: Callable[[], None]) -> None:
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        return
    current = EN.current_leaving(pupil_id)
    activity_log.record("enrolment.details.open", target=pupil.admission_no)
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Leaving details - {pupil.display_name}")
    window_sizing.fit(win, "720x560", (620, 460))
    body, footer = scrolled_form(win)
    reason = current.reason if current else (pupil.leaving_reason or EN.OTHER)
    ttk.Label(body, text=f"{pupil.display_name} ({pupil.admission_no}) left on "
                         f"{pupil.leaving_date or '—'}: {reason}",
              font=("", 11, "bold"), wraplength=600).grid(row=0, column=0, columnspan=2,
                                                          sticky="w")
    view = EN.LeaverView(pupil, current)
    todo = view.actions()
    ttk.Label(body, text=("Still to do: " + "; ".join(todo)) if todo else "Nothing to do.",
              foreground="#a60" if todo else "#060", wraplength=600, justify="left").grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(4, 8))
    values = {k: getattr(current, k) for k in EN.DETAIL_FIELDS} if current else {}
    fields, _sync = _detail_fields(body, 2, values, lambda: reason)
    error_var = tk.StringVar()
    ttk.Label(footer, textvariable=error_var, foreground="#a00", wraplength=660,
              justify="left").pack(anchor="w")

    def save() -> None:
        try:
            EN.record_details(pupil_id, _collect(fields), actor=principal)
        except EN.ValidationError as e:
            error_var.set("Please fix:\n• " + "\n• ".join(e.problems))
            return
        except (EN.PermissionDenied, EN.NotFound) as e:
            messagebox.showerror("Leaving details", str(e), parent=win)
            return
        win.destroy()
        after()

    bar = ttk.Frame(footer)
    bar.pack(anchor="e", pady=(4, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def reinstate_dialog(owner: tk.Misc, *, principal: Principal, pupil_id: int,
                     after: Callable[[], None]) -> None:
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        return
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Reinstate {pupil.display_name}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Put {pupil.display_name} back on roll? Their login will be "
                        "reopened with the same username and password.",
              wraplength=380, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(frm, text="Year group").grid(row=1, column=0, sticky="w", pady=(10, 2))
    year = ttk.Combobox(frm, values=[str(y) for y in P.YEAR_GROUPS], state="readonly",
                        width=5)
    year.set(str(pupil.year_group))
    year.grid(row=1, column=1, sticky="w", pady=(10, 2))
    ttk.Label(frm, text="Reason *").grid(row=2, column=0, sticky="w")
    note = ttk.Entry(frm, width=40)
    note.grid(row=2, column=1, sticky="w")

    def go() -> None:
        try:
            EN.reinstate(pupil_id, actor=principal, note=note.get(),
                         year_group=int(year.get()))
        except (EN.ValidationError, EN.PermissionDenied, EN.NotFound) as e:
            messagebox.showerror("Reinstate", str(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Reinstated", f"{pupil.display_name} is back on roll.",
                            parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Reinstate", command=go).pack(side="right", padx=(0, 6))
