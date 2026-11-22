"""Staff HR compliance windows: equality monitoring (and the person's own
declaration), gender pay gap, HESA staff return and HR retention.

Opened from the Reports hub (``reports_gui.py``). Each window asks
``domain/staff_hr/access`` through the domain modules, which refuse on
their own too — a button left enabled by mistake still cannot leak.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

from education_system.systems.university.domains.staff.domain.staff_hr import (
    equality,
    hesa_staff,
    pay_gap,
    retention,
)
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import _access


def _window(parent, title: str, size: str = "900x650") -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(size)
    win.minsize(700, 450)
    return win


def _text(parent) -> scrolledtext.ScrolledText:
    box = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=('Courier New', 10))
    box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
    return box


def _show(box, lines) -> None:
    box.config(state=tk.NORMAL)
    box.delete('1.0', tk.END)
    box.insert(tk.END, "\n".join(lines) if isinstance(lines, (list, tuple)) else str(lines))
    box.config(state=tk.DISABLED)


def _guard(win, fn):
    """Run ``fn``; show refusals and errors in a dialog parented to ``win``."""
    try:
        return fn()
    except PermissionError as e:
        messagebox.showwarning("Not permitted", str(e), parent=win)
    except (ValueError, LookupError) as e:
        messagebox.showerror("Cannot do that", str(e), parent=win)
    except Exception as e:  # noqa: BLE001 - show, don't crash the window
        messagebox.showerror("Error", f"{type(e).__name__}: {e}", parent=win)
    return None


# ── my equality information ─────────────────────────────────────────────


class MyEqualityWindow:
    """The signed-in person's own, voluntary declaration."""

    def __init__(self, parent, gui):
        self.gui = gui
        self.actor = _access.actor(gui)
        self.win = _window(parent, "My equality information", "760x560")
        ttk.Label(self.win, wraplength=700, justify=tk.LEFT, text=(
            "Answering is voluntary. Your answers are kept apart from your personnel record; "
            "HR only ever sees them as counts, with small groups hidden. Leave a question "
            "blank or choose 'Prefer not to say' if you would rather not answer.")).pack(
            fill=tk.X, padx=10, pady=10)
        bar = ttk.Frame(self.win)
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Button(bar, text="Save", command=self._save).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bar, text="Withdraw all my answers", command=self._withdraw).pack(side=tk.LEFT)
        ttk.Button(bar, text="Close", command=self.win.destroy).pack(side=tk.RIGHT)
        form = ttk.Frame(self.win)
        form.pack(fill=tk.BOTH, expand=True, padx=10)
        current = _guard(self.win, lambda: equality.get_own(self.actor)) or {}
        self.vars = {}
        for row, (field, (question, answers)) in enumerate(equality.CATEGORIES.items()):
            ttk.Label(form, text=question, wraplength=300, justify=tk.LEFT).grid(
                row=row, column=0, sticky=tk.W, pady=4)
            var = tk.StringVar(value=current.get(field) or '')
            ttk.Combobox(form, textvariable=var, values=('',) + tuple(answers), state='readonly',
                         width=52).grid(row=row, column=1, sticky=tk.W, padx=8, pady=4)
            self.vars[field] = var

    def _save(self):
        answers = {f: v.get() for f, v in self.vars.items()}
        if _guard(self.win, lambda: equality.declare(self.actor, **answers)) is not None:
            messagebox.showinfo("Saved", "Thank you — your answers are saved.", parent=self.win)

    def _withdraw(self):
        if not messagebox.askyesno("Withdraw", "Delete all your equality answers?", parent=self.win):
            return
        _guard(self.win, lambda: equality.withdraw(self.actor))
        for var in self.vars.values():
            var.set('')


# ── equality monitoring (HR, counts only) ───────────────────────────────


