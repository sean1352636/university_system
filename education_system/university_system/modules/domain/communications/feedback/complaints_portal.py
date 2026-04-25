"""
University Complaints Portal
A GUI application for students and staff to submit and track complaints.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import os
from datetime import datetime
import uuid


# ---------- Data Layer ----------
DATA_FILE = "complaints.json"


def load_complaints():
    """Load complaints from JSON file."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_complaints(complaints):
    """Save complaints to JSON file."""
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(complaints, f, indent=2)
        return True
    except IOError:
        return False


# ---------- Main Application ----------
class ComplaintsPortal(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("University Complaints Portal")
        self.geometry("900x650")
        self.configure(bg="#f0f4f8")

        self.complaints = load_complaints()

        self._configure_styles()
        self._build_header()
        self._build_notebook()

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background="#f0f4f8", borderwidth=0)
        style.configure("TNotebook.Tab", padding=[20, 10], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", "#1e3a8a"), ("!selected", "#cbd5e1")],
                  foreground=[("selected", "white"), ("!selected", "#1e293b")])
        style.configure("TFrame", background="#f0f4f8")
        style.configure("TLabel", background="#f0f4f8", font=("Segoe UI", 10))
        style.configure("Header.TLabel", background="#1e3a8a", foreground="white",
                        font=("Segoe UI", 18, "bold"), padding=15)
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Submit.TButton", background="#1e3a8a", foreground="white")
        style.map("Submit.TButton", background=[("active", "#2563eb")])
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        background="#1e3a8a", foreground="white")

    def _build_header(self):
        header = ttk.Label(self, text="🎓  University Complaints Portal",
                           style="Header.TLabel", anchor="center")
        header.pack(fill="x")

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)

        self.submit_tab = SubmitTab(self.notebook, self)
        self.view_tab = ViewTab(self.notebook, self)
        self.admin_tab = AdminTab(self.notebook, self)

        self.notebook.add(self.submit_tab, text="📝 Submit Complaint")
        self.notebook.add(self.view_tab, text="🔍 Track Complaint")
        self.notebook.add(self.admin_tab, text="⚙️ Admin Panel")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, event):
        selected = self.notebook.index("current")
        if selected == 2:
            self.admin_tab.refresh()

    def add_complaint(self, complaint):
        self.complaints.append(complaint)
        save_complaints(self.complaints)

    def update_complaint(self, complaint_id, status, response):
        for c in self.complaints:
            if c["id"] == complaint_id:
                c["status"] = status
                c["response"] = response
                c["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                break
        save_complaints(self.complaints)

    def find_complaint(self, complaint_id):
        for c in self.complaints:
            if c["id"] == complaint_id:
                return c
        return None


# ---------- Submit Tab ----------
class SubmitTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build_form()

    def _build_form(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=40, pady=20)

        ttk.Label(container, text="Submit a New Complaint",
                  font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2,
                                                      sticky="w", pady=(0, 20))

        # Name
        ttk.Label(container, text="Full Name *").grid(row=1, column=0, sticky="w", pady=5)
        self.name_entry = ttk.Entry(container, width=50, font=("Segoe UI", 10))
        self.name_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=(10, 0))

        # Student ID
        ttk.Label(container, text="Student/Staff ID *").grid(row=2, column=0, sticky="w", pady=5)
        self.id_entry = ttk.Entry(container, width=50, font=("Segoe UI", 10))
        self.id_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=(10, 0))

        # Email
        ttk.Label(container, text="Email Address *").grid(row=3, column=0, sticky="w", pady=5)
        self.email_entry = ttk.Entry(container, width=50, font=("Segoe UI", 10))
        self.email_entry.grid(row=3, column=1, sticky="ew", pady=5, padx=(10, 0))

        # Category
        ttk.Label(container, text="Category *").grid(row=4, column=0, sticky="w", pady=5)
        self.category_var = tk.StringVar()
        categories = ["Academic", "Facilities", "Hostel/Accommodation", "Library",
                      "IT Services", "Food Services", "Transportation",
                      "Harassment/Discrimination", "Financial/Fees", "Other"]
        self.category_menu = ttk.Combobox(container, textvariable=self.category_var,
                                          values=categories, state="readonly",
                                          font=("Segoe UI", 10))
        self.category_menu.grid(row=4, column=1, sticky="ew", pady=5, padx=(10, 0))
        self.category_menu.current(0)

        # Priority
        ttk.Label(container, text="Priority *").grid(row=5, column=0, sticky="w", pady=5)
        self.priority_var = tk.StringVar(value="Medium")
        priority_frame = ttk.Frame(container)
        priority_frame.grid(row=5, column=1, sticky="w", pady=5, padx=(10, 0))
        for i, level in enumerate(["Low", "Medium", "High", "Urgent"]):
            ttk.Radiobutton(priority_frame, text=level, variable=self.priority_var,
                            value=level).pack(side="left", padx=5)

        # Subject
        ttk.Label(container, text="Subject *").grid(row=6, column=0, sticky="w", pady=5)
        self.subject_entry = ttk.Entry(container, width=50, font=("Segoe UI", 10))
        self.subject_entry.grid(row=6, column=1, sticky="ew", pady=5, padx=(10, 0))

        # Description
        ttk.Label(container, text="Description *").grid(row=7, column=0, sticky="nw", pady=5)
        self.desc_text = scrolledtext.ScrolledText(container, width=50, height=8,
                                                    font=("Segoe UI", 10), wrap="word")
        self.desc_text.grid(row=7, column=1, sticky="ew", pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=8, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Submit Complaint", style="Submit.TButton",
                   command=self.submit).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Clear Form",
                   command=self.clear).pack(side="left", padx=5)

        container.columnconfigure(1, weight=1)

    def submit(self):
        name = self.name_entry.get().strip()
        user_id = self.id_entry.get().strip()
        email = self.email_entry.get().strip()
        category = self.category_var.get()
        priority = self.priority_var.get()
        subject = self.subject_entry.get().strip()
        description = self.desc_text.get("1.0", "end").strip()

        if not all([name, user_id, email, subject, description]):
            messagebox.showerror("Validation Error",
                                 "Please fill in all required fields (*)")
            return

        if "@" not in email or "." not in email:
            messagebox.showerror("Validation Error", "Please enter a valid email address.")
            return

        complaint = {
            "id": str(uuid.uuid4())[:8].upper(),
            "name": name,
            "user_id": user_id,
            "email": email,
            "category": category,
            "priority": priority,
            "subject": subject,
            "description": description,
            "status": "Pending",
            "response": "",
            "submitted": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        self.app.add_complaint(complaint)
        messagebox.showinfo("Success",
                            f"Complaint submitted successfully!\n\n"
                            f"Your Tracking ID: {complaint['id']}\n\n"
                            f"Please save this ID to track your complaint.")
        self.clear()

    def clear(self):
        self.name_entry.delete(0, "end")
        self.id_entry.delete(0, "end")
        self.email_entry.delete(0, "end")
        self.subject_entry.delete(0, "end")
        self.desc_text.delete("1.0", "end")
        self.category_menu.current(0)
        self.priority_var.set("Medium")


# ---------- View/Track Tab ----------
class ViewTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=40, pady=20)

        ttk.Label(container, text="Track Your Complaint",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 15))

        search_frame = ttk.Frame(container)
        search_frame.pack(fill="x", pady=10)
        ttk.Label(search_frame, text="Enter Tracking ID:").pack(side="left")
        self.track_entry = ttk.Entry(search_frame, width=20, font=("Segoe UI", 10))
        self.track_entry.pack(side="left", padx=10)
        ttk.Button(search_frame, text="Search", style="Submit.TButton",
                   command=self.search).pack(side="left")

        self.result_text = scrolledtext.ScrolledText(container, height=20,
                                                     font=("Consolas", 10),
                                                     wrap="word", bg="white")
        self.result_text.pack(fill="both", expand=True, pady=15)
        self.result_text.config(state="disabled")

    def search(self):
        cid = self.track_entry.get().strip().upper()
        if not cid:
            messagebox.showwarning("Input Error", "Please enter a tracking ID.")
            return

        complaint = self.app.find_complaint(cid)
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", "end")

        if complaint:
            status_color = {
                "Pending": "🟡",
                "In Progress": "🔵",
                "Resolved": "🟢",
                "Rejected": "🔴",
            }.get(complaint["status"], "⚪")

            info = f"""
╔══════════════════════════════════════════════════════════════╗
║                    COMPLAINT DETAILS                         ║
╚══════════════════════════════════════════════════════════════╝

Tracking ID    : {complaint['id']}
Status         : {status_color} {complaint['status']}
Priority       : {complaint['priority']}
Category       : {complaint['category']}

─────────────────── Submitter Information ───────────────────
Name           : {complaint['name']}
Student/Staff ID: {complaint['user_id']}
Email          : {complaint['email']}

─────────────────────── Complaint ────────────────────────────
Subject        : {complaint['subject']}

Description    :
{complaint['description']}

──────────────────── Admin Response ──────────────────────────
{complaint['response'] if complaint['response'] else '(No response yet)'}

─────────────────────── Timeline ─────────────────────────────
Submitted      : {complaint['submitted']}
Last Updated   : {complaint['updated']}
"""
            self.result_text.insert("1.0", info)
        else:
            self.result_text.insert("1.0",
                                    f"\n  No complaint found with ID: {cid}\n\n"
                                    f"  Please verify your tracking ID and try again.")

        self.result_text.config(state="disabled")


# ---------- Admin Tab ----------
class AdminTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.authenticated = False
        self._build_login()

    def _build_login(self):
        self.login_frame = ttk.Frame(self)
        self.login_frame.pack(fill="both", expand=True, padx=40, pady=60)

        ttk.Label(self.login_frame, text="🔒 Admin Authentication",
                  font=("Segoe UI", 14, "bold")).pack(pady=10)
        ttk.Label(self.login_frame,
                  text="(Default password: admin123)",
                  font=("Segoe UI", 9, "italic"),
                  foreground="#64748b").pack()

        pw_frame = ttk.Frame(self.login_frame)
        pw_frame.pack(pady=20)
        ttk.Label(pw_frame, text="Password:").pack(side="left", padx=5)
        self.pw_entry = ttk.Entry(pw_frame, show="*", width=25, font=("Segoe UI", 10))
        self.pw_entry.pack(side="left", padx=5)
        self.pw_entry.bind("<Return>", lambda e: self.authenticate())

        ttk.Button(self.login_frame, text="Login", style="Submit.TButton",
                   command=self.authenticate).pack(pady=5)

    def authenticate(self):
        if self.pw_entry.get() == "admin123":
            self.authenticated = True
            self.login_frame.destroy()
            self._build_dashboard()
            self.refresh()
        else:
            messagebox.showerror("Access Denied", "Incorrect password.")
            self.pw_entry.delete(0, "end")

    def _build_dashboard(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # Stats bar
        self.stats_frame = ttk.Frame(container)
        self.stats_frame.pack(fill="x", pady=(0, 10))

        # Filter bar
        filter_frame = ttk.Frame(container)
        filter_frame.pack(fill="x", pady=5)
        ttk.Label(filter_frame, text="Filter by Status:").pack(side="left", padx=5)
        self.filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var,
                                     values=["All", "Pending", "In Progress", "Resolved", "Rejected"],
                                     state="readonly", width=15)
        filter_combo.pack(side="left", padx=5)
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(filter_frame, text="🔄 Refresh", command=self.refresh).pack(side="left", padx=5)

        # Treeview
        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill="both", expand=True, pady=10)

        columns = ("ID", "Name", "Category", "Priority", "Subject", "Status", "Date")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)

        widths = {"ID": 90, "Name": 140, "Category": 130, "Priority": 80,
                  "Subject": 200, "Status": 100, "Date": 130}
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self.open_complaint)

        # Action buttons
        action_frame = ttk.Frame(container)
        action_frame.pack(fill="x", pady=10)
        ttk.Button(action_frame, text="View/Update Selected", style="Submit.TButton",
                   command=lambda: self.open_complaint(None)).pack(side="left", padx=5)
        ttk.Button(action_frame, text="Delete Selected",
                   command=self.delete_complaint).pack(side="left", padx=5)

        # Configure row tags for status colors
        self.tree.tag_configure("Pending", background="#fef3c7")
        self.tree.tag_configure("In Progress", background="#dbeafe")
        self.tree.tag_configure("Resolved", background="#d1fae5")
        self.tree.tag_configure("Rejected", background="#fee2e2")

    def refresh(self):
        if not self.authenticated:
            return

        # Update stats
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        complaints = self.app.complaints
        total = len(complaints)
        pending = sum(1 for c in complaints if c["status"] == "Pending")
        in_progress = sum(1 for c in complaints if c["status"] == "In Progress")
        resolved = sum(1 for c in complaints if c["status"] == "Resolved")
        rejected = sum(1 for c in complaints if c["status"] == "Rejected")

        stats = [
            ("Total", total, "#1e3a8a"),
            ("Pending", pending, "#d97706"),
            ("In Progress", in_progress, "#2563eb"),
            ("Resolved", resolved, "#059669"),
            ("Rejected", rejected, "#dc2626"),
        ]

        for label, value, color in stats:
            card = tk.Frame(self.stats_frame, bg=color, padx=15, pady=10)
            card.pack(side="left", padx=5, fill="x", expand=True)
            tk.Label(card, text=str(value), bg=color, fg="white",
                     font=("Segoe UI", 16, "bold")).pack()
            tk.Label(card, text=label, bg=color, fg="white",
                     font=("Segoe UI", 9)).pack()

        # Refresh tree
        for item in self.tree.get_children():
            self.tree.delete(item)

        filter_status = self.filter_var.get()
        for c in complaints:
            if filter_status != "All" and c["status"] != filter_status:
                continue
            self.tree.insert("", "end", values=(
                c["id"], c["name"], c["category"], c["priority"],
                c["subject"][:40] + ("..." if len(c["subject"]) > 40 else ""),
                c["status"], c["submitted"]
            ), tags=(c["status"],))

    def open_complaint(self, event):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a complaint first.")
            return

        cid = self.tree.item(selection[0])["values"][0]
        complaint = self.app.find_complaint(cid)
        if complaint:
            ComplaintDetailWindow(self, self.app, complaint)

    def delete_complaint(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a complaint first.")
            return

        cid = self.tree.item(selection[0])["values"][0]
        if messagebox.askyesno("Confirm Delete",
                               f"Delete complaint {cid}? This cannot be undone."):
            self.app.complaints = [c for c in self.app.complaints if c["id"] != cid]
            save_complaints(self.app.complaints)
            self.refresh()
            messagebox.showinfo("Deleted", "Complaint deleted successfully.")


# ---------- Complaint Detail Window ----------
class ComplaintDetailWindow(tk.Toplevel):
    def __init__(self, parent, app, complaint):
        super().__init__(parent)
        self.app = app
        self.complaint = complaint
        self.parent_tab = parent

        self.title(f"Complaint {complaint['id']}")
        self.geometry("600x600")
        self.configure(bg="#f0f4f8")
        self.transient(parent)
        self.grab_set()

        self._build()

    def _build(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(container, text=f"Complaint #{self.complaint['id']}",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")

        info = f"""Submitter: {self.complaint['name']} ({self.complaint['user_id']})
Email: {self.complaint['email']}
Category: {self.complaint['category']}  |  Priority: {self.complaint['priority']}
Submitted: {self.complaint['submitted']}  |  Updated: {self.complaint['updated']}

Subject: {self.complaint['subject']}"""
        ttk.Label(container, text=info, justify="left",
                  font=("Segoe UI", 10)).pack(anchor="w", pady=10)

        ttk.Label(container, text="Description:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        desc_box = scrolledtext.ScrolledText(container, height=6, wrap="word",
                                              font=("Segoe UI", 10))
        desc_box.pack(fill="x", pady=5)
        desc_box.insert("1.0", self.complaint["description"])
        desc_box.config(state="disabled")

        ttk.Label(container, text="Status:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.status_var = tk.StringVar(value=self.complaint["status"])
        status_combo = ttk.Combobox(container, textvariable=self.status_var,
                                     values=["Pending", "In Progress", "Resolved", "Rejected"],
                                     state="readonly")
        status_combo.pack(fill="x", pady=5)

        ttk.Label(container, text="Admin Response:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.response_box = scrolledtext.ScrolledText(container, height=6, wrap="word",
                                                      font=("Segoe UI", 10))
        self.response_box.pack(fill="x", pady=5)
        self.response_box.insert("1.0", self.complaint["response"])

        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save Changes", style="Submit.TButton",
                   command=self.save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Close",
                   command=self.destroy).pack(side="left", padx=5)

    def save(self):
        status = self.status_var.get()
        response = self.response_box.get("1.0", "end").strip()
        self.app.update_complaint(self.complaint["id"], status, response)
        self.parent_tab.refresh()
        messagebox.showinfo("Saved", "Complaint updated successfully.")
        self.destroy()


# ---------- Entry Point ----------
if __name__ == "__main__":
    app = ComplaintsPortal()
    app.mainloop()
