"""Standalone Tk launcher for the KPI Dashboard.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The header shows the signed-in user, and
KPI updates are stamped with that identity in the log.

Persistence: data lives in the central `student_records.db` (KPI and
dashboard tables managed by the underlying service). Any stray *.db
files alongside this module are removed on startup.

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


from education_system.university_system.modules.domain.analytics.kpi_dashboard import (  # noqa: E402
    KpiDashboardService,
    KpiDashboardError,
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
                logger.info("Removed legacy KPI DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


class _Frame(tk.Frame):
    def __init__(self, parent, user=None):
        super().__init__(parent, bg="#ecf0f1")
        self._svc = KpiDashboardService()
        self._user = user
        self._user_display = _user_display_name(user)
        self._build()
        self._refresh()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Institutional KPI Dashboard",
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white").pack(
            side="left", padx=20, pady=8)
        role = (self._user or {}).get('role') or ('—' if self._user else 'not signed in')
        tk.Label(hdr, text=f"Signed in: {self._user_display}  ({role})",
                 font=("Helvetica", 9), bg="#2c3e50",
                 fg="#bdc3c7").pack(side="right", padx=20, pady=14)

        ctrl = tk.Frame(self, bg="#ecf0f1"); ctrl.pack(fill="x", padx=10, pady=6)
        tk.Button(ctrl, text="Refresh KPIs", command=self._refresh).pack(side="left", padx=4)
        tk.Button(ctrl, text="Update KPI Actual", command=self._update_actual).pack(side="left", padx=4)
        tk.Button(ctrl, text="View Dashboard", command=self._view_dashboard).pack(side="left", padx=4)

        cols = ("id", "name", "category", "current", "target", "status", "progress%")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c in cols:
            self._tree.heading(c, text=c.title()); self._tree.column(c, width=110)
        self._tree.pack(fill="both", expand=True, padx=10, pady=8)

    def _refresh(self):
        for r in self._tree.get_children(): self._tree.delete(r)
        try:
            for k in self._svc.list_kpis():
                kid = k.get("kpi_id") or k.get("id")
                st = self._svc.kpi_status(kid)
                self._tree.insert("", "end", values=(
                    kid, k.get("name") or k.get("kpi_name", "-"),
                    k.get("kpi_category") or k.get("category", "-"),
                    k.get("current_value", "-"), k.get("target_value", "-"),
                    st.get("status", "-"),
                    f"{(st.get('progress') or 0) * 100:.1f}",
                ))
        except KpiDashboardError as e:
            messagebox.showerror("Error", str(e))

    def _update_actual(self):
        kid = simpledialog.askinteger("KPI", "KPI ID:", parent=self)
        if kid is None: return
        val = simpledialog.askfloat("KPI", "New current value:", parent=self)
        if val is None: return
        try:
            self._svc.update_kpi_actual(kid, val)
            logger.info("KPI actual updated kpi_id=%s value=%s by=%s",
                        kid, val, self._user_display)
            self._refresh()
        except KpiDashboardError as e:
            messagebox.showerror("Error", str(e))

    def _view_dashboard(self):
        did = simpledialog.askinteger("Dashboard", "Dashboard ID:", parent=self)
        if did is None: return
        try:
            d = self._svc.get_dashboard(did)
        except KpiDashboardError as e:
            messagebox.showerror("Error", str(e)); return
        win = tk.Toplevel(self); win.title(f"Dashboard #{did}"); win.geometry("680x420")
        txt = tk.Text(win, wrap="word"); txt.pack(fill="both", expand=True, padx=10, pady=10)
        meta = d.get("dashboard") or d
        txt.insert("end", f"Dashboard: {meta.get('name', meta.get('dashboard_name','-'))}\n")
        txt.insert("end", f"Owner: {meta.get('owner_id','-')}\n\n")
        for w in d.get("widgets", []):
            kpi = w.get("resolved_kpi") or w.get("kpi")
            txt.insert("end", f"  • {w.get('title') or w.get('widget_name','widget')}\n")
            if kpi:
                txt.insert("end", f"      KPI {kpi.get('kpi_id') or kpi.get('id')}: "
                                  f"{kpi.get('current_value')} / {kpi.get('target_value')}\n")
        txt.config(state="disabled")


def main() -> None:
    _remove_legacy_db()
    user = _get_current_user()
    logger.info("KPI Dashboard starting user=%s role=%s",
                _user_display_name(user),
                (user or {}).get('role') or 'none')
    root = tk.Tk()
    root.title("KPI Dashboard"); root.geometry("960x600")
    _Frame(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