class EqualityReportWindow:
    def __init__(self, parent, gui):
        self.actor = _access.actor(gui)
        self.win = _window(parent, "Equality monitoring")
        bar = ttk.Frame(self.win)
        bar.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(bar, text="Break down by:").pack(side=tk.LEFT)
        self.group = tk.StringVar(value='(none)')
        ttk.Combobox(bar, textvariable=self.group, state='readonly', width=18,
                     values=('(none)',) + equality.GROUP_BY).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Run", command=self._run).pack(side=tk.LEFT)
        admin = _access.can(gui, 'hr_admin')
        ttk.Button(bar, text="Smallest group...", command=self._min_group,
                   state=tk.NORMAL if admin else tk.DISABLED).pack(side=tk.RIGHT)
        self.out = _text(self.win)
        self._run()

    def _run(self):
        group = None if self.group.get() == '(none)' else self.group.get()
        report = _guard(self.win, lambda: equality.aggregate(self.actor, group_by=group))
        if report:
            _show(self.out, equality.report_lines(report))

    def _min_group(self):
        value = simpledialog.askinteger("Smallest group", "Hide groups smaller than:",
                                        parent=self.win, minvalue=2, maxvalue=100,
                                        initialvalue=equality.min_group())
        if value and _guard(self.win, lambda: equality.set_min_group(self.actor, value)) is None:
            self._run()


# ── gender pay gap ──────────────────────────────────────────────────────


class PayGapWindow:
    def __init__(self, parent, gui):
        self.actor = _access.actor(gui)
        self.win = _window(parent, "Gender pay gap")
        bar = ttk.Frame(self.win)
        bar.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(bar, text="Snapshot date:").pack(side=tk.LEFT)
        self.snapshot = tk.StringVar(value=pay_gap.snapshot_for().isoformat())
        ttk.Entry(bar, textvariable=self.snapshot, width=12).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Run", command=self._run).pack(side=tk.LEFT)
        self.out = _text(self.win)
        self._run()

    def _run(self):
        r = _guard(self.win, lambda: pay_gap.gender_pay_gap(self.actor, self.snapshot.get().strip()
                                                            or None))
        if r:
            _show(self.out, pay_gap.report_lines(r))


# ── HESA staff return ───────────────────────────────────────────────────


