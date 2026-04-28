"""Standalone Tk launcher for Peer Mentoring Matching.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The header shows the signed-in user; key
write actions are stamped with that identity in the log.

Persistence: data lives in the central `student_records.db` (tables
`mentor_profiles`, `mentee_preferences`, `mentor_match_recommendations`,
`mentoring_outcomes` managed by `MentoringMatchingService`). The
service's previous `:memory:` default is gone — it now uses the shared
`get_connection()` when no explicit `db_path` is supplied. Any stray
*.db files alongside this module are removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""
from __future__ import annotations

import logging
import os
import pathlib
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


from education_system.university_system.modules.domain.student_affairs.student_union.services.mentoring_matching import (  # noqa: E402
    MentoringMatchingService,
    MentoringMatchingError,
)


def _get_current_user():
    """Resolve the logged-in user dict from EDU_AUTH_* env vars, with a
    fallback to the in-process global auth singleton."""
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': role,
            'email': email,
            'permissions': [p for p in perms_raw.split(',') if p],
        }
    try:
        from education_system.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _user_display_name(user):
    if not user:
        return 'Guest'
    return (user.get('username') or user.get('email') or
            user.get('user_id') or user.get('id') or 'Unknown')


def _remove_legacy_db():
    """Sweep any stray local SQLite files left alongside this module
    by earlier iterations. Data lives in the central student_records.db."""
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(here):
        return
    for fname in os.listdir(here):
        if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
            path = os.path.join(here, fname)
            try:
                os.remove(path)
                logger.info("Removed legacy mentoring-matching DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


class _Frame(tk.Frame):
    def __init__(self, parent, user=None):
        super().__init__(parent, bg="#ecf0f1")
        # Pass db_path=None so the service hits the central
        # student_records.db (its constructor used to default to
        # :memory:, which silently lost everything between launches).
        self._svc = MentoringMatchingService(db_path=None)
        self._user = user
        self._user_display = _user_display_name(user)
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Peer Mentoring Matching",
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white").pack(
            side="left", padx=20, pady=8)
        role = (self._user or {}).get('role') or ('—' if self._user else 'not signed in')
        tk.Label(hdr, text=f"Signed in: {self._user_display}  ({role})",
                 font=("Helvetica", 9), bg="#2c3e50",
                 fg="#bdc3c7").pack(side="right", padx=20, pady=14)

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
            mid = int(v["Mentor ID"].get())
            self._svc.upsert_mentor_profile(
                mid,
                course=v["Course"].get(), strengths_csv=v["Strengths"].get(),
                availability_csv=v["Availability"].get(),
                languages_csv=v["Languages"].get(),
                max_mentees=int(v["Max mentees"].get() or 3),
            )
            logger.info("Mentor profile saved mentor_id=%s by=%s", mid, self._user_display)
            messagebox.showinfo("OK", "Mentor profile saved.")
        except (MentoringMatchingError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def _save_mentee(self):
        try:
            v = self._pvars
            mid = int(v["Mentee ID"].get())
            self._svc.upsert_mentee_preferences(
                mid,
                course=v["Course"].get(),
                learning_goals_csv=v["Goals"].get(),
                availability_csv=v["Availability"].get(),
                preferred_languages_csv=v["Languages"].get(),
            )
            logger.info("Mentee preferences saved mentee_id=%s by=%s", mid, self._user_display)
            messagebox.showinfo("OK", "Mentee prefs saved.")
        except (MentoringMatchingError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def _recommend(self):
        try:
            mid = int(self._pvars["Mentee ID"].get())
            recs = self._svc.recommend_mentors(mid, top_n=5)
            logger.info("Mentor recommendations generated mentee_id=%s count=%s by=%s",
                        mid, len(recs), self._user_display)
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
    _remove_legacy_db()
    user = _get_current_user()
    logger.info("Mentoring Matching starting user=%s role=%s",
                _user_display_name(user),
                (user or {}).get('role') or 'none')
    root = tk.Tk()
    root.title("Peer Mentoring Matching"); root.geometry("960x620")
    _Frame(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
