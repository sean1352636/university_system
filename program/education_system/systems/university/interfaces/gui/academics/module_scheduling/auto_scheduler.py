"""Database + GUI adapter for the automated scheduling / optimization suite.

Loads solver inputs from the scheduling database, runs the pure solver in
``auto_scheduler_core``, presents a what-if simulation dialog, and commits the
chosen proposals back to the timetable (as drafts for a sandbox, or published
for the live schedule).

Wires eight features onto ``ModuleSchedulingGUI``:
  1 auto-timetable generator     5 heuristic re-balancer
  2 constraint solver (weighted) 6 back-to-back detector
  3 what-if simulation           7 travel-time constraints
  4 optimization-goal selector   8 forecast-aware capacity
"""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.infrastructure.database.db import (
    get_connection, transaction,
)
from education_system.systems.university.interfaces.gui.academics.module_scheduling.main_gui import (
    ModuleSchedulingGUI,
)
from education_system.systems.university.interfaces.gui.academics.module_scheduling import (
    auto_scheduler_core as core,
)

# When a room's capacity is 0 / NULL in the database it means "unset", not
# "seats nobody". Treat it as effectively unlimited so the tool stays usable on
# partially-populated data; real positive capacities are always respected.
_UNLIMITED_CAPACITY = 100_000


# --------------------------------------------------------------------------- #
# Parsing helpers for loosely-typed instructor preference columns
# --------------------------------------------------------------------------- #
def _parse_pref_days(raw) -> frozenset[str]:
    if not raw:
        return frozenset()
    valid = {d.lower(): d for d in core.DAYS_OF_WEEK}
    out = set()
    for tok in str(raw).replace(";", ",").split(","):
        key = tok.strip().lower()
        if key in valid:
            out.add(valid[key])
    return frozenset(out)


def _parse_pref_windows(raw) -> tuple[tuple[str, str], ...]:
    """Parse 'HH:MM-HH:MM, HH:MM-HH:MM' into window pairs. Ignores junk."""
    if not raw:
        return ()
    out = []
    for tok in str(raw).replace(";", ",").split(","):
        tok = tok.strip()
        if "-" not in tok:
            continue
        a, b = tok.split("-", 1)
        a, b = a.strip(), b.strip()
        try:
            core.to_minutes(a)
            core.to_minutes(b)
        except (ValueError, AttributeError):
            continue
        out.append((a, b))
    return tuple(out)


# --------------------------------------------------------------------------- #
# Load solver inputs from the database
# --------------------------------------------------------------------------- #
def _auto_load_inputs(self, options, session_duration=60, session_type="Lecture",
                      only_unscheduled=True):
    """Return (reqs, rooms, instructors, existing) from the live database.

    * ``reqs`` — one session per module that still needs scheduling. Headcount
      comes from current enrollment; the forecast applies ``options.forecast_growth``.
    * ``existing`` — published schedule, treated as fixed occupancy.
    """
    with get_connection() as conn:
        cur = conn.cursor()

        # Rooms (active only).
        cur.execute(
            "SELECT id, COALESCE(building, ''), COALESCE(capacity, 0), "
            "COALESCE(room_type, '') FROM rooms WHERE is_active = 1")
        rooms = []
        for rid, building, capacity, rtype in cur.fetchall():
            cap = int(capacity) if capacity and int(capacity) > 0 else _UNLIMITED_CAPACITY
            rooms.append(core.Room(id=rid, building=building or f"B{rid}",
                                   capacity=cap, room_type=rtype))

        # Instructors (active only).
        cur.execute(
            "SELECT id, COALESCE(first_name,''), COALESCE(last_name,''), "
            "preferred_days, preferred_times, max_hours_per_week "
            "FROM instructors WHERE is_active = 1")
        instructors = []
        for iid, first, last, pdays, ptimes, maxh in cur.fetchall():
            name = f"{first} {last}".strip() or f"Instructor {iid}"
            max_min = int(maxh) * 60 if maxh else None
            instructors.append(core.Instructor(
                id=iid, name=name,
                preferred_days=_parse_pref_days(pdays),
                preferred_windows=_parse_pref_windows(ptimes),
                max_minutes_per_week=max_min))

        # Enrollment per module.
        cur.execute(
            "SELECT module_code, COUNT(*) FROM student_modules "
            "WHERE LOWER(COALESCE(status,'enrolled')) = 'enrolled' "
            "GROUP BY module_code")
        enrollment = {code: n for code, n in cur.fetchall()}

        # Already-published schedule -> fixed occupancy.
        cur.execute(
            "SELECT module_code, session_type, day_of_week, start_time, end_time, "
            "room_id, instructor_id FROM module_schedule WHERE status = 'published'")
        existing = []
        scheduled_codes = set()
        for code, stype, day, start, end, room_id, instr_id in cur.fetchall():
            scheduled_codes.add(code)
            if (day in core.DAYS_OF_WEEK and room_id is not None
                    and instr_id is not None and start and end):
                existing.append(core.Assignment(
                    module_code=code, session_type=stype or "Lecture", day=day,
                    start=start, end=end, room_id=room_id, instructor_id=instr_id))

        # Modules needing a slot.
        cur.execute(
            "SELECT module_code FROM modules WHERE is_active = 1 "
            "AND module_code IS NOT NULL AND module_code != ''")
        reqs = []
        growth = 1.0 + max(0.0, options.forecast_growth)
        for (code,) in cur.fetchall():
            if only_unscheduled and code in scheduled_codes:
                continue
            current = int(enrollment.get(code, 0))
            forecast = int(math.ceil(current * growth))
            reqs.append(core.ModuleReq(
                module_code=code, session_type=session_type,
                duration=session_duration, current_enrollment=current,
                forecast_enrollment=forecast))

    return reqs, rooms, instructors, existing


