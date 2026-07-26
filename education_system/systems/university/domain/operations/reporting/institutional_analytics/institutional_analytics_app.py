"""Standalone Tk launcher for Institutional Analytics.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity, shown in the header.

Data: computed live from the central ``student_records.db`` via
``InstitutionalAnalyticsService`` (read-only aggregate queries).

Logging: routed through the shared rotating ``app.log`` via
``infrastructure.logging.log_config.configure_logging``.
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
    from education_system.systems.university.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; using default handlers", exc_info=True)


from education_system.systems.university.domain.operations.reporting.institutional_analytics import (  # noqa: E402
    InstitutionalAnalyticsError,
    InstitutionalAnalyticsService,
)


def _get_current_user():
    user_id = os.environ.get("EDU_AUTH_USER_ID") or ""
    username = os.environ.get("EDU_AUTH_USERNAME") or ""
    role = os.environ.get("EDU_AUTH_ROLE") or ""
    if user_id or username:
        return {"user_id": user_id or None, "username": username, "role": role}
    try:
        from education_system.systems.university.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, "current_user", None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _user_display_name(user):
    if not user:
        return "Guest"
    return user.get("username") or user.get("user_id") or "Unknown"


def _pct(v):
    return "-" if v is None else f"{v:.2f}%"


def _money(v):
    if v is None:
        return "-"
    try:
        return f"£{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


class _Frame(tk.Frame):
    def __init__(self, parent, user=None):
        super().__init__(parent, bg="#ecf0f1")
        self._svc = InstitutionalAnalyticsService()
        self._user_display = _user_display_name(user)
        self._role = (user or {}).get("role") or ("—" if user else "not signed in")
        self._build()
        self._refresh()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Institutional Analytics", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=8)
        tk.Label(hdr, text=f"Signed in: {self._user_display}  ({self._role})",
                 font=("Helvetica", 9), bg="#2c3e50", fg="#bdc3c7").pack(
            side="right", padx=20, pady=14)

        ctrl = tk.Frame(self, bg="#ecf0f1"); ctrl.pack(fill="x", padx=10, pady=6)
        tk.Button(ctrl, text="Refresh", command=self._refresh).pack(side="left", padx=4)

        # Headline KPI strip
        self._headline = tk.Frame(self, bg="#ecf0f1")
        self._headline.pack(fill="x", padx=10, pady=(0, 6))

        # Tabbed detail views
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=8)
        self._tabs: dict[str, ttk.Treeview] = {}
        for name, cols in (
            ("Enrolment", ("course", "students")),
            ("Retention", ("course", "n", "retention%", "attrition%", "completion%")),
            ("Modules", ("module", "enrolments", "pass%", "in_progress")),
            ("Capacity", ("course", "enrolled", "capacity", "fill%")),
            ("Finance", ("item", "value")),
        ):
            frame = tk.Frame(self._nb)
            tree = ttk.Treeview(frame, columns=cols, show="headings")
            for c in cols:
                tree.heading(c, text=c.title())
                tree.column(c, width=140 if c in ("course", "module", "item") else 100)
            tree.pack(fill="both", expand=True)
            frame.pack(fill="both", expand=True)
            self._nb.add(frame, text=name)
            self._tabs[name] = tree

    def _kpi_card(self, label, value, color="#34495e"):
        card = tk.Frame(self._headline, bg=color, padx=12, pady=8)
        card.pack(side="left", padx=4)
        tk.Label(card, text=value, font=("Helvetica", 13, "bold"),
                 bg=color, fg="white").pack()
        tk.Label(card, text=label, font=("Helvetica", 8),
                 bg=color, fg="#ecf0f1").pack()

    def _clear(self):
        for w in self._headline.winfo_children():
            w.destroy()
        for tree in self._tabs.values():
            for r in tree.get_children():
                tree.delete(r)

    def _refresh(self):
        self._clear()
        try:
            data = self._svc.institutional_overview()
        except InstitutionalAnalyticsError as e:
            messagebox.showerror("Error", str(e)); return
        h = data["headline"]
        self._kpi_card("Students", str(h.get("total_students") or "-"), "#2980b9")
        self._kpi_card("Retention", _pct(h.get("retention_rate")), "#27ae60")
        self._kpi_card("Fill rate", _pct(h.get("overall_fill_rate")), "#8e44ad")
        self._kpi_card("Pass rate", _pct(h.get("module_pass_rate")), "#16a085")
        self._kpi_card("Revenue", _money(h.get("revenue_collected")), "#d35400")

        sec = data["sections"]
        for row in sec.get("enrollment", {}).get("by_course", []):
            self._tabs["Enrolment"].insert("", "end", values=(row["label"], row["count"]))
        for c in sec.get("retention", {}).get("by_course", []):
            self._tabs["Retention"].insert("", "end", values=(
                c["course"], c["total"], _pct(c["retention_rate"]),
                _pct(c["attrition_rate"]), _pct(c["completion_rate"])))
        for m in sec.get("modules", {}).get("modules", [])[:50]:
            self._tabs["Modules"].insert("", "end", values=(
                m["module_name"] or m["module_code"], m["enrolments"],
                _pct(m["pass_rate"]), m["in_progress"]))
        for c in sec.get("capacity", {}).get("courses", []):
            self._tabs["Capacity"].insert("", "end", values=(
                c["course_name"] or c["course_code"], c["enrolled"],
                c["capacity"], _pct(c["fill_rate"])))
        fin = sec.get("finance", {})
        rev = fin.get("revenue", {})
        ft = self._tabs["Finance"]
        if rev:
            ft.insert("", "end", values=("Revenue collected", _money(rev.get("collected_total"))))
            for method, amt in rev.get("by_method", {}).items():
                ft.insert("", "end", values=(f"  via {method}", _money(amt)))
        fees = fin.get("fees", {})
        if fees:
            ft.insert("", "end", values=("Fees outstanding", _money(fees.get("outstanding_total"))))
            ft.insert("", "end", values=("Fees waived", _money(fees.get("waived_total"))))


def main() -> None:
    user = _get_current_user()
    logger.info("Institutional Analytics starting user=%s", _user_display_name(user))
    root = tk.Tk()
    root.title("Institutional Analytics"); root.geometry("980x620")
    _Frame(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
