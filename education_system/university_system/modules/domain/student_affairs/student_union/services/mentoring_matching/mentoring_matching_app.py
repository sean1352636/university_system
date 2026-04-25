"""Standalone Tk launcher for Peer Mentoring Matching."""
from __future__ import annotations

import sys, pathlib  # noqa: E401
_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.university_system.modules.domain.student_affairs.student_union.services.mentoring_matching import (
    MentoringMatchingService,
    MentoringMatchingError,
)


class _Frame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#ecf0f1")
        self._svc = MentoringMatchingService()
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Peer Mentoring Matching",
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white").pack(
            side="left", padx=20, pady=8)

        prof = tk.LabelFrame(self, text="Mentor profile (CSV fields)", bg="#ecf0f1", padx=8, pady=4)
        prof.pack(fill="x", padx=10, pady=4)
        self._mvars = {l: tk.StringVar() for l in
                       ("Mentor ID", "Course", "Strengths", "Availability",
                        "Languages", "Max mentees")}
        for i, l in enumerate(self._mvars):
            tk.Label(prof, text=l + ":", bg="#ecf0f1").grid(row=i // 3, column=(i % 3) * 2,
                                                            padx=4, pady=2, sticky="e")
            tk.Entry(prof, textvariable=self._mvars[l], width=18).grid(
                row=i // 3, column=(i % 3) * 2 + 1, padx=4, pady=2)
        tk.Button(prof, text="Save Mentor", command=self._save_mentor).grid(
            row=2, column=5, padx=8, pady=4)

        pref = tk.LabelFrame(self, text="Mentee preferences (CSV fields)", bg="#ecf0f1", padx=8, pady=4)
        pref.pack(fill="x", padx=10, pady=4)
        self._pvars = {l: tk.StringVar() for l in
                       ("Mentee ID", "Course", "Goals", "Availability", "Languages")}
        for i, l in enumerate(self._pvars):
            tk.Label(pref, text=l + ":", bg="#ecf0f1").grid(row=i // 3, column=(i % 3) * 2,
                                                            padx=4, pady=2, sticky="e")
            tk.Entry(pref, textvariable=self._pvars[l], width=18).grid(
                row=i // 3, column=(i % 3) * 2 + 1, padx=4, pady=2)
        tk.Button(pref, text="Save Mentee", command=self._save_mentee).grid(
            row=2, column=5, padx=8, pady=4)
        tk.Button(pref, text="Recommend Mentors", command=self._recommend).grid(
            row=2, column=4, padx=8, pady=4)
        tk.Button(pref, text="Outcomes Summary", command=self._summary).grid(
            row=2, column=3, padx=8, pady=4)

        cols = ("rank", "mentor_id", "score", "reasons")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        for c in cols: self._tree.heading(c, text=c.title()); self._tree.column(c, width=160)
        self._tree.pack(fill="both", expand=True, padx=10, pady=8)

    def _save_mentor(self):
        try:
            v = self._mvars
            self._svc.upsert_mentor_profile(
                int(v["Mentor ID"].get()),
                course=v["Course"].get(), strengths_csv=v["Strengths"].get(),
                availability_csv=v["Availability"].get(),
                languages_csv=v["Languages"].get(),
                max_mentees=int(v["Max mentees"].get() or 3),
            )
            messagebox.showinfo("OK", "Mentor profile saved.")
        except (MentoringMatchingError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def _save_mentee(self):
        try:
            v = self._pvars
            self._svc.upsert_mentee_preferences(
                int(v["Mentee ID"].get()),
                course=v["Course"].get(),
                learning_goals_csv=v["Goals"].get(),
                availability_csv=v["Availability"].get(),
                preferred_languages_csv=v["Languages"].get(),
            )
            messagebox.showinfo("OK", "Mentee prefs saved.")
        except (MentoringMatchingError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def _recommend(self):
        try:
            mid = int(self._pvars["Mentee ID"].get())
            recs = self._svc.recommend_mentors(mid, top_n=5)
        except (MentoringMatchingError, ValueError) as e:
            messagebox.showerror("Error", str(e)); return
        for r in self._tree.get_children(): self._tree.delete(r)
        for i, r in enumerate(recs, 1):
            self._tree.insert("", "end", values=(i, r["mentor_id"], r["score"],
                                                 "; ".join(r.get("reasons", []))))

    def _summary(self):
        mid = simpledialog.askinteger("Summary", "Mentor ID (Cancel for all):", parent=self)
        s = self._svc.outcomes_summary(mentor_id=mid) if mid else self._svc.outcomes_summary()
        messagebox.showinfo("Summary",
            f"Count:                {s.get('count', 0)}\n"
            f"Avg confidence delta: {s.get('avg_confidence_delta')}\n"
            f"Avg satisfaction:     {s.get('avg_satisfaction')}\n"
            f"% would recommend:    {s.get('pct_would_recommend')}")


def main() -> None:
    root = tk.Tk()
    root.title("Peer Mentoring Matching"); root.geometry("960x620")
    _Frame(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