class HesaStaffWindow:
    def __init__(self, parent, gui):
        self.actor = _access.actor(gui)
        self.win = _window(parent, "HESA staff return", "1000x680")
        admin = _access.can(gui, 'hr_admin')
        bar = ttk.Frame(self.win)
        bar.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(bar, text="Academic year:").pack(side=tk.LEFT)
        self.year = tk.StringVar(value=hesa_staff.year_bounds()[0])
        ttk.Entry(bar, textvariable=self.year, width=9).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Validate", command=self._validate).pack(side=tk.LEFT)
        ttk.Button(bar, text="Fix personal details...", command=self._fix).pack(side=tk.LEFT, padx=4)
        state = tk.NORMAL if admin else tk.DISABLED
        ttk.Button(bar, text="Generate return", command=self._generate, state=state).pack(
            side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Export XML...", command=self._export, state=state).pack(side=tk.LEFT)
        ttk.Button(bar, text="UKPRN...", command=self._ukprn, state=state).pack(side=tk.RIGHT)
        cols = ('id', 'year', 'status', 'by', 'created')
        self.returns = ttk.Treeview(self.win, columns=cols, show='headings', height=5)
        for c, w in zip(cols, (60, 90, 100, 120, 170)):
            self.returns.heading(c, text=c.title())
            self.returns.column(c, width=w)
        self.returns.pack(fill=tk.X, padx=10)
        self.out = _text(self.win)
        self._load_returns()
        self._validate()

    def _load_returns(self):
        self.returns.delete(*self.returns.get_children())
        for r in _guard(self.win, lambda: hesa_staff.list_returns(self.actor)) or []:
            self.returns.insert('', tk.END, values=(r['id'], r['academic_year'], r['status'],
                                                    r['created_by'] or '', r['created_at'] or ''))

    def _validate(self):
        v = _guard(self.win, lambda: hesa_staff.validate(self.actor, self.year.get().strip() or None))
        if not v:
            return
        lines = [f"Reporting year {v['academic_year']} ({v['start']} to {v['end']})",
                 f"Staff to return: {v['people']}   contracts: {v['contracts']}",
                 f"No equality declaration (returned as 'not available'): {v['without_declaration']}",
                 ""]
        if v['valid']:
            lines.append("No missing data.")
        else:
            lines.append(f"{len(v['issues'])} staff record(s) with missing data:")
            for issue in v['issues']:
                lines.append(f"  {issue['employee_id'] or '-':<10}{issue['username']}")
                lines += [f"      - {m}" for m in issue['missing']]
        _show(self.out, lines)

    def _fix(self):
        who = simpledialog.askstring("Personal details", "Username or employee number:",
                                     parent=self.win)
        if not who:
            return
        dob = simpledialog.askstring("Personal details", "Date of birth (YYYY-MM-DD, blank to keep):",
                                     parent=self.win) or None
        nation = simpledialog.askstring("Personal details", "Nationality (blank to keep):",
                                        parent=self.win) or None
        _guard(self.win, lambda: hesa_staff.set_personal_details(self.actor, who.strip(), dob, nation))
        self._validate()

    def _generate(self):
        year = self.year.get().strip() or None
        v = _guard(self.win, lambda: hesa_staff.validate(self.actor, year))
        if v is None:
            return
        allow = False
        if not v['valid']:
            allow = messagebox.askyesno(
                "Missing data", f"{len(v['issues'])} record(s) have missing data. Generate a draft "
                "return with the problems listed in its log?", parent=self.win)
            if not allow:
                return
        r = _guard(self.win, lambda: hesa_staff.create_return(self.actor, year, allow_errors=allow))
        if r:
            messagebox.showinfo("Generated", f"Staff return {r['return_id']} ({r['academic_year']}) "
                                f"saved as {r['status']}."
                                + ("" if r['ukprn_set'] else "\nSet the UKPRN before submitting."),
                                parent=self.win)
            self._load_returns()

    def _export(self):
        sel = self.returns.selection()
        if not sel:
            messagebox.showinfo("Export", "Select a return first.", parent=self.win)
            return
        return_id = self.returns.item(sel[0], 'values')[0]
        xml = _guard(self.win, lambda: hesa_staff.export_xml(self.actor, int(return_id)))
        if xml is None:
            return
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension='.xml',
                                            initialfile=f"hesa_staff_{return_id}.xml",
                                            filetypes=[('XML', '*.xml')])
        if path:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(xml)

    def _ukprn(self):
        value = simpledialog.askstring("UKPRN", "UK Provider Reference Number (8 digits):",
                                       parent=self.win, initialvalue=equality.setting('ukprn', ''))
        if value is None:
            return
        if value and not (value.isdigit() and len(value) == 8):
            messagebox.showerror("UKPRN", "A UKPRN is 8 digits.", parent=self.win)
            return
        _guard(self.win, lambda: equality.set_setting(self.actor, 'ukprn', value))


# ── HR retention ────────────────────────────────────────────────────────


