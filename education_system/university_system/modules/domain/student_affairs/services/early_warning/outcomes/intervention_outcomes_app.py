"""Standalone Tk launcher for Intervention Outcomes."""
from __future__ import annotations

import sys, pathlib  # noqa: E401
_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.domain.student_affairs.services.early_warning.outcomes import (
    InterventionOutcomesService,
    InterventionOutcomesError,
)


class _Frame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#ecf0f1")
        self._svc = InterventionOutcomesService()
        self._build()
        self._refresh()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Intervention Outcomes", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=8)

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

    def _iid(self) -> int:
        return int(self._vars["Intervention ID"].get().strip())

    def _baseline(self):
        try:
            self._svc.set_baseline(self._iid(), float(self._vars["Pre-score"].get()),
                                   subject_area=self._vars["Subject area"].get() or None)
            messagebox.showinfo("OK", "Baseline saved."); self._refresh()
        except (InterventionOutcomesError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def _session(self):
        try:
            self._svc.record_session(self._iid(),
                                     self._vars["Session date (YYYY-MM-DD)"].get().strip())
            messagebox.showinfo("OK", "Session recorded."); self._refresh()
        except (InterventionOutcomesError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def _outcome(self):
        try:
            out = self._svc.set_outcome(self._iid(), float(self._vars["Post-score"].get()))
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


def main() -> None:
    root = tk.Tk()
    root.title("Intervention Outcomes")
    root.geometry("960x600")
    _Frame(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
