"""Batch Operations section.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CARD_BG,
    CONTENT_BG,
    SYSTEM_ORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class BatchMixin:
    # ------------------------------------------------------------------
    # Section: Batch Operations (Feature 11)
    # ------------------------------------------------------------------

    def _build_batch(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame, text="Batch Operations",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Perform bulk changes across users and systems.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        # Batch role change
        tk.Label(
            frame, text="Bulk Role Change",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(0, 6))

        role_card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        role_card.pack(fill=tk.X, padx=24, pady=(0, 16))

        r1 = tk.Frame(role_card, bg=CARD_BG)
        r1.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(r1, text="System:", font=("Segoe UI", 10), bg=CARD_BG, width=14, anchor=tk.W).pack(side=tk.LEFT)
        batch_sys_var = tk.StringVar(value="university")
        ttk.Combobox(
            r1, textvariable=batch_sys_var, values=list(SYSTEM_ORDER), state="readonly", width=14,
        ).pack(side=tk.LEFT)

        r2 = tk.Frame(role_card, bg=CARD_BG)
        r2.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(r2, text="Current Role:", font=("Segoe UI", 10), bg=CARD_BG, width=14, anchor=tk.W).pack(
            side=tk.LEFT
        )
        batch_from_var = tk.StringVar(value="student")
        ttk.Combobox(
            r2, textvariable=batch_from_var,
            values=["superadmin", "admin", "staff", "student", "parent"],
            state="readonly", width=14,
        ).pack(side=tk.LEFT)

        r3 = tk.Frame(role_card, bg=CARD_BG)
        r3.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(r3, text="New Role:", font=("Segoe UI", 10), bg=CARD_BG, width=14, anchor=tk.W).pack(side=tk.LEFT)
        batch_to_var = tk.StringVar(value="staff")
        ttk.Combobox(
            r3, textvariable=batch_to_var,
            values=["superadmin", "admin", "staff", "student", "parent"],
            state="readonly", width=14,
        ).pack(side=tk.LEFT)

        batch_result = tk.Label(role_card, text="", font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_MUTED)
        batch_result.pack(padx=12, pady=4, anchor=tk.W)

        def _do_batch_role():
            sys_key = batch_sys_var.get()
            from_role = batch_from_var.get()
            to_role = batch_to_var.get()
            if from_role == to_role:
                messagebox.showwarning("Validation", "Current and new roles must differ.")
                return
            svc = self._get_admin_service()
            if not svc:
                return
            try:
                all_users = svc.get_all_users(system=sys_key, role=from_role)
                if not all_users:
                    batch_result.config(text=f"No users found with role '{from_role}' in {sys_key}.", fg="#e67e22")
                    return
                if not messagebox.askyesno(
                    "Confirm Batch Role Change",
                    f"Change {len(all_users)} user(s) from '{from_role}' to '{to_role}' in {sys_key}?",
                ):
                    return
                count = 0
                for u in all_users:
                    new_sr = []
                    for s in u.get("systems", []):
                        if s["system_key"] == sys_key and s["role"] == from_role:
                            new_sr.append({"system_key": sys_key, "role": to_role})
                        else:
                            new_sr.append(s)
                    svc.update_user_systems(u["id"], new_sr)
                    count += 1
                batch_result.config(text=f"Updated {count} user(s) to role '{to_role}'.", fg="#27ae60")
            except Exception as exc:
                batch_result.config(text=f"Error: {exc}", fg="#e74c3c")

        tk.Button(
            role_card, text="Apply Batch Role Change", font=("Segoe UI", 10),
            bg="#e67e22", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=12,
            command=_do_batch_role,
        ).pack(padx=12, pady=(0, 12), anchor=tk.W)

        # Batch deactivation
        tk.Label(
            frame, text="Bulk Deactivation",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(0, 6))

        deact_card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        deact_card.pack(fill=tk.X, padx=24, pady=(0, 16))

        d1 = tk.Frame(deact_card, bg=CARD_BG)
        d1.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(d1, text="System:", font=("Segoe UI", 10), bg=CARD_BG, width=14, anchor=tk.W).pack(side=tk.LEFT)
        deact_sys_var = tk.StringVar(value="university")
        ttk.Combobox(
            d1, textvariable=deact_sys_var, values=list(SYSTEM_ORDER), state="readonly", width=14,
        ).pack(side=tk.LEFT)

        d2 = tk.Frame(deact_card, bg=CARD_BG)
        d2.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(d2, text="Role:", font=("Segoe UI", 10), bg=CARD_BG, width=14, anchor=tk.W).pack(side=tk.LEFT)
        deact_role_var = tk.StringVar(value="student")
        ttk.Combobox(
            d2, textvariable=deact_role_var,
            values=["superadmin", "admin", "staff", "student", "parent"],
            state="readonly", width=14,
        ).pack(side=tk.LEFT)

        deact_result = tk.Label(deact_card, text="", font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_MUTED)
        deact_result.pack(padx=12, pady=4, anchor=tk.W)

        def _do_batch_deactivate():
            sys_key = deact_sys_var.get()
            role = deact_role_var.get()
            svc = self._get_admin_service()
            if not svc:
                return
            try:
                users = svc.get_all_users(system=sys_key, role=role)
                active_users = [u for u in users if u.get("is_active")]
                if not active_users:
                    deact_result.config(text="No active users match this filter.", fg="#e67e22")
                    return
                if not messagebox.askyesno(
                    "Confirm Bulk Deactivation",
                    f"Deactivate {len(active_users)} active user(s) with role '{role}' in {sys_key}?",
                ):
                    return
                for u in active_users:
                    svc.deactivate_user(u["id"])
                deact_result.config(text=f"Deactivated {len(active_users)} user(s).", fg="#27ae60")
            except Exception as exc:
                deact_result.config(text=f"Error: {exc}", fg="#e74c3c")

        tk.Button(
            deact_card, text="Deactivate All Matching", font=("Segoe UI", 10),
            bg="#e74c3c", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=12,
            command=_do_batch_deactivate,
        ).pack(padx=12, pady=(0, 12), anchor=tk.W)
