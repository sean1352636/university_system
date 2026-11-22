"""GUI panels for the Sixth Form User Management module.

Tabbed view that focuses on roles and access (the user-CRUD lives in
the existing User Accounts window):

  * Summary  — headline counts (active / locked / admins / by role)
  * Access matrix — per-system users + role breakdown
  * Users — full user table with checkboxes for bulk actions
              (grant role, revoke access, activate/deactivate)

Split 2026-10-22: this module is now a facade. The window entry point lives
here; the tab builders and dialogs live in sibling modules (_common, tab_*,
dialogs_user) and every name is re-exported from here unchanged.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from typing import Any
from education_system.systems.sixth_form.domain.governance.user_management import integrations as integ

# Re-export everything that used to be defined in this module.
from ._common import (
    _clear,
    _heading,
)
from .tab_users import (
    _build_summary_tab,
    _build_matrix_tab,
    _build_users_tab,
    _build_archived_tab,
)
from .tab_bulk import (
    _build_bulk_tab,
)
from .tab_security import (
    _build_security_tab,
)
from .tab_policy import (
    _build_policy_tab,
)
from .tab_monitoring import (
    _build_monitoring_tab,
)
from .tab_compliance import (
    _build_compliance_tab,
)
from .tab_integrations import (
    _build_integrations_tab,
)


def open_user_management_window(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "User Management")

    if not getattr(gui, "auth", None):
        ttk.Label(frame, text="No active session — cannot load users.",
                  foreground="#a33").pack(anchor="w")
        return

    # ── Quick search bar (#48) — always visible. ──
    qs = ttk.Frame(frame)
    qs.pack(fill="x", pady=(0, 6))
    ttk.Label(qs, text="🔎 Quick search:").pack(side="left",
                                                   padx=(0, 4))
    qs_var = tk.StringVar()
    qs_entry = ttk.Entry(qs, textvariable=qs_var, width=40)
    qs_entry.pack(side="left", padx=(0, 4))
    qs_result_var = tk.StringVar()
    ttk.Label(qs, textvariable=qs_result_var,
              foreground="#444").pack(side="left", padx=(8, 0))

    def _do_quick_search(_e=None):
        rows = integ.quick_search(gui.auth, qs_var.get(), limit=15)
        if not rows:
            qs_result_var.set("(no matches)")
            return
        names = ", ".join(
            f"#{r['id']} {r['username']}"
            + (f" ({r['display_name']})" if r['display_name'] else "")
            for r in rows[:5])
        suffix = f" …+{len(rows) - 5} more" if len(rows) > 5 else ""
        qs_result_var.set(names + suffix)

    qs_entry.bind("<Return>", _do_quick_search)
    ttk.Button(qs, text="Find",
               command=_do_quick_search).pack(side="left", padx=(4, 0))

    nb = SidebarBook(frame)
    nb.pack(fill="both", expand=True)

    summary_tab = ttk.Frame(nb, padding=8)
    matrix_tab = ttk.Frame(nb, padding=8)
    users_tab = ttk.Frame(nb, padding=8)
    archived_tab = ttk.Frame(nb, padding=8)
    bulk_tab = ttk.Frame(nb, padding=8)
    security_tab = ttk.Frame(nb, padding=8)
    policy_tab = ttk.Frame(nb, padding=8)
    monitoring_tab = ttk.Frame(nb, padding=8)
    compliance_tab = ttk.Frame(nb, padding=8)
    integ_tab = ttk.Frame(nb, padding=8)
    nb.add(summary_tab, text="Summary")
    nb.add(matrix_tab,  text="Access matrix")
    nb.add(users_tab,   text="Users & bulk actions")
    nb.add(archived_tab, text="Archived")
    nb.add(bulk_tab,    text="Bulk & onboarding")
    nb.add(security_tab, text="Security")
    nb.add(policy_tab,  text="Access policy")
    nb.add(monitoring_tab, text="Monitoring")
    nb.add(compliance_tab, text="Compliance")
    nb.add(integ_tab, text="Integrations")

    state: dict[str, Any] = {
        "refresh_summary": None,
        "refresh_matrix":  None,
        "refresh_users":   None,
        "refresh_archived": None,
    }

    def refresh_all() -> None:
        for k in ("refresh_summary", "refresh_matrix",
                  "refresh_users", "refresh_archived"):
            if state[k]:
                state[k]()

    _build_summary_tab(gui, summary_tab, state)
    _build_matrix_tab(gui, matrix_tab, state)
    _build_users_tab(gui, users_tab, state, refresh_all)
    _build_archived_tab(gui, archived_tab, state, refresh_all)
    _build_bulk_tab(gui, bulk_tab, refresh_all)
    _build_security_tab(gui, security_tab, refresh_all)
    _build_policy_tab(gui, policy_tab, refresh_all)
    _build_monitoring_tab(gui, monitoring_tab)
    _build_compliance_tab(gui, compliance_tab, refresh_all)
    _build_integrations_tab(gui, integ_tab, refresh_all)
