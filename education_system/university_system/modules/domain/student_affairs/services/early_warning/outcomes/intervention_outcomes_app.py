"""Standalone Tk launcher for Intervention Outcomes.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The header shows the signed-in user, and
session-recording calls stamp the user's name on the row.

Persistence: data lives in the central `student_records.db`
(tables `intervention_outcomes` and `intervention_sessions` managed
by the underlying service). Any stray *.db files alongside this
module are removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""
from __future__ import annotations

import logging
import os
import pathlib
import sys
import tkinter as tk
from tkinter import ttk, messagebox

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


from education_system.university_system.modules.domain.student_affairs.services.early_warning.outcomes import (  # noqa: E402
    InterventionOutcomesService,
    InterventionOutcomesError,
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
    """Sweep any stray local SQLite files left alongside this module by
    earlier iterations. Data lives in the central student_records.db."""
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(here):
        return
    for fname in os.listdir(here):
        if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
            path = os.path.join(here, fname)
            try:
                os.remove(path)
                logger.info("Removed legacy outcomes DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


class _Frame(tk.Frame):
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


def main() -> None:
    _remove_legacy_db()
    user = _get_current_user()
    logger.info("Intervention Outcomes starting user=%s role=%s",
                _user_display_name(user),
                (user or {}).get('role') or 'none')
    root = tk.Tk()
    root.title("Intervention Outcomes")
    root.geometry("960x600")
    _Frame(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
