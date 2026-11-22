"""Interviews tab of the Sixth Form Admissions window.

Split out of ``admissions_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import datetime as _dt
import tkinter as tk
from collections import Counter
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox, simpledialog
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
)
from . import applicant_actions as act
from ._common import _parse_date, _prompt, _today
from ._sidecar import CONFIG_FILE, DEFAULT_SLOT_CAP, ROOMS_FILE, _load_json, _merge_ics, _store_json


# ══ Interviews tab ════════════════════════════════════════════════

class InterviewsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Interviews")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.insert(0, _today())
        self.from_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="To:").pack(side="left")
        self.to_e = ttk.Entry(bar, width=12)
        plus = (_dt.date.today() + _dt.timedelta(days=30)).isoformat()
        self.to_e.insert(0, plus)
        self.to_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Next 7",
                    command=lambda: self._preset(7)
                    ).pack(side="left", padx=2)
        ttk.Button(bar, text="Next 30",
                    command=lambda: self._preset(30)
                    ).pack(side="left", padx=2)
        self.agenda_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Agenda view", variable=self.agenda_var,
                         command=self.refresh).pack(side="left", padx=8)
        ttk.Button(bar, text="Schedule…",
                    command=self._schedule).pack(side="left", padx=4)
        ttk.Button(bar, text="Record outcome…",
                    command=self._record_outcome).pack(side="left", padx=4)
        ttk.Button(bar, text="Reschedule…",
                    command=self._reschedule).pack(side="left", padx=2)
        ttk.Button(bar, text="Cancel…",
                    command=self._cancel).pack(side="left", padx=2)
        ttk.Button(bar, text="No-show",
                    command=self._no_show).pack(side="left", padx=2)
        ttk.Button(bar, text="Export .ics",
                    command=self._export_ics).pack(side="left", padx=2)

        # Extra scheduling tools (items 16–25).
        tools_mb = ttk.Menubutton(bar, text="Tools ▾")
        tmenu = tk.Menu(tools_mb, tearoff=0)
        tmenu.add_command(label="Calendar (month)…",
                           command=self._calendar_view)
        tmenu.add_command(label="Panel view (by interviewer)…",
                           command=self._panel_view)
        tmenu.add_command(label="Slot capacity…", command=self._slot_capacity)
        tmenu.add_separator()
        tmenu.add_command(label="Bulk schedule…", command=self._bulk_schedule)
        tmenu.add_command(label="Reschedule a whole day…",
                           command=self._reschedule_batch)
        tmenu.add_command(label="Assign room…", command=self._room_assignment)
        tmenu.add_separator()
        tmenu.add_command(label="Send reminders…", command=self._send_reminders)
        tmenu.add_command(label="Detect clashes", command=self._detect_clashes)
        tmenu.add_command(label="No-show report…", command=self._no_show_report)
        tmenu.add_command(label="Export all .ics…", command=self._export_all_ics)
        tools_mb["menu"] = tmenu
        tools_mb.pack(side="left", padx=(8, 2))
        ok = act.can_admissions()
        for b in bar.winfo_children():
            if isinstance(b, ttk.Button) and str(b.cget("text")) in (
                    "Schedule…", "Record outcome…", "Reschedule…", "Cancel…",
                    "No-show"):
                act.gate(b, ok)
        for label in ("Bulk schedule…", "Reschedule a whole day…",
                      "Assign room…", "Send reminders…"):
            act.gate_menu(tmenu, label, ok)

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                  anchor="w").pack(side="bottom", fill="x", padx=8,
                                   pady=(0, 8))

        body = ttk.Frame(self.frame)
        body.pack(fill="both", expand=True, padx=8, pady=4)
        table_frame = ttk.Frame(body)
        table_frame.pack(side="left", fill="both", expand=True)
        # #0 (tree column) shows date-group headers in agenda mode.
        cols = ("id", "name", "interviewer", "status", "subjects")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                  show="tree headings")
        self.tree.heading("#0", text="Date")
        self.tree.column("#0", width=150, anchor="w")
        widths = {"id": 80, "name": 180,
                  "interviewer": 150, "status": 150, "subjects": 260}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("done", background="#eeeeee")
        self.tree.tag_configure("clash", background="#ffd0d0")
        self.tree.tag_configure("group",
                                 font=("TkDefaultFont", 10, "bold"))

        # Interviewer workload panel (item 22).
        side = ttk.LabelFrame(body, text="Interviewer load")
        side.pack(side="right", fill="y", padx=(8, 0))
        self.load_tree = ttk.Treeview(side, columns=("n",), show="tree",
                                       height=18, selectmode="none")
        self.load_tree.column("#0", width=150, anchor="w")
        self.load_tree.pack(fill="both", expand=True, padx=4, pady=4)

    def _preset(self, days: int) -> None:
        today = _dt.date.today()
        self.from_e.delete(0, "end")
        self.from_e.insert(0, today.isoformat())
        self.to_e.delete(0, "end")
        self.to_e.insert(0,
                          (today + _dt.timedelta(days=days)).isoformat())
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        df = self.from_e.get().strip()
        dt = self.to_e.get().strip()
        rows = [a for a in data.list_applicants() if a.interview_date]
        rows = [a for a in rows
                 if (not df or a.interview_date >= df)
                 and (not dt or a.interview_date <= dt)]
        rows.sort(key=lambda a: (a.interview_date or "",
                                  a.interviewer or "", a.full_name))
        today = _today()
        # Detect clashes: same interviewer booked twice on the same day.
        slot_counts = Counter(
            (a.interview_date, a.interviewer)
            for a in rows if a.interviewer)
        clashes = {k for k, n in slot_counts.items() if n > 1}

        agenda = self.agenda_var.get()
        clash_n = 0
        current_group = None
        for a in rows:
            tags: tuple[str, ...] = ()
            if a.interview_date and a.interview_date < today:
                tags += ("done",)
            is_clash = (a.interview_date, a.interviewer) in clashes
            if is_clash:
                tags += ("clash",)
                clash_n += 1
            parent = ""
            if agenda:
                if a.interview_date != current_group:
                    current_group = a.interview_date
                    parent = self.tree.insert(
                        "", "end", text=a.interview_date or "—",
                        open=True, tags=("group",))
                    self._last_group = parent
                parent = self._last_group
            self.tree.insert(
                parent, "end", iid=a.applicant_id,
                text="" if agenda else (a.interview_date or "—"),
                values=(a.applicant_id, a.full_name,
                        a.interviewer or "—", a.status,
                        ", ".join(a.subjects)),
                tags=tags)

        # Workload panel.
        for i in self.load_tree.get_children():
            self.load_tree.delete(i)
        load = Counter(a.interviewer or "(unassigned)" for a in rows)
        for who, n in sorted(load.items(), key=lambda kv: (-kv[1], kv[0])):
            self.load_tree.insert("", "end", text=f"{who}: {n}")

        msg = f"{len(rows)} interview(s) between {df} and {dt}."
        if clash_n:
            msg += f"  ⚠ {clash_n} in clashing slots."
        self.count_var.set(msg)

    def _selected_applicant(self) -> Applicant | None:
        sel = self.tree.selection()
        if not sel:
            return None
        # Group header rows are not valid applicant ids.
        return data.get_applicant(sel[0])

    def _schedule(self) -> None:
        rows = data.list_applicants(open_only=True)
        if not rows:
            messagebox.showinfo("Schedule",
                                  "No open applicants.")
            return
        ScheduleDialog(self.frame.winfo_toplevel(), rows,
                          on_save=self.refresh)

    def _record_outcome(self) -> None:
        a = self._selected_applicant()
        if a is None:
            messagebox.showinfo(
                "Record outcome",
                "Select a scheduled interview row first.")
            return
        RecordOutcomeDialog(self.frame.winfo_toplevel(), a,
                            on_save=self.refresh)

    def _reschedule(self) -> None:
        a = self._selected_applicant()
        if a is None:
            messagebox.showinfo("Reschedule", "Select an interview row.")
            return
        date = _prompt(self.frame, "Reschedule",
                       "New interview date (YYYY-MM-DD):",
                       a.interview_date or _today())
        if not date:
            return
        reason = _prompt(self.frame, "Reschedule", "Reason (optional):", "")
        try:
            data.reschedule_interview(a.applicant_id, new_date=date,
                                       reason=reason or None,
                                       interviewer=a.interviewer)
        except Exception as e:  # noqa: BLE001 — every refusal is shown
            act.show_error(self.frame, "Reschedule", e)
            return
        self.refresh()

    def _cancel(self) -> None:
        a = self._selected_applicant()
        if a is None:
            messagebox.showinfo("Cancel", "Select an interview row.")
            return
        if not messagebox.askyesno(
                "Cancel interview",
                f"Cancel {a.full_name}'s interview and return them to "
                f"'Under Review'?"):
            return
        reason = _prompt(self.frame, "Cancel", "Reason (optional):", "")
        if reason is None:
            return
        ok, _ = act.attempt(self.frame, "Cancel interview",
                            data.cancel_interview, a.applicant_id,
                            reason=reason or None)
        if ok:
            self.refresh()

    def _no_show(self) -> None:
        a = self._selected_applicant()
        if a is None:
            messagebox.showinfo("No-show", "Select an interview row.")
            return
        if not messagebox.askyesno(
                "No-show",
                f"Record {a.full_name} as a no-show and flag for follow-up?"):
            return
        ok, _ = act.attempt(self.frame, "No-show", data.mark_no_show,
                            a.applicant_id, follow_up=True)
        if ok:
            self.refresh()

    def _export_ics(self) -> None:
        a = self._selected_applicant()
        if a is None or not a.interview_date:
            messagebox.showinfo("Export .ics",
                                  "Select a row with a scheduled interview.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.frame.winfo_toplevel(), defaultextension=".ics",
            initialfile=f"interview_{a.applicant_id}.ics",
            filetypes=[("Calendar", "*.ics")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(data.interview_to_ics(a.applicant_id))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Export .ics", str(e))
            return
        messagebox.showinfo("Export .ics", f"Saved to {path}")

    # ── shared helpers ───────────────────────────────────────────

    def _range(self) -> tuple[str, str]:
        return self.from_e.get().strip(), self.to_e.get().strip()

    def _range_rows(self) -> list[Applicant]:
        df, dt = self._range()
        rows = [a for a in data.list_applicants() if a.interview_date]
        return sorted(
            (a for a in rows
             if (not df or a.interview_date >= df)
             and (not dt or a.interview_date <= dt)),
            key=lambda a: (a.interview_date or "", a.interviewer or "",
                           a.full_name))

    # ── calendar / panel / capacity (items 16, 22, 25) ──────────

    def _calendar_view(self) -> None:
        rows = self._range_rows()
        counts = Counter(a.interview_date[:10] for a in rows
                         if a.interview_date)
        anchor = _parse_date(self.from_e.get().strip()) or _dt.date.today()
        top = self.frame.winfo_toplevel()
        win = tk.Toplevel(top)
        win.title(f"Interview calendar — {anchor:%B %Y}")
        win.transient(top)
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"{anchor:%B %Y}",
                   font=("TkDefaultFont", 12, "bold")).grid(
            row=0, column=0, columnspan=7, pady=(0, 6))
        import calendar
        for c, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri",
                                    "Sat", "Sun")):
            ttk.Label(frm, text=name, width=10, anchor="center").grid(
                row=1, column=c, padx=1, pady=1)
        cal = calendar.Calendar(firstweekday=0)
        for r, week in enumerate(cal.monthdatescalendar(anchor.year,
                                                          anchor.month),
                                  start=2):
            for c, day in enumerate(week):
                n = counts.get(day.isoformat(), 0)
                muted = day.month != anchor.month
                cell = ttk.Label(
                    frm, relief="solid", borderwidth=1, anchor="nw",
                    width=10, justify="left",
                    text=f"{day.day}\n{('● ' + str(n)) if n else ''}",
                    foreground="#999" if muted else (
                        "#b00000" if n else "#333"))
                cell.grid(row=r, column=c, padx=1, pady=1, sticky="nsew",
                          ipady=8)
        ttk.Button(frm, text="Close", command=win.destroy).grid(
            row=99, column=6, pady=(8, 0), sticky="e")

    def _panel_view(self) -> None:
        rows = self._range_rows()
        by_who: dict[str, list[Applicant]] = {}
        for a in rows:
            by_who.setdefault(a.interviewer or "(unassigned)", []).append(a)
        top = self.frame.winfo_toplevel()
        win = tk.Toplevel(top)
        win.title("Interview panels")
        win.transient(top)
        tree = ttk.Treeview(win, show="tree", height=22)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for who in sorted(by_who):
            group = tree.insert("", "end",
                                 text=f"{who}  ({len(by_who[who])})",
                                 open=True)
            for a in by_who[who]:
                tree.insert(group, "end",
                             text=f"{a.interview_date or '—'}  ·  "
                                  f"{a.applicant_id}  {a.full_name}  "
                                  f"[{a.status}]")

    def _slot_capacity(self) -> None:
        cap = int(_load_json(CONFIG_FILE, {}).get(
            "daily_slot_cap", DEFAULT_SLOT_CAP))
        new = simpledialog.askinteger(
            "Slot capacity", "Interview slots available per day:",
            parent=self.frame.winfo_toplevel(), initialvalue=cap,
            minvalue=1, maxvalue=100)
        if new is not None and new != cap:
            cfg = _load_json(CONFIG_FILE, {})
            cfg["daily_slot_cap"] = new
            _store_json(CONFIG_FILE, cfg)
            cap = new
        counts = Counter(a.interview_date[:10] for a in self._range_rows()
                         if a.interview_date)
        lines = [f"Daily cap: {cap} slot(s)", ""]
        for day in sorted(counts):
            used = counts[day]
            free = cap - used
            flag = "  ⚠ OVER" if free < 0 else ""
            lines.append(f"  {day}   used {used:>2}  free {free:>3}{flag}")
        if not counts:
            lines.append("  (no interviews scheduled in range)")
        TextViewerDialog(self.frame.winfo_toplevel(),
                          "Slot capacity", "\n".join(lines))

    # ── bulk scheduling (items 17, 24) ──────────────────────────

    def _bulk_schedule(self) -> None:
        pool = data.list_applicants(status="Under Review") + \
            data.list_applicants(status="Submitted")
        if not pool:
            messagebox.showinfo(
                "Bulk schedule",
                "No applicants in 'Submitted' or 'Under Review' to schedule.")
            return
        start = _prompt(self.frame, "Bulk schedule",
                        f"Schedule {len(pool)} applicant(s) starting from "
                        f"date (YYYY-MM-DD):", _today())
        if not start:
            return
        start_d = _parse_date(start)
        if start_d is None:
            messagebox.showerror("Bulk schedule", "Invalid start date.")
            return
        per_day = simpledialog.askinteger(
            "Bulk schedule", "Interviews per day:",
            parent=self.frame.winfo_toplevel(), initialvalue=DEFAULT_SLOT_CAP,
            minvalue=1, maxvalue=50)
        if not per_day:
            return
        who = _prompt(self.frame, "Bulk schedule",
                      "Interviewer for all (blank = leave unset):", "")
        if who is None:
            return
        if not messagebox.askyesno(
                "Bulk schedule",
                f"Schedule {len(pool)} applicant(s), {per_day} per day, "
                f"from {start_d.isoformat()}?"):
            return
        failures = []
        for i, a in enumerate(pool):
            day = start_d + _dt.timedelta(days=i // per_day)
            try:
                data.schedule_interview(
                    a.applicant_id, interview_date=day.isoformat(),
                    interviewer=who.strip() or None)
            except Exception as e:  # noqa: BLE001
                failures.append(f"{a.applicant_id}: {e}")
        self.refresh()
        msg = f"Scheduled {len(pool) - len(failures)} of {len(pool)}."
        if failures:
            msg += "\n\nFailed:\n" + "\n".join(failures[:12])
        messagebox.showinfo("Bulk schedule", msg)

    def _reschedule_batch(self) -> None:
        day = _prompt(self.frame, "Reschedule a whole day",
                      "Which interview date to shift (YYYY-MM-DD)?", _today())
        if not day:
            return
        affected = [a for a in self._range_rows()
                    if a.interview_date and a.interview_date[:10] == day[:10]]
        if not affected:
            messagebox.showinfo("Reschedule a whole day",
                                  f"No interviews found on {day}.")
            return
        shift = simpledialog.askinteger(
            "Reschedule a whole day",
            f"Shift all {len(affected)} interview(s) by how many days?",
            parent=self.frame.winfo_toplevel(), initialvalue=1)
        if not shift:
            return
        base = _parse_date(day)
        new_day = (base + _dt.timedelta(days=shift)).isoformat()
        failures = []
        for a in affected:
            try:
                data.reschedule_interview(
                    a.applicant_id, new_date=new_day,
                    reason=f"Day moved {shift:+d}d", interviewer=a.interviewer)
            except Exception as e:  # noqa: BLE001
                failures.append(f"{a.applicant_id}: {e}")
        self.refresh()
        messagebox.showinfo(
            "Reschedule a whole day",
            f"Moved {len(affected) - len(failures)} interview(s) to "
            f"{new_day}." + ("\n\nFailed:\n" + "\n".join(failures)
                             if failures else ""))

    # ── rooms (item 21) ─────────────────────────────────────────

    def _room_assignment(self) -> None:
        a = self._selected_applicant()
        if a is None:
            messagebox.showinfo("Assign room", "Select an interview row.")
            return
        rooms = _load_json(ROOMS_FILE, {})
        current = rooms.get(a.applicant_id, "")
        room = _prompt(self.frame, "Assign room",
                       f"Room for {a.full_name}'s interview "
                       f"({a.interview_date or 'unscheduled'}):", current)
        if room is None:
            return
        room = room.strip()
        if room:
            rooms[a.applicant_id] = room
        else:
            rooms.pop(a.applicant_id, None)
        _store_json(ROOMS_FILE, rooms)
        messagebox.showinfo(
            "Assign room",
            f"Room for {a.applicant_id} set to '{room}'." if room
            else f"Room for {a.applicant_id} cleared.")

    # ── reminders / clashes / reports / bulk ics (18, 19, 20, 23) ─

    def _send_reminders(self) -> None:
        target = _prompt(
            self.frame, "Send reminders",
            "Send interview reminders for which date (YYYY-MM-DD)?",
            (_dt.date.today() + _dt.timedelta(days=1)).isoformat())
        if not target:
            return
        rooms = _load_json(ROOMS_FILE, {})
        due = [a for a in self._range_rows()
               if a.interview_date and a.interview_date[:10] == target[:10]]
        if not due:
            messagebox.showinfo("Send reminders",
                                  f"No interviews scheduled on {target}.")
            return
        lines = [f"Interview reminders for {target} "
                 f"({len(due)} applicant(s))", "=" * 52, ""]
        for a in due:
            room = rooms.get(a.applicant_id, "TBC")
            lines += [
                f"To: {a.email or '(no email on file)'}",
                f"Subject: Your sixth-form interview on {a.interview_date}",
                "",
                f"Dear {a.first_name},",
                "",
                f"This is a reminder of your interview on "
                f"{a.interview_date}. Interviewer: "
                f"{a.interviewer or 'TBC'}. Room: {room}.",
                "",
                "Please arrive 10 minutes early with your ID.",
                "",
                "-" * 52, ""]
        TextViewerDialog(
            self.frame.winfo_toplevel(),
            f"Reminders — {target}", "\n".join(lines),
            save_name=f"reminders_{target}.txt")
        if not messagebox.askyesno(
                "Send reminders",
                f"E-mail the interview invitation (with calendar entry) to "
                f"the {len(due)} applicant(s) now?"):
            return
        from education_system.systems.sixth_form.domain.admissions import (
            admissions_comms,
        )
        sent, failed = [], []
        for a in due:
            try:
                msgs = admissions_comms.send_interview_invite(a.applicant_id)
                sent += [f"{a.applicant_id} {m.to_address}: {m.label}"
                         for m in msgs]
            except Exception as e:  # noqa: BLE001 — reported per applicant
                failed.append(f"{a.applicant_id}: "
                              f"{act.describe(e).splitlines()[-1]}")
        TextViewerDialog(
            self.frame.winfo_toplevel(), f"Reminders sent — {target}",
            "\n".join([f"Queued {len(sent)} message(s).", ""] + sent
                      + (["", f"Not sent ({len(failed)}):"] + failed
                         if failed else [])))

    def _detect_clashes(self) -> None:
        rows = self._range_rows()
        slots = Counter((a.interview_date, a.interviewer)
                        for a in rows if a.interviewer)
        clashes = {k for k, n in slots.items() if n > 1}
        if not clashes:
            messagebox.showinfo("Detect clashes",
                                  "No interviewer double-bookings in range.")
            return
        lines = ["Interviewer double-bookings:", ""]
        for (date, who) in sorted(clashes):
            who_rows = [a for a in rows
                        if a.interview_date == date and a.interviewer == who]
            lines.append(f"  {date}  {who}  ×{len(who_rows)}: "
                         + ", ".join(x.applicant_id for x in who_rows))
        TextViewerDialog(self.frame.winfo_toplevel(),
                          "Clashes", "\n".join(lines))

    def _no_show_report(self) -> None:
        flagged = [a for a in data.list_applicants() if a.follow_up]
        lines = [f"Follow-up / no-show list ({len(flagged)} applicant(s))",
                 "=" * 52, ""]
        for a in flagged:
            lines.append(f"  {a.applicant_id}  {a.full_name:<24} "
                         f"[{a.status}]  interview: "
                         f"{a.interview_date or '—'}  "
                         f"{a.email or ''}")
        if not flagged:
            lines.append("  (nobody currently flagged for follow-up)")
        TextViewerDialog(self.frame.winfo_toplevel(),
                          "No-show / follow-up report", "\n".join(lines),
                          save_name="follow_up_report.txt")

    def _export_all_ics(self) -> None:
        rows = self._range_rows()
        if not rows:
            messagebox.showinfo("Export all .ics",
                                  "No interviews in the current range.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.frame.winfo_toplevel(), defaultextension=".ics",
            initialfile="interviews.ics", filetypes=[("Calendar", "*.ics")])
        if not path:
            return
        body, n = _merge_ics([a.applicant_id for a in rows])
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Export all .ics", str(e))
            return
        messagebox.showinfo("Export all .ics",
                              f"Wrote {n} interview event(s) to {path}")


# Sibling names used only at call time; imported last so any import order works.
from .dialogs_actions import RecordOutcomeDialog, ScheduleDialog, TextViewerDialog  # noqa: E402
