"""Student Self-Service Portal — tkinter GUI frame.

Provides a notebook with three tabs:
  - My Journey: educational timeline for the current user
  - My Records: grades and attendance per system
  - Requests: submit and track record requests (admin can resolve)
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.platform.delivery.portals.student.portal_service import (
    PortalService,
    REQUEST_TYPES,
)

SYSTEM_LABELS = {
    "primary": "Primary School",
    "secondary": "Secondary School",
    "sixth_form": "Sixth Form College",
    "university": "University",
}

HEADER_BG = "#1a5276"


class StudentSelfServiceFrame(tk.Frame):
    """Student self-service portal GUI — embeddable tk.Frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._service = PortalService()
        self._auth = auth or {}
        self._username = self._resolve_auth("username", "")
        self._is_admin = self._resolve_auth("role", "").lower() in (
            "admin", "superadmin", "staff",
        )
        self._build_ui()

    def _resolve_auth(self, key, default=""):
        """Get a value from auth whether it's a dict or a UserAuth object."""
        if isinstance(self._auth, dict):
            return self._auth.get(key, default)
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get(key, default)
        return default

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Student Self-Service Portal",
            font=("Helvetica", 15, "bold"),
            bg=HEADER_BG,
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        # Notebook
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_journey_tab()
        self._build_records_tab()
        self._build_requests_tab()

    # ---- Tab 1: My Journey ------------------------------------------------

    def _build_journey_tab(self):
        tab = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(tab, text="My Journey")

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=10, pady=8)
        ttk.Button(btn_frame, text="Load My Journey", command=self._load_journey).pack(
            side="left"
        )
        self._journey_status = tk.StringVar(value="")
        tk.Label(
            btn_frame, textvariable=self._journey_status, bg="#ecf0f1",
            font=("Helvetica", 9, "italic"), fg="#7f8c8d",
        ).pack(side="left", padx=10)

        # Scrollable frame
        outer = tk.Frame(tab, bg="#ecf0f1")
        outer.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._journey_canvas = tk.Canvas(outer, bg="#ecf0f1", highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=self._journey_canvas.yview)
        self._journey_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._journey_canvas.pack(side="left", fill="both", expand=True)

        self._journey_frame = tk.Frame(self._journey_canvas, bg="#ecf0f1")
        self._journey_win = self._journey_canvas.create_window(
            (0, 0), window=self._journey_frame, anchor="nw"
        )
        self._journey_frame.bind(
            "<Configure>",
            lambda e: self._journey_canvas.configure(
                scrollregion=self._journey_canvas.bbox("all")
            ),
        )
        self._journey_canvas.bind(
            "<Configure>",
            lambda e: self._journey_canvas.itemconfig(self._journey_win, width=e.width),
        )

    def _load_journey(self):
        for w in self._journey_frame.winfo_children():
            w.destroy()

        if not self._username:
            self._journey_status.set("No user logged in.")
            return

        try:
            stages = self._service.get_my_journey(self._username)
        except Exception as exc:
            self._journey_status.set(f"Error: {exc}")
            return

        if not stages:
            self._journey_status.set("No journey data found.")
            tk.Label(
                self._journey_frame, text="No journey records found for your account.",
                bg="#ecf0f1", fg="#95a5a6", font=("Helvetica", 10, "italic"), pady=20,
            ).pack(fill="x")
            return

        self._journey_status.set(f"{len(stages)} stage(s) found")

        colours = {
            "primary": "#27ae60", "secondary": "#2980b9",
            "sixth_form": "#8e44ad", "university": "#c0392b",
        }

        for idx, stage in enumerate(stages):
            sys_key = stage.get("system", "")
            colour = colours.get(sys_key, "#7f8c8d")
            label = SYSTEM_LABELS.get(sys_key, sys_key.title())

            card = tk.LabelFrame(
                self._journey_frame, text=f"  {label}  ", bg="white",
                fg=colour, font=("Helvetica", 11, "bold"),
                padx=12, pady=8, relief="groove", bd=1,
            )
            card.pack(fill="x", padx=5, pady=5)

            row = 0
            for field, value in [
                ("Student ID", stage.get("student_id", "")),
                ("Name", stage.get("name", "")),
                ("Year / Group", stage.get("year_group", "")),
                ("Status", stage.get("status", "")),
                ("Enrolled", stage.get("enrolled_date", "")),
            ]:
                if not value:
                    continue
                tk.Label(card, text=f"{field}:", bg="white",
                         font=("Helvetica", 9, "bold"), anchor="w").grid(
                    row=row, column=0, sticky="w", padx=(0, 10), pady=1)
                tk.Label(card, text=str(value), bg="white",
                         font=("Helvetica", 9), anchor="w").grid(
                    row=row, column=1, sticky="w", pady=1)
                row += 1

        self._journey_canvas.yview_moveto(0)

    # ---- Tab 2: My Records ------------------------------------------------

    def _build_records_tab(self):
        tab = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(tab, text="My Records")

        sel_frame = tk.Frame(tab, bg="#ecf0f1")
        sel_frame.pack(fill="x", padx=10, pady=8)

        tk.Label(sel_frame, text="System:", bg="#ecf0f1",
                 font=("Helvetica", 10)).pack(side="left")
        self._system_var = tk.StringVar(value="primary")
        sys_combo = ttk.Combobox(
            sel_frame, textvariable=self._system_var,
            values=["primary", "secondary", "sixth_form", "university"],
            state="readonly", width=18,
        )
        sys_combo.pack(side="left", padx=5)
        ttk.Button(sel_frame, text="Load Records", command=self._load_records).pack(
            side="left", padx=5
        )
        self._records_status = tk.StringVar(value="")
        tk.Label(sel_frame, textvariable=self._records_status, bg="#ecf0f1",
                 font=("Helvetica", 9, "italic"), fg="#7f8c8d").pack(side="left", padx=10)

        # Grades treeview
        tk.Label(tab, text="Grades / Assessments", bg="#ecf0f1",
                 font=("Helvetica", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(5, 0))

        grades_frame = tk.Frame(tab)
        grades_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        g_cols = ("field1", "field2", "field3", "field4", "field5")
        self._grades_tree = ttk.Treeview(
            grades_frame, columns=g_cols, show="headings", height=8,
        )
        for c in g_cols:
            self._grades_tree.heading(c, text=c)
            self._grades_tree.column(c, width=120)
        g_vsb = ttk.Scrollbar(grades_frame, orient="vertical", command=self._grades_tree.yview)
        self._grades_tree.configure(yscrollcommand=g_vsb.set)
        self._grades_tree.pack(side="left", fill="both", expand=True)
        g_vsb.pack(side="right", fill="y")

        # Attendance summary
        tk.Label(tab, text="Attendance Summary", bg="#ecf0f1",
                 font=("Helvetica", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(5, 0))
        self._att_label = tk.Label(
            tab, text="(no data)", bg="#ecf0f1", font=("Helvetica", 10), anchor="w",
        )
        self._att_label.pack(fill="x", padx=15, pady=(0, 10))

    def _load_records(self):
        self._grades_tree.delete(*self._grades_tree.get_children())
        self._att_label.config(text="(no data)")

        if not self._username:
            self._records_status.set("No user logged in.")
            return

        system = self._system_var.get()
        try:
            records = self._service.get_my_records(self._username, system)
        except Exception as exc:
            self._records_status.set(f"Error: {exc}")
            return

        # Grades
        grades = records.get("grades", [])
        if grades:
            # Determine columns dynamically from first record
            keys = list(grades[0].keys())[:5]
            for i, c in enumerate(("field1", "field2", "field3", "field4", "field5")):
                heading = keys[i] if i < len(keys) else ""
                self._grades_tree.heading(c, text=heading)
            for g in grades[:200]:
                vals = tuple(str(g.get(k, "")) for k in keys)
                # Pad to 5
                vals = vals + ("",) * (5 - len(vals))
                self._grades_tree.insert("", "end", values=vals)
            self._records_status.set(f"{len(grades)} grade record(s)")
        else:
            self._records_status.set("No grade records found.")

        # Attendance
        att = records.get("attendance", {})
        if att:
            parts = []
            if "total_sessions" in att:
                parts.append(f"Total sessions: {att['total_sessions']}")
            if "present" in att:
                parts.append(f"Present: {att['present']}")
            if "percentage" in att:
                parts.append(f"Attendance: {att['percentage']}%")
            self._att_label.config(text="  |  ".join(parts) if parts else "(no data)")

    # ---- Tab 3: Requests ---------------------------------------------------

    def _build_requests_tab(self):
        tab = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(tab, text="Requests")

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=10, pady=8)
        ttk.Button(btn_frame, text="Refresh", command=self._load_requests).pack(side="left")
        ttk.Button(btn_frame, text="New Request", command=self._new_request_dialog).pack(
            side="left", padx=5
        )
        if self._is_admin:
            ttk.Button(btn_frame, text="View Pending (Admin)",
                       command=self._load_pending_requests).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Resolve Selected",
                       command=self._resolve_selected).pack(side="left", padx=5)

        self._req_status = tk.StringVar(value="")
        tk.Label(btn_frame, textvariable=self._req_status, bg="#ecf0f1",
                 font=("Helvetica", 9, "italic"), fg="#7f8c8d").pack(side="left", padx=10)

        # Treeview
        req_frame = tk.Frame(tab)
        req_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        r_cols = ("id", "username", "type", "details", "status", "created_at", "resolved_by")
        self._req_tree = ttk.Treeview(
            req_frame, columns=r_cols, show="headings", height=12,
        )
        for col, heading, width in [
            ("id", "ID", 40),
            ("username", "User", 100),
            ("type", "Type", 90),
            ("details", "Details", 220),
            ("status", "Status", 80),
            ("created_at", "Created", 140),
            ("resolved_by", "Resolved By", 100),
        ]:
            self._req_tree.heading(col, text=heading)
            self._req_tree.column(col, width=width)

        r_vsb = ttk.Scrollbar(req_frame, orient="vertical", command=self._req_tree.yview)
        self._req_tree.configure(yscrollcommand=r_vsb.set)
        self._req_tree.pack(side="left", fill="both", expand=True)
        r_vsb.pack(side="right", fill="y")

    def _load_requests(self):
        self._req_tree.delete(*self._req_tree.get_children())
        if not self._username:
            self._req_status.set("No user logged in.")
            return
        try:
            reqs = self._service.get_my_requests(self._username)
        except Exception as exc:
            self._req_status.set(f"Error: {exc}")
            return
        self._req_status.set(f"{len(reqs)} request(s)")
        for r in reqs:
            self._req_tree.insert("", "end", iid=str(r["id"]), values=(
                r.get("id", ""),
                r.get("username", ""),
                r.get("request_type", ""),
                r.get("details", ""),
                r.get("status", ""),
                r.get("created_at", ""),
                r.get("resolved_by", ""),
            ))

    def _load_pending_requests(self):
        self._req_tree.delete(*self._req_tree.get_children())
        try:
            reqs = self._service.get_pending_requests()
        except Exception as exc:
            self._req_status.set(f"Error: {exc}")
            return
        self._req_status.set(f"{len(reqs)} pending request(s)")
        for r in reqs:
            self._req_tree.insert("", "end", iid=str(r["id"]), values=(
                r.get("id", ""),
                r.get("username", ""),
                r.get("request_type", ""),
                r.get("details", ""),
                r.get("status", ""),
                r.get("created_at", ""),
                r.get("resolved_by", ""),
            ))

    def _new_request_dialog(self):
        if not self._username:
            messagebox.showwarning("Request", "No user logged in.", parent=self)
            return

        dlg = tk.Toplevel(self)
        dlg.title("New Record Request")
        dlg.geometry("420x300")
        dlg.resizable(False, False)
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Request Type:", bg="#ecf0f1",
                 font=("Helvetica", 10)).pack(anchor="w", padx=15, pady=(15, 2))
        type_var = tk.StringVar(value=REQUEST_TYPES[0])
        ttk.Combobox(
            dlg, textvariable=type_var, values=list(REQUEST_TYPES),
            state="readonly", width=25,
        ).pack(anchor="w", padx=15)

        tk.Label(dlg, text="Details:", bg="#ecf0f1",
                 font=("Helvetica", 10)).pack(anchor="w", padx=15, pady=(10, 2))
        details_text = tk.Text(dlg, height=6, width=45, wrap="word")
        details_text.pack(padx=15)

        def _submit():
            rtype = type_var.get()
            details = details_text.get("1.0", "end").strip()
            if not details:
                messagebox.showwarning("Request", "Please enter details.", parent=dlg)
                return
            try:
                self._service.submit_record_request(self._username, rtype, details)
                messagebox.showinfo("Request", "Request submitted.", parent=dlg)
                dlg.destroy()
                self._load_requests()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=dlg)

        ttk.Button(dlg, text="Submit", command=_submit).pack(pady=15)

    def _resolve_selected(self):
        sel = self._req_tree.selection()
        if not sel:
            messagebox.showwarning("Resolve", "Select a request first.", parent=self)
            return
        req_id = int(sel[0])
        try:
            self._service.resolve_request(req_id, self._username, status="resolved")
            messagebox.showinfo("Resolved", f"Request {req_id} resolved.", parent=self)
            self._load_pending_requests()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def refresh(self):
        """Called when the module is shown in the sidebar."""
        pass