ModuleSchedulingGUI._auto_load_inputs = _auto_load_inputs


def run_auto_schedule(self, goal="balanced", weights=None, options=None,
                      session_duration=60, session_type="Lecture",
                      only_unscheduled=True, limit=None):
    """Load inputs and run the solver. Returns a ``core.SolveResult``. Pure —
    writes nothing to the database (that's the what-if guarantee)."""
    options = options or core.Options()
    weights = weights or core.weights_for_goal(goal)
    reqs, rooms, instructors, existing = self._auto_load_inputs(
        options, session_duration=session_duration, session_type=session_type,
        only_unscheduled=only_unscheduled)
    if limit is not None:
        reqs = reqs[:limit]
    return core.solve(reqs, rooms, instructors, existing=existing,
                      weights=weights, options=options)


ModuleSchedulingGUI.run_auto_schedule = run_auto_schedule


def _commit_auto_proposals(self, result, status="draft"):
    """Write proposed assignments to the timetable via the scheduler API.

    ``status='draft'`` stages a sandbox overlay (skips conflict checks +
    notifications); ``status='published'`` writes them live. Returns
    (committed, failed)."""
    committed, failed = 0, 0
    changed_by = getattr(self, "current_user", None) or "auto-scheduler"
    for a in result.assignments:
        try:
            ok = self.scheduler.add_module_schedule(
                a.module_code, a.day, a.start, a.end, a.room_id, a.instructor_id,
                a.session_type, status=status, changed_by=changed_by)
            if ok:
                committed += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return committed, failed


ModuleSchedulingGUI._commit_auto_proposals = _commit_auto_proposals


def clear_sandbox_drafts(self):
    """Delete all draft (sandbox) schedule rows."""
    try:
        with transaction() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM module_schedule WHERE status = 'draft'")
            removed = cur.rowcount
        return removed
    except Exception:
        return 0


ModuleSchedulingGUI.clear_sandbox_drafts = clear_sandbox_drafts


