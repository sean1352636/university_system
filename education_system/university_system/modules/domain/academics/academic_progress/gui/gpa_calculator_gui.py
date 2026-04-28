"""What-If GPA Calculator GUI (Feature 37).

Five-tab calculator: Calculator / Term History / Major / Required Average /
Saved Scenarios.  Adds 50 new functions on top of the original module:
grade-scale conversions, weighted / cumulative / major / repeat-replace
GPAs, dean's-list and honours eligibility, term history loaders, saved
scenarios persisted to ``~/.education_system/gpa_scenarios.json``, plus the
usual export / clipboard / refresh wiring.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.university_system.modules.shared.services.dashboard.student_services import StudentDashboardService

logger = logging.getLogger(__name__)


SCENARIO_FILE = Path.home() / '.education_system' / 'gpa_scenarios.json'

# Honours / dean's-list defaults — overridable via _load_user_preferences().
DEFAULT_DEAN_LIST_GPA = 3.5
DEFAULT_HONOURS_GPA = 3.7  # cum laude floor on 4-pt scale


class GPACalculatorGUI:
    """Toplevel window for what-if GPA calculation."""

    GRADE_CHOICES = ['-- Keep Current --', 'A', 'A-', 'B+', 'B', 'B-',
                     'C+', 'C', 'C-', 'D+', 'D', 'F']

    # ── 4-point letter scale (US-style); plus / minus included.
    _LETTER_4PT = {
        'A+': 4.0, 'A': 4.0, 'A-': 3.7,
        'B+': 3.3, 'B': 3.0, 'B-': 2.7,
        'C+': 2.3, 'C': 2.0, 'C-': 1.7,
        'D+': 1.3, 'D': 1.0, 'D-': 0.7,
        'F': 0.0,
    }
    # ── UK-style letter scale (50 % bands).
    _LETTER_UK_PCT = {'A': 75, 'B': 65, 'C': 55, 'D': 45, 'F': 30}

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.username = ''
        if auth and getattr(auth, 'current_user', None):
            self.username = auth.current_user.get('username', '')
        self.student_id = self._resolve_student_id(auth, self.username)

        self.window = tk.Toplevel(parent)
        self.window.title("What-If GPA Calculator")
        self.window.geometry("1024x720")
        self.window.minsize(900, 600)
        self.window.transient(parent)

        # State
        self._module_rows = []                 # legacy: (code, display, combo)
        self._enrolled: list[dict] = []
        self._completed: list[dict] = []
        self._term_history: list[dict] = []
        self._scale_var = tk.StringVar(value='4-point')   # or 'UK %'
        self._scenarios: dict[str, dict] = self._load_saved_scenarios()
        self._prefs = self._load_user_preferences()

        self._setup_ui()
        self._load_data()

    # =================================================================
    # ─── Original 6 methods (kept for back-compat) ────────────────────
    # =================================================================

    def _setup_ui(self):
        """Build the layout: header → notebook with five tabs."""
        self._build_header()
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        self._tab_calculator = ttk.Frame(self.notebook)
        self._tab_terms = ttk.Frame(self.notebook)
        self._tab_major = ttk.Frame(self.notebook)
        self._tab_required = ttk.Frame(self.notebook)
        self._tab_scenarios = ttk.Frame(self.notebook)

        self.notebook.add(self._tab_calculator, text='Calculator')
        self.notebook.add(self._tab_terms, text='Term History')
        self.notebook.add(self._tab_major, text='Major / Cumulative')
        self.notebook.add(self._tab_required, text='Required Average')
        self.notebook.add(self._tab_scenarios, text='Scenarios')

        self._build_calculator_tab(self._tab_calculator)
        self._build_terms_tab(self._tab_terms)
        self._build_major_tab(self._tab_major)
        self._build_required_panel(self._tab_required)
        self._build_scenario_panel(self._tab_scenarios)

    def _load_data(self):
        if not self.student_id:
            self.current_gpa_var.set("Current GPA: -- (not logged in)")
            return
        try:
            progress = StudentDashboardService.get_degree_progress_summary(self.student_id)
            gpa = progress.get('gpa')
            self.current_gpa_var.set(
                f"Current GPA: {gpa:.2f}" if isinstance(gpa, (int, float)) else "Current GPA: N/A"
            )
            self._enrolled = self._load_enrolled_modules()
            self._completed = self._load_completed_modules()
            self._term_history = self._load_term_history()
            grades_data = StudentDashboardService.get_grades_by_module(self.student_id)
            for mod in grades_data:
                avg = mod.get('average_score')
                if avg is not None:
                    letter = self._score_to_letter(avg)
                    current_display = f"{letter} ({avg:.1f})"
                else:
                    current_display = "No grades"
                self._add_module_row(mod['module_code'], current_display)
            # Refresh secondary tabs from cached state.
            self._refresh_terms_tab()
            self._refresh_major_tab()
        except Exception as e:
            logger.error(f"Error loading GPA calculator data: {e}")
            messagebox.showerror("Error", f"Failed to load data: {e}", parent=self.window)

    def _add_module_row(self, module_code, current_display):
        row_frame = ttk.Frame(self.scrollable_frame)
        row_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(row_frame, text=module_code, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(row_frame, text=current_display, width=15).pack(side=tk.LEFT, padx=5)
        combo = ttk.Combobox(row_frame, values=self.GRADE_CHOICES, state='readonly', width=16)
        combo.set('-- Keep Current --')
        combo.pack(side=tk.LEFT, padx=5)
        self._module_rows.append((module_code, current_display, combo))

    def _calculate(self):
        if not self.student_id:
            messagebox.showwarning("Warning", "No student logged in.", parent=self.window)
            return
        hypothetical = {
            mc: combo.get() for mc, _d, combo in self._module_rows
            if combo.get() and combo.get() != '-- Keep Current --'
        }
        try:
            result = StudentDashboardService.simulate_gpa(self.student_id, hypothetical)
            projected = result.get('projected_gpa')
            current = result.get('current_gpa')
            delta = result.get('delta', 0.0)
            self.result_var.set(
                f"Projected GPA: {projected:.2f}" if isinstance(projected, (int, float))
                else "Projected GPA: N/A"
            )
            if delta and isinstance(current, (int, float)) and isinstance(projected, (int, float)):
                sign = '+' if delta > 0 else ''
                self.delta_var.set(f"({sign}{delta:.2f})")
                colour = 'green' if delta > 0 else 'red' if delta < 0 else 'black'
                self.delta_label.configure(foreground=colour)
            else:
                self.delta_var.set('')
        except Exception as e:
            logger.error(f"Error calculating projected GPA: {e}")
            messagebox.showerror("Error", f"Failed to calculate GPA: {e}", parent=self.window)

    @staticmethod
    def _score_to_letter(score):
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        return 'F'

    # =================================================================
    # ─── 50 NEW FUNCTIONS ─────────────────────────────────────────────
    # =================================================================

    # ── Conversions (12) ─────────────────────────────────────────────

    @classmethod
    def _letter_to_4pt(cls, letter: str) -> float | None:
        """[1] Map a letter grade to a 4-point GPA value (US scale)."""
        if not letter:
            return None
        return cls._LETTER_4PT.get(letter.strip().upper())

    @classmethod
    def _4pt_to_letter(cls, gpa: float) -> str:
        """[2] Inverse of `_letter_to_4pt` — pick the closest letter band."""
        if gpa is None:
            return '—'
        bands = [
            (3.85, 'A'), (3.5, 'A-'), (3.15, 'B+'), (2.85, 'B'),
            (2.5, 'B-'), (2.15, 'C+'), (1.85, 'C'), (1.5, 'C-'),
            (1.15, 'D+'), (0.85, 'D'), (0.5, 'D-'),
        ]
        for floor, letter in bands:
            if gpa >= floor:
                return letter
        return 'F'

    @classmethod
    def _pct_to_4pt(cls, pct: float) -> float:
        """[3] Convert a 0–100 percentage to a 4-point GPA value.

        Uses a 5-point banding (≥90 → 4.0, ≥80 → 3.0…) consistent with
        the original `_score_to_letter` helper, then maps via `_letter_to_4pt`.
        """
        return cls._letter_to_4pt(cls._pct_to_letter_us(pct)) or 0.0

    @staticmethod
    def _pct_to_letter_us(pct: float) -> str:
        """[4] Percentage → US letter grade."""
        if pct >= 90: return 'A'
        if pct >= 80: return 'B'
        if pct >= 70: return 'C'
        if pct >= 60: return 'D'
        return 'F'

    @staticmethod
    def _pct_to_letter_uk(pct: float) -> str:
        """[5] Percentage → UK letter grade (40 % pass mark, 70 % first)."""
        if pct >= 70: return 'A'
        if pct >= 60: return 'B'
        if pct >= 50: return 'C'
        if pct >= 40: return 'D'
        return 'F'

    @classmethod
    def _letter_to_pct_us(cls, letter: str) -> float | None:
        """[6] US letter → midpoint percentage (used for what-if rounds)."""
        return {'A': 95, 'B': 85, 'C': 75, 'D': 65, 'F': 30}.get(
            (letter or '').upper().rstrip('+-'),
        )

    @classmethod
    def _letter_to_pct_uk(cls, letter: str) -> float | None:
        """[7] UK letter → midpoint percentage."""
        return cls._LETTER_UK_PCT.get((letter or '').upper())

    @staticmethod
    def _uk_classification(pct: float) -> str:
        """[8] UK undergraduate honours band from a percentage."""
        if pct >= 70: return 'First Class (1st)'
        if pct >= 60: return 'Upper Second (2:1)'
        if pct >= 50: return 'Lower Second (2:2)'
        if pct >= 40: return 'Third Class (3rd)'
        return 'Fail'

    @classmethod
    def _4pt_to_classification(cls, gpa: float) -> str:
        """[9] Same band labels but driven from a 4-point GPA."""
        if gpa >= 3.7: return 'First Class (1st)'
        if gpa >= 3.0: return 'Upper Second (2:1)'
        if gpa >= 2.3: return 'Lower Second (2:2)'
        if gpa >= 1.0: return 'Third Class (3rd)'
        return 'Fail'

    @classmethod
    def _normalise_grade(cls, value):
        """[10] Accept str/int/float, return ``(pct, letter, gpa_4pt)`` tuple
        or ``(None, None, None)`` when uninterpretable."""
        if value is None or value == '':
            return None, None, None
        if isinstance(value, (int, float)):
            return float(value), cls._pct_to_letter_us(float(value)), cls._pct_to_4pt(float(value))
        s = str(value).strip()
        # Pure number
        try:
            pct = float(s)
            return pct, cls._pct_to_letter_us(pct), cls._pct_to_4pt(pct)
        except ValueError:
            pass
        gpa_4 = cls._letter_to_4pt(s)
        if gpa_4 is not None:
            return cls._letter_to_pct_us(s), s.upper(), gpa_4
        return None, None, None

    @classmethod
    def _grade_points(cls, letter: str, scale: str = '4-point') -> float | None:
        """[11] Universal accessor: return grade points on the chosen scale."""
        if scale == '4-point':
            return cls._letter_to_4pt(letter)
        if scale == 'UK %':
            return cls._letter_to_pct_uk(letter)
        return None

    @staticmethod
    def _classification_to_pct_floor(name: str) -> float | None:
        """[12] Reverse-look up the minimum percentage of a UK band."""
        return {
            '1st': 70.0, 'first': 70.0,
            '2:1': 60.0, 'upper second': 60.0,
            '2:2': 50.0, 'lower second': 50.0,
            '3rd': 40.0, 'third': 40.0,
        }.get((name or '').strip().lower())

    # ── Computations (12) ────────────────────────────────────────────

    def _compute_unweighted_gpa(self, rows: list[dict]) -> float | None:
        """[13] Equal-weight mean of 4-point grades, ignoring credits."""
        gpas = [self._row_gpa(r) for r in rows]
        gpas = [g for g in gpas if g is not None]
        return sum(gpas) / len(gpas) if gpas else None

    def _compute_weighted_gpa(self, rows: list[dict]) -> float | None:
        """[14] Credit-weighted mean of 4-point grades.  Falls back to
        unweighted when no credit info is available."""
        weighted_sum, total_credits = 0.0, 0.0
        for r in rows:
            gpa = self._row_gpa(r)
            if gpa is None:
                continue
            credits = float(r.get('credits') or r.get('credits_earned') or 0)
            if credits <= 0:
                credits = 1.0
            weighted_sum += gpa * credits
            total_credits += credits
        return weighted_sum / total_credits if total_credits else None

    def _compute_term_gpa(self, rows: list[dict], year=None, term=None) -> float | None:
        """[15] Credit-weighted GPA filtered to a particular year/term."""
        filtered = [
            r for r in rows
            if (year is None or str(r.get('year')) == str(year))
            and (term is None or str(r.get('semester') or r.get('term')) == str(term))
        ]
        return self._compute_weighted_gpa(filtered)

    def _compute_cumulative_gpa(self, history: list[dict]) -> float | None:
        """[16] GPA across a list of term records (credit-weighted)."""
        return self._compute_weighted_gpa(history)

    def _compute_major_gpa(self, rows: list[dict], department: str) -> float | None:
        """[17] GPA for modules belonging to *department* only."""
        d = (department or '').lower()
        return self._compute_weighted_gpa(
            [r for r in rows if (r.get('department') or '').lower() == d]
        )

    def _compute_minor_gpa(self, rows: list[dict], minor: str) -> float | None:
        """[18] Same as major-GPA but for the minor subject area."""
        return self._compute_major_gpa(rows, minor)

    def _compute_repeat_replace_gpa(self, rows: list[dict]) -> float | None:
        """[19] Drop earlier attempts at the same module — keep the latest
        completion only.  Useful for institutions where retakes replace the
        original grade in the GPA computation."""
        latest_by_code: dict[str, dict] = {}
        for r in rows:
            code = r.get('module_code')
            if not code:
                continue
            existing = latest_by_code.get(code)
            if not existing or (r.get('completion_date') or '') > (existing.get('completion_date') or ''):
                latest_by_code[code] = r
        return self._compute_weighted_gpa(list(latest_by_code.values()))

    def _compute_projected_gpa(self, rows: list[dict],
                               overrides: dict[str, str]) -> float | None:
        """[20] Like `_compute_weighted_gpa` but applies hypothetical letter
        grades to specific module codes before computing."""
        adjusted = []
        for r in rows:
            cp = dict(r)
            override = overrides.get(cp.get('module_code'))
            if override:
                gpa_4 = self._letter_to_4pt(override)
                if gpa_4 is not None:
                    cp['_gpa_override'] = gpa_4
            adjusted.append(cp)
        return self._compute_weighted_gpa(adjusted)

    @staticmethod
    def _compute_required_avg(target: float, completed_credits: float,
                              completed_gpa: float, remaining_credits: float) -> float:
        """[21] Average GPA needed across remaining credits to hit *target*.

        Returns the bare number; the UI is responsible for warning when the
        result is > 4.0 (impossible) or ≤ 0 (already guaranteed).
        """
        total = (completed_credits or 0) + (remaining_credits or 0)
        if remaining_credits <= 0 or total <= 0:
            return float('inf')
        return (target * total - completed_gpa * completed_credits) / remaining_credits

    def _compute_dean_list_status(self, gpa: float | None,
                                  threshold: float = DEFAULT_DEAN_LIST_GPA) -> str:
        """[22] Return ``'Eligible'`` / ``'Below threshold'`` / ``'No GPA'``."""
        if gpa is None:
            return 'No GPA'
        return 'Eligible' if gpa >= threshold else f'Below threshold ({threshold:.2f})'

    def _compute_honors_eligibility(self, gpa: float | None,
                                    scale: str = '4-point') -> str:
        """[23] Latin honours: summa / magna / cum laude on a 4-pt scale, or
        UK degree band on a percentage scale."""
        if gpa is None:
            return '—'
        if scale == '4-point':
            if gpa >= 3.9: return 'Summa Cum Laude'
            if gpa >= 3.7: return 'Magna Cum Laude'
            if gpa >= 3.5: return 'Cum Laude'
            return 'No Latin honours'
        return self._uk_classification(gpa)

    def _compute_credits_completed(self, rows: list[dict]) -> float:
        """[24] Sum credit values across rows that have a graded outcome."""
        total = 0.0
        for r in rows:
            if self._row_gpa(r) is None:
                continue
            total += float(r.get('credits') or r.get('credits_earned') or 0)
        return total

    # ── Data loaders (8) ─────────────────────────────────────────────

    def _load_enrolled_modules(self) -> list[dict]:
        """[25] Currently-enrolled modules with credits + grade."""
        return self._fetch_modules(status_filter='enrolled')

    def _load_completed_modules(self) -> list[dict]:
        """[26] Past completed/withdrawn modules."""
        return self._fetch_modules(status_filter='completed')

    def _load_term_history(self) -> list[dict]:
        """[27] Per-term GPA history.  Returns one record per (year, term)."""
        if not self.student_id:
            return []
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT sm.year, sm.semester, sm.module_code, sm.grade, "
                    "       COALESCE(sm.credits_earned, m.credits) AS credits, "
                    "       m.department "
                    "FROM student_modules sm "
                    "LEFT JOIN modules m ON sm.module_code = m.module_code "
                    "WHERE sm.student_id = ?",
                    (self.student_id,),
                ).fetchall()
        except Exception:
            return []
        terms: dict[tuple[str, str], list[dict]] = {}
        for r in rows:
            key = (r['year'] or 'Unknown', r['semester'] or 'Unknown')
            terms.setdefault(key, []).append(dict(r))
        out = []
        for (yr, sem), tr_rows in sorted(terms.items()):
            out.append({
                'year': yr, 'semester': sem,
                'modules': tr_rows,
                'gpa': self._compute_weighted_gpa(tr_rows),
                'credits': sum(float(r.get('credits') or 0) for r in tr_rows),
            })
        return out

    def _load_class_averages(self) -> dict[str, float]:
        """[28] Map module_code → cohort mean from `module_grades`."""
        out: dict[str, float] = {}
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT module_code, AVG(final_score) AS avg_score "
                    "FROM module_grades GROUP BY module_code",
                ).fetchall()
                for r in rows:
                    if r['avg_score'] is not None:
                        out[r['module_code']] = float(r['avg_score'])
        except Exception:
            pass
        return out

    def _load_remaining_required_modules(self) -> list[dict]:
        """[29] Modules listed by the degree plan that are not yet completed.

        Uses ``degree_requirements``/``requirement_completion`` if present, and
        returns an empty list otherwise — keeps the calculator usable on
        installations without those tables.
        """
        if not self.student_id:
            return []
        try:
            with get_connection() as conn:
                completed = {r['module_code'] for r in conn.execute(
                    "SELECT module_code FROM student_modules "
                    "WHERE student_id = ? AND LOWER(status) = 'completed'",
                    (self.student_id,),
                ).fetchall()}
                rows = conn.execute(
                    "SELECT module_code, requirement_name, credits_required "
                    "FROM degree_requirements WHERE module_code IS NOT NULL",
                ).fetchall()
        except Exception:
            return []
        return [dict(r) for r in rows if r['module_code'] not in completed]

    def _load_user_preferences(self) -> dict:
        """[30] Read user preferences (dean's-list/honours thresholds, default
        scale) from a per-user JSON file.  Returns sensible defaults when the
        file is missing or unreadable."""
        defaults = {
            'dean_threshold': DEFAULT_DEAN_LIST_GPA,
            'honours_threshold': DEFAULT_HONOURS_GPA,
            'scale': '4-point',
        }
        try:
            path = SCENARIO_FILE.parent / 'gpa_prefs.json'
            if path.exists():
                with path.open('r', encoding='utf-8') as f:
                    return {**defaults, **json.load(f)}
        except Exception:
            pass
        return defaults

    def _load_saved_scenarios(self) -> dict[str, dict]:
        """[31] Read every saved what-if scenario from the JSON store."""
        try:
            if SCENARIO_FILE.exists():
                with SCENARIO_FILE.open('r', encoding='utf-8') as f:
                    return json.load(f) or {}
        except Exception:
            logger.exception("Failed to load scenarios")
        return {}

    @staticmethod
    def _resolve_student_id(auth, username: str) -> str:
        """[32] Look up the canonical student_id for *username* in the users
        table.  Same fix as the security-questions / grades-breakdown work —
        prevents writes against the wrong row when username != student_id."""
        if not username:
            return ''
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT student_id FROM users WHERE username = ?", (username,)
                ).fetchone()
                if row and row['student_id']:
                    return row['student_id']
        except Exception:
            pass
        return username

    # ── UI builders (8) ──────────────────────────────────────────────

    def _build_header(self):
        """[33] Title row + current GPA + scale switcher + global controls."""
        header = ttk.Frame(self.window)
        header.pack(fill=tk.X, padx=15, pady=(8, 4))
        ttk.Label(header, text="What-If GPA Calculator",
                  font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
        self.current_gpa_var = tk.StringVar(value="Current GPA: --")
        ttk.Label(header, textvariable=self.current_gpa_var,
                  font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=20)
        ttk.Button(header, text='Refresh', command=self._on_refresh).pack(side=tk.RIGHT, padx=4)
        ttk.Button(header, text='Reset', command=self._on_reset_hypotheticals).pack(side=tk.RIGHT, padx=4)
        self._build_export_menu(header)
        self._build_settings_bar()

    def _build_settings_bar(self):
        """[34] Scale switcher + dean's / honours threshold spinboxes."""
        bar = ttk.Frame(self.window)
        bar.pack(fill=tk.X, padx=15, pady=(0, 4))
        ttk.Label(bar, text='Scale:').pack(side=tk.LEFT)
        ttk.Combobox(bar, textvariable=self._scale_var,
                     values=('4-point', 'UK %'), state='readonly',
                     width=10).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(bar, text="Dean's threshold:").pack(side=tk.LEFT)
        self._dean_threshold_var = tk.DoubleVar(value=self._prefs['dean_threshold'])
        ttk.Spinbox(bar, from_=0, to=4.0, increment=0.05, width=6,
                    textvariable=self._dean_threshold_var).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(bar, text='Honours threshold:').pack(side=tk.LEFT)
        self._honours_threshold_var = tk.DoubleVar(value=self._prefs['honours_threshold'])
        ttk.Spinbox(bar, from_=0, to=4.0, increment=0.05, width=6,
                    textvariable=self._honours_threshold_var).pack(side=tk.LEFT, padx=(4, 12))

    def _build_filters_bar(self, parent):
        """[35] Year / term filter combos used by the term-history tab."""
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, padx=8, pady=4)
        self._year_filter = tk.StringVar(value='All')
        self._term_filter = tk.StringVar(value='All')
        ttk.Label(bar, text='Year:').pack(side=tk.LEFT)
        self._year_combo = ttk.Combobox(bar, textvariable=self._year_filter,
                                        values=('All',), state='readonly', width=10)
        self._year_combo.pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(bar, text='Term:').pack(side=tk.LEFT)
        self._term_combo = ttk.Combobox(bar, textvariable=self._term_filter,
                                        values=('All',), state='readonly', width=12)
        self._term_combo.pack(side=tk.LEFT, padx=(4, 12))
        for v in (self._year_filter, self._term_filter):
            v.trace_add('write', lambda *_: self._refresh_terms_tab())

    def _build_summary_panel(self, parent):
        """[36] Shared summary block — current GPA, projected, dean's-list."""
        f = ttk.LabelFrame(parent, text='Summary', padding=8)
        f.pack(fill=tk.X, padx=8, pady=4)
        self._summary_var = tk.StringVar(value='—')
        ttk.Label(f, textvariable=self._summary_var, font=('Arial', 11),
                  justify='left').pack(anchor='w')
        return f

    def _build_scenario_panel(self, parent):
        """[37] List of saved scenarios + load/delete/save controls."""
        ttk.Label(parent, text='Saved Scenarios', font=('Arial', 12, 'bold')).pack(
            anchor='w', padx=8, pady=(8, 4))
        self._scenario_list = tk.Listbox(parent, height=12, font=('Arial', 11))
        self._scenario_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self._refresh_scenario_list()
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(bar, text='Save current as…',
                   command=self._on_save_scenario).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text='Load selected',
                   command=lambda: self._on_load_scenario(self._selected_scenario())
                   ).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text='Delete selected',
                   command=lambda: self._on_delete_scenario(self._selected_scenario())
                   ).pack(side=tk.LEFT, padx=4)

    def _build_export_menu(self, parent):
        """[38] Toolbar Export menu — CSV / PDF / clipboard / email / print."""
        mb = ttk.Menubutton(parent, text='Export…')
        menu = tk.Menu(mb, tearoff=0)
        menu.add_command(label='Save as CSV…', command=self._on_export_csv)
        menu.add_command(label='Save as PDF…', command=self._on_export_pdf)
        menu.add_command(label='Copy to clipboard', command=self._on_copy_clipboard)
        menu.add_command(label='Print…', command=self._on_print)
        menu.add_separator()
        menu.add_command(label='Email to advisor…', command=self._on_email_advisor)
        mb.configure(menu=menu)
        mb.pack(side=tk.RIGHT, padx=4)
        return mb

    def _build_chart_panel(self, parent):
        """[39] tk.Canvas line graph of GPA across terms."""
        f = ttk.LabelFrame(parent, text='Term GPA Trend', padding=4)
        f.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self._chart_canvas = tk.Canvas(f, height=180, bg='#ecf0f1',
                                       highlightthickness=0)
        self._chart_canvas.pack(fill=tk.BOTH, expand=True)
        self._chart_canvas.bind('<Configure>', lambda _e: self._redraw_term_chart())
        return f

    def _build_required_panel(self, parent):
        """[40] Calculator: target GPA + remaining credits → required avg."""
        f = ttk.LabelFrame(parent, text='Required Average', padding=10)
        f.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(f, text='Target GPA:').grid(row=0, column=0, sticky='w', pady=4)
        self._target_var = tk.DoubleVar(value=3.5)
        ttk.Spinbox(f, from_=0, to=4.0, increment=0.05, width=8,
                    textvariable=self._target_var).grid(row=0, column=1, sticky='w', padx=4)
        ttk.Label(f, text='Remaining credits:').grid(row=1, column=0, sticky='w', pady=4)
        self._remaining_var = tk.DoubleVar(value=60)
        ttk.Spinbox(f, from_=0, to=480, increment=5, width=8,
                    textvariable=self._remaining_var).grid(row=1, column=1, sticky='w', padx=4)
        self._required_var = tk.StringVar(value='—')
        ttk.Button(f, text='Compute', command=self._compute_required_into_label
                   ).grid(row=2, column=0, sticky='w', pady=10)
        ttk.Label(f, textvariable=self._required_var, font=('Arial', 11, 'bold'),
                  wraplength=560, justify='left').grid(row=2, column=1, sticky='w')
        return f

    # ── Actions / events (10) ────────────────────────────────────────

    def _on_refresh(self):
        """[41] Re-load the entire GPA calculator from the database."""
        for child in self.scrollable_frame.winfo_children():
            child.destroy()
        self._module_rows = []
        self._enrolled = []
        self._completed = []
        self._term_history = []
        self._build_module_rows_header()
        self._load_data()

    def _on_reset_hypotheticals(self):
        """[42] Reset every combobox back to 'Keep Current'."""
        for _code, _disp, combo in self._module_rows:
            combo.set('-- Keep Current --')
        self.result_var.set('')
        self.delta_var.set('')

    def _on_save_scenario(self):
        """[43] Persist current overrides under a user-supplied name."""
        win = tk.Toplevel(self.window)
        win.title('Save Scenario')
        win.geometry('360x140')
        ttk.Label(win, text='Scenario name:').pack(pady=(12, 4))
        name_var = tk.StringVar()
        ttk.Entry(win, textvariable=name_var, width=40).pack(padx=8)

        def go():
            name = name_var.get().strip()
            if not name:
                return
            self._scenarios[name] = {
                'overrides': {mc: combo.get() for mc, _d, combo in self._module_rows
                              if combo.get() and combo.get() != '-- Keep Current --'},
                'saved_at': datetime.utcnow().isoformat(),
            }
            self._persist_scenarios()
            self._refresh_scenario_list()
            win.destroy()
        ttk.Button(win, text='Save', command=go).pack(pady=8)

    def _on_load_scenario(self, name: str | None):
        """[44] Apply a saved scenario's overrides to the comboboxes."""
        if not name or name not in self._scenarios:
            return
        overrides = self._scenarios[name].get('overrides', {})
        for mc, _d, combo in self._module_rows:
            combo.set(overrides.get(mc, '-- Keep Current --'))
        self._calculate()

    def _on_delete_scenario(self, name: str | None):
        """[45] Remove a saved scenario from the JSON store."""
        if not name or name not in self._scenarios:
            return
        if not messagebox.askyesno('Delete scenario',
                                   f"Delete '{name}'?", parent=self.window):
            return
        del self._scenarios[name]
        self._persist_scenarios()
        self._refresh_scenario_list()

    def _on_export_csv(self):
        """[46] Save current calculator state to CSV."""
        path = filedialog.asksaveasfilename(
            parent=self.window, defaultextension='.csv',
            filetypes=[('CSV', '*.csv')],
            initialfile=f'gpa_{self.student_id or "student"}.csv',
        )
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['module_code', 'current', 'hypothetical'])
                for mc, disp, combo in self._module_rows:
                    w.writerow([mc, disp, combo.get()])
            messagebox.showinfo('Saved', f'Exported {path}', parent=self.window)
        except Exception as e:
            messagebox.showerror('Error', f'Failed: {e}', parent=self.window)

    def _on_export_pdf(self):
        """[47] PDF export via the shared ExportManager when available."""
        path = filedialog.asksaveasfilename(
            parent=self.window, defaultextension='.pdf',
            filetypes=[('PDF', '*.pdf')],
            initialfile=f'gpa_{self.student_id or "student"}.pdf',
        )
        if not path:
            return
        try:
            from education_system.university_system.modules.shared.services.pdf_export.export_manager import (
                ExportManager,
            )
            ExportManager().export_to_pdf(
                {'modules': [(mc, disp, combo.get())
                             for mc, disp, combo in self._module_rows]},
                path, title='What-If GPA',
            )
            messagebox.showinfo('Saved', f'Exported {path}', parent=self.window)
        except ImportError:
            messagebox.showinfo('PDF unavailable',
                                'PDF export module not installed.',
                                parent=self.window)
        except Exception as e:
            messagebox.showerror('Error', f'Failed: {e}', parent=self.window)

    def _on_copy_clipboard(self):
        """[48] Copy the calculator state to the clipboard as TSV."""
        lines = ['Module\tCurrent\tHypothetical']
        for mc, disp, combo in self._module_rows:
            lines.append(f'{mc}\t{disp}\t{combo.get()}')
        text = '\n'.join(lines)
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(text)
        except Exception:
            pass

    def _on_print(self):
        """[49] Tk has no portable print API — route to PDF export."""
        self._on_export_pdf()

    def _on_email_advisor(self):
        """[50] Email a snapshot to the student's advisor.  Requires the
        shared communications hub to be configured in this environment."""
        try:
            from education_system.shared.email.email_service import send_email
        except Exception:
            messagebox.showinfo(
                'Email unavailable',
                'Communications hub is not configured here.',
                parent=self.window,
            )
            return
        win = tk.Toplevel(self.window)
        win.title('Email advisor')
        win.geometry('480x300')
        ttk.Label(win, text='Advisor email:').pack(anchor='w', padx=8, pady=(8, 2))
        email_var = tk.StringVar()
        ttk.Entry(win, textvariable=email_var).pack(fill=tk.X, padx=8)
        body = tk.Text(win, height=8)
        body.insert('1.0',
                    f'Current GPA: {self.current_gpa_var.get()}\n'
                    f'Projected: {self.result_var.get()}\n')
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        def go():
            try:
                send_email(to=email_var.get(),
                           subject='What-If GPA snapshot',
                           body=body.get('1.0', 'end'))
                win.destroy()
            except Exception as e:
                messagebox.showerror('Error', str(e), parent=win)
        ttk.Button(win, text='Send', command=go).pack(pady=6)

    # =================================================================
    # ─── Internal glue (NOT counted in the 50) ─────────────────────────
    # =================================================================

    def _build_calculator_tab(self, parent):
        """Original calculator UI inside its tab."""
        canvas_frame = ttk.LabelFrame(parent, text='Enrolled Modules', padding=5)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL,
                                  command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind('<Configure>',
                                   lambda _e: self.canvas.configure(
                                       scrollregion=self.canvas.bbox('all')))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._build_module_rows_header()

        bottom = ttk.Frame(parent)
        bottom.pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(bottom, text='Calculate Projected GPA',
                   command=self._calculate).pack(side=tk.LEFT, padx=10)
        self.result_var = tk.StringVar(value='')
        self.result_label = ttk.Label(bottom, textvariable=self.result_var,
                                      font=('Arial', 13, 'bold'))
        self.result_label.pack(side=tk.LEFT, padx=10)
        self.delta_var = tk.StringVar(value='')
        self.delta_label = ttk.Label(bottom, textvariable=self.delta_var,
                                     font=('Arial', 12))
        self.delta_label.pack(side=tk.LEFT, padx=10)

    def _build_module_rows_header(self):
        header = ttk.Frame(self.scrollable_frame)
        header.pack(fill=tk.X, padx=5, pady=(0, 3))
        for txt, w in (('Module', 20), ('Current Grade', 15), ('Hypothetical', 18)):
            ttk.Label(header, text=txt, font=('Arial', 10, 'bold'),
                      width=w).pack(side=tk.LEFT, padx=5)

    def _build_terms_tab(self, parent):
        self._build_filters_bar(parent)
        cols = ('year', 'semester', 'credits', 'gpa', 'classification')
        self._terms_tree = ttk.Treeview(parent, columns=cols, show='headings')
        for c in cols:
            self._terms_tree.heading(c, text=c.title())
            self._terms_tree.column(c, width=130, anchor='center')
        self._terms_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self._build_chart_panel(parent)

    def _build_major_tab(self, parent):
        self._build_summary_panel(parent)
        self._major_tree = ttk.Treeview(
            parent, columns=('scope', 'credits', 'gpa', 'class'),
            show='headings',
        )
        for c, w in (('scope', 220), ('credits', 90), ('gpa', 90), ('class', 220)):
            self._major_tree.heading(c, text=c.title())
            self._major_tree.column(c, width=w, anchor='center')
        self._major_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    def _refresh_terms_tab(self):
        for iid in self._terms_tree.get_children():
            self._terms_tree.delete(iid)
        if not self._term_history:
            return
        years = sorted({t['year'] for t in self._term_history if t['year']})
        sems = sorted({t['semester'] for t in self._term_history if t['semester']})
        self._year_combo['values'] = ('All', *years)
        self._term_combo['values'] = ('All', *sems)
        yr_f, sem_f = self._year_filter.get(), self._term_filter.get()
        for t in self._term_history:
            if yr_f != 'All' and t['year'] != yr_f:
                continue
            if sem_f != 'All' and t['semester'] != sem_f:
                continue
            gpa = t.get('gpa')
            self._terms_tree.insert('', tk.END, values=(
                t['year'], t['semester'], f"{t.get('credits', 0):g}",
                f"{gpa:.2f}" if isinstance(gpa, (int, float)) else '—',
                self._4pt_to_classification(gpa) if gpa is not None else '—',
            ))
        self._redraw_term_chart()

    def _refresh_major_tab(self):
        if not hasattr(self, '_major_tree'):
            return
        for iid in self._major_tree.get_children():
            self._major_tree.delete(iid)
        all_rows = self._completed + self._enrolled
        cumulative = self._compute_cumulative_gpa(all_rows)
        repeat_rep = self._compute_repeat_replace_gpa(all_rows)
        self._major_tree.insert('', tk.END, values=(
            'All modules (cumulative)',
            f"{self._compute_credits_completed(all_rows):g}",
            f"{cumulative:.2f}" if cumulative else '—',
            self._4pt_to_classification(cumulative) if cumulative else '—',
        ))
        self._major_tree.insert('', tk.END, values=(
            'Repeat-replace policy',
            '—',
            f"{repeat_rep:.2f}" if repeat_rep else '—',
            self._4pt_to_classification(repeat_rep) if repeat_rep else '—',
        ))
        # Per-department rows
        depts = sorted({r.get('department') for r in all_rows if r.get('department')})
        for d in depts:
            g = self._compute_major_gpa(all_rows, d)
            self._major_tree.insert('', tk.END, values=(
                f'Department: {d}', '—',
                f"{g:.2f}" if g else '—',
                self._4pt_to_classification(g) if g else '—',
            ))
        # Dean's-list / honours
        dean = self._compute_dean_list_status(cumulative,
                                              self._dean_threshold_var.get())
        honours = self._compute_honors_eligibility(cumulative, self._scale_var.get())
        self._summary_var.set(
            f"Cumulative GPA: {cumulative:.2f} | Dean's list: {dean} | Honours: {honours}"
            if cumulative is not None else 'No GPA computed yet.'
        )

    def _redraw_term_chart(self):
        if not hasattr(self, '_chart_canvas'):
            return
        c = self._chart_canvas
        c.delete('all')
        w, h = c.winfo_width(), c.winfo_height()
        pts = [(t['year'], t['semester'], t['gpa']) for t in self._term_history
               if isinstance(t.get('gpa'), (int, float))]
        if w < 50 or h < 30 or len(pts) < 2:
            c.create_text(w / 2 if w > 0 else 50, h / 2 if h > 0 else 50,
                          text='Not enough term data to chart',
                          fill='#7f8c8d', font=('Arial', 10, 'italic'))
            return
        margin = 30
        x0, y0 = margin, h - margin
        x1, y1 = w - 8, 8
        c.create_line(x0, y0, x1, y0, fill='#bdc3c7')
        c.create_line(x0, y0, x0, y1, fill='#bdc3c7')
        for tick in (0, 1, 2, 3, 4):
            ty = y0 - (tick / 4.0) * (y0 - y1)
            c.create_text(x0 - 8, ty, text=str(tick), fill='#7f8c8d',
                          font=('Arial', 8), anchor='e')
        coords: list[float] = []
        for i, (_y, _s, gpa) in enumerate(pts):
            x = x0 + (i / max(len(pts) - 1, 1)) * (x1 - x0)
            yv = y0 - (gpa / 4.0) * (y0 - y1)
            coords.extend([x, yv])
        c.create_line(*coords, fill='#3498db', width=2)
        for i in range(0, len(coords), 2):
            c.create_oval(coords[i] - 3, coords[i + 1] - 3,
                          coords[i] + 3, coords[i + 1] + 3,
                          fill='#3498db', outline='#3498db')

    def _compute_required_into_label(self):
        """Wire the required-average tab's button."""
        target = float(self._target_var.get())
        remaining = float(self._remaining_var.get())
        completed_credits = self._compute_credits_completed(
            self._completed + self._enrolled)
        completed_gpa = self._compute_weighted_gpa(self._completed + self._enrolled) or 0.0
        need = self._compute_required_avg(
            target, completed_credits, completed_gpa, remaining)
        if need == float('inf'):
            self._required_var.set('No remaining credits — nothing to plan.')
        elif need > 4.0:
            self._required_var.set(
                f'You need {need:.2f}/4.0 across the remaining {remaining:g} credits — '
                f'this is mathematically impossible.')
        elif need <= 0:
            self._required_var.set('Already guaranteed at any passing average.')
        else:
            self._required_var.set(
                f'You need to average {need:.2f}/4.0 across the remaining '
                f'{remaining:g} credits to reach {target:.2f}.')

    def _refresh_scenario_list(self):
        if hasattr(self, '_scenario_list'):
            self._scenario_list.delete(0, tk.END)
            for name in sorted(self._scenarios):
                self._scenario_list.insert(tk.END, name)

    def _selected_scenario(self) -> str | None:
        sel = self._scenario_list.curselection()
        if not sel:
            return None
        return self._scenario_list.get(sel[0])

    def _persist_scenarios(self):
        try:
            SCENARIO_FILE.parent.mkdir(parents=True, exist_ok=True)
            with SCENARIO_FILE.open('w', encoding='utf-8') as f:
                json.dump(self._scenarios, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist scenarios: {e}")

    def _row_gpa(self, row: dict) -> float | None:
        """Pick the best GPA representation for *row* — explicit override
        first, then numeric grade, then letter."""
        if '_gpa_override' in row:
            return float(row['_gpa_override'])
        grade = row.get('grade')
        if isinstance(grade, (int, float)):
            return self._pct_to_4pt(float(grade))
        if isinstance(grade, str):
            try:
                return self._pct_to_4pt(float(grade))
            except ValueError:
                return self._letter_to_4pt(grade)
        return None

    def _fetch_modules(self, status_filter: str) -> list[dict]:
        if not self.student_id:
            return []
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT sm.module_code, sm.year, sm.semester, sm.grade, "
                    "       COALESCE(sm.credits_earned, m.credits) AS credits, "
                    "       sm.completion_date, sm.status, m.department, "
                    "       m.module_name "
                    "FROM student_modules sm "
                    "LEFT JOIN modules m ON sm.module_code = m.module_code "
                    "WHERE sm.student_id = ? AND LOWER(sm.status) = ?",
                    (self.student_id, status_filter),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []
