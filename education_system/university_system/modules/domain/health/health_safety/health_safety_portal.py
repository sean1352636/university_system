"""
University Health and Safety Portal
A comprehensive GUI application for managing health and safety at a university.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import json
import os


class HealthSafetyPortal:
    def __init__(self, root):
        self.root = root
        self.root.title("University Health & Safety Portal")
        self.root.geometry("1100x700")
        self.root.configure(bg="#f0f4f8")

        # Data storage files
        self.incidents_file = "incidents.json"
        self.hazards_file = "hazards.json"
        self.training_file = "training.json"

        # Load existing data
        self.incidents = self.load_data(self.incidents_file)
        self.hazards = self.load_data(self.hazards_file)
        self.training_records = self.load_data(self.training_file)

        # Current logged in user (simulated)
        self.current_user = None

        # Setup styling
        self.setup_styles()

        # Show login screen first
        self.show_login()

    def setup_styles(self):
        """Configure ttk styles for a modern look."""
        style = ttk.Style()
        style.theme_use("clam")

        # Configure colors
        style.configure("TButton",
                       padding=10,
                       font=("Segoe UI", 10),
                       background="#2c5282",
                       foreground="white")
        style.map("TButton",
                 background=[("active", "#2b6cb0")])

        style.configure("Nav.TButton",
                       padding=15,
                       font=("Segoe UI", 11, "bold"),
                       background="#1a365d",
                       foreground="white")
        style.map("Nav.TButton",
                 background=[("active", "#2c5282")])

        style.configure("Danger.TButton",
                       background="#c53030",
                       foreground="white")
        style.map("Danger.TButton",
                 background=[("active", "#9b2c2c")])

        style.configure("Success.TButton",
                       background="#2f855a",
                       foreground="white")
        style.map("Success.TButton",
                 background=[("active", "#276749")])

        style.configure("TLabel",
                       background="#f0f4f8",
                       font=("Segoe UI", 10))

        style.configure("Header.TLabel",
                       background="#f0f4f8",
                       font=("Segoe UI", 18, "bold"),
                       foreground="#1a365d")

        style.configure("SubHeader.TLabel",
                       background="#f0f4f8",
                       font=("Segoe UI", 12, "bold"),
                       foreground="#2c5282")

        style.configure("Treeview",
                       font=("Segoe UI", 10),
                       rowheight=28)
        style.configure("Treeview.Heading",
                       font=("Segoe UI", 10, "bold"),
                       background="#2c5282",
                       foreground="white")

    def load_data(self, filename):
        """Load data from JSON file."""
        if os.path.exists(filename):
            try:
                with open(filename, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def save_data(self, filename, data):
        """Save data to JSON file."""
        try:
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            messagebox.showerror("Error", f"Could not save data: {e}")

    def clear_window(self):
        """Clear all widgets from the window."""
        for widget in self.root.winfo_children():
            widget.destroy()

    # ==================== LOGIN SCREEN ====================
    def show_login(self):
        """Display the login screen."""
        self.clear_window()

        # Header frame
        header_frame = tk.Frame(self.root, bg="#1a365d", height=120)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        tk.Label(header_frame,
                text="🏥 University Health & Safety Portal",
                font=("Segoe UI", 24, "bold"),
                bg="#1a365d",
                fg="white").pack(pady=30)

        # Login form
        login_frame = tk.Frame(self.root, bg="#f0f4f8")
        login_frame.pack(expand=True)

        form_container = tk.Frame(login_frame, bg="white", padx=50, pady=40,
                                  relief="ridge", bd=1)
        form_container.pack(pady=50)

        tk.Label(form_container, text="Sign In",
                font=("Segoe UI", 18, "bold"),
                bg="white", fg="#1a365d").grid(row=0, column=0, columnspan=2, pady=(0, 20))

        tk.Label(form_container, text="Username:",
                font=("Segoe UI", 11),
                bg="white").grid(row=1, column=0, sticky="w", pady=5)
        self.username_entry = tk.Entry(form_container, font=("Segoe UI", 11), width=30)
        self.username_entry.grid(row=1, column=1, pady=5, padx=10)

        tk.Label(form_container, text="Role:",
                font=("Segoe UI", 11),
                bg="white").grid(row=2, column=0, sticky="w", pady=5)
        self.role_var = tk.StringVar(value="Student")
        role_combo = ttk.Combobox(form_container, textvariable=self.role_var,
                                  values=["Student", "Staff", "Faculty", "H&S Officer", "Administrator"],
                                  state="readonly", font=("Segoe UI", 11), width=28)
        role_combo.grid(row=2, column=1, pady=5, padx=10)

        tk.Label(form_container, text="Department:",
                font=("Segoe UI", 11),
                bg="white").grid(row=3, column=0, sticky="w", pady=5)
        self.dept_var = tk.StringVar(value="Computer Science")
        dept_combo = ttk.Combobox(form_container, textvariable=self.dept_var,
                                  values=["Computer Science", "Chemistry", "Physics", "Biology",
                                         "Engineering", "Medicine", "Arts", "Business", "Other"],
                                  state="readonly", font=("Segoe UI", 11), width=28)
        dept_combo.grid(row=3, column=1, pady=5, padx=10)

        ttk.Button(form_container, text="Sign In",
                  command=self.handle_login).grid(row=4, column=0, columnspan=2, pady=20, sticky="ew")

        # Emergency button on login screen
        emergency_frame = tk.Frame(self.root, bg="#f0f4f8")
        emergency_frame.pack(pady=10)
        tk.Label(emergency_frame,
                text="🚨 In case of emergency, dial 999 or campus security: 01234-567890",
                font=("Segoe UI", 10, "italic"),
                bg="#f0f4f8", fg="#c53030").pack()

    def handle_login(self):
        """Process login."""
        username = self.username_entry.get().strip()
        if not username:
            messagebox.showwarning("Login Error", "Please enter a username.")
            return

        self.current_user = {
            "username": username,
            "role": self.role_var.get(),
            "department": self.dept_var.get()
        }
        self.show_dashboard()

    # ==================== DASHBOARD ====================
    def show_dashboard(self):
        """Display the main dashboard."""
        self.clear_window()

        # Top header
        header = tk.Frame(self.root, bg="#1a365d", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🏥 University Health & Safety Portal",
                font=("Segoe UI", 16, "bold"),
                bg="#1a365d", fg="white").pack(side="left", padx=20, pady=20)

        user_info = f"👤 {self.current_user['username']} ({self.current_user['role']}) | {self.current_user['department']}"
        tk.Label(header, text=user_info,
                font=("Segoe UI", 10),
                bg="#1a365d", fg="white").pack(side="right", padx=20, pady=25)

        # Main container with sidebar and content
        main_container = tk.Frame(self.root, bg="#f0f4f8")
        main_container.pack(fill="both", expand=True)

        # Sidebar
        sidebar = tk.Frame(main_container, bg="#2d3748", width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        nav_buttons = [
            ("🏠 Dashboard", self.show_dashboard_content),
            ("⚠️ Report Incident", self.show_report_incident),
            ("📋 View Incidents", self.show_incidents_list),
            ("🔍 Report Hazard", self.show_report_hazard),
            ("📊 View Hazards", self.show_hazards_list),
            ("🎓 Training", self.show_training),
            ("📚 Resources", self.show_resources),
            ("🚨 Emergency Info", self.show_emergency),
            ("🚪 Logout", self.show_login),
        ]

        for text, command in nav_buttons:
            btn = tk.Button(sidebar, text=text,
                          font=("Segoe UI", 11),
                          bg="#2d3748", fg="white",
                          bd=0, pady=15, padx=20,
                          anchor="w",
                          activebackground="#4a5568",
                          activeforeground="white",
                          cursor="hand2",
                          command=command)
            btn.pack(fill="x")

        # Content area
        self.content_frame = tk.Frame(main_container, bg="#f0f4f8")
        self.content_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        # Show default dashboard content
        self.show_dashboard_content()

    def clear_content(self):
        """Clear the content frame."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_dashboard_content(self):
        """Show dashboard overview with statistics."""
        self.clear_content()

        tk.Label(self.content_frame, text="Dashboard Overview",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 20))

        # Stats cards
        stats_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        stats_frame.pack(fill="x", pady=10)

        total_incidents = len(self.incidents)
        open_incidents = sum(1 for i in self.incidents if i.get("status") == "Open")
        total_hazards = len(self.hazards)
        high_risk = sum(1 for h in self.hazards if h.get("risk_level") == "High")

        stats = [
            ("Total Incidents", total_incidents, "#3182ce", "📋"),
            ("Open Incidents", open_incidents, "#dd6b20", "⚠️"),
            ("Reported Hazards", total_hazards, "#805ad5", "🔍"),
            ("High Risk Items", high_risk, "#c53030", "🚨"),
        ]

        for i, (label, value, color, icon) in enumerate(stats):
            card = tk.Frame(stats_frame, bg=color, width=200, height=120)
            card.grid(row=0, column=i, padx=10, pady=5, sticky="ew")
            card.pack_propagate(False)
            stats_frame.grid_columnconfigure(i, weight=1)

            tk.Label(card, text=icon, font=("Segoe UI", 24),
                    bg=color, fg="white").pack(pady=(15, 0))
            tk.Label(card, text=str(value), font=("Segoe UI", 22, "bold"),
                    bg=color, fg="white").pack()
            tk.Label(card, text=label, font=("Segoe UI", 10),
                    bg=color, fg="white").pack()

        # Recent activity
        tk.Label(self.content_frame, text="Recent Incidents",
                font=("Segoe UI", 14, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(30, 10))

        recent_frame = tk.Frame(self.content_frame, bg="white", relief="ridge", bd=1)
        recent_frame.pack(fill="both", expand=True, pady=5)

        columns = ("ID", "Type", "Location", "Date", "Severity", "Status")
        tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=8)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=140, anchor="w")

        # Show last 10 incidents
        for incident in self.incidents[-10:][::-1]:
            tree.insert("", "end", values=(
                incident.get("id", ""),
                incident.get("type", ""),
                incident.get("location", ""),
                incident.get("date", ""),
                incident.get("severity", ""),
                incident.get("status", "")
            ))

        tree.pack(fill="both", expand=True, padx=5, pady=5)

        # Quick actions
        tk.Label(self.content_frame, text="Quick Actions",
                font=("Segoe UI", 14, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(20, 10))

        actions_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        actions_frame.pack(fill="x")

        ttk.Button(actions_frame, text="⚠️ Report New Incident",
                  style="Danger.TButton",
                  command=self.show_report_incident).pack(side="left", padx=5)
        ttk.Button(actions_frame, text="🔍 Report Hazard",
                  command=self.show_report_hazard).pack(side="left", padx=5)
        ttk.Button(actions_frame, text="🎓 View Training",
                  command=self.show_training).pack(side="left", padx=5)

    # ==================== REPORT INCIDENT ====================
    def show_report_incident(self):
        """Show incident reporting form."""
        self.clear_content()

        tk.Label(self.content_frame, text="⚠️ Report an Incident",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 10))

        tk.Label(self.content_frame,
                text="Report any accidents, injuries, or near-misses that occurred on campus.",
                font=("Segoe UI", 10, "italic"),
                bg="#f0f4f8", fg="#4a5568").pack(anchor="w", pady=(0, 20))

        form = tk.Frame(self.content_frame, bg="white", relief="ridge", bd=1, padx=30, pady=20)
        form.pack(fill="both", expand=True)

        # Incident type
        tk.Label(form, text="Incident Type *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=0, column=0, sticky="w", pady=5)
        incident_type = ttk.Combobox(form, values=[
            "Slip/Trip/Fall", "Chemical Spill", "Fire/Smoke", "Equipment Failure",
            "Injury", "Near Miss", "Electrical", "Biological", "Other"
        ], state="readonly", font=("Segoe UI", 10), width=40)
        incident_type.grid(row=0, column=1, pady=5, padx=10, sticky="w")
        incident_type.set("Slip/Trip/Fall")

        # Location
        tk.Label(form, text="Location *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=1, column=0, sticky="w", pady=5)
        location_entry = tk.Entry(form, font=("Segoe UI", 10), width=42)
        location_entry.grid(row=1, column=1, pady=5, padx=10, sticky="w")

        # Date
        tk.Label(form, text="Date *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=2, column=0, sticky="w", pady=5)
        date_entry = tk.Entry(form, font=("Segoe UI", 10), width=42)
        date_entry.grid(row=2, column=1, pady=5, padx=10, sticky="w")
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M"))

        # Severity
        tk.Label(form, text="Severity *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=3, column=0, sticky="w", pady=5)
        severity = ttk.Combobox(form, values=["Low", "Medium", "High", "Critical"],
                                state="readonly", font=("Segoe UI", 10), width=40)
        severity.grid(row=3, column=1, pady=5, padx=10, sticky="w")
        severity.set("Low")

        # People involved
        tk.Label(form, text="People Involved", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=4, column=0, sticky="w", pady=5)
        people_entry = tk.Entry(form, font=("Segoe UI", 10), width=42)
        people_entry.grid(row=4, column=1, pady=5, padx=10, sticky="w")

        # Description
        tk.Label(form, text="Description *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=5, column=0, sticky="nw", pady=5)
        description = scrolledtext.ScrolledText(form, font=("Segoe UI", 10),
                                                width=42, height=6)
        description.grid(row=5, column=1, pady=5, padx=10, sticky="w")

        # Actions taken
        tk.Label(form, text="Immediate Actions Taken", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=6, column=0, sticky="nw", pady=5)
        actions = scrolledtext.ScrolledText(form, font=("Segoe UI", 10),
                                            width=42, height=4)
        actions.grid(row=6, column=1, pady=5, padx=10, sticky="w")

        # Submit button
        def submit_incident():
            if not location_entry.get() or not description.get("1.0", "end-1c").strip():
                messagebox.showwarning("Validation Error",
                                     "Please fill in all required fields (marked with *).")
                return

            new_incident = {
                "id": f"INC-{len(self.incidents) + 1:04d}",
                "type": incident_type.get(),
                "location": location_entry.get(),
                "date": date_entry.get(),
                "severity": severity.get(),
                "people_involved": people_entry.get(),
                "description": description.get("1.0", "end-1c"),
                "actions_taken": actions.get("1.0", "end-1c"),
                "reported_by": self.current_user["username"],
                "department": self.current_user["department"],
                "status": "Open",
                "reported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.incidents.append(new_incident)
            self.save_data(self.incidents_file, self.incidents)
            messagebox.showinfo("Success",
                              f"Incident {new_incident['id']} has been reported successfully.\n"
                              f"The H&S team will review it shortly.")
            self.show_dashboard_content()

        btn_frame = tk.Frame(form, bg="white")
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Submit Report",
                  style="Success.TButton",
                  command=submit_incident).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=self.show_dashboard_content).pack(side="left", padx=5)

    # ==================== INCIDENTS LIST ====================
    def show_incidents_list(self):
        """Display all incidents."""
        self.clear_content()

        tk.Label(self.content_frame, text="📋 All Incidents",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 20))

        # Filter frame
        filter_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        filter_frame.pack(fill="x", pady=5)

        tk.Label(filter_frame, text="Filter by status:",
                bg="#f0f4f8", font=("Segoe UI", 10)).pack(side="left", padx=5)
        status_filter = ttk.Combobox(filter_frame, values=["All", "Open", "In Progress", "Resolved", "Closed"],
                                     state="readonly", width=15)
        status_filter.set("All")
        status_filter.pack(side="left", padx=5)

        # List frame
        list_frame = tk.Frame(self.content_frame, bg="white", relief="ridge", bd=1)
        list_frame.pack(fill="both", expand=True, pady=10)

        columns = ("ID", "Type", "Location", "Date", "Severity", "Reporter", "Status")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings")

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor="w")

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True, padx=5, pady=5)

        def refresh_list():
            for item in tree.get_children():
                tree.delete(item)
            filter_val = status_filter.get()
            for incident in self.incidents[::-1]:
                if filter_val == "All" or incident.get("status") == filter_val:
                    tree.insert("", "end", values=(
                        incident.get("id", ""),
                        incident.get("type", ""),
                        incident.get("location", ""),
                        incident.get("date", ""),
                        incident.get("severity", ""),
                        incident.get("reported_by", ""),
                        incident.get("status", "")
                    ))

        refresh_list()
        status_filter.bind("<<ComboboxSelected>>", lambda e: refresh_list())

        # View details on double-click
        def view_details(event):
            selected = tree.selection()
            if not selected:
                return
            item = tree.item(selected[0])
            incident_id = item["values"][0]
            incident = next((i for i in self.incidents if i.get("id") == incident_id), None)
            if incident:
                self.show_incident_details(incident)

        tree.bind("<Double-1>", view_details)

        # Buttons
        btn_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        btn_frame.pack(fill="x", pady=10)

        def update_status():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("No Selection", "Please select an incident first.")
                return
            item = tree.item(selected[0])
            incident_id = item["values"][0]
            self.update_incident_status(incident_id, refresh_list)

        ttk.Button(btn_frame, text="View Details",
                  command=lambda: view_details(None)).pack(side="left", padx=5)
        if self.current_user["role"] in ["H&S Officer", "Administrator"]:
            ttk.Button(btn_frame, text="Update Status",
                      command=update_status).pack(side="left", padx=5)

        tk.Label(self.content_frame,
                text="Double-click an incident to view full details.",
                font=("Segoe UI", 9, "italic"),
                bg="#f0f4f8", fg="#4a5568").pack(anchor="w")

    def show_incident_details(self, incident):
        """Show detailed view of an incident."""
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Incident Details - {incident.get('id')}")
        detail_window.geometry("600x500")
        detail_window.configure(bg="white")

        tk.Label(detail_window, text=f"Incident {incident.get('id')}",
                font=("Segoe UI", 16, "bold"),
                bg="white", fg="#1a365d").pack(pady=10)

        info_frame = tk.Frame(detail_window, bg="white", padx=20)
        info_frame.pack(fill="both", expand=True)

        details = [
            ("Type:", incident.get("type", "")),
            ("Location:", incident.get("location", "")),
            ("Date:", incident.get("date", "")),
            ("Severity:", incident.get("severity", "")),
            ("People Involved:", incident.get("people_involved", "None")),
            ("Reported By:", incident.get("reported_by", "")),
            ("Department:", incident.get("department", "")),
            ("Status:", incident.get("status", "")),
            ("Reported At:", incident.get("reported_at", "")),
        ]

        for i, (label, value) in enumerate(details):
            tk.Label(info_frame, text=label, font=("Segoe UI", 10, "bold"),
                    bg="white").grid(row=i, column=0, sticky="w", pady=3)
            tk.Label(info_frame, text=value, font=("Segoe UI", 10),
                    bg="white", wraplength=400, justify="left").grid(row=i, column=1, sticky="w", padx=10, pady=3)

        tk.Label(info_frame, text="Description:", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=len(details), column=0, sticky="nw", pady=5)
        desc_text = tk.Text(info_frame, height=4, width=50, font=("Segoe UI", 10), wrap="word")
        desc_text.insert("1.0", incident.get("description", ""))
        desc_text.config(state="disabled")
        desc_text.grid(row=len(details), column=1, sticky="w", padx=10, pady=5)

        tk.Label(info_frame, text="Actions Taken:", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=len(details)+1, column=0, sticky="nw", pady=5)
        actions_text = tk.Text(info_frame, height=3, width=50, font=("Segoe UI", 10), wrap="word")
        actions_text.insert("1.0", incident.get("actions_taken", "None"))
        actions_text.config(state="disabled")
        actions_text.grid(row=len(details)+1, column=1, sticky="w", padx=10, pady=5)

        ttk.Button(detail_window, text="Close",
                  command=detail_window.destroy).pack(pady=15)

    def update_incident_status(self, incident_id, refresh_callback):
        """Update the status of an incident."""
        update_window = tk.Toplevel(self.root)
        update_window.title("Update Incident Status")
        update_window.geometry("400x200")
        update_window.configure(bg="white")

        tk.Label(update_window, text=f"Update {incident_id}",
                font=("Segoe UI", 14, "bold"), bg="white").pack(pady=10)

        tk.Label(update_window, text="New Status:",
                font=("Segoe UI", 10), bg="white").pack(pady=5)
        status_var = tk.StringVar(value="In Progress")
        status_combo = ttk.Combobox(update_window, textvariable=status_var,
                                    values=["Open", "In Progress", "Resolved", "Closed"],
                                    state="readonly", width=25)
        status_combo.pack(pady=5)

        def save_status():
            for incident in self.incidents:
                if incident.get("id") == incident_id:
                    incident["status"] = status_var.get()
                    incident["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    break
            self.save_data(self.incidents_file, self.incidents)
            messagebox.showinfo("Success", "Status updated successfully.")
            update_window.destroy()
            refresh_callback()

        ttk.Button(update_window, text="Save",
                  style="Success.TButton",
                  command=save_status).pack(pady=15)

    # ==================== HAZARDS ====================
    def show_report_hazard(self):
        """Show hazard reporting form."""
        self.clear_content()

        tk.Label(self.content_frame, text="🔍 Report a Hazard",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 10))

        tk.Label(self.content_frame,
                text="Report potential hazards before they cause incidents.",
                font=("Segoe UI", 10, "italic"),
                bg="#f0f4f8", fg="#4a5568").pack(anchor="w", pady=(0, 20))

        form = tk.Frame(self.content_frame, bg="white", relief="ridge", bd=1, padx=30, pady=20)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="Hazard Category *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=0, column=0, sticky="w", pady=5)
        category = ttk.Combobox(form, values=[
            "Physical", "Chemical", "Biological", "Ergonomic",
            "Electrical", "Fire", "Environmental", "Radiation", "Other"
        ], state="readonly", font=("Segoe UI", 10), width=40)
        category.grid(row=0, column=1, pady=5, padx=10, sticky="w")
        category.set("Physical")

        tk.Label(form, text="Location *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=1, column=0, sticky="w", pady=5)
        location_entry = tk.Entry(form, font=("Segoe UI", 10), width=42)
        location_entry.grid(row=1, column=1, pady=5, padx=10, sticky="w")

        tk.Label(form, text="Risk Level *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=2, column=0, sticky="w", pady=5)
        risk_level = ttk.Combobox(form, values=["Low", "Medium", "High"],
                                  state="readonly", font=("Segoe UI", 10), width=40)
        risk_level.grid(row=2, column=1, pady=5, padx=10, sticky="w")
        risk_level.set("Low")

        tk.Label(form, text="Description *", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=3, column=0, sticky="nw", pady=5)
        description = scrolledtext.ScrolledText(form, font=("Segoe UI", 10),
                                                width=42, height=5)
        description.grid(row=3, column=1, pady=5, padx=10, sticky="w")

        tk.Label(form, text="Suggested Mitigation", font=("Segoe UI", 10, "bold"),
                bg="white").grid(row=4, column=0, sticky="nw", pady=5)
        mitigation = scrolledtext.ScrolledText(form, font=("Segoe UI", 10),
                                               width=42, height=4)
        mitigation.grid(row=4, column=1, pady=5, padx=10, sticky="w")

        def submit_hazard():
            if not location_entry.get() or not description.get("1.0", "end-1c").strip():
                messagebox.showwarning("Validation Error",
                                     "Please fill in all required fields.")
                return

            new_hazard = {
                "id": f"HAZ-{len(self.hazards) + 1:04d}",
                "category": category.get(),
                "location": location_entry.get(),
                "risk_level": risk_level.get(),
                "description": description.get("1.0", "end-1c"),
                "mitigation": mitigation.get("1.0", "end-1c"),
                "reported_by": self.current_user["username"],
                "department": self.current_user["department"],
                "status": "Active",
                "reported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.hazards.append(new_hazard)
            self.save_data(self.hazards_file, self.hazards)
            messagebox.showinfo("Success",
                              f"Hazard {new_hazard['id']} has been reported successfully.")
            self.show_dashboard_content()

        btn_frame = tk.Frame(form, bg="white")
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Submit Report",
                  style="Success.TButton",
                  command=submit_hazard).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=self.show_dashboard_content).pack(side="left", padx=5)

    def show_hazards_list(self):
        """Display all hazards."""
        self.clear_content()

        tk.Label(self.content_frame, text="📊 Reported Hazards",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 20))

        list_frame = tk.Frame(self.content_frame, bg="white", relief="ridge", bd=1)
        list_frame.pack(fill="both", expand=True, pady=10)

        columns = ("ID", "Category", "Location", "Risk Level", "Reporter", "Status", "Date")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings")

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor="w")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True, padx=5, pady=5)

        for hazard in self.hazards[::-1]:
            tree.insert("", "end", values=(
                hazard.get("id", ""),
                hazard.get("category", ""),
                hazard.get("location", ""),
                hazard.get("risk_level", ""),
                hazard.get("reported_by", ""),
                hazard.get("status", ""),
                hazard.get("reported_at", "")[:10]
            ))

    # ==================== TRAINING ====================
    def show_training(self):
        """Display training modules."""
        self.clear_content()

        tk.Label(self.content_frame, text="🎓 Health & Safety Training",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 20))

        training_modules = [
            ("Fire Safety Awareness", "30 min", "Required", "Covers evacuation procedures, fire extinguisher use, and prevention."),
            ("Manual Handling", "45 min", "Required", "Safe lifting techniques and preventing musculoskeletal injuries."),
            ("Laboratory Safety", "60 min", "Faculty/Staff", "Chemical handling, PPE, and lab emergency procedures."),
            ("First Aid Basics", "90 min", "Optional", "Basic first aid skills including CPR and wound care."),
            ("Mental Health Awareness", "40 min", "Recommended", "Recognizing mental health issues and support resources."),
            ("DSE Assessment", "20 min", "Staff", "Display Screen Equipment assessment for office workers."),
            ("COSHH Training", "50 min", "Lab Users", "Control of Substances Hazardous to Health regulations."),
            ("Electrical Safety", "35 min", "Technical Staff", "Safe use of electrical equipment and PAT testing basics."),
        ]

        # Container for training cards
        canvas = tk.Canvas(self.content_frame, bg="#f0f4f8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#f0f4f8")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for i, (title, duration, required, desc) in enumerate(training_modules):
            card = tk.Frame(scrollable_frame, bg="white", relief="ridge", bd=1)
            card.pack(fill="x", pady=5, padx=5)

            header = tk.Frame(card, bg="white")
            header.pack(fill="x", padx=15, pady=10)

            tk.Label(header, text=title, font=("Segoe UI", 12, "bold"),
                    bg="white", fg="#1a365d").pack(side="left")

            badge_color = "#c53030" if required == "Required" else "#3182ce" if required == "Recommended" else "#718096"
            tk.Label(header, text=f" {required} ", font=("Segoe UI", 9),
                    bg=badge_color, fg="white").pack(side="right", padx=5)
            tk.Label(header, text=f"⏱ {duration}", font=("Segoe UI", 9),
                    bg="white", fg="#4a5568").pack(side="right", padx=5)

            tk.Label(card, text=desc, font=("Segoe UI", 10),
                    bg="white", fg="#4a5568", wraplength=700, justify="left").pack(anchor="w", padx=15, pady=(0, 5))

            # Check if completed
            completed = any(t.get("user") == self.current_user["username"] and
                          t.get("module") == title for t in self.training_records)

            btn_frame = tk.Frame(card, bg="white")
            btn_frame.pack(anchor="w", padx=15, pady=10)

            if completed:
                tk.Label(btn_frame, text="✓ Completed", font=("Segoe UI", 10, "bold"),
                        bg="white", fg="#2f855a").pack(side="left")
            else:
                ttk.Button(btn_frame, text="Mark as Completed",
                          command=lambda t=title: self.complete_training(t)).pack(side="left")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def complete_training(self, module):
        """Mark a training module as completed."""
        record = {
            "user": self.current_user["username"],
            "module": module,
            "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "department": self.current_user["department"]
        }
        self.training_records.append(record)
        self.save_data(self.training_file, self.training_records)
        messagebox.showinfo("Success", f"Training '{module}' marked as completed!")
        self.show_training()

    # ==================== RESOURCES ====================
    def show_resources(self):
        """Show safety resources and guidelines."""
        self.clear_content()

        tk.Label(self.content_frame, text="📚 Safety Resources & Guidelines",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#1a365d").pack(anchor="w", pady=(0, 20))

        resources = [
            ("🔥 Fire Safety Policy",
             "Know your nearest fire exit. In case of fire: Raise alarm, evacuate via nearest safe route, "
             "assemble at designated point, do not use lifts, do not re-enter until cleared."),
            ("🧪 Laboratory Safety Rules",
             "Always wear appropriate PPE. No eating or drinking in labs. Know the location of safety "
             "showers, eyewash stations, and fire extinguishers. Report all spills immediately."),
            ("💼 Office Ergonomics",
             "Adjust your chair so feet are flat on the floor. Screen should be at arm's length, top at "
             "eye level. Take regular breaks every 30-60 minutes. Report any discomfort."),
            ("🧠 Mental Health Support",
             "The university offers counselling services available to all students and staff. "
             "Contact the Wellbeing Centre on extension 2500 or visit the Student Services building."),
            ("🚶 Manual Handling Guidelines",
             "Assess the load before lifting. Keep back straight, bend at knees. Hold load close to body. "
             "Avoid twisting. Use mechanical aids when available."),
            ("⚡ Electrical Safety",
             "Do not overload sockets. Report damaged cables or equipment immediately. All portable "
             "electrical equipment should be PAT tested. Never use electrical equipment in wet conditions."),
        ]

        canvas = tk.Canvas(self.content_frame, bg="#f0f4f8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#f0f4f8")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for title, content in resources:
            card = tk.Frame(scrollable_frame, bg="white", relief="ridge", bd=1)
            card.pack(fill="x", pady=5, padx=5)

            tk.Label(card, text=title, font=("Segoe UI", 13, "bold"),
                    bg="white", fg="#1a365d").pack(anchor="w", padx=15, pady=(10, 5))
            tk.Label(card, text=content, font=("Segoe UI", 10),
                    bg="white", fg="#2d3748", wraplength=700, justify="left").pack(anchor="w", padx=15, pady=(0, 15))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # ==================== EMERGENCY INFO ====================
    def show_emergency(self):
        """Show emergency contact information."""
        self.clear_content()

        tk.Label(self.content_frame, text="🚨 Emergency Information",
                font=("Segoe UI", 20, "bold"),
                bg="#f0f4f8", fg="#c53030").pack(anchor="w", pady=(0, 20))

        # Emergency banner
        banner = tk.Frame(self.content_frame, bg="#c53030", height=80)
        banner.pack(fill="x", pady=10)
        banner.pack_propagate(False)

        tk.Label(banner, text="⚠️ IN CASE OF LIFE-THREATENING EMERGENCY, DIAL 999",
                font=("Segoe UI", 16, "bold"),
                bg="#c53030", fg="white").pack(pady=25)

        # Contacts grid
        contacts_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        contacts_frame.pack(fill="both", expand=True, pady=10)

        contacts = [
            ("🚓 Emergency Services", "999", "Police, Fire, Ambulance"),
            ("🛡️ Campus Security", "01234-567890", "24/7 Available"),
            ("🏥 First Aid", "ext. 2222", "On-campus first aiders"),
            ("👨‍⚕️ Occupational Health", "ext. 2300", "Mon-Fri, 9am-5pm"),
            ("🧠 Mental Health Crisis", "0800-111-2222", "24/7 Samaritans"),
            ("🔥 Fire Officer", "ext. 3000", "Campus fire safety"),
            ("☣️ H&S Department", "ext. 2500", "Health & Safety office"),
            ("🔧 Estates (Urgent)", "ext. 4000", "Building/maintenance issues"),
        ]

        for i, (title, number, note) in enumerate(contacts):
            row = i // 2
            col = i % 2

            card = tk.Frame(contacts_frame, bg="white", relief="ridge", bd=2, padx=20, pady=15)
            card.grid(row=row, column=col, sticky="ew", padx=10, pady=8)
            contacts_frame.grid_columnconfigure(col, weight=1)

            tk.Label(card, text=title, font=("Segoe UI", 12, "bold"),
                    bg="white", fg="#1a365d").pack(anchor="w")
            tk.Label(card, text=number, font=("Segoe UI", 16, "bold"),
                    bg="white", fg="#c53030").pack(anchor="w", pady=5)
            tk.Label(card, text=note, font=("Segoe UI", 9, "italic"),
                    bg="white", fg="#4a5568").pack(anchor="w")

        # Evacuation info
        evac_frame = tk.Frame(self.content_frame, bg="#fef3c7", relief="ridge", bd=2, padx=20, pady=15)
        evac_frame.pack(fill="x", pady=20)

        tk.Label(evac_frame, text="🏃 Evacuation Procedure",
                font=("Segoe UI", 12, "bold"),
                bg="#fef3c7", fg="#92400e").pack(anchor="w")
        tk.Label(evac_frame,
                text="1. On hearing alarm, leave immediately via nearest fire exit\n"
                     "2. Do not use lifts - use stairs\n"
                     "3. Do not stop to collect belongings\n"
                     "4. Proceed to designated assembly point\n"
                     "5. Report to the Fire Warden\n"
                     "6. Do not re-enter building until the all-clear is given",
                font=("Segoe UI", 10),
                bg="#fef3c7", fg="#78350f", justify="left").pack(anchor="w", pady=5)


def main():
    root = tk.Tk()
    app = HealthSafetyPortal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
