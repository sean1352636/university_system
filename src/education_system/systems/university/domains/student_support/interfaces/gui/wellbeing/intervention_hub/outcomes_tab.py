"""Interventions window — Outcomes tab.

The former standalone Intervention Outcomes app (``domain/services/
early_warning/outcomes/intervention_outcomes_app.py``), unchanged on
screen: pre/post scores, session log, value-added and the summary for
early-warning interventions. It is now a Frame the Interventions window
embeds; user resolution and the standalone ``main()`` live there.

Persistence: ``intervention_outcomes`` and ``intervention_sessions`` in
the central ``student_records.db``, via ``InterventionOutcomesService``.
"""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.domains.student_support.domain.early_warning.outcomes import (
    InterventionOutcomesService,
    InterventionOutcomesError,
)

logger = logging.getLogger(__name__)

__all__ = ["InterventionOutcomesFrame"]


def _user_display_name(user):
    if not user:
        return 'Guest'
    return (user.get('username') or user.get('email') or
            user.get('user_id') or user.get('id') or 'Unknown')


class InterventionOutcomesFrame(tk.Frame):
    def __init__(self, parent, user=None):
        super().__init__(parent, bg="#ecf0f1")
        self._svc = InterventionOutcomesService()
        self._user = user
        self._user_display = _user_display_name(user)
        self._build()
        self._refresh()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Intervention Outcomes", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=8)
        role = (self._user or {}).get('role') or ('—' if self._user else 'not signed in')
        tk.Label(hdr, text=f"Signed in: {self._user_display}  ({role})",
                 font=("Helvetica", 9), bg="#2c3e50",
                 fg="#bdc3c7").pack(side="right", padx=20, pady=14)

        form = tk.LabelFrame(self, text="Action", bg="#ecf0f1", padx=8, pady=6)
        form.pack(fill="x", padx=10, pady=8)
        labels = ["Intervention ID", "Pre-score", "Post-score",
                  "Session date (YYYY-MM-DD)", "Subject area"]
        self._vars = {l: tk.StringVar() for l in labels}
        for i, l in enumerate(labels):
            tk.Label(form, text=l + ":", bg="#ecf0f1").grid(row=i // 3, column=(i % 3) * 2,
                                                            padx=4, pady=3, sticky="e")
            tk.Entry(form, textvariable=self._vars[l], width=18).grid(
                row=i // 3, column=(i % 3) * 2 + 1, padx=4, pady=3)

        btns = tk.Frame(form, bg="#ecf0f1"); btns.grid(row=2, column=0, columnspan=6, pady=4)
        tk.Button(btns, text="Set Baseline", command=self._baseline).pack(side="left", padx=4)
        tk.Button(btns, text="Record Session", command=self._session).pack(side="left", padx=4)
        tk.Button(btns, text="Set Outcome", command=self._outcome).pack(side="left", padx=4)
        tk.Button(btns, text="Refresh", command=self._refresh).pack(side="left", padx=4)
        tk.Button(btns, text="Summary", command=self._summary).pack(side="left", padx=4)

        cols = ("id", "student", "type", "subject", "sess", "pre", "post", "va", "status")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c in cols:
            self._tree.heading(c, text=c.title()); self._tree.column(c, width=90)
        self._tree.pack(fill="both", expand=True, padx=10, pady=8)

    def prefill(self, intervention_id: int) -> None:
        """Put an intervention's ID in the form (from Student Overview)."""
        self._vars["Intervention ID"].set(str(intervention_id))
        self._refresh()
        for item in self._tree.get_children():
            if str(self._tree.item(item)["values"][0]) == str(intervention_id):
                self._tree.selection_set(item)
                self._tree.see(item)
                break

    def refresh(self) -> None:
        self._refresh()

    def _iid(self) -> int:
        return int(self._vars["Intervention ID"].get().strip())

    def _baseline(self):
        try:
            iid = self._iid()
            pre = float(self._vars["Pre-score"].get())
            self._svc.set_baseline(iid, pre,
                                   subject_area=self._vars["Subject area"].get() or None)
            logger.info("Outcome baseline set intervention=%s pre=%s by=%s",
                        iid, pre, self._user_display)
            messagebox.showinfo("OK", "Baseline saved."); self._refresh()
        except (InterventionOutcomesError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def _session(self):
        try:
            iid = self._iid()
            session_date = self._vars["Session date (YYYY-MM-DD)"].get().strip()
            self._svc.record_session(iid, session_date,
                                     recorded_by=self._user_display or None)
            logger.info("Outcome session recorded intervention=%s date=%s by=%s",
                        iid, session_date, self._user_display)
            messagebox.showinfo("OK", "Session recorded."); self._refresh()
        except (InterventionOutcomesError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def _outcome(self):
        try:
            iid = self._iid()
            post = float(self._vars["Post-score"].get())
            out = self._svc.set_outcome(iid, post)
            logger.info("Outcome final score set intervention=%s post=%s value_added=%s by=%s",
                        iid, post, out.get('value_added'), self._user_display)
            messagebox.showinfo("OK", f"value_added = {out.get('value_added')}"); self._refresh()
        except (InterventionOutcomesError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def _refresh(self):
        for r in self._tree.get_children(): self._tree.delete(r)
        try:
            for r in self._svc.list_with_outcomes():
                self._tree.insert("", "end", values=(
                    r["intervention_id"], r.get("student_id", "-"),
                    r.get("intervention_type", "-"), r.get("subject_area", "-") or "-",
                    f"{r.get('sessions_completed') or 0}/{r.get('sessions_total') or 0}",
                    r.get("pre_assessment_score", "-"), r.get("post_assessment_score", "-"),
                    r.get("value_added", "-"), r.get("status", "-"),
                ))
        except InterventionOutcomesError as e:
            messagebox.showerror("Error", str(e))

    def _summary(self):
        s = self._svc.summary()
        messagebox.showinfo("Summary",
            f"Interventions:        {s.get('interventions', 0)}\n"
            f"With baseline:        {s.get('with_baseline', 0)}\n"
            f"With outcome:         {s.get('with_outcome', 0)}\n"
            f"Positive value-added: {s.get('positive_value_added', 0)}\n"
            f"Avg value-added:      {s.get('avg_value_added')}\n"
            f"Sessions:             {s.get('total_sessions_completed', 0)}/{s.get('total_sessions_planned', 0)}")
