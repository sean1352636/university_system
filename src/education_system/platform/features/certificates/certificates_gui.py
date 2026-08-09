"""GUI component for certificate and transcript management.

Provides a tabbed interface with:
  - Certificates: View and manage certificates
  - Transcripts: View and export transcripts
  - Generate: Create new certificates
  - Verify: Verify certificates by number
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

logger = logging.getLogger(__name__)


class CertificatesGUI(tk.Frame):
    """Tabbed frame for certificates and transcripts management."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth

        # Lazy-load services
        self._cert_svc = None

        self._build_ui()

    def _get_cert_svc(self):
        if self._cert_svc is None:
            from education_system.platform.features.certificates.certificate_service import CertificateService
            self._cert_svc = CertificateService(self._db_path)
        return self._cert_svc

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _current_user(self):
        if not self._auth:
            return None
        user = getattr(self._auth, "current_user", None)
        if user is None and hasattr(self._auth, "get_current_user"):
            try:
                user = self._auth.get_current_user()
            except Exception:
                user = None
        return user or None

    def _is_student(self):
        """True iff the logged-in user has only the 'student' role.

        Staff/admin (or unauthenticated callers) get the full GUI.
        """
        user = self._current_user()
        if not user:
            return False
        role = (user.get("role") or "").lower()
        if role:
            return role == "student"
        # Multi-system shared auth packs roles per system_key.
        roles = {
            (s.get("role") or "").lower()
            for s in (user.get("systems") or [])
        }
        roles.discard("")
        return bool(roles) and roles.issubset({"student"})

    def _student_identity(self):
        """Return (student_id, display_name) for the logged-in student."""
        user = self._current_user() or {}
        sid = (
            user.get("student_id")
            or user.get("user_id")
            or user.get("id")
            or user.get("username")
            or ""
        )
        name = (
            user.get("display_name")
            or user.get("name")
            or (
                f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            )
            or str(sid)
        )
        return str(sid), name

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#f5f6fa")

        student_mode = self._is_student()
        sid, name = self._student_identity() if student_mode else ("", "")

        # Header
        header = tk.Frame(self, bg="#1a3c6e", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        header_text = (
            f"My Certificates & Transcript — {name or sid}"
            if student_mode
            else "Certificates & Transcripts"
        )
        tk.Label(
            header,
            text=header_text,
            font=("Helvetica", 16, "bold"),
            bg="#1a3c6e",
            fg="white",
        ).pack(side="left", padx=20)

        # Notebook
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=10, pady=10)

        if student_mode:
            self._build_my_certificates_tab(sid)
            self._build_my_transcript_tab(name or sid)
            return

        # Staff/admin: full management surface.
        self._build_certificates_tab()
        self._build_transcripts_tab()
        self._build_generate_tab()
        self._build_verify_tab()

    # ── Student-only Tabs ────────────────────────────────────────────

    def _build_my_certificates_tab(self, student_id):
        tab = tk.Frame(self._notebook, bg="#ffffff")
        self._notebook.add(tab, text="  My Certificate  ")

        info = tk.Frame(tab, bg="#ffffff", pady=10)
        info.pack(fill="x", padx=15)
        tk.Label(
            info,
            text=f"Certificates issued to {student_id}",
            bg="#ffffff",
            font=("Helvetica", 11, "bold"),
            fg="#1a3c6e",
        ).pack(side="left")
        ttk.Button(info, text="Refresh",
                   command=lambda: self._load_my_certificates(student_id)).pack(side="right", padx=(0, 5))
        ttk.Button(info, text="Export Selected as HTML",
                   command=self._export_cert_html).pack(side="right", padx=(0, 5))

        cols = ("cert_number", "type", "course", "award_date", "grade", "status", "issued_by")
        self._cert_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        headers = {
            "cert_number": ("Certificate No.", 170),
            "type": ("Type", 100),
            "course": ("Course", 200),
            "award_date": ("Award Date", 100),
            "grade": ("Grade", 70),
            "status": ("Status", 80),
            "issued_by": ("Issued By", 100),
        }
        for col, (heading, width) in headers.items():
            self._cert_tree.heading(col, text=heading)
            self._cert_tree.column(col, width=width, minwidth=40)

        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._cert_tree.yview)
        self._cert_tree.configure(yscrollcommand=vsb.set)
        self._cert_tree.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        vsb.pack(side="right", fill="y")

        # Load on open
        self.after(0, lambda: self._load_my_certificates(student_id))

    def _load_my_certificates(self, student_id):
        for item in self._cert_tree.get_children():
            self._cert_tree.delete(item)
        try:
            certs = self._get_cert_svc().list_certificates(student_id=student_id)
            for c in certs:
                self._cert_tree.insert(
                    "",
                    "end",
                    iid=str(c.get("id", "")),
                    values=(
                        c.get("certificate_number", ""),
                        c.get("certificate_type", ""),
                        c.get("course_name", ""),
                        c.get("award_date", ""),
                        c.get("grade", ""),
                        c.get("status", ""),
                        c.get("issued_by", ""),
                    ),
                )
            if not certs:
                # Inline notice instead of a popup so the empty state is calm.
                self._cert_tree.insert(
                    "", "end", values=("(none)", "", "No certificates on file yet.", "", "", "", "")
                )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load certificates: {e}", parent=self)

    def _build_my_transcript_tab(self, student_name):
        from education_system.platform.features.certificates.digital_transcript_frame import DigitalTranscriptFrame

        tab = tk.Frame(self._notebook, bg="#ffffff")
        self._notebook.add(tab, text="  My Transcript  ")
        DigitalTranscriptFrame(
            tab,
            db_path=self._db_path,
            auth=self._auth,
            restrict_to_student=student_name,
        ).pack(fill="both", expand=True)

    # ── Certificates Tab ─────────────────────────────────────────────

    def _build_certificates_tab(self):
        tab = tk.Frame(self._notebook, bg="#ffffff")
        self._notebook.add(tab, text="  Certificates  ")

        # Controls
        ctrl = tk.Frame(tab, bg="#ffffff", pady=10)
        ctrl.pack(fill="x", padx=15)

        tk.Label(ctrl, text="Student ID:", bg="#ffffff",
                 font=("Helvetica", 10)).pack(side="left", padx=(0, 5))
        self._cert_student_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=self._cert_student_var, width=20).pack(
            side="left", padx=(0, 10)
        )
        ttk.Button(ctrl, text="Search", command=self._search_certificates).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(ctrl, text="Show All", command=self._show_all_certificates).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(ctrl, text="Export HTML", command=self._export_cert_html).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(ctrl, text="Revoke Selected", command=self._revoke_selected).pack(
            side="left"
        )

        # Treeview
        cols = ("id", "student_id", "cert_number", "type", "course",
                "award_date", "grade", "status", "issued_by")
        self._cert_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        headers = {
            "id": ("ID", 40),
            "student_id": ("Student", 80),
            "cert_number": ("Certificate No.", 150),
            "type": ("Type", 90),
            "course": ("Course", 160),
            "award_date": ("Award Date", 90),
            "grade": ("Grade", 60),
            "status": ("Status", 70),
            "issued_by": ("Issued By", 80),
        }
        for col, (heading, width) in headers.items():
            self._cert_tree.heading(col, text=heading)
            self._cert_tree.column(col, width=width, minwidth=30)

        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._cert_tree.yview)
        self._cert_tree.configure(yscrollcommand=vsb.set)
        self._cert_tree.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        vsb.pack(side="right", fill="y")

    def _search_certificates(self):
        sid = self._cert_student_var.get().strip()
        if not sid:
            messagebox.showwarning("Input Required", "Enter a Student ID to search.",
                                   parent=self)
            return
        self._load_certificates(student_id=sid)

    def _show_all_certificates(self):
        self._load_certificates()

    def _load_certificates(self, student_id=None):
        for item in self._cert_tree.get_children():
            self._cert_tree.delete(item)
        try:
            certs = self._get_cert_svc().list_certificates(student_id=student_id)
            for c in certs:
                self._cert_tree.insert(
                    "",
                    "end",
                    iid=str(c.get("id", "")),
                    values=(
                        c.get("id", ""),
                        c.get("student_id", ""),
                        c.get("certificate_number", ""),
                        c.get("certificate_type", ""),
                        c.get("course_name", ""),
                        c.get("award_date", ""),
                        c.get("grade", ""),
                        c.get("status", ""),
                        c.get("issued_by", ""),
                    ),
                )
            if not certs:
                messagebox.showinfo("No Results", "No certificates found.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load certificates: {e}",
                                 parent=self)

    def _export_cert_html(self):
        sel = self._cert_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a certificate to export.",
                                   parent=self)
            return
        cert_id = sel[0]  # iid is the cert id; works for both staff and student tabs
        try:
            html = self._get_cert_svc().export_certificate_html(int(cert_id))
            path = filedialog.asksaveasfilename(
                parent=self,
                defaultextension=".html",
                filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
                initialfile=f"certificate_{cert_id}.html",
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
                messagebox.showinfo("Exported", f"Certificate saved to:\n{path}",
                                    parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}", parent=self)

    def _revoke_selected(self):
        sel = self._cert_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a certificate to revoke.",
                                   parent=self)
            return
        cert_id = sel[0]
        reason = tk.simpledialog.askstring(
            "Revoke Certificate",
            "Enter reason for revocation:",
            parent=self,
        ) if hasattr(tk, "simpledialog") else None

        if reason is None:
            # Try the simpler approach
            from tkinter import simpledialog
            reason = simpledialog.askstring(
                "Revoke Certificate",
                "Enter reason for revocation:",
                parent=self,
            )
        if not reason:
            return
        try:
            self._get_cert_svc().revoke_certificate(int(cert_id), reason)
            messagebox.showinfo("Revoked", "Certificate has been revoked.", parent=self)
            self._show_all_certificates()
        except Exception as e:
            messagebox.showerror("Error", f"Revocation failed: {e}", parent=self)

    # ── Transcripts Tab ──────────────────────────────────────────────

    def _build_transcripts_tab(self):
        from education_system.platform.features.certificates.digital_transcript_frame import DigitalTranscriptFrame

        tab = tk.Frame(self._notebook, bg="#ffffff")
        self._notebook.add(tab, text="  Transcripts  ")

        # Cross-system transcript browser (search-by-name across all systems).
        DigitalTranscriptFrame(tab, db_path=self._db_path, auth=self._auth).pack(
            fill="both", expand=True
        )

    # ── Generate Tab ─────────────────────────────────────────────────

    def _build_generate_tab(self):
        tab = tk.Frame(self._notebook, bg="#ffffff")
        self._notebook.add(tab, text="  Generate  ")

        # Title
        tk.Label(tab, text="Generate New Certificate", font=("Helvetica", 14, "bold"),
                 bg="#ffffff", fg="#1a3c6e").pack(pady=(15, 10))

        form = tk.Frame(tab, bg="#ffffff")
        form.pack(padx=30, pady=5)

        fields = [
            ("Student ID:", "_gen_student_var"),
            ("Course Name:", "_gen_course_var"),
            ("Award Date (YYYY-MM-DD):", "_gen_date_var"),
            ("Grade (optional):", "_gen_grade_var"),
            ("Additional Info:", "_gen_info_var"),
            ("Issued By:", "_gen_issuer_var"),
        ]

        for i, (label_text, var_name) in enumerate(fields):
            tk.Label(form, text=label_text, bg="#ffffff", font=("Helvetica", 10),
                     anchor="w").grid(row=i, column=0, sticky="w", padx=(0, 10), pady=5)
            var = tk.StringVar()
            setattr(self, var_name, var)
            ttk.Entry(form, textvariable=var, width=40).grid(
                row=i, column=1, pady=5, sticky="ew"
            )

        # Certificate type dropdown
        type_row = len(fields)
        tk.Label(form, text="Certificate Type:", bg="#ffffff",
                 font=("Helvetica", 10), anchor="w").grid(
            row=type_row, column=0, sticky="w", padx=(0, 10), pady=5
        )
        self._gen_type_var = tk.StringVar(value="completion")
        type_menu = ttk.Combobox(
            form,
            textvariable=self._gen_type_var,
            values=["completion", "achievement", "attendance", "merit", "distinction"],
            state="readonly",
            width=37,
        )
        type_menu.grid(row=type_row, column=1, pady=5, sticky="ew")

        # Set default date
        self._gen_date_var.set(datetime.now().strftime("%Y-%m-%d"))

        # Generate button
        ttk.Button(tab, text="Generate Certificate",
                   command=self._on_generate_cert).pack(pady=15)

        # Result display
        self._gen_result_var = tk.StringVar()
        tk.Label(tab, textvariable=self._gen_result_var, bg="#ffffff",
                 fg="#27ae60", font=("Helvetica", 10), wraplength=500).pack(pady=5)

    def _on_generate_cert(self):
        sid = self._gen_student_var.get().strip()
        course = self._gen_course_var.get().strip()
        award_date = self._gen_date_var.get().strip()
        cert_type = self._gen_type_var.get()

        if not sid or not course or not award_date:
            messagebox.showwarning(
                "Missing Fields",
                "Student ID, Course Name, and Award Date are required.",
                parent=self,
            )
            return

        try:
            cert = self._get_cert_svc().generate_certificate(
                student_id=sid,
                certificate_type=cert_type,
                course_name=course,
                award_date=award_date,
                grade=self._gen_grade_var.get().strip() or None,
                additional_info=self._gen_info_var.get().strip() or None,
                issued_by=self._gen_issuer_var.get().strip() or None,
            )
            self._gen_result_var.set(
                f"Certificate generated successfully!\n"
                f"Certificate No: {cert.get('certificate_number', 'N/A')}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate certificate: {e}",
                                 parent=self)

    # ── Verify Tab ───────────────────────────────────────────────────

    def _build_verify_tab(self):
        tab = tk.Frame(self._notebook, bg="#ffffff")
        self._notebook.add(tab, text="  Verify  ")

        tk.Label(tab, text="Certificate Verification", font=("Helvetica", 14, "bold"),
                 bg="#ffffff", fg="#1a3c6e").pack(pady=(20, 10))

        tk.Label(tab, text="Enter a certificate number to verify its authenticity.",
                 bg="#ffffff", fg="#666666", font=("Helvetica", 10)).pack(pady=(0, 15))

        search_frame = tk.Frame(tab, bg="#ffffff")
        search_frame.pack(pady=5)

        tk.Label(search_frame, text="Certificate Number:", bg="#ffffff",
                 font=("Helvetica", 10)).pack(side="left", padx=(0, 10))
        self._verify_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self._verify_var, width=30).pack(
            side="left", padx=(0, 10)
        )
        ttk.Button(search_frame, text="Verify", command=self._on_verify).pack(
            side="left"
        )

        # Result card
        self._verify_frame = tk.Frame(tab, bg="#ffffff", padx=20, pady=15)
        self._verify_frame.pack(fill="x", padx=40, pady=20)

        self._verify_result = tk.Text(
            self._verify_frame, wrap="word", font=("Courier", 11),
            height=14, state="disabled", bg="#fafafa", relief="groove", bd=1,
        )
        self._verify_result.pack(fill="both", expand=True)

    def _on_verify(self):
        cert_num = self._verify_var.get().strip()
        if not cert_num:
            messagebox.showwarning("Input Required",
                                   "Enter a certificate number to verify.",
                                   parent=self)
            return

        try:
            result = self._get_cert_svc().verify_certificate(cert_num)
            self._verify_result.configure(state="normal")
            self._verify_result.delete("1.0", "end")

            if result.get("valid"):
                status_icon = "[VALID]"
                status_color = "#27ae60"
            else:
                status_icon = "[INVALID]"
                status_color = "#e74c3c"

            self._verify_result.insert("end", f"  {status_icon}\n\n")
            self._verify_result.insert("end", f"  Status: {result.get('status', 'N/A')}\n")
            self._verify_result.insert("end", f"  Message: {result.get('message', '')}\n\n")

            if result.get("certificate_number"):
                self._verify_result.insert("end", f"  Certificate No:  {result['certificate_number']}\n")
                self._verify_result.insert("end", f"  Type:            {result.get('certificate_type', 'N/A')}\n")
                self._verify_result.insert("end", f"  Student:         {result.get('student_name', 'N/A')}\n")
                self._verify_result.insert("end", f"  Course:          {result.get('course_name', 'N/A')}\n")
                self._verify_result.insert("end", f"  Award Date:      {result.get('award_date', 'N/A')}\n")
                if result.get("grade"):
                    self._verify_result.insert("end", f"  Grade:           {result['grade']}\n")
                self._verify_result.insert("end", f"  Issued By:       {result.get('issued_by', 'N/A')}\n")
                self._verify_result.insert("end", f"  Issued At:       {result.get('issued_at', 'N/A')}\n")

            self._verify_result.configure(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", f"Verification failed: {e}", parent=self)

    # ------------------------------------------------------------------
    # Public refresh hook
    # ------------------------------------------------------------------

    def refresh(self):
        """Called when the frame is shown."""
        pass
