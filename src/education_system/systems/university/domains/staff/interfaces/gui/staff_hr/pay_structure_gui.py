"""Pay Structure and Pensions tabs of the Payroll window.

Pay Structure (payroll only): the pay spine by pay year, grades, job →
grade, a contract's pay terms, the annual increment and pay awards.
Pensions: everyone sees their own membership and may opt out; payroll
also edits scheme rates and tiers and enrols people.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from education_system.systems.university.domains.staff.domain.staff_hr import (
    pay_structure,
    pensions,
)
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import _access
from education_system.systems.university.infrastructure.i18n import get_text as _t


def _tree(parent, columns, widths=None, height=8):
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
    tree = ttk.Treeview(frame, columns=columns, show='headings', height=height,
                        yscrollcommand=scroll.set)
    scroll.config(command=tree.yview)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=(widths or {}).get(col, 110))
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    return tree


def _fill(tree, rows):
    tree.delete(*tree.get_children())
    for values in rows:
        tree.insert('', tk.END, values=values)


def _entries(parent, fields, width=14):
    """A grid of labelled entries: ``fields`` = [(key, label, default)]."""
    out = {}
    for i, (key, label, default) in enumerate(fields):
        row, col = divmod(i, 4)
        ttk.Label(parent, text=label).grid(row=row, column=col * 2, sticky='e', padx=5, pady=4)
        entry = ttk.Entry(parent, width=width)
        if default:
            entry.insert(0, default)
        entry.grid(row=row, column=col * 2 + 1, sticky='w', padx=5, pady=4)
        out[key] = entry
    return out


def _money(value):
    return '-' if value is None else f"£{float(value):,.2f}"


class PayStructureTabsMixin:
    """Mixed into ``PayrollGUI`` (needs ``self.notebook``, ``self.root``,
    ``self.auth``)."""

    def _ps_error(self, exc):
        messagebox.showerror(_t('gui.staff.staff_hr.payroll.dialogs.error', default="Error"),
                             str(exc), parent=self.root)

    def _ps_ok(self, text):
        messagebox.showinfo(_t('gui.staff.staff_hr.payroll.dialogs.success', default="Success"),
                            text, parent=self.root)

    def _ps_call(self, fn, *args, done=None, after=None, **kwargs):
        try:
            result = fn(*args, **kwargs)
        except (ValueError, PermissionError) as exc:
            self._ps_error(exc)
            return None
        if done:
            self._ps_ok(done(result) if callable(done) else done)
        if after:
            after()
        return result

    # ==================== PAY STRUCTURE (PAYROLL) ====================

    def _create_pay_structure_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.payroll.tabs.pay_structure',
                                       default="Pay Structure"))
        inner = ttk.Notebook(tab)
        inner.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        for title, build in (("Pay Spine", self._ps_spine), ("Grades", self._ps_grades),
                             ("Jobs", self._ps_jobs), ("Contract Pay", self._ps_contract),
                             ("Increments", self._ps_increments), ("Pay Award", self._ps_award)):
            frame = ttk.Frame(inner)
            inner.add(frame, text=title)
            build(frame)

    # -- spine
    def _ps_spine(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(bar, text="Pay year:").pack(side=tk.LEFT)
        self.ps_year = ttk.Combobox(bar, width=10)
        self.ps_year.pack(side=tk.LEFT, padx=5)
        self.ps_year.bind('<<ComboboxSelected>>', lambda e: self._ps_load_spine())
        ttk.Button(bar, text="Refresh", command=self._ps_load_spine).pack(side=tk.LEFT, padx=5)
        form = ttk.LabelFrame(tab, text="Set a point's value", padding=8)
        form.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        self.ps_spine_form = _entries(form, [('point', 'Point:', ''), ('value', 'Annual value:', ''),
                                             ('year', 'Pay year:', pay_structure.current_pay_year()),
                                             ('label', 'Label:', '')])
        buttons = ttk.Frame(form)
        buttons.grid(row=1, column=0, columnspan=8, pady=5)
        ttk.Button(buttons, text="Save Value", command=self._ps_save_spine).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text="Delete Selected Point",
                   command=self._ps_delete_point).pack(side=tk.LEFT, padx=5)
        self.ps_spine_tree = _tree(tab, ('Point', 'Label', 'Annual Value', 'From Year'))
        self._ps_load_spine()

    def _ps_load_spine(self):
        years = pay_structure.pay_years()
        current = pay_structure.current_pay_year()
        self.ps_year['values'] = sorted(set(years) | {current}, reverse=True)
        year = self.ps_year.get() or current
        self.ps_year.set(year)
        _fill(self.ps_spine_tree, [(r['point'], r['label'], _money(r['annual_value']),
                                    r['value_from_year'] or '-')
                                   for r in pay_structure.list_spine(year)])

    def _ps_save_spine(self):
        f = self.ps_spine_form
        try:
            point, value = int(f['point'].get()), float(f['value'].get())
        except ValueError:
            self._ps_error("Point must be a whole number and value a number")
            return
        self._ps_call(pay_structure.set_spine_value, self.auth, point, f['year'].get().strip(),
                      value, f['label'].get().strip() or None,
                      done="Spine value saved", after=self._ps_load_spine)

    def _ps_delete_point(self):
        sel = self.ps_spine_tree.selection()
        if not sel:
            return
        point = self.ps_spine_tree.item(sel[0])['values'][0]
        if messagebox.askyesno("Confirm", f"Delete spine point {point}?", parent=self.root):
            self._ps_call(pay_structure.delete_spine_point, self.auth, point,
                          done="Point deleted", after=self._ps_load_spine)

    # -- grades
    def _ps_grades(self, tab):
        form = ttk.LabelFrame(tab, text="Add or change a grade", padding=8)
        form.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        self.ps_grade_form = _entries(form, [('code', 'Code:', ''), ('name', 'Name:', ''),
                                             ('min', 'Bottom point:', ''), ('max', 'Top point:', ''),
                                             ('contrib', 'Top contribution pt:', '')])
        self.ps_grade_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Active", variable=self.ps_grade_active).grid(
            row=1, column=2, columnspan=2, sticky='w')
        ttk.Button(form, text="Save Grade", command=self._ps_save_grade).grid(
            row=1, column=4, columnspan=2, pady=5)
        self.ps_grade_tree = _tree(tab, ('Code', 'Name', 'Bottom', 'Top', 'Contribution Top',
                                         'Active'))
        self.ps_grade_tree.bind('<<TreeviewSelect>>', self._ps_pick_grade)
        self._ps_load_grades()

    def _ps_load_grades(self):
        rows = pay_structure.list_grades(include_inactive=True)
        _fill(self.ps_grade_tree, [(g['grade_code'], g['name'], g['min_point'], g['max_point'],
                                    g['contribution_max_point'] or '-',
                                    'Yes' if g['is_active'] else 'No') for g in rows])
        codes = [g['grade_code'] for g in rows if g['is_active']]
        for combo in ('ps_job_grade', 'ps_c_grade'):
            if hasattr(self, combo):
                getattr(self, combo)['values'] = [''] + codes

    def _ps_pick_grade(self, _event=None):
        sel = self.ps_grade_tree.selection()
        if not sel:
            return
        values = self.ps_grade_tree.item(sel[0])['values']
        for key, value in zip(('code', 'name', 'min', 'max', 'contrib'), values):
            self.ps_grade_form[key].delete(0, tk.END)
            if value != '-':
                self.ps_grade_form[key].insert(0, value)
        self.ps_grade_active.set(values[5] == 'Yes')

    def _ps_save_grade(self):
        f = self.ps_grade_form
        try:
            low, high = int(f['min'].get()), int(f['max'].get())
            contrib = int(f['contrib'].get()) if f['contrib'].get().strip() else None
        except ValueError:
            self._ps_error("Points must be whole numbers")
            return
        self._ps_call(pay_structure.save_grade, self.auth, f['code'].get().strip(),
                      f['name'].get().strip(), low, high, contrib, self.ps_grade_active.get(),
                      done="Grade saved", after=self._ps_load_grades)

    # -- jobs
    def _ps_jobs(self, tab):
        form = ttk.LabelFrame(tab, text="Put a job title on a grade", padding=8)
        form.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Label(form, text="Job title:").grid(row=0, column=0, padx=5)
        self.ps_job_title = ttk.Entry(form, width=30)
        self.ps_job_title.grid(row=0, column=1, padx=5)
        ttk.Label(form, text="Grade:").grid(row=0, column=2, padx=5)
        self.ps_job_grade = ttk.Combobox(form, width=12, state='readonly')
        self.ps_job_grade.grid(row=0, column=3, padx=5)
        ttk.Button(form, text="Map Job", command=self._ps_map_job).grid(row=0, column=4, padx=5)
        ttk.Button(form, text="Remove Selected",
                   command=self._ps_unmap_job).grid(row=0, column=5, padx=5)
        self.ps_job_tree = _tree(tab, ('Job Title', 'Grade', 'Grade Name'),
                                 {'Job Title': 260, 'Grade Name': 200})
        self._ps_load_jobs()
        self._ps_load_grades()

    def _ps_load_jobs(self):
        _fill(self.ps_job_tree, [(j['job_title'], j['grade_code'], j['grade_name'] or '')
                                 for j in pay_structure.list_job_grades()])

    def _ps_map_job(self):
        self._ps_call(pay_structure.map_job, self.auth, self.ps_job_title.get(),
                      self.ps_job_grade.get() or None, done="Job mapped", after=self._ps_load_jobs)

    def _ps_unmap_job(self):
        sel = self.ps_job_tree.selection()
        if sel:
            title = self.ps_job_tree.item(sel[0])['values'][0]
            self._ps_call(pay_structure.map_job, self.auth, title, None,
                          done="Mapping removed", after=self._ps_load_jobs)

    # -- contract pay
    def _ps_contract(self, tab):
        form = ttk.LabelFrame(tab, text="A contract's pay terms", padding=8)
        form.pack(fill=tk.X, padx=10, pady=5)
        self.ps_c_form = _entries(form, [('contract', 'Contract ID:', ''), ('point', 'Spine point:', ''),
                                         ('fte', 'FTE (0-1):', ''), ('override', 'Override salary:', ''),
                                         ('reason', 'Override reason:', '')])
        ttk.Label(form, text="Grade:").grid(row=1, column=2, sticky='e', padx=5)
        self.ps_c_grade = ttk.Combobox(form, width=12, state='readonly')
        self.ps_c_grade.grid(row=1, column=3, sticky='w', padx=5)
        ttk.Label(form, text="Pension:").grid(row=1, column=4, sticky='e', padx=5)
        self.ps_c_scheme = ttk.Combobox(form, width=10, state='readonly',
                                        values=[''] + [s['scheme_code'] for s in pensions.list_schemes()])
        self.ps_c_scheme.grid(row=1, column=5, sticky='w', padx=5)
        self.ps_c_clear = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Clear override", variable=self.ps_c_clear).grid(
            row=1, column=6, columnspan=2, sticky='w')
        ttk.Button(form, text="Apply Pay Terms", command=self._ps_assign).grid(
            row=2, column=0, columnspan=8, pady=6)
        self.ps_c_result = ttk.Label(tab, text="Blank fields are left as they are. Salary = spine "
                                               "value for the pay year (or the override) x FTE.")
        self.ps_c_result.pack(fill=tk.X, padx=12, pady=8)
        self._ps_load_grades()

    def _ps_assign(self):
        f = self.ps_c_form
        try:
            contract_id = int(f['contract'].get())
            point = int(f['point'].get()) if f['point'].get().strip() else None
            fte = float(f['fte'].get()) if f['fte'].get().strip() else None
            override = float(f['override'].get()) if f['override'].get().strip() else None
        except ValueError:
            self._ps_error("Contract ID and point are whole numbers; FTE and salary are numbers")
            return
        result = self._ps_call(pay_structure.assign, self.auth, contract_id,
                               grade_code=self.ps_c_grade.get() or None, spine_point=point, fte=fte,
                               pension_scheme=self.ps_c_scheme.get() or None,
                               salary_override=override,
                               override_reason=f['reason'].get().strip() or None,
                               clear_override=self.ps_c_clear.get())
        if result:
            self.ps_c_result.config(
                text=f"Contract {contract_id}: full-time {_money(result['full_time'])} "
                     f"({result['source']}), FTE {result['fte']}, "
                     f"actual {_money(result['full_time'] * result['fte'])} a year")

    # -- increments
    def _ps_increments(self, tab):
        settings = pay_structure.get_settings()
        form = ttk.LabelFrame(tab, text="Annual increment", padding=8)
        form.pack(fill=tk.X, padx=10, pady=5)
        self.ps_inc_form = _entries(form, [
            ('mmdd', 'Increment date (MM-DD):', settings.get('increment_date', '08-01')),
            ('months', 'Qualifying months:', settings.get('increment_min_service_months', '6')),
            ('effective', 'Effective date:', pay_structure.last_increment_date(
                None, settings.get('increment_date', '08-01')).isoformat())])
        buttons = ttk.Frame(form)
        buttons.grid(row=1, column=0, columnspan=8, pady=5)
        ttk.Button(buttons, text="Save Settings", command=self._ps_save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text="Preview Increment", command=self._ps_preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text="Run Increment", command=self._ps_run_increment).pack(side=tk.LEFT, padx=5)
        ttk.Label(tab, text="Moves / holds").pack(anchor='w', padx=12)
        self.ps_move_tree = _tree(tab, ('Contract', 'Person', 'From', 'To', 'Outcome', 'Reason'),
                                  {'Reason': 220}, height=7)
        ttk.Label(tab, text="Past runs (select to see its moves)").pack(anchor='w', padx=12)
        self.ps_run_tree = _tree(tab, ('Run', 'Effective', 'Pay Year', 'Moved', 'Held', 'By'),
                                 height=4)
        self.ps_run_tree.bind('<<TreeviewSelect>>', self._ps_pick_run)
        self._ps_load_runs()

    def _ps_load_runs(self):
        try:
            runs = pay_structure.increment_runs(self.auth)
        except PermissionError:
            runs = []
        _fill(self.ps_run_tree, [(r['run_id'], r['effective_date'], r['pay_year'], r['moved'],
                                  r['held'], r['run_by']) for r in runs])

    def _ps_show_moves(self, moves):
        _fill(self.ps_move_tree, [(m['contract_id'], m['user_id'], m['from_point'], m['to_point'],
                                   m['outcome'], m['reason']) for m in moves])

    def _ps_pick_run(self, _event=None):
        sel = self.ps_run_tree.selection()
        if sel:
            moves = self._ps_call(pay_structure.increment_moves, self.auth,
                                  self.ps_run_tree.item(sel[0])['values'][0])
            self._ps_show_moves(moves or [])

    def _ps_save_settings(self):
        f = self.ps_inc_form
        try:
            pay_structure.set_setting(self.auth, 'increment_date', f['mmdd'].get())
        except (ValueError, PermissionError) as exc:
            self._ps_error(exc)
            return
        self._ps_call(pay_structure.set_setting, self.auth, 'increment_min_service_months',
                      f['months'].get(), done="Settings saved")

    def _ps_preview(self):
        plan = self._ps_call(pay_structure.preview_increments, self.auth,
                             self.ps_inc_form['effective'].get().strip())
        if plan is not None:
            self._ps_show_moves(plan)

    def _ps_run_increment(self):
        effective = self.ps_inc_form['effective'].get().strip()
        if not messagebox.askyesno("Confirm", f"Apply the annual increment effective {effective}?",
                                   parent=self.root):
            return
        self._ps_call(pay_structure.run_increments, self.auth, effective,
                      done=lambda r: ("Already run for that date" if r['already_run'] else
                                      f"{r['moved']} moved, {r['held']} held"),
                      after=self._ps_load_runs)

    # -- pay award
    def _ps_award(self, tab):
        form = ttk.LabelFrame(tab, text="Pay award (new pay-year spine values)", padding=8)
        form.pack(fill=tk.X, padx=10, pady=5)
        current = pay_structure.current_pay_year()
        start = int(current[:4]) + 1
        self.ps_award_form = _entries(form, [
            ('year', 'New pay year:', f"{start}/{(start + 1) % 100:02d}"),
            ('pct', 'Uplift %:', ''), ('minimum', 'Minimum £:', '0'),
            ('source', 'From pay year:', ''), ('notes', 'Notes:', '')])
        ttk.Button(form, text="Apply Pay Award", command=self._ps_apply_award).grid(
            row=2, column=0, columnspan=8, pady=6)
        self.ps_award_tree = _tree(tab, ('Pay Year', 'From', 'Uplift %', 'Minimum', 'Points',
                                         'By', 'Applied'))
        self._ps_load_awards()

    def _ps_load_awards(self):
        _fill(self.ps_award_tree, [(a['pay_year'], a['from_pay_year'], a['uplift_percent'],
                                    _money(a['minimum_uplift']), a['points_updated'],
                                    a['applied_by'], a['applied_at'])
                                   for a in pay_structure.list_pay_awards()])

    def _ps_apply_award(self):
        f = self.ps_award_form
        try:
            pct, minimum = float(f['pct'].get()), float(f['minimum'].get() or 0)
        except ValueError:
            self._ps_error("Uplift and minimum are numbers")
            return
        if not messagebox.askyesno("Confirm", f"Apply a {pct}% pay award for {f['year'].get()}?",
                                   parent=self.root):
            return
        self._ps_call(pay_structure.apply_pay_award, self.auth, f['year'].get().strip(), pct,
                      f['source'].get().strip() or None, minimum, f['notes'].get().strip() or None,
                      done=lambda r: f"{r['points_updated']} points set for {r['pay_year']}; "
                                     f"{r['contracts_resynced']} salaries updated",
                      after=self._ps_load_awards)

    # ==================== PENSIONS ====================

    def _create_pensions_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.payroll.tabs.pensions', default="Pensions"))
        inner = ttk.Notebook(tab)
        inner.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        frame = ttk.Frame(inner)
        inner.add(frame, text="My Pension")
        self._pn_mine(frame)
        if _access.can(self, 'payroll'):
            for title, build in (("Schemes", self._pn_schemes), ("Members", self._pn_members)):
                frame = ttk.Frame(inner)
                inner.add(frame, text=title)
                build(frame)

    def _pn_mine(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=8)
        ttk.Label(bar, text="Opt out from:").pack(side=tk.LEFT)
        self.pn_out_date = ttk.Entry(bar, width=12)
        self.pn_out_date.insert(0, date.today().isoformat())
        self.pn_out_date.pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="Opt Out of My Pension", command=self._pn_opt_out_me).pack(side=tk.LEFT, padx=5)
        self.pn_mine_tree = _tree(tab, ('Scheme', 'Name', 'Joined', 'Left', 'Reason'),
                                  {'Name': 240, 'Reason': 200})
        self._pn_load_mine()

    def _pn_load_mine(self):
        rows = self._ps_call(pensions.memberships, self.auth, _access.user_key(self)) or []
        _fill(self.pn_mine_tree, [(m['scheme_code'], m['scheme_name'] or '', m['joined_on'],
                                   m['opted_out_on'] or '-', m['opt_out_reason'] or '')
                                  for m in rows])

    def _pn_opt_out_me(self):
        if not messagebox.askyesno("Confirm", "Leave your pension scheme? You lose your employer's "
                                              "contributions from that date.", parent=self.root):
            return
        done = self._ps_call(pensions.opt_out, self.auth, _access.user_key(self),
                             self.pn_out_date.get().strip(), 'opted out by member')
        if done is False:
            self._ps_error("You are not in a pension scheme")
        elif done:
            self._ps_ok("You have opted out")
        self._pn_load_mine()

    def _pn_schemes(self, tab):
        form = ttk.LabelFrame(tab, text="Scheme rates (percentages)", padding=8)
        form.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        self.pn_form = _entries(form, [('code', 'Code:', ''), ('name', 'Name:', ''),
                                       ('ee', 'Employee %:', ''), ('er', 'Employer %:', '')])
        ttk.Label(form, text="Tier basis:").grid(row=1, column=0, sticky='e', padx=5)
        self.pn_basis = ttk.Combobox(form, values=['actual', 'fte'], width=8, state='readonly')
        self.pn_basis.grid(row=1, column=1, sticky='w', padx=5)
        self.pn_tiered = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Tiered", variable=self.pn_tiered).grid(row=1, column=2, sticky='w')
        ttk.Label(form, text="Tiers (lower-upper:rate; ...):").grid(row=2, column=0, sticky='e', padx=5)
        self.pn_tiers = ttk.Entry(form, width=90)
        self.pn_tiers.grid(row=2, column=1, columnspan=7, sticky='w', padx=5, pady=4)
        buttons = ttk.Frame(form)
        buttons.grid(row=3, column=0, columnspan=8, pady=5)
        ttk.Button(buttons, text="Save Scheme", command=self._pn_save_scheme).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text="Save Tiers", command=self._pn_save_tiers).pack(side=tk.LEFT, padx=5)
        self.pn_scheme_tree = _tree(tab, ('Code', 'Name', 'Employee %', 'Employer %', 'Tiered',
                                          'Basis', 'Active'), {'Name': 260}, height=6)
        self.pn_scheme_tree.bind('<<TreeviewSelect>>', self._pn_pick_scheme)
        self._pn_load_schemes()

    def _pn_load_schemes(self):
        self._pn_scheme_rows = {s['scheme_code']: s for s in pensions.list_schemes(True)}
        _fill(self.pn_scheme_tree, [(s['scheme_code'], s['name'], s['employee_rate_pct'],
                                     s['employer_rate_pct'], 'Yes' if s['tiered'] else 'No',
                                     s['tier_basis'], 'Yes' if s['is_active'] else 'No')
                                    for s in self._pn_scheme_rows.values()])

    def _pn_pick_scheme(self, _event=None):
        sel = self.pn_scheme_tree.selection()
        if not sel:
            return
        scheme = self._pn_scheme_rows.get(str(self.pn_scheme_tree.item(sel[0])['values'][0]))
        if not scheme:
            return
        for key, field in (('code', 'scheme_code'), ('name', 'name'), ('ee', 'employee_rate_pct'),
                           ('er', 'employer_rate_pct')):
            self.pn_form[key].delete(0, tk.END)
            self.pn_form[key].insert(0, scheme[field])
        self.pn_basis.set(scheme['tier_basis'])
        self.pn_tiered.set(bool(scheme['tiered']))
        self.pn_tiers.delete(0, tk.END)
        self.pn_tiers.insert(0, '; '.join(
            f"{t['lower_limit']:g}-{'' if t['upper_limit'] is None else format(t['upper_limit'], 'g')}"
            f":{t['employee_rate_pct']:g}" for t in scheme['tiers']))

    def _pn_save_scheme(self):
        f = self.pn_form
        try:
            ee = float(f['ee'].get()) if f['ee'].get().strip() else None
            er = float(f['er'].get()) if f['er'].get().strip() else None
        except ValueError:
            self._ps_error("Rates are percentages, e.g. 6.1")
            return
        self._ps_call(pensions.update_scheme, self.auth, f['code'].get(),
                      name=f['name'].get().strip() or None, employee_rate_pct=ee,
                      employer_rate_pct=er, tiered=self.pn_tiered.get(),
                      tier_basis=self.pn_basis.get() or None,
                      done="Scheme saved", after=self._pn_load_schemes)

    def _pn_save_tiers(self):
        tiers = []
        try:
            for part in filter(None, (p.strip() for p in self.pn_tiers.get().split(';'))):
                band, rate = part.split(':')
                low, high = band.split('-')
                tiers.append((float(low), float(high) if high.strip() else None, float(rate)))
        except ValueError:
            self._ps_error("Write tiers as lower-upper:rate; leave the last upper empty")
            return
        self._ps_call(pensions.set_tiers, self.auth, self.pn_form['code'].get().strip().upper(),
                      tiers, done="Tiers saved", after=self._pn_load_schemes)

    def _pn_members(self, tab):
        form = ttk.LabelFrame(tab, text="Enrol", padding=8)
        form.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        self.pn_enrol = _entries(form, [('user', 'Username:', ''),
                                        ('date', 'From:', date.today().isoformat())])
        ttk.Label(form, text="Scheme:").grid(row=1, column=0, sticky='e', padx=5)
        self.pn_enrol_scheme = ttk.Combobox(form, width=10, state='readonly',
                                            values=[s['scheme_code'] for s in pensions.list_schemes()])
        self.pn_enrol_scheme.grid(row=1, column=1, sticky='w', padx=5)
        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=0, columnspan=8, pady=5)
        ttk.Button(buttons, text="Enrol", command=self._pn_do_enrol).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text="Opt Out Selected", command=self._pn_opt_out_selected).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(buttons, text="Refresh", command=self._pn_load_members).pack(side=tk.LEFT, padx=5)
        self.pn_member_tree = _tree(tab, ('ID', 'Person', 'Scheme', 'Joined', 'Left', 'Reason'),
                                    {'Reason': 200})
        self._pn_load_members()

    def _pn_load_members(self):
        rows = self._ps_call(pensions.memberships, self.auth) or []
        _fill(self.pn_member_tree, [(m['membership_id'], m['user_id'], m['scheme_code'],
                                     m['joined_on'], m['opted_out_on'] or '-',
                                     m['opt_out_reason'] or '') for m in rows])

    def _pn_do_enrol(self):
        self._ps_call(pensions.enrol, self.auth, self.pn_enrol['user'].get().strip(),
                      self.pn_enrol_scheme.get(), self.pn_enrol['date'].get().strip(),
                      done="Enrolled", after=self._pn_load_members)

    def _pn_opt_out_selected(self):
        sel = self.pn_member_tree.selection()
        if not sel:
            return
        user = self.pn_member_tree.item(sel[0])['values'][1]
        if messagebox.askyesno("Confirm", f"Opt {user} out of their pension?", parent=self.root):
            self._ps_call(pensions.opt_out, self.auth, str(user),
                          self.pn_enrol['date'].get().strip(), 'opted out by payroll',
                          after=self._pn_load_members)


__all__ = ['PayStructureTabsMixin']
