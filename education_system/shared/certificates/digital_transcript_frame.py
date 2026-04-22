"""Digital Transcript — tkinter GUI frame.

Embeddable cross-system transcript browser. Searches students across all
education subsystems via TranscriptService, renders the selected student's
transcript, and supports save / clipboard / summary view.

Originally lived at education_system.shared.transcript.transcript_gui;
moved here when the standalone Digital Transcript window was folded into
the Certificates GUI's Transcripts tab.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from education_system.shared.transcript.transcript_service import (
    TranscriptService,
    SYSTEM_LABELS,
)

HEADER_BG = "#1a5276"


class DigitalTranscriptFrame(tk.Frame):
    """Digital transcript GUI — embeddable tk.Frame."""

    def __init__(self, parent, db_path=None, auth=None, restrict_to_student=None, **kwargs):
        """
        Args:
            restrict_to_student: when set, hide the search/results UI and
                auto-generate the transcript for that student name. Used by
                the student-facing Certificates GUI to lock the view to the
                logged-in user.
        """
        super().__init__(parent, **kwargs)
        self._service = TranscriptService()
        self._auth = auth or {}
        self._restrict_to_student = restrict_to_student
        self._search_results = []
        self._current_text = ""
        self._summary_mode = False
        self._current_transcript = None
        self._build_ui()

        if self._restrict_to_student:
            self.after(0, lambda: self._auto_generate(self._restrict_to_student))

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        restricted = bool(self._restrict_to_student)
        title = ("My Transcript" if restricted else "Digital Transcript")

        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=title,
            font=("Helvetica", 15, "bold"),
            bg=HEADER_BG,
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._status_var = tk.StringVar(value="")

        if not restricted:
            search_frame = tk.Frame(self, bg="#ecf0f1", pady=8)
            search_frame.pack(fill="x", padx=15)

            tk.Label(search_frame, text="Student name:", bg="#ecf0f1",
                     font=("Helvetica", 10)).pack(side="left", padx=(0, 5))
            self._search_var = tk.StringVar()
            entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
            entry.pack(side="left", padx=(0, 5))
            entry.bind("<Return>", lambda e: self._search())

            ttk.Button(search_frame, text="Search", command=self._search).pack(side="left", padx=4)
            ttk.Button(search_frame, text="Clear", command=self._clear).pack(side="left", padx=4)

            tk.Label(search_frame, textvariable=self._status_var, bg="#ecf0f1",
                     font=("Helvetica", 9, "italic"), fg="#7f8c8d").pack(side="right", padx=10)

            tk.Label(self, text="Search Results", bg="#ecf0f1",
                     font=("Helvetica", 10, "bold"), anchor="w").pack(fill="x", padx=15, pady=(5, 0))

            tree_frame = tk.Frame(self)
            tree_frame.pack(fill="x", padx=15, pady=(0, 5))

            cols = ("system", "student_id", "name", "year_group", "status")
            self._tree = ttk.Treeview(
                tree_frame, columns=cols, show="headings", selectmode="browse", height=5,
            )
            for col, heading, width in [
                ("system", "System", 130),
                ("student_id", "Student ID", 100),
                ("name", "Name", 200),
                ("year_group", "Year/Group", 100),
                ("status", "Status", 90),
            ]:
                self._tree.heading(col, text=heading)
                self._tree.column(col, width=width, anchor="center" if col in ("status", "year_group") else "w")

            t_vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
            self._tree.configure(yscrollcommand=t_vsb.set)
            self._tree.pack(side="left", fill="x", expand=True)
            t_vsb.pack(side="right", fill="y")
        else:
            self._search_var = None
            self._tree = None
            # Status row at the top so the student sees "Generating…" / errors.
            status_row = tk.Frame(self, bg="#ecf0f1", pady=8)
            status_row.pack(fill="x", padx=15)
            tk.Label(status_row, textvariable=self._status_var, bg="#ecf0f1",
                     font=("Helvetica", 10, "italic"), fg="#7f8c8d").pack(side="left")

        action_frame = tk.Frame(self, bg="#ecf0f1")
        action_frame.pack(fill="x", padx=15, pady=5)

        if not restricted:
            ttk.Button(action_frame, text="Generate Transcript",
                       command=self._generate).pack(side="left", padx=4)
        ttk.Button(action_frame, text="Save to File",
                   command=self._save_to_file).pack(side="left", padx=4)
        ttk.Button(action_frame, text="Print (Copy)",
                   command=self._copy_to_clipboard).pack(side="left", padx=4)
        self._summary_btn = ttk.Button(
            action_frame, text="Summary View", command=self._toggle_summary
        )
        self._summary_btn.pack(side="left", padx=4)

        text_frame = tk.Frame(self)
        text_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self._text_widget = tk.Text(
            text_frame, wrap="word", font=("Courier", 10),
            bg="white", fg="#2c3e50", state="disabled",
        )
        txt_vsb = ttk.Scrollbar(text_frame, orient="vertical", command=self._text_widget.yview)
        self._text_widget.configure(yscrollcommand=txt_vsb.set)
        self._text_widget.pack(side="left", fill="both", expand=True)
        txt_vsb.pack(side="right", fill="y")

    def _auto_generate(self, student_name):
        """Generate transcript for a fixed student (student-portal mode)."""
        self._status_var.set("Generating transcript...")
        self.update_idletasks()
        try:
            transcript = self._service.generate_transcript(student_name)
            self._current_transcript = transcript
            self._summary_mode = False
            self._summary_btn.config(text="Summary View")
            text = self._service.format_transcript(transcript)
            self._current_text = text
            self._set_text(text)
            self._status_var.set("Transcript generated.")
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            self._set_text(f"Could not generate transcript: {exc}")

    def _search(self):
        query = self._search_var.get().strip()
        if not query:
            messagebox.showwarning("Search", "Please enter a student name.", parent=self)
            return

        self._tree.delete(*self._tree.get_children())
        self._search_results = []

        try:
            results = self._service.search_students(query)
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            return

        if not results:
            self._status_var.set("No students found.")
            return

        self._search_results = results
        self._status_var.set(f"{len(results)} result(s)")

        for idx, r in enumerate(results):
            sys_label = SYSTEM_LABELS.get(r["system"], r["system"])
            self._tree.insert("", "end", iid=str(idx), values=(
                sys_label,
                r.get("student_id", ""),
                r.get("name", ""),
                r.get("year_group", ""),
                r.get("status", ""),
            ))

    def _clear(self):
        self._search_var.set("")
        self._tree.delete(*self._tree.get_children())
        self._search_results = []
        self._status_var.set("")
        self._set_text("")
        self._current_transcript = None

    def _generate(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Transcript", "Select a student first.", parent=self)
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._search_results):
            return

        student_name = self._search_results[idx].get("name", "")
        if not student_name:
            return

        self._status_var.set("Generating transcript...")
        self.update_idletasks()

        try:
            transcript = self._service.generate_transcript(student_name)
            self._current_transcript = transcript
            self._summary_mode = False
            self._summary_btn.config(text="Summary View")
            text = self._service.format_transcript(transcript)
            self._current_text = text
            self._set_text(text)
            self._status_var.set("Transcript generated.")
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")

    def _toggle_summary(self):
        if not self._current_transcript:
            messagebox.showinfo("Summary", "Generate a transcript first.", parent=self)
            return

        if self._summary_mode:
            self._set_text(self._current_text)
            self._summary_mode = False
            self._summary_btn.config(text="Summary View")
        else:
            try:
                student_name = self._current_transcript.get("student_name", "")
                summary = self._service.get_transcript_summary(student_name)
                self._set_text(summary)
                self._summary_mode = True
                self._summary_btn.config(text="Full View")
            except Exception as exc:
                self._status_var.set(f"Error: {exc}")

    def _save_to_file(self):
        text = self._get_text()
        if not text.strip():
            messagebox.showinfo("Save", "Nothing to save.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Transcript",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            try:
                self._service.save_transcript(text, path)
                messagebox.showinfo("Saved", f"Transcript saved to:\n{path}", parent=self)
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self)

    def _copy_to_clipboard(self):
        text = self._get_text()
        if not text.strip():
            messagebox.showinfo("Print", "Nothing to copy.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._status_var.set("Copied to clipboard.")

    def _set_text(self, text):
        self._text_widget.configure(state="normal")
        self._text_widget.delete("1.0", "end")
        self._text_widget.insert("1.0", text)
        self._text_widget.configure(state="disabled")

    def _get_text(self):
        return self._text_widget.get("1.0", "end").strip()

    def refresh(self):
        """Called when the module is shown in the sidebar."""
        pass
