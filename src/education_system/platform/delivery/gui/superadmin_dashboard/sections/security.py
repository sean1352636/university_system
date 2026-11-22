"""Security Training, Permissions and Password Policy sections.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CARD_BG,
    CONTENT_BG,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class SecurityMixin:
    # ------------------------------------------------------------------
    # Section: Cross-System Notifications
    # ------------------------------------------------------------------

    def _build_security_training(self):
        """Launch and report authorised click-only awareness simulations."""
        tk.Label(
            self._content_frame, text="ICT Security Training Simulations",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))
        tk.Label(
            self._content_frame,
            text="Send a signed test link to every active user with an email address. "
                 "Clicks are recorded without collecting credentials.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED, wraplength=850,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 14))

        from education_system.platform.governance.security.training_simulation import (
            SimulationError, default_simulation,
        )
        try:
            service = default_simulation()
        except SimulationError as exc:
            self._show_error(str(exc))
            return

        form = tk.LabelFrame(
            self._content_frame, text=" New campaign ", font=("Segoe UI", 11, "bold"),
            bg=CARD_BG, fg=TEXT_DARK, padx=14, pady=12,
        )
        form.pack(fill=tk.X, padx=24, pady=(0, 14))

        date_var = tk.StringVar(value=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
        time_var = tk.StringVar(value="09:00")
        course_var = tk.StringVar(value="ICT Security Awareness Training")
        location_var = tk.StringVar(value="Online")
        fields = [
            ("Training date", date_var),
            ("Training time (24-hour HH:MM)", time_var),
            ("Course name", course_var), ("Location", location_var),
        ]
        for row, (label, variable) in enumerate(fields):
            tk.Label(form, text=label, bg=CARD_BG, fg=TEXT_DARK).grid(
                row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            tk.Entry(form, textvariable=variable, width=42).grid(
                row=row, column=1, sticky="ew", pady=4)
        form.columnconfigure(1, weight=1)

        def launch_campaign():
            if not messagebox.askyesno(
                "Confirm security test",
                "Send this simulation to every active user with an email address "
                "and add the course to their calendars?",
            ):
                return
            try:
                result = service.launch_all(
                    date_var.get().strip(),
                    int(self.user_info.get("id") or self.user_info.get("user_id")),
                    course_var.get().strip() or "ICT Security Awareness Training",
                    location_var.get().strip() or "Online",
                    time_var.get().strip() or "09:00",
                )
                summary = (
                    f"Users targeted: {result['targeted']}\n"
                    f"Emails stored in database: {result['sent']}\n"
                    f"Failed: {result['failed']}\n"
                    f"Calendar events: {len(result['calendar_event_ids'])}"
                )
                failures = [item for item in result["recipients"] if item["status"] == "failed"]
                if failures:
                    details = "\n".join(
                        f"• {item['email']}: {item.get('error', 'Unknown delivery error')}"
                        for item in failures
                    )
                    messagebox.showwarning(
                        "Campaign launched with delivery failures",
                        f"{summary}\n\nDelivery errors:\n{details}\n\n"
                        "Check the application database and recipient account, then retry.",
                    )
                else:
                    messagebox.showinfo("Campaign launched", summary)
                self._show_section("security_training")
            except (SimulationError, TypeError, ValueError) as exc:
                messagebox.showerror("Campaign not launched", str(exc))
            except Exception as exc:
                messagebox.showerror("Campaign not launched", f"Unexpected error: {exc}")

        tk.Button(
            form, text="Send to All", command=launch_campaign,
            bg="#c0392b", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=14, pady=7,
        ).grid(row=0, column=2, sticky="w", padx=(24, 0), pady=4)

        report = tk.LabelFrame(
            self._content_frame, text=" Campaign report ", font=("Segoe UI", 11, "bold"),
            bg=CARD_BG, fg=TEXT_DARK, padx=10, pady=10,
        )
        report.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 20))
        columns = ("date", "course", "system", "recipients", "sent", "clicked", "failed")
        tree = ttk.Treeview(report, columns=columns, show="headings", height=7)
        headings = {
            "date": "Training date", "course": "Course", "system": "System",
            "recipients": "Recipients", "sent": "Stored", "clicked": "Clicked", "failed": "Failed",
        }
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=90 if column != "course" else 240, anchor="center")
        tree.pack(fill=tk.BOTH, expand=True)
        for row in service.campaign_report():
            tree.insert("", tk.END, values=(
                row["training_date"], row["course_name"], row["target_system"],
                row["recipients"] or 0, row["sent"] or 0,
                row["clicked"] or 0, row["failed"] or 0,
            ))

        register_rows = service.training_register()
        notebook = ttk.Notebook(report)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        clicked_tab = ttk.Frame(notebook)
        register_tab = ttk.Frame(notebook)
        clicked_rows = [row for row in register_rows if row["first_clicked_at"]]
        attending_rows = [row for row in register_rows if row["registered"]]
        notebook.add(clicked_tab, text=f"Clicked links ({len(clicked_rows)})")
        notebook.add(register_tab, text=f"Course register ({len(attending_rows)})")

        def _register_tree(parent, columns_and_headings):
            holder = ttk.Frame(parent)
            holder.pack(fill=tk.BOTH, expand=True)
            scrollbar = ttk.Scrollbar(holder, orient=tk.VERTICAL)
            result_tree = ttk.Treeview(
                holder, columns=tuple(column for column, _heading, _width in columns_and_headings),
                show="headings", height=8, yscrollcommand=scrollbar.set,
            )
            scrollbar.config(command=result_tree.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            for column, heading, width in columns_and_headings:
                result_tree.heading(column, text=heading)
                result_tree.column(column, width=width, minwidth=70, anchor="center")
            return result_tree

        clicked_tree = _register_tree(clicked_tab, (
            ("name", "User", 160), ("email", "Email", 190),
            ("course", "Course", 210), ("date", "Training date", 100),
            ("clicked", "First clicked", 155), ("clicks", "Clicks", 60),
        ))
        for row in clicked_rows:
            clicked_tree.insert("", tk.END, values=(
                row["display_name"] or row["username"], row["email"], row["course_name"],
                row["training_date"], row["first_clicked_at"][:19], row["click_count"],
            ))

        attending_tree = _register_tree(register_tab, (
            ("name", "User", 150), ("email", "Email", 180),
            ("system", "System", 90), ("course", "Course", 190),
            ("date", "Date", 90), ("time", "Time", 65),
            ("location", "Location", 100), ("clicked", "Link clicked", 85),
            ("invitation", "Invitation", 85),
        ))
        for row in attending_rows:
            attending_tree.insert("", tk.END, values=(
                row["display_name"] or row["username"], row["email"], row["target_system"],
                row["course_name"], row["training_date"], row["training_time"],
                row["location"], "Yes" if row["first_clicked_at"] else "No",
                row["invitation_delivery_status"].title(),
            ))

    # ------------------------------------------------------------------
    # Section: Permission Matrix (Feature 8)
    # ------------------------------------------------------------------

    def _build_permissions(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame, text="Permission Matrix",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="View user roles across all education systems at a glance.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 12))

        tree_frame = tk.Frame(frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.X, padx=24, pady=(0, 12))

        # A column per system, from SYSTEM_ORDER — a hardcoded column list
        # here silently hid a user's access to any system added later.
        columns = ("username", "display_name", *SYSTEM_ORDER)
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=22)

        headings = [("username", "Username", 95), ("display_name", "Display Name", 120)]
        headings += [(key, SYSTEM_LABELS.get(key, key), 92) for key in SYSTEM_ORDER]
        for col, heading, w in headings:
            tree.heading(col, text=heading)
            tree.column(col, width=w, minwidth=60, stretch=False)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        # With every system present the row is wider than the pane, so it
        # needs to scroll sideways as well or the last systems are unreachable.
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        all_users = []
        svc = self._get_admin_service()
        if svc:
            try:
                all_users = svc.get_all_users()
            except Exception:
                pass

        for u in all_users:
            sys_map = {}
            for s in u.get("systems", []):
                sys_map[s["system_key"]] = s["role"]
            tree.insert("", tk.END, values=(
                u.get("username", ""),
                u.get("display_name", ""),
                *(sys_map.get(key, "\u2014") for key in SYSTEM_ORDER),
            ))

        if not all_users:
            tk.Label(
                frame, text="No user data available.",
                font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
            ).pack(padx=24, pady=8)

    # ------------------------------------------------------------------
    # Section: Quick Launch
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Section: Password Policy
    # ------------------------------------------------------------------

    def _build_password_policy(self):
        """Embed the standalone Password Reset Dashboard, bound to this
        session's shared auth object."""
        if self.auth is None or not hasattr(self.auth, "get_password_policy_overview"):
            self._show_error(
                "Password policy controls are unavailable (auth service missing)."
            )
            return
        try:
            from education_system.platform.delivery.gui.password_reset_dashboard import (
                PasswordResetDashboardFrame,
            )
            dash = PasswordResetDashboardFrame(self._content_frame, self.auth)
            dash.pack(fill=tk.BOTH, expand=True)
        except Exception as exc:
            self._show_error(f"Could not load the Password Reset Dashboard: {exc}")
