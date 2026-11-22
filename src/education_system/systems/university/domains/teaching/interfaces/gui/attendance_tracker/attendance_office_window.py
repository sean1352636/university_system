"""Attendance Office: registers, authorised absences, UKVI, non-engagement, funding.

The rules live in ``university/application`` (attendance_registers,
attendance_engagement); this window collects input and shows results.
"""
import logging
import tkinter as tk
from contextlib import closing
from datetime import date
from tkinter import ttk, messagebox, simpledialog, filedialog

from education_system.systems.university.application.attendance import engagement as eng
from education_system.systems.university.application.attendance import registers as reg
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


def _tree(parent, columns, widths, height=12):
    frame = ttk.Frame(parent)
    frame.pack(fill='both', expand=True)
    tree = ttk.Treeview(frame, columns=[c for c, _ in columns], show='headings', height=height)
    for (key, heading), width in zip(columns, widths):
        tree.heading(key, text=heading)
        tree.column(key, width=width, anchor='w')
    bar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side='right', fill='y')
    tree.pack(side='left', fill='both', expand=True)
    return tree


class AttendanceOfficeWindow:
    def __init__(self, parent, auth=None):
        self.auth = auth
        self.win = tk.Toplevel(parent)
        self.win.title("Attendance Office")
        self.win.geometry("1150x720")
        self.win.minsize(900, 560)
        try:
            self.win.transient(parent)
        except tk.TclError:
            pass
        with closing(get_connection()) as conn:
            start, end = reg.default_window(conn)
        self.start_var = tk.StringVar(value=start.isoformat())
        self.end_var = tk.StringVar(value=end.isoformat())
        nb = ttk.Notebook(self.win)
        nb.pack(fill='both', expand=True, padx=8, pady=8)
        for label, builder in (("Registers", self._registers), ("Absences", self._absences),
                               ("UKVI", self._ukvi), ("Engagement", self._engagement),
                               ("Funding", self._funding)):
            frame = ttk.Frame(nb, padding=8)
            nb.add(frame, text=label)
            try:
                builder(frame)
            except Exception:
                logger.exception("Attendance Office %s tab failed", label)
                ttk.Label(frame, text=f"{label} could not be loaded.").pack()

    # ── helpers ─────────────────────────────────────────────────────────

    def _user(self):
        user = getattr(self.auth, 'current_user', None) or {}
        return user.get('username') or 'attendance_office'

    def _run(self, action, success=None):
        try:
            with closing(get_connection()) as conn:
                result = action(conn)
                conn.commit()
        except ValueError as e:
            messagebox.showwarning("Attendance Office", str(e), parent=self.win)
            return None
        except Exception as e:
            logger.exception("Attendance Office action failed")
            messagebox.showerror("Attendance Office", f"Failed: {e}", parent=self.win)
            return None
        if success:
            messagebox.showinfo("Attendance Office", success(result) if callable(success) else success,
                                parent=self.win)
        return result if result is not None else True

    def _window(self):
        return self.start_var.get().strip(), self.end_var.get().strip()

    def _range_bar(self, parent, on_refresh):
        bar = ttk.Frame(parent)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="From").pack(side='left')
        ttk.Entry(bar, textvariable=self.start_var, width=12).pack(side='left', padx=4)
        ttk.Label(bar, text="to").pack(side='left')
        ttk.Entry(bar, textvariable=self.end_var, width=12).pack(side='left', padx=4)
        ttk.Button(bar, text="Refresh", command=on_refresh).pack(side='left', padx=6)
        return bar

    # ── registers ───────────────────────────────────────────────────────

    def _registers(self, tab):
        self._range_bar(tab, self._load_registers)
        ttk.Label(tab, text="Timetabled sessions with no register taken (from module_schedule, inside "
                            "term, outside holidays):", foreground='#555').pack(anchor='w')
        self.missing_tree = _tree(tab, [("date", "Date"), ("time", "Time"), ("module", "Module"),
                                        ("instructor", "Instructor")], [100, 110, 120, 220], height=9)
        look = ttk.Frame(tab)
        look.pack(fill='x', pady=(10, 4))
        ttk.Label(look, text="Student ID:").pack(side='left')
        self.student_var = tk.StringVar()
        ttk.Entry(look, textvariable=self.student_var, width=14).pack(side='left', padx=6)
        ttk.Button(look, text="Show attendance", command=self._student).pack(side='left')
        self.student_text = tk.Text(tab, height=8, wrap='word')
        self.student_text.pack(fill='both', expand=True)
        self._load_registers()

    def _load_registers(self):
        self.missing_tree.delete(*self.missing_tree.get_children())
        start, end = self._window()
        with closing(get_connection()) as conn:
            for s in reg.register_compliance(conn, start, end):
                self.missing_tree.insert('', 'end', values=(s['date'], f"{s['start_time']}-{s['end_time']}",
                                                            s['module_code'], s['instructor'] or '—'))

    def _student(self):
        sid = self.student_var.get().strip()
        if not sid:
            return
        start, end = self._window()
        with closing(get_connection()) as conn:
            s = reg.student_summary(conn, sid, start, end)
        text = (f"{sid}: {s['expected']} timetabled session(s) between {start} and {end}\n"
                f"  present {s['present']}, late {s['late']}, excused {s['excused']}, absent {s['absent']}, "
                f"no register {s['no_register']}\n"
                f"  Attendance: {s['attendance_pct'] if s['attendance_pct'] is not None else '—'}% "
                f"(of sessions with a register; excused not counted)\n"
                f"  Register coverage: {s['coverage_pct'] if s['coverage_pct'] is not None else '—'}%"
                + ("  ← low coverage: the attendance figure rests on few registers"
                   if s['coverage_pct'] is not None and s['coverage_pct'] < 75 else "")
                + f"\n  Consecutive unexcused absences: {s['consecutive_missed']}")
        self.student_text.delete('1.0', 'end')
        self.student_text.insert('end', text)

    # ── absences ────────────────────────────────────────────────────────

    def _absences(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="Record self-certification for a student",
                   command=self._self_cert).pack(side='left')
        ttk.Button(bar, text="Refresh", command=self._load_absences).pack(side='left', padx=6)
        ttk.Label(tab, text="Approved absences (including self-certifications). Absences they cover are "
                            "stored as 'excused' automatically — before or after the register is taken.",
                  foreground='#555', wraplength=1000).pack(anchor='w', pady=(0, 6))
        self.abs_tree = _tree(tab, [("id", "#"), ("student", "Student"), ("from", "From"), ("to", "To"),
                                    ("module", "Module"), ("kind", "Type"), ("reason", "Reason"),
                                    ("excused", "Excused")], [50, 100, 95, 95, 100, 120, 330, 70])
        self._load_absences()

    def _load_absences(self):
        self.abs_tree.delete(*self.abs_tree.get_children())
        with closing(get_connection()) as conn:
            rows = conn.execute(
                "SELECT r.id, r.student_id, r.date, COALESCE(r.date_end, r.date), COALESCE(r.module_code, 'all'), "
                "       COALESCE(r.self_certified, 0), r.reason, "
                "       (SELECT COUNT(*) FROM attendance_records a "
                "         WHERE a.reason = 'authorised absence (request #' || r.id || ')') "
                "FROM absence_requests r WHERE LOWER(r.status) = 'approved' ORDER BY r.date DESC LIMIT 300").fetchall()
        for r in rows:
            self.abs_tree.insert('', 'end', values=(r[0], r[1], r[2], r[3], r[4],
                                                    "self-certified" if r[5] else "approved request",
                                                    r[6] or '', r[7]))

    def _self_cert(self):
        sid = simpledialog.askstring("Self-certification", "Student ID:", parent=self.win)
        start = sid and simpledialog.askstring("Self-certification", "First day ill (YYYY-MM-DD):",
                                               initialvalue=date.today().isoformat(), parent=self.win)
        end = start and simpledialog.askstring("Self-certification", "Last day ill (YYYY-MM-DD):",
                                               initialvalue=start, parent=self.win)
        reason = end and simpledialog.askstring("Self-certification", "Illness:", parent=self.win)
        if reason and self._run(lambda c: eng.self_certify(c, sid.strip(), start, end, reason),
                                "Self-certification recorded."):
            self._load_absences()

    # ── UKVI ────────────────────────────────────────────────────────────

    def _ukvi(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="Scan sponsored students", command=self._ukvi_scan).pack(side='left')
        ttk.Button(bar, text="Resolve selected", command=self._ukvi_resolve).pack(side='left', padx=6)
        self.show_closed = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Show resolved", variable=self.show_closed,
                        command=self._load_ukvi).pack(side='left')
        ttk.Button(bar, text="Term time on a date…", command=self._ukvi_term_time).pack(
            side='left', padx=6)
        with closing(get_connection()) as conn:
            limit = reg.setting(conn, "ukvi_missed_contact_points", 10)
            days = reg.setting(conn, "ukvi_report_working_days", 10)
            today_limit = eng.student_work_limit(conn, date.today())["message"]
        ttk.Label(tab, text=f"Today: {today_limit}", foreground='#1f4e79').pack(anchor='w')
        ttk.Label(tab, text=f"Students with an active Student-route visa who miss {limit} timetabled sessions "
                            f"in a row are flagged; the report is due {days} working days after detection.",
                  foreground='#555', wraplength=1000).pack(anchor='w', pady=(0, 6))
        self.ukvi_tree = _tree(tab, [("id", "#"), ("student", "Student"), ("name", "Name"), ("missed", "Missed"),
                                     ("last", "Last engaged"), ("due", "Report due"), ("status", "Status"),
                                     ("ref", "UKVI ref")], [40, 90, 180, 70, 100, 100, 120, 160])
        self.ukvi_tree.tag_configure('overdue', background='#ffebee')
        self._load_ukvi()

    def _load_ukvi(self):
        self.ukvi_tree.delete(*self.ukvi_tree.get_children())
        with closing(get_connection()) as conn:
            for a in eng.ukvi_alerts(conn, self.show_closed.get()):
                status = "OVERDUE" if a['overdue'] else a['status']
                self.ukvi_tree.insert('', 'end', iid=str(a['id']), values=(
                    a['id'], a['student_id'], a['name'] or '', a['consecutive_missed'],
                    a['last_engaged_on'] or 'never', a['report_due'], status, a['ukvi_reference'] or ''),
                    tags=('overdue',) if a['overdue'] else ())

    def _ukvi_term_time(self):
        """Is a date term time (20-hour work limit) or official vacation, per the
        published academic calendar?"""
        raw = simpledialog.askstring("Term time", "Date (YYYY-MM-DD):",
                                     initialvalue=date.today().isoformat(), parent=self.win)
        if not raw:
            return
        try:
            day = date.fromisoformat(raw.strip())
        except ValueError:
            messagebox.showwarning("Term time", "Enter a date like 2026-10-05.", parent=self.win)
            return
        with closing(get_connection()) as conn:
            result = eng.student_work_limit(conn, day)
        messagebox.showinfo("Term time", f"{day}: {result['message']}", parent=self.win)

    def _ukvi_scan(self):
        if self._run(lambda c: eng.ukvi_scan(c), lambda r: f"{len(r)} new alert(s)."):
            self._load_ukvi()

    def _ukvi_resolve(self):
        sel = self.ukvi_tree.selection()
        if not sel:
            return
        outcome = simpledialog.askstring("Resolve", "Outcome: " + ", ".join(eng.UKVI_OUTCOMES),
                                         initialvalue="reported", parent=self.win)
        if not outcome:
            return
        ref = simpledialog.askstring("Resolve", "UKVI reference / how and when reported:",
                                     parent=self.win) if outcome.strip() == "reported" else None
        notes = simpledialog.askstring("Resolve", "Notes:", parent=self.win)
        if self._run(lambda c: eng.resolve_ukvi_alert(c, int(sel[0]), outcome.strip(), self._user(), ref, notes),
                     "Alert resolved."):
            self._load_ukvi()

    # ── engagement ──────────────────────────────────────────────────────

    def _engagement(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        for label, cmd in (("Scan for non-engagement", self._eng_scan), ("Open case…", self._eng_open),
                           ("Advance stage", self._eng_advance), ("Resolve", self._eng_resolve),
                           ("History", self._eng_history), ("Confirm withdrawal", self._eng_withdraw)):
            ttk.Button(bar, text=label, command=cmd).pack(side='left', padx=(0, 6))
        ttk.Label(tab, text="Stages: " + " → ".join(s.replace('_', ' ') for s in eng.ENGAGEMENT_STAGES)
                  + ". Each stage has a response deadline; withdrawal is confirmed separately.",
                  foreground='#555').pack(anchor='w', pady=(0, 6))
        self.case_tree = _tree(tab, [("id", "#"), ("student", "Student"), ("name", "Name"), ("stage", "Stage"),
                                     ("opened", "Opened"), ("due", "Respond by"), ("reason", "Why")],
                               [40, 90, 170, 150, 95, 95, 330])
        self.case_tree.tag_configure('overdue', background='#fff3e0')
        self._load_cases()

    def _load_cases(self):
        self.case_tree.delete(*self.case_tree.get_children())
        with closing(get_connection()) as conn:
            for c in eng.cases(conn):
                self.case_tree.insert('', 'end', iid=str(c['id']), values=(
                    c['id'], c['student_id'], c['name'] or '', c['stage'].replace('_', ' '), c['opened_on'],
                    c['due_on'] or '—', c['opened_reason']), tags=('overdue',) if c['overdue'] else ())

    def _selected_case(self):
        sel = self.case_tree.selection()
        if not sel:
            messagebox.showwarning("Attendance Office", "Select a case.", parent=self.win)
            return None
        return int(sel[0])

    def _eng_scan(self):
        start, end = self._window()
        if self._run(lambda c: eng.engagement_scan(c, start, end, self._user()),
                     lambda r: f"{len(r)} case(s) opened."):
            self._load_cases()

    def _eng_open(self):
        sid = simpledialog.askstring("Open case", "Student ID:", parent=self.win)
        reason = sid and simpledialog.askstring("Open case", "Why?", parent=self.win)
        if reason and self._run(lambda c: eng.open_case(c, sid.strip(), reason, self._user()), "Case opened."):
            self._load_cases()

    def _eng_advance(self):
        cid = self._selected_case()
        notes = cid and simpledialog.askstring("Advance", "What happened at this stage?", parent=self.win)
        if notes and self._run(lambda c: eng.advance_case(c, cid, self._user(), notes),
                               lambda stage: f"Moved to {stage.replace('_', ' ')}."):
            self._load_cases()

    def _eng_resolve(self):
        cid = self._selected_case()
        reason = cid and simpledialog.askstring("Resolve", "Why is the case closing?", parent=self.win)
        if reason and self._run(lambda c: eng.resolve_case(c, cid, self._user(), reason), "Case resolved."):
            self._load_cases()

    def _eng_history(self):
        cid = self._selected_case()
        if not cid:
            return
        with closing(get_connection()) as conn:
            rows = eng.case_history(conn, cid)
        messagebox.showinfo("Case history", "\n".join(
            f"{str(h['changed_at'])[:16]}  {h['from_stage'] or 'opened'} → {h['to_stage']}  "
            f"({h['actor'] or '—'}): {h['notes'] or ''}" for h in rows) or "No history.", parent=self.win)

    def _eng_withdraw(self):
        cid = self._selected_case()
        if not cid:
            return
        reason = simpledialog.askstring("Confirm withdrawal",
                                        "This withdraws the student. Reason for the record:", parent=self.win)
        if not reason or not messagebox.askyesno("Confirm withdrawal", "Withdraw this student now?", parent=self.win):
            return
        try:
            eng.confirm_withdrawal(cid, self._user(), reason)
        except ValueError as e:
            messagebox.showwarning("Attendance Office", str(e), parent=self.win)
            return
        except Exception as e:
            messagebox.showerror("Attendance Office", f"Withdrawal failed: {e}", parent=self.win)
            return
        messagebox.showinfo("Attendance Office", "Student withdrawn and case closed.", parent=self.win)
        self._load_cases()

    # ── funding ─────────────────────────────────────────────────────────

    def _funding(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Term:").pack(side='left')
        with closing(get_connection()) as conn:
            terms = [r[0] for r in conn.execute("SELECT name FROM academic_terms ORDER BY start_date")]
        self.term_var = tk.StringVar(value=terms[-1] if terms else '')
        ttk.Combobox(bar, textvariable=self.term_var, values=terms, width=24, state='readonly').pack(side='left', padx=6)
        for label, cmd in (("Load", self._load_funding), ("Set status…", self._funding_set),
                           ("Confirm all shown", self._funding_confirm), ("Export CSV", self._funding_export)):
            ttk.Button(bar, text=label, command=cmd).pack(side='left', padx=(0, 6))
        ttk.Label(tab, text="Students to confirm as attending to the student finance body. Students in a "
                            "formal non-engagement case, or with no attendance this term, are suggested as "
                            "'held'.", foreground='#555', wraplength=1000).pack(anchor='w', pady=(0, 6))
        self.fund_tree = _tree(tab, [("student", "Student"), ("name", "Name"), ("pct", "Attendance %"),
                                     ("status", "Status"), ("why", "Why")], [100, 220, 100, 110, 400])

    def _load_funding(self):
        self.fund_tree.delete(*self.fund_tree.get_children())
        rows = self._run(lambda c: eng.funding_candidates(c, self.term_var.get()))
        for r in rows or []:
            self.fund_tree.insert('', 'end', iid=str(r['student_id']), values=(
                r['student_id'], r['name'], '—' if r['attendance_pct'] is None else r['attendance_pct'],
                r['suggested'], r['why']))

    def _funding_set(self):
        status = simpledialog.askstring("Status", "One of: " + ", ".join(eng.FUNDING_STATUSES), parent=self.win)
        if not status or status.strip() not in eng.FUNDING_STATUSES:
            return
        for iid in self.fund_tree.selection():
            values = list(self.fund_tree.item(iid)['values'])
            values[3], values[4] = status.strip(), f"set by {self._user()}"
            self.fund_tree.item(iid, values=values)

    def _funding_confirm(self):
        decisions = {iid: self.fund_tree.item(iid)['values'][3] for iid in self.fund_tree.get_children()}
        if decisions and self._run(lambda c: eng.confirm_funding(c, self.term_var.get(), decisions, self._user()),
                                   lambda n: f"{n} confirmation(s) recorded."):
            self._load_funding()

    def _funding_export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", parent=self.win,
                                            initialfile=f"funding_confirmations_{self.term_var.get()}.csv")
        if path:
            self._run(lambda c: eng.export_funding(c, self.term_var.get(), path), lambda n: f"{n} row(s) exported.")