class RetentionWindow:
    def __init__(self, parent, gui):
        self.actor = _access.actor(gui)
        self.win = _window(parent, "HR record retention", "1000x700")
        bar = ttk.Frame(self.win)
        bar.pack(fill=tk.X, padx=10, pady=10)
        for label, cmd in (("Preview", self._preview), ("Run now", self._run),
                           ("Edit policy...", self._edit), ("Holds", self._holds),
                           ("Place hold...", self._hold), ("Release hold...", self._release),
                           ("Erase a leaver...", self._erase), ("Recent runs", self._runs)):
            ttk.Button(bar, text=label, command=cmd).pack(side=tk.LEFT, padx=2)
        cols = ('record_type', 'label', 'keep_months', 'trigger', 'action', 'enabled')
        self.tree = ttk.Treeview(self.win, columns=cols, show='headings', height=8)
        for c, w in zip(cols, (150, 220, 90, 160, 90, 70)):
            self.tree.heading(c, text=c.replace('_', ' ').title())
            self.tree.column(c, width=w)
        self.tree.pack(fill=tk.X, padx=10)
        self.out = _text(self.win)
        self._load()
        self._preview()

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        for p in retention.policies():
            self.tree.insert('', tk.END, iid=p['record_type'], values=(
                p['record_type'], p['label'], p['keep_months'], p['trigger'], p['action'],
                'yes' if p['enabled'] else 'no'))

    def _preview(self):
        plan = _guard(self.win, lambda: retention.preview(self.actor))
        if plan is None:
            return
        lines = [f"{'Record':<24}{'Table':<34}{'Action':<11}{'Due':>6}{'People':>8}", "-" * 83]
        for p in plan:
            lines.append(f"{p['record_type']:<24}{p['table'][:33]:<34}{p['action']:<11}"
                         f"{p['due']:>6}{p['people']:>8}{'' if p.get('enabled', True) else '  (off)'}")
        _show(self.out, lines or ["Nothing is due."])

    def _run(self):
        if not messagebox.askyesno("Run retention", "Delete or anonymise every record that is now "
                                   "due? This cannot be undone.", parent=self.win):
            return
        done = _guard(self.win, lambda: retention.run(self.actor))
        if done is not None:
            _show(self.out, ["Done:"] + [f"  {d['record_type']:<24}{d['table']:<34}{d['action']:<11}"
                                         f"{d['rows']:>6}" for d in done])

    def _edit(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Edit policy", "Select a policy first.", parent=self.win)
            return
        policy = {p['record_type']: p for p in retention.policies()}[sel[0]]
        months = simpledialog.askinteger("Keep for", f"{policy['label']}: months to keep "
                                         f"({policy['trigger']})", parent=self.win, minvalue=0,
                                         initialvalue=policy['keep_months'])
        if months is None:
            return
        action = simpledialog.askstring("Then", "anonymise or delete:", parent=self.win,
                                        initialvalue=policy['action'])
        if action is None:
            return
        enabled = messagebox.askyesno("Enabled", "Apply this policy automatically?", parent=self.win)
        _guard(self.win, lambda: retention.update_policy(self.actor, sel[0], months,
                                                         action.strip().lower(), enabled))
        self._load()

    def _holds(self):
        rows = _guard(self.win, lambda: retention.list_holds(self.actor))
        if rows is None:
            return
        _show(self.out, ["Active holds:"] + [f"  #{h['hold_id']:<5}{h['username']:<20}"
                                             f"{h['placed_at']:<21}{h['reason']}" for h in rows]
              if rows else ["No active holds."])

    def _hold(self):
        who = simpledialog.askstring("Place hold", "Username:", parent=self.win)
        if not who:
            return
        reason = simpledialog.askstring("Place hold", "Reason:", parent=self.win)
        if _guard(self.win, lambda: retention.place_hold(self.actor, who.strip(), reason or '')):
            self._holds()

    def _release(self):
        hold = simpledialog.askinteger("Release hold", "Hold number:", parent=self.win)
        if hold is not None:
            _guard(self.win, lambda: retention.release_hold(self.actor, hold))
            self._holds()

    def _erase(self):
        who = simpledialog.askstring("Erase a leaver", "Username of the leaver:", parent=self.win)
        if not who:
            return
        if not messagebox.askyesno("Erase", f"Erase {who}'s HR data now? Payroll and right-to-work "
                                   "records still under a legal duty are kept.", parent=self.win):
            return
        r = _guard(self.win, lambda: retention.erase_leaver(self.actor, who.strip()))
        if r:
            lines = [f"Erased. The person is now '{r['alias']}' in HR records.", "", "Done:"]
            lines += [f"  {d['record_type']}: {d['rows']} {d['table']} row(s) {d['action']}d"
                      for d in r['done']] or ["  (no case or absence records)"]
            if r['kept']:
                lines += ["", "Kept (legal duty):"] + [
                    f"  {k['record_type']}: {k['rows']} {k['table']} row(s) until {k['until']}"
                    for k in r['kept']]
            _show(self.out, lines)

    def _runs(self):
        rows = _guard(self.win, lambda: retention.recent_runs(self.actor))
        if rows is not None:
            _show(self.out, [f"{r['at']:<21}{r['actor'] or '':<18}{r['record_type']:<24}"
                             f"{r['table_name'][:30]:<31}{r['action']:<10}{r['rows_affected']:>5}"
                             for r in rows] or ["No runs yet."])


__all__ = ['EqualityReportWindow', 'HesaStaffWindow', 'MyEqualityWindow', 'PayGapWindow',
           'RetentionWindow']
