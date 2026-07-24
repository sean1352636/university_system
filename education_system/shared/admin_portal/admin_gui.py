"""Central Admin Portal GUI.

Provides a tkinter Frame with notebook tabs for superadmin dashboard:
System Health, User Management, Audit Log, and Overview.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.admin_portal.admin_service import AdminService, SYSTEM_LABELS

HEADER_BG = "#1a5276"
HEADER_FG = "white"
BG = "#ecf0f1"

SYSTEM_KEYS = ["primary", "secondary", "sixth_form", "university"]
ROLE_OPTIONS = ["", "admin", "staff", "teacher", "student", "parent"]


class CentralAdminFrame(tk.Frame):
    """Superadmin dashboard frame with notebook tabs."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AdminService()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg=BG)

        # Header
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Central Admin Portal",
            font=("Helvetica", 15, "bold"), bg=HEADER_BG, fg=HEADER_FG,
        ).pack(side="left", padx=20, pady=10)
        ttk.Button(header, text="Refresh All", command=self.refresh).pack(
            side="right", padx=20, pady=10)

        # Notebook
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_health_tab()
        self._build_users_tab()
        self._build_audit_tab()
        self._build_overview_tab()

    # ---- System Health tab ----

    def _build_health_tab(self):
        frame = tk.Frame(self._nb, bg=BG)
        self._nb.add(frame, text="System Health")

        self._health_cards_frame = tk.Frame(frame, bg=BG)
        self._health_cards_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def _refresh_health(self):
        for w in self._health_cards_frame.winfo_children():
            w.destroy()

        health = self._svc.get_system_health()
        for i, info in enumerate(health):
            card = tk.LabelFrame(
                self._health_cards_frame, text=info["label"],
                bg="white", font=("Helvetica", 11, "bold"),
                padx=15, pady=10,
            )
            card.grid(row=i // 2, column=i % 2, padx=10, pady=10, sticky="nsew")

            status_color = "#27ae60" if info["status"] == "online" else "#e74c3c"
            tk.Label(card, text=info["status"].upper(),
                     fg=status_color, bg="white",
                     font=("Helvetica", 10, "bold")).pack(anchor="w")

            for label, val in [
                ("Students", info["student_count"]),
                ("Staff", info["staff_count"]),
                ("DB Size", f"{info['db_size_mb']} MB"),
                ("Last Activity", info["last_activity"] or "N/A"),
            ]:
                row = tk.Frame(card, bg="white")
                row.pack(fill="x", pady=1)
                tk.Label(row, text=f"{label}:", bg="white",
                         font=("Helvetica", 9, "bold"), width=14, anchor="w").pack(side="left")
                tk.Label(row, text=str(val), bg="white",
                         font=("Helvetica", 9)).pack(side="left")

        # Make grid expand
        for c in range(2):
            self._health_cards_frame.columnconfigure(c, weight=1)

    # ---- User Management tab ----

    def _build_users_tab(self):
        frame = tk.Frame(self._nb, bg=BG)
        self._nb.add(frame, text="User Management")

        # Filters
        filter_frame = tk.Frame(frame, bg=BG, pady=8)
        filter_frame.pack(fill="x", padx=10)

        tk.Label(filter_frame, text="System:", bg=BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 5))
        self._user_system_var = tk.StringVar(value="")
        system_opts = [""] + SYSTEM_KEYS
        ttk.Combobox(filter_frame, textvariable=self._user_system_var,
                     values=system_opts, state="readonly", width=15).pack(side="left", padx=5)

        tk.Label(filter_frame, text="Role:", bg=BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(15, 5))
        self._user_role_var = tk.StringVar(value="")
        ttk.Combobox(filter_frame, textvariable=self._user_role_var,
                     values=ROLE_OPTIONS, state="readonly", width=12).pack(side="left", padx=5)

        ttk.Button(filter_frame, text="Filter", command=self._refresh_users).pack(
            side="left", padx=15)

        # Treeview
        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("username", "display_name", "role", "systems", "last_login", "active")
        self._users_tree = ttk.Treeview(tree_frame, columns=columns,
                                        show="headings", selectmode="browse")
        for col, heading, width in [
            ("username", "Username", 120),
            ("display_name", "Display Name", 160),
            ("role", "Role(s)", 120),
            ("systems", "System(s)", 180),
            ("last_login", "Last Login", 140),
            ("active", "Active", 60),
        ]:
            self._users_tree.heading(col, text=heading)
            self._users_tree.column(col, width=width,
                                    anchor="center" if col in ("active",) else "w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._users_tree.yview)
        self._users_tree.configure(yscrollcommand=vsb.set)
        self._users_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _refresh_users(self):
        self._users_tree.delete(*self._users_tree.get_children())
        system = self._user_system_var.get() or None
        role = self._user_role_var.get() or None

        try:
            users = self._svc.get_all_users(system=system, role=role)
            for u in users:
                roles = sorted(set(s["role"] for s in u["systems"]))
                systems = sorted(set(
                    SYSTEM_LABELS.get(s["system_key"], s["system_key"])
                    for s in u["systems"]
                ))
                self._users_tree.insert("", "end", values=(
                    u["username"],
                    u["display_name"],
                    ", ".join(roles),
                    ", ".join(systems),
                    (u["last_login"] or "Never")[:19],
                    "Yes" if u["is_active"] else "No",
                ))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load users: {e}", parent=self)

    # ---- Audit Log tab ----

    def _build_audit_tab(self):
        frame = tk.Frame(self._nb, bg=BG)
        self._nb.add(frame, text="Audit Log")

        toolbar = tk.Frame(frame, bg=BG, pady=8)
        toolbar.pack(fill="x", padx=10)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_audit).pack(side="left")

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("type", "timestamp", "description", "details")
        self._audit_tree = ttk.Treeview(tree_frame, columns=columns,
                                        show="headings", selectmode="browse")
        for col, heading, width in [
            ("type", "Type", 100),
            ("timestamp", "Timestamp", 150),
            ("description", "Description", 250),
            ("details", "Details", 300),
        ]:
            self._audit_tree.heading(col, text=heading)
            self._audit_tree.column(col, width=width, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._audit_tree.yview)
        self._audit_tree.configure(yscrollcommand=vsb.set)
        self._audit_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _refresh_audit(self):
        self._audit_tree.delete(*self._audit_tree.get_children())
        try:
            entries = self._svc.get_audit_summary(limit=100)
            for e in entries:
                self._audit_tree.insert("", "end", values=(
                    e["type"].capitalize(),
                    (e["timestamp"] or "")[:19],
                    e["description"],
                    e["details"],
                ))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load audit log: {e}", parent=self)

    # ---- Overview tab ----

    def _build_overview_tab(self):
        frame = tk.Frame(self._nb, bg=BG)
        self._nb.add(frame, text="Overview")

        self._overview_frame = tk.Frame(frame, bg=BG)
        self._overview_frame.pack(fill="both", expand=True, padx=20, pady=20)

    def _refresh_overview(self):
        for w in self._overview_frame.winfo_children():
            w.destroy()

        try:
            summary = self._svc.get_user_summary()
            health = self._svc.get_system_health()
        except Exception:
            summary = {"total_users": 0, "by_system": {}, "by_role": {}}
            health = []

        total_students = sum(h["student_count"] for h in health)
        active_systems = sum(1 for h in health if h["status"] == "online")

        # Summary metrics row
        metrics_frame = tk.Frame(self._overview_frame, bg=BG)
        metrics_frame.pack(fill="x", pady=(0, 20))

        for i, (label, value, color) in enumerate([
            ("Total Users", summary["total_users"], "#2980b9"),
            ("Total Students", total_students, "#27ae60"),
            ("Active Systems", f"{active_systems}/4", "#8e44ad"),
        ]):
            card = tk.Frame(metrics_frame, bg=color, padx=20, pady=15)
            card.grid(row=0, column=i, padx=10, sticky="nsew")
            tk.Label(card, text=str(value), bg=color, fg="white",
                     font=("Helvetica", 24, "bold")).pack()
            tk.Label(card, text=label, bg=color, fg="white",
                     font=("Helvetica", 10)).pack()
            metrics_frame.columnconfigure(i, weight=1)

        # Users by role
        role_frame = tk.LabelFrame(self._overview_frame, text="Users by Role",
                                   bg="white", font=("Helvetica", 11, "bold"),
                                   padx=15, pady=10)
        role_frame.pack(fill="x", pady=10)

        by_role = summary.get("by_role", {})
        if by_role:
            for role, count in sorted(by_role.items()):
                row = tk.Frame(role_frame, bg="white")
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"{role.capitalize()}:", bg="white",
                         font=("Helvetica", 10, "bold"), width=15, anchor="w").pack(side="left")
                tk.Label(row, text=str(count), bg="white",
                         font=("Helvetica", 10)).pack(side="left")
        else:
            tk.Label(role_frame, text="No user data available", bg="white",
                     font=("Helvetica", 10, "italic")).pack()

        # Users by system
        sys_frame = tk.LabelFrame(self._overview_frame, text="Users by System",
                                  bg="white", font=("Helvetica", 11, "bold"),
                                  padx=15, pady=10)
        sys_frame.pack(fill="x", pady=10)

        by_system = summary.get("by_system", {})
        if by_system:
            for sys_key in SYSTEM_KEYS:
                if sys_key not in by_system and sys_key.replace("secondary", "secondary") not in by_system:
                    continue
                roles = by_system.get(sys_key, by_system.get(
                    sys_key.replace("secondary", "secondary"), {}))
                total = sum(roles.values())
                label = SYSTEM_LABELS.get(sys_key, sys_key)
                detail = ", ".join(f"{r}: {c}" for r, c in sorted(roles.items()))
                row = tk.Frame(sys_frame, bg="white")
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"{label}:", bg="white",
                         font=("Helvetica", 10, "bold"), width=20, anchor="w").pack(side="left")
                tk.Label(row, text=f"{total} ({detail})", bg="white",
                         font=("Helvetica", 10)).pack(side="left")
        else:
            tk.Label(sys_frame, text="No system data available", bg="white",
                     font=("Helvetica", 10, "italic")).pack()

    # ------------------------------------------------------------------
    # Public refresh
    # ------------------------------------------------------------------

    def refresh(self):
        """Refresh all tabs."""
        self._refresh_health()
        self._refresh_users()
        self._refresh_audit()
        self._refresh_overview()
