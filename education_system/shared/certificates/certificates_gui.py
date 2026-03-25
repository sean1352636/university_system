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
        self._transcript_svc = None

        self._build_ui()

    def _get_cert_svc(self):
        if self._cert_svc is None:
            from education_system.shared.certificates.certificate_service import CertificateService
            self._cert_svc = CertificateService(self._db_path)
        return self._cert_svc

    def _get_transcript_svc(self):
        if self._transcript_svc is None:
            from education_system.shared.certificates.transcript_service import TranscriptService
            self._transcript_svc = TranscriptService(self._db_path)
        return self._transcript_svc

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#f5f6fa")

        # Header
        header = tk.Frame(self, bg="#1a3c6e", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Certificates & Transcripts",
            font=("Helvetica", 16, "bold"),
            bg="#1a3c6e",
            fg="white",
        ).pack(side="left", padx=20)

        # Notebook
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_certificates_tab()
        self._build_transcripts_tab()
        self._build_generate_tab()
        self._build_verify_tab()

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
                self._cert_tree.insert("", "end", values=(
                    c.get("id", ""),
                    c.get("student_id", ""),
                    c.get("certificate_number", ""),
                    c.get("certificate_type", ""),
                    c.get("course_name", ""),
                    c.get("award_date", ""),
                    c.get("grade", ""),
                    c.get("status", ""),
                    c.get("issued_by", ""),
                ))
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
        cert_id = self._cert_tree.item(sel[0], "values")[0]
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
        cert_id = self._cert_tree.item(sel[0], "values")[0]
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
        tab = tk.Frame(self._notebook, bg="#ffffff")
        self._notebook.add(tab, text="  Transcripts  ")

        ctrl = tk.Frame(tab, bg="#ffffff", pady=10)
        ctrl.pack(fill="x", padx=15)

        tk.Label(ctrl, text="Student ID:", bg="#ffffff",
                 font=("Helvetica", 10)).pack(side="left", padx=(0, 5))
        self._tr_student_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=self._tr_student_var, width=20).pack(
            side="left", padx=(0, 10)
        )

        tk.Label(ctrl, text="Academic Year:", bg="#ffffff",
                 font=("Helvetica", 10)).pack(side="left", padx=(0, 5))
        self._tr_year_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=self._tr_year_var, width=14).pack(
            side="left", padx=(0, 10)
        )

        ttk.Button(ctrl, text="Generate", command=self._generate_transcript).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(ctrl, text="Export HTML", command=self._export_transcript_html).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(ctrl, text="Export CSV", command=self._export_transcript_csv).pack(
            side="left"
        )

        # Transcript display area
        self._tr_text = tk.Text(tab, wrap="word", font=("Courier", 10),
                                state="disabled", bg="#fafafa")
        tr_scroll = ttk.Scrollbar(tab, orient="vertical", command=self._tr_text.yview)
        self._tr_text.configure(yscrollcommand=tr_scroll.set)
        self._tr_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        tr_scroll.pack(side="right", fill="y")

    def _get_tr_args(self):
        sid = self._tr_student_var.get().strip()
        if not sid:
            messagebox.showwarning("Input Required", "Enter a Student ID.", parent=self)
            return None, None
        year = self._tr_year_var.get().strip() or None
        return sid, year

    def _generate_transcript(self):
        sid, year = self._get_tr_args()
        if sid is None:
            return
        try:
            data = self._get_transcript_svc().generate_transcript(sid, academic_year=year)
            self._tr_text.configure(state="normal")
            self._tr_text.delete("1.0", "end")
            self._tr_text.insert("end", f"TRANSCRIPT FOR: {data['student_name']}\n")
            self._tr_text.insert("end", f"Student ID: {data['student_id']}\n")
            self._tr_text.insert("end", f"Institution: {data['institution']}\n")
            self._tr_text.insert("end", f"Academic Year: {data['academic_year']}\n")
            self._tr_text.insert("end", f"Generated: {data['generated_at']}\n")
            self._tr_text.insert("end", f"Transcript ID: {data.get('transcript_id', 'N/A')}\n")
            self._tr_text.insert("end", "-" * 60 + "\n\n")

            if data["subjects"]:
                self._tr_text.insert("end", f"{'Subject':<30} {'Grade':<10} {'Credits':<10} {'Date'}\n")
                self._tr_text.insert("end", "-" * 70 + "\n")
                for s in data["subjects"]:
                    self._tr_text.insert(
                        "end",
                        f"{s['name']:<30} {s['grade']:<10} {s['credits']:<10} {s['date']}\n",
                    )
            else:
                self._tr_text.insert("end", "No academic records found.\n")

            self._tr_text.insert("end", "\n" + "-" * 60 + "\n")
            self._tr_text.insert("end", f"Overall Average / GPA: {data['gpa']}\n")
            self._tr_text.configure(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", f"Transcript generation failed: {e}",
                                 parent=self)

    def _export_transcript_html(self):
        sid, year = self._get_tr_args()
        if sid is None:
            return
        try:
            html = self._get_transcript_svc().export_transcript_html(sid, academic_year=year)
            path = filedialog.asksaveasfilename(
                parent=self,
                defaultextension=".html",
                filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
                initialfile=f"transcript_{sid}.html",
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
                messagebox.showinfo("Exported", f"Transcript saved to:\n{path}",
                                    parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}", parent=self)

    def _export_transcript_csv(self):
        sid, year = self._get_tr_args()
        if sid is None:
            return
        try:
            path = filedialog.asksaveasfilename(
                parent=self,
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"transcript_{sid}.csv",
            )
            if path:
                self._get_transcript_svc().export_transcript_csv(sid, path, academic_year=year)
                messagebox.showinfo("Exported", f"Transcript CSV saved to:\n{path}",
                                    parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"CSV export failed: {e}", parent=self)

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