# --------------------------------------------------------------------------- #
# Back-to-back detector (feature 6) — standalone report on the live schedule
# --------------------------------------------------------------------------- #
def show_back_to_back_report(self):
    """Report instructor sessions with little/no transition time, plus
    cross-building travel-time violations, over the published schedule."""
    options = core.Options()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, COALESCE(building,''), COALESCE(capacity,0), COALESCE(room_type,'') "
            "FROM rooms")
        rooms_by_id = {}
        for rid, building, cap, rtype in cur.fetchall():
            rooms_by_id[rid] = core.Room(rid, building or f"B{rid}",
                                         int(cap) if cap else _UNLIMITED_CAPACITY, rtype)
        cur.execute(
            "SELECT module_code, session_type, day_of_week, start_time, end_time, "
            "room_id, instructor_id FROM module_schedule WHERE status = 'published'")
        assigns = []
        for code, stype, day, start, end, room_id, instr_id in cur.fetchall():
            if (day in core.DAYS_OF_WEEK and room_id in rooms_by_id
                    and instr_id is not None and start and end):
                assigns.append(core.Assignment(code, stype or "Lecture", day,
                                                start, end, room_id, instr_id))

    b2b = core.find_back_to_back(assigns, rooms_by_id, options)
    travel = core.find_travel_violations(assigns, rooms_by_id, options)

    win = tk.Toplevel(self.root)
    win.title("Back-to-Back & Travel-Time Report")
    win.geometry("760x520")
    win.transient(self.root)

    ttk.Label(win, text="Back-to-back sessions (tight/zero transition)",
              font=("Arial", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
    cols = ("Instructor", "Day", "Gap (min)", "Same building", "First", "Second")
    t1 = ttk.Treeview(win, columns=cols, show="headings", height=8)
    for c in cols:
        t1.heading(c, text=c)
        t1.column(c, width=120)
    t1.pack(fill=tk.BOTH, expand=True, padx=10)
    for r in b2b:
        t1.insert("", tk.END, values=(r["instructor_id"], r["day"], r["gap_minutes"],
                                      "Yes" if r["same_building"] else "No",
                                      r["first"], r["second"]))
    if not b2b:
        t1.insert("", tk.END, values=("—", "None found", "", "", "", ""))

    ttk.Label(win, text="Travel-time violations (different buildings, gap too short)",
              font=("Arial", 11, "bold")).pack(anchor="w", padx=10, pady=(12, 2))
    cols2 = ("Instructor", "Day", "Gap", "Required", "From", "To")
    t2 = ttk.Treeview(win, columns=cols2, show="headings", height=6)
    for c in cols2:
        t2.heading(c, text=c)
        t2.column(c, width=110)
    t2.pack(fill=tk.BOTH, expand=True, padx=10)
    for r in travel:
        t2.insert("", tk.END, values=(r["instructor_id"], r["day"],
                                      f"{r['gap_minutes']}m", f"{r['required']}m",
                                      r["from_building"], r["to_building"]))
    if not travel:
        t2.insert("", tk.END, values=("—", "None found", "", "", "", ""))

    ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)


ModuleSchedulingGUI.show_back_to_back_report = show_back_to_back_report


# --------------------------------------------------------------------------- #
# What-if simulation dialog (features 1-5, 7, 8)
# --------------------------------------------------------------------------- #
def show_auto_scheduler_dialog(self):
    """Interactive what-if auto-scheduler: pick a goal, tune weights + options,
    run the solver, preview the proposed timetable and its impact, then commit
    (sandbox draft or live) or discard."""
    dialog = tk.Toplevel(self.root)
    dialog.title("Auto-Scheduler — What-If Simulation")
    dialog.geometry("1040x760")
    dialog.transient(self.root)

    self._auto_last_result = None

    # ---- Controls (top) ----------------------------------------------------
    ctrl = ttk.LabelFrame(dialog, text="1. Optimization goal & constraints", padding=10)
    ctrl.pack(fill=tk.X, padx=10, pady=(10, 4))

    goal_var = tk.StringVar(value="balanced")
    ttk.Label(ctrl, text="Goal:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
    goal_labels = {
        "balanced": "Balanced",
        "room_utilization": "Room utilization",
        "student_compactness": "Student compactness",
        "instructor_preference": "Instructor preference",
    }
    goal_combo = ttk.Combobox(
        ctrl, textvariable=goal_var, state="readonly", width=24,
        values=list(goal_labels.keys()))
    goal_combo.grid(row=0, column=1, sticky="w", padx=4)

    # Options
    dur_var = tk.IntVar(value=60)
    step_var = tk.IntVar(value=60)
    travel_var = tk.IntVar(value=15)
    transition_var = tk.IntVar(value=0)
    growth_var = tk.IntVar(value=0)        # forecast growth %
    only_unsched_var = tk.BooleanVar(value=True)

    def _add_spin(parent, label, var, frm, to, inc, col):
        ttk.Label(parent, text=label).grid(row=1, column=col * 2, sticky="w", padx=4, pady=3)
        ttk.Spinbox(parent, from_=frm, to=to, increment=inc, textvariable=var,
                    width=7).grid(row=1, column=col * 2 + 1, sticky="w", padx=4)

    _add_spin(ctrl, "Duration (min):", dur_var, 30, 240, 15, 0)
    _add_spin(ctrl, "Slot step (min):", step_var, 15, 120, 15, 1)
    _add_spin(ctrl, "Travel time (min):", travel_var, 0, 120, 5, 2)
    _add_spin(ctrl, "Min transition (min):", transition_var, 0, 60, 5, 3)
    _add_spin(ctrl, "Forecast growth (%):", growth_var, 0, 200, 5, 4)
    ttk.Checkbutton(ctrl, text="Only unscheduled modules",
                    variable=only_unsched_var).grid(row=0, column=4, columnspan=2,
                                                     sticky="w", padx=4)

    # ---- Weights (tunable) -------------------------------------------------
    wframe = ttk.LabelFrame(dialog, text="2. Soft-constraint weights (tunable)", padding=10)
    wframe.pack(fill=tk.X, padx=10, pady=4)
    weight_vars = {
        "gap_per_hour": tk.DoubleVar(),
        "room_underfill": tk.DoubleVar(),
        "instructor_pref_bonus": tk.DoubleVar(),
        "day_balance": tk.DoubleVar(),
        "back_to_back": tk.DoubleVar(),
    }
    weight_labels = {
        "gap_per_hour": "Gap penalty /hr",
        "room_underfill": "Room underfill /seat",
        "instructor_pref_bonus": "Instructor pref bonus",
        "day_balance": "Day balance",
        "back_to_back": "Back-to-back penalty",
    }

    def _load_goal_weights(*_):
        w = core.weights_for_goal(goal_var.get())
        for k, var in weight_vars.items():
            var.set(round(getattr(w, k), 3))

    for i, (k, lbl) in enumerate(weight_labels.items()):
        ttk.Label(wframe, text=lbl + ":").grid(row=0, column=i * 2, sticky="w", padx=4)
        ttk.Spinbox(wframe, from_=0, to=100, increment=0.5, width=7,
                    textvariable=weight_vars[k]).grid(row=0, column=i * 2 + 1, padx=4)
    goal_combo.bind("<<ComboboxSelected>>", _load_goal_weights)
    _load_goal_weights()

    # ---- Summary + results -------------------------------------------------
    summary_var = tk.StringVar(value="Run a simulation to preview a proposed timetable.")
    ttk.Label(dialog, textvariable=summary_var, font=("Arial", 10),
              justify="left", wraplength=1000).pack(anchor="w", padx=12, pady=(6, 2))

    nb = ttk.Notebook(dialog)
    nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

    prop_frame = ttk.Frame(nb)
    nb.add(prop_frame, text="Proposed placements")
    prop_cols = ("Module", "Type", "Day", "Start", "End", "Room", "Instructor",
                 "Headcount", "Capacity")
    prop_tree = ttk.Treeview(prop_frame, columns=prop_cols, show="headings")
    for c in prop_cols:
        prop_tree.heading(c, text=c)
        prop_tree.column(c, width=90)
    psb = ttk.Scrollbar(prop_frame, orient="vertical", command=prop_tree.yview)
    prop_tree.configure(yscrollcommand=psb.set)
    prop_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    psb.pack(side=tk.RIGHT, fill=tk.Y)

    issues_frame = ttk.Frame(nb)
    nb.add(issues_frame, text="Unplaced / conflicts")
    issues_txt = tk.Text(issues_frame, wrap="word")
    issues_txt.pack(fill=tk.BOTH, expand=True)

    # Cache room/instructor names for display.
    room_names, instr_names, headcounts = {}, {}, {}

    def _refresh_lookup_names():
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, COALESCE(building,''), COALESCE(room_number,''), "
                        "COALESCE(capacity,0) FROM rooms")
            for rid, b, num, cap in cur.fetchall():
                room_names[rid] = (f"{b}-{num}".strip("-") or f"Room {rid}", cap)
            cur.execute("SELECT id, COALESCE(first_name,''), COALESCE(last_name,'') "
                        "FROM instructors")
            for iid, f, l in cur.fetchall():
                instr_names[iid] = f"{f} {l}".strip() or f"Instr {iid}"
            cur.execute("SELECT module_code, COUNT(*) FROM student_modules "
                        "WHERE LOWER(COALESCE(status,'enrolled'))='enrolled' "
                        "GROUP BY module_code")
            for code, n in cur.fetchall():
                headcounts[code] = n

    def _build_options():
        return core.Options(
            day_start="09:00", day_end="18:00",
            step_minutes=max(15, step_var.get()),
            same_building_transition=max(0, transition_var.get()),
            cross_building_travel=max(0, travel_var.get()),
            forecast_growth=max(0, growth_var.get()) / 100.0,
            max_local_search_passes=20)

    def _build_weights():
        return core.Weights(**{k: float(v.get()) for k, v in weight_vars.items()})

    def run_simulation():
        prop_tree.delete(*prop_tree.get_children())
        issues_txt.delete("1.0", tk.END)
        summary_var.set("Running simulation…")
        dialog.update_idletasks()
        try:
            _refresh_lookup_names()
            options = _build_options()
            result = self.run_auto_schedule(
                goal=goal_var.get(), weights=_build_weights(), options=options,
                session_duration=max(15, dur_var.get()),
                only_unscheduled=only_unsched_var.get())
        except Exception as e:
            summary_var.set(f"Simulation failed: {e}")
            return
        self._auto_last_result = result

        for a in result.assignments:
            rn, cap = room_names.get(a.room_id, (str(a.room_id), "?"))
            prop_tree.insert("", tk.END, values=(
                a.module_code, a.session_type, a.day, a.start, a.end, rn,
                instr_names.get(a.instructor_id, str(a.instructor_id)),
                headcounts.get(a.module_code, 0), cap))

        placed = result.placed_count
        unplaced = len(result.unplaced)
        summary_var.set(
            f"Placed {placed} module(s); {unplaced} unplaceable. "
            f"Soft cost {result.total_cost:,.1f} "
            f"(gaps {result.breakdown['gaps']:.1f}, underfill "
            f"{result.breakdown['underfill']:.1f}, pref {result.breakdown['pref']:.1f}, "
            f"balance {result.breakdown['day_balance']:.1f}, "
            f"back-to-back {result.breakdown['back_to_back']:.1f}). "
            f"Hard violations: {result.hard_violations}. "
            f"Back-to-back flags: {len(result.back_to_back)}; "
            f"travel violations: {len(result.travel_violations)}.")

        lines = []
        if result.unplaced:
            lines.append("UNPLACEABLE MODULES (no feasible room/slot/instructor):")
            for r in result.unplaced:
                lines.append(f"  • {r.module_code} — needs capacity "
                             f"{r.required_capacity}, {r.duration}min {r.session_type}")
            lines.append("")
        if result.back_to_back:
            lines.append("BACK-TO-BACK (tight transitions):")
            for r in result.back_to_back:
                lines.append(f"  • Instr {r['instructor_id']} {r['day']}: "
                             f"{r['first']} → {r['second']} ({r['gap_minutes']}min gap)")
            lines.append("")
        if result.travel_violations:
            lines.append("TRAVEL-TIME VIOLATIONS:")
            for r in result.travel_violations:
                lines.append(f"  • Instr {r['instructor_id']} {r['day']}: "
                             f"{r['from_building']}→{r['to_building']} "
                             f"only {r['gap_minutes']}min (needs {r['required']})")
        if not lines:
            lines.append("No unplaced modules, back-to-back flags, or travel "
                         "violations. 🎉")
        issues_txt.insert("1.0", "\n".join(lines))

    # ---- Action buttons ----------------------------------------------------
    btns = ttk.Frame(dialog)
    btns.pack(fill=tk.X, padx=10, pady=(4, 10))

    ttk.Button(btns, text="▶ Run simulation", command=run_simulation).pack(side=tk.LEFT, padx=4)

    def _commit(status):
        result = getattr(self, "_auto_last_result", None)
        if not result or not result.assignments:
            messagebox.showwarning("Nothing to commit",
                                   "Run a simulation with at least one placement first.",
                                   parent=dialog)
            return
        label = "sandbox draft" if status == "draft" else "the live timetable"
        if not messagebox.askyesno(
                "Confirm commit",
                f"Write {len(result.assignments)} proposed session(s) to {label}?",
                parent=dialog):
            return
        committed, failed = self._commit_auto_proposals(result, status=status)
        try:
            self.refresh_all_data()
        except Exception:
            pass
        messagebox.showinfo(
            "Commit complete",
            f"Committed {committed} session(s) as {status}."
            + (f" {failed} could not be written (conflicts)." if failed else ""),
            parent=dialog)

    ttk.Button(btns, text="Commit as Draft (sandbox)",
               command=lambda: _commit("draft")).pack(side=tk.LEFT, padx=4)
    ttk.Button(btns, text="Commit as Published (live)",
               command=lambda: _commit("published")).pack(side=tk.LEFT, padx=4)

    def _clear_sandbox():
        if not messagebox.askyesno("Clear sandbox",
                                   "Delete all draft (sandbox) schedule rows?",
                                   parent=dialog):
            return
        removed = self.clear_sandbox_drafts()
        try:
            self.refresh_all_data()
        except Exception:
            pass
        messagebox.showinfo("Sandbox cleared", f"Removed {removed} draft row(s).",
                            parent=dialog)

    ttk.Button(btns, text="Clear sandbox drafts",
               command=_clear_sandbox).pack(side=tk.LEFT, padx=4)
    ttk.Button(btns, text="Discard & Close",
               command=dialog.destroy).pack(side=tk.RIGHT, padx=4)


ModuleSchedulingGUI.show_auto_scheduler_dialog = show_auto_scheduler_dialog
