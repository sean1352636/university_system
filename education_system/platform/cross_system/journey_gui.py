"""Student Journey panel — the single student view, as a Tkinter frame.

A read-only GUI over
:func:`education_system.platform.cross_system.student_view.build_overview`:
look a learner up by canonical ``journey_id`` or by any system's local
student id, and see their whole history across all five systems —
demographics, each phase's record, attendance and results, and the
transition timeline.

Follows the shared-frame convention used by the analytics / GDPR / admin
panels: a ``tk.Frame`` subclass taking ``(parent, db_path=None, auth=None)``
that the host packs with ``fill='both', expand=True``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from education_system.platform.cross_system import (
    journey_cli,
    progression,
    student_view,
)
from education_system.platform.kernel.database.paths import SYSTEM_LABELS, SYSTEM_ORDER

_HEADER_BG = "#1a5276"
_BODY_BG = "#ecf0f1"
_CARD_BG = "white"

# Lookup modes for the selector: label -> system key (None = canonical id).
_LOOKUP_MODES = [("Journey ID", None)] + [
    (SYSTEM_LABELS.get(s, s.title()) + " student ID", s) for s in SYSTEM_ORDER
]


class StudentJourneyFrame(tk.Frame):
    """Cross-system single student view."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._build_ui()
        self._prefill_from_auth()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg=_BODY_BG)

        header = tk.Frame(self, bg=_HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Student Journey", font=("Helvetica", 15, "bold"),
            bg=_HEADER_BG, fg="white",
        ).pack(side="left", padx=20, pady=10)

        # ── Lookup bar ────────────────────────────────────────────────
        bar = tk.Frame(self, bg=_BODY_BG)
        bar.pack(fill="x", padx=15, pady=(10, 4))

        tk.Label(bar, text="Look up by:", bg=_BODY_BG).pack(side="left")
        self._mode_var = tk.StringVar(value=_LOOKUP_MODES[-1][0])  # university
        self._mode_box = ttk.Combobox(
            bar, textvariable=self._mode_var, state="readonly", width=24,
            values=[label for label, _ in _LOOKUP_MODES])
        self._mode_box.pack(side="left", padx=(6, 12))

        self._id_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self._id_var, width=32)
        entry.pack(side="left")
        entry.bind("<Return>", lambda _e: self._lookup())

        ttk.Button(bar, text="View", command=self._lookup).pack(
            side="left", padx=8)

        self._status = tk.Label(self, text="", bg=_BODY_BG, fg="#7b241c",
                                font=("Helvetica", 9, "italic"))
        self._status.pack(fill="x", padx=18, anchor="w")

        # ── Scrollable result area ────────────────────────────────────
        outer = tk.Frame(self, bg=_BODY_BG)
        outer.pack(fill="both", expand=True, padx=15, pady=(4, 12))
        self._canvas = tk.Canvas(outer, bg=_BODY_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical",
                            command=self._canvas.yview)
        self._results = tk.Frame(self._canvas, bg=_BODY_BG)
        self._results.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._results, anchor="nw")
        self._canvas.configure(yscrollcommand=vsb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _prefill_from_auth(self):
        """If a student is logged in, pre-load their own journey."""
        try:
            cu = getattr(self._auth, "current_user", None) or {}
            sid = cu.get("student_id")
            if sid:
                self._mode_var.set(_LOOKUP_MODES[-1][0])  # university
                self._id_var.set(str(sid))
                self._lookup()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Lookup + render
    # ------------------------------------------------------------------

    def _selected_system(self):
        label = self._mode_var.get()
        for lbl, sys in _LOOKUP_MODES:
            if lbl == label:
                return sys
        return None

    def _lookup(self):
        key = (self._id_var.get() or "").strip()
        self._clear_results()
        if not key:
            self._status.config(text="Enter an ID to look up.")
            return
        system = self._selected_system()
        try:
            if system is None:
                overview = student_view.build_overview(key)
            else:
                overview = student_view.build_overview_for_student(system, key)
        except Exception as exc:  # defensive; the service is best-effort
            self._status.config(text=f"Lookup failed: {exc}")
            return
        if not overview.get("found"):
            self._status.config(
                text="No journey found for that identifier.")
            return
        self._status.config(text="")
        self._render(overview)

    def _clear_results(self):
        for w in self._results.winfo_children():
            w.destroy()

    def _render(self, overview: dict):
        self._overview = overview
        p = overview.get("person", {})
        # ── Person header card ────────────────────────────────────────
        card = tk.Frame(self._results, bg=_CARD_BG, bd=1, relief="groove",
                        padx=16, pady=12)
        card.pack(fill="x", pady=(0, 10))
        tk.Label(card, text=p.get("full_name", "?"), bg=_CARD_BG,
                 font=("Helvetica", 16, "bold")).pack(anchor="w")
        self._maybe_add_promote(card, overview)
        meta = (
            f"DOB: {p.get('date_of_birth') or '—'}     "
            f"UPN: {p.get('upn') or '—'}     "
            f"NHS: {p.get('nhs_number') or '—'}")
        tk.Label(card, text=meta, bg=_CARD_BG,
                 font=("Helvetica", 10)).pack(anchor="w", pady=(2, 0))
        tk.Label(
            card,
            text=f"Currently: {p.get('current_system') or '—'} "
                 f"({p.get('status') or '—'})     "
                 f"Journey {overview.get('journey_id', '')}",
            bg=_CARD_BG, fg="#555", font=("Helvetica", 9)).pack(anchor="w")

        # ── Per-phase cards ───────────────────────────────────────────
        for phase in overview.get("phases", []):
            self._render_phase(phase)

        # ── Transitions timeline ──────────────────────────────────────
        transitions = overview.get("transitions", [])
        if transitions:
            self._render_transitions(transitions)

    def _promote_source(self, overview: dict):
        """The (system, local_id) a learner would be promoted *from* — their
        current phase — or None if promotion isn't possible from here."""
        current = (overview.get("person") or {}).get("current_system")
        if not current or progression.next_phase(current) is None:
            return None
        if journey_cli.promote_kind(current) is None:
            return None
        for phase in overview.get("phases", []):
            if phase.get("system") == current and phase.get("student_id"):
                return current, phase["student_id"]
        return None

    def _maybe_add_promote(self, card, overview: dict):
        src = self._promote_source(overview)
        if not src:
            return
        system, sid = src
        nxt = progression.next_phase(system)
        label = SYSTEM_LABELS.get(nxt, nxt.title())
        ttk.Button(
            card, text=f"Promote to {label} ▶",
            command=lambda: self._promote(system, sid, nxt, label)
        ).pack(anchor="w", pady=(8, 0))

    def _promote(self, system: str, student_id: str, nxt: str, label: str):
        if not messagebox.askyesno(
                "Promote learner",
                f"Promote {student_id} from {SYSTEM_LABELS.get(system, system)} "
                f"to {label}?\n\nThis creates their record in the next system "
                "and is hard to undo."):
            return
        extra = {}
        if journey_cli.promote_kind(system) == "subjects":
            for i in (1, 2, 3):
                val = simpledialog.askstring(
                    "A-Level subjects", f"A-Level subject {i}:", parent=self)
                if not val:
                    messagebox.showinfo("Cancelled",
                                        "Three subjects are required.")
                    return
                extra[f"subject_{i}"] = val.strip()
        try:
            journey_cli.promote(system, student_id, **extra)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Promotion failed", str(exc))
            return
        messagebox.showinfo("Promoted",
                            f"{student_id} promoted to {label}.")
        # Refresh the view so the new phase shows immediately.
        self._lookup()

    def _render_phase(self, phase: dict):
        lf = ttk.LabelFrame(
            self._results,
            text=f"  {phase.get('label', phase['system'])}  "
                 f"[{phase.get('student_id', '')}]  ")
        lf.pack(fill="x", pady=6)

        record = phase.get("record") or {}
        if record:
            grid = tk.Frame(lf)
            grid.pack(fill="x", padx=10, pady=6)
            for i, (k, v) in enumerate(record.items()):
                if v in (None, ""):
                    continue
                r, c = divmod(i, 3)
                cell = tk.Frame(grid)
                cell.grid(row=r, column=c, sticky="w", padx=8, pady=2)
                tk.Label(cell, text=f"{k.replace('_', ' ').title()}: ",
                         font=("Helvetica", 9, "bold")).pack(side="left")
                tk.Label(cell, text=str(v),
                         font=("Helvetica", 9)).pack(side="left")

        att = phase.get("attendance")
        if att:
            marks = "  ".join(f"{m}={n}" for m, n in att["by_mark"].items())
            tk.Label(lf, text=f"Attendance: {att['total']} record(s)   {marks}",
                     font=("Helvetica", 9)).pack(anchor="w", padx=10, pady=(0, 4))

        results = phase.get("results")
        if results:
            self._render_results_tree(lf, results)

    @staticmethod
    def _render_results_tree(parent, results: list[dict]):
        cols = list(results[0].keys())
        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill="x", padx=10, pady=(0, 6))
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                            height=min(len(results), 6))
        for c in cols:
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=120, anchor="w")
        for row in results:
            tree.insert("", tk.END,
                        values=[row.get(c, "") for c in cols])
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.columnconfigure(0, weight=1)

    def _render_transitions(self, transitions: list[dict]):
        lf = ttk.LabelFrame(self._results, text="  Transitions  ")
        lf.pack(fill="x", pady=6)
        for t in transitions:
            line = (f"{t.get('occurred_at', '?')}   "
                    f"{t.get('from_system') or '—'} → {t.get('to_system')}")
            if t.get("reason"):
                line += f"   · {t['reason']}"
            tk.Label(lf, text=line, font=("Helvetica", 9)).pack(
                anchor="w", padx=10, pady=1)


__all__ = ["StudentJourneyFrame"]
