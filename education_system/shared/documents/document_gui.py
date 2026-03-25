"""Shared Document Storage GUI.

Provides a tkinter Frame for managing cross-system documents:
searching, uploading, viewing, and deleting documents that follow
students across education systems.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

from education_system.shared.documents.document_service import (
    DocumentService, DOCUMENT_TYPES,
)

HEADER_BG = "#1a5276"
HEADER_FG = "white"
BG = "#ecf0f1"

SYSTEM_KEYS = ["primary", "secondary", "college", "university"]
SYSTEM_LABELS = {
    "primary": "Primary School",
    "secondary": "Secondary School",
    "college": "Sixth Form College",
    "university": "University",
}


class SharedDocumentsFrame(tk.Frame):
    """Frame for managing cross-system shared documents."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = DocumentService()
        self._build_ui()

    def _get_username(self):
        if isinstance(self._auth, dict):
            return self._auth.get("username", "unknown")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("username", "unknown")
        return "unknown"

    def _get_system_key(self):
        if isinstance(self._auth, dict):
            return self._auth.get("system_key", "")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("system_key", "")
        return ""

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
            header, text="Shared Documents",
            font=("Helvetica", 15, "bold"), bg=HEADER_BG, fg=HEADER_FG,
        ).pack(side="left", padx=20, pady=10)

        btn_frame = tk.Frame(header, bg=HEADER_BG)
        btn_frame.pack(side="right", padx=10)
        ttk.Button(btn_frame, text="Upload", command=self._upload_dialog).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(
            side="left", padx=5)

        # Search / filter bar
        filter_frame = tk.Frame(self, bg=BG, pady=8)
        filter_frame.pack(fill="x", padx=10)

        tk.Label(filter_frame, text="Student:", bg=BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 5))
        self._search_name_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self._search_name_var,
                  width=20).pack(side="left", padx=5)

        tk.Label(filter_frame, text="System:", bg=BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(15, 5))
        self._filter_system_var = tk.StringVar(value="")
        ttk.Combobox(filter_frame, textvariable=self._filter_system_var,
                     values=[""] + SYSTEM_KEYS, state="readonly",
                     width=14).pack(side="left", padx=5)

        tk.Label(filter_frame, text="Type:", bg=BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(15, 5))
        self._filter_type_var = tk.StringVar(value="")
        ttk.Combobox(filter_frame, textvariable=self._filter_type_var,
                     values=[""] + DOCUMENT_TYPES, state="readonly",
                     width=14).pack(side="left", padx=5)

        ttk.Button(filter_frame, text="Search",
                   command=self.refresh).pack(side="left", padx=15)

        # Documents treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        columns = ("id", "title", "student", "doc_type", "system", "uploaded_by", "date")
        self._tree = ttk.Treeview(tree_frame, columns=columns,
                                  show="headings", selectmode="browse")
        for col, heading, width in [
            ("id", "ID", 40),
            ("title", "Title", 200),
            ("student", "Student", 150),
            ("doc_type", "Type", 100),
            ("system", "System", 130),
            ("uploaded_by", "Uploaded By", 100),
            ("date", "Date", 130),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width,
                              anchor="center" if col == "id" else "w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Action buttons
        action_frame = tk.Frame(self, bg=BG, pady=5)
        action_frame.pack(fill="x", padx=10)
        ttk.Button(action_frame, text="View / Open Location",
                   command=self._view_document).pack(side="left", padx=5)
        ttk.Button(action_frame, text="Delete",
                   command=self._delete_document).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Refresh / search
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload the document list with current filters."""
        self._tree.delete(*self._tree.get_children())
        name = self._search_name_var.get().strip() or None
        system = self._filter_system_var.get() or None
        doc_type = self._filter_type_var.get() or None

        try:
            docs = self._svc.get_documents(
                student_name=name, system=system, doc_type=doc_type)
            for d in docs:
                self._tree.insert("", "end", iid=d["id"], values=(
                    d["id"],
                    d["title"],
                    d["student_name"],
                    d["doc_type"],
                    SYSTEM_LABELS.get(d["system"], d["system"]),
                    d.get("uploaded_by", ""),
                    (d.get("created_at") or "")[:16],
                ))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load documents: {e}",
                                 parent=self)

    # ------------------------------------------------------------------
    # Upload dialog
    # ------------------------------------------------------------------

    def _upload_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Upload Document")
        dlg.geometry("480x420")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        frm = tk.Frame(dlg, padx=20, pady=15)
        frm.pack(fill="both", expand=True)

        row = 0
        pad = {"padx": 5, "pady": 5}

        # Student name
        tk.Label(frm, text="Student Name:", font=("Helvetica", 10, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=name_var, width=30).grid(
            row=row, column=1, **pad)
        row += 1

        # Student ID
        tk.Label(frm, text="Student ID:", font=("Helvetica", 10, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        sid_var = tk.StringVar()
        ttk.Entry(frm, textvariable=sid_var, width=30).grid(
            row=row, column=1, **pad)
        row += 1

        # System
        tk.Label(frm, text="System:", font=("Helvetica", 10, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        sys_var = tk.StringVar(value=self._get_system_key() or SYSTEM_KEYS[0])
        ttk.Combobox(frm, textvariable=sys_var, values=SYSTEM_KEYS,
                     state="readonly", width=27).grid(row=row, column=1, **pad)
        row += 1

        # Document type
        tk.Label(frm, text="Type:", font=("Helvetica", 10, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        type_var = tk.StringVar(value="other")
        ttk.Combobox(frm, textvariable=type_var, values=DOCUMENT_TYPES,
                     state="readonly", width=27).grid(row=row, column=1, **pad)
        row += 1

        # Title
        tk.Label(frm, text="Title:", font=("Helvetica", 10, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=title_var, width=30).grid(
            row=row, column=1, **pad)
        row += 1

        # Description
        tk.Label(frm, text="Description:", font=("Helvetica", 10, "bold")).grid(
            row=row, column=0, sticky="nw", **pad)
        desc_text = tk.Text(frm, height=3, width=30, font=("Helvetica", 10))
        desc_text.grid(row=row, column=1, **pad)
        row += 1

        # File picker
        tk.Label(frm, text="File:", font=("Helvetica", 10, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        file_frame = tk.Frame(frm)
        file_frame.grid(row=row, column=1, **pad)
        file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=file_var, width=22,
                  state="readonly").pack(side="left")

        def _pick_file():
            fp = filedialog.askopenfilename(
                parent=dlg, title="Select Document File")
            if fp:
                file_var.set(fp)

        ttk.Button(file_frame, text="Browse", command=_pick_file).pack(
            side="left", padx=5)
        row += 1

        # Upload button
        def _upload():
            sname = name_var.get().strip()
            stitle = title_var.get().strip()
            fpath = file_var.get().strip()
            if not sname:
                messagebox.showwarning("Validation", "Student name is required.",
                                       parent=dlg)
                return
            if not stitle:
                messagebox.showwarning("Validation", "Title is required.",
                                       parent=dlg)
                return
            if not fpath or not Path(fpath).exists():
                messagebox.showwarning("Validation",
                                       "Select a valid file.", parent=dlg)
                return

            try:
                fname = Path(fpath).name
                doc_id = self._svc.upload_document(
                    student_name=sname,
                    student_id=sid_var.get().strip(),
                    system=sys_var.get(),
                    doc_type=type_var.get(),
                    title=stitle,
                    description=desc_text.get("1.0", "end").strip(),
                    file_data=fpath,
                    filename=fname,
                    uploaded_by=self._get_username(),
                    uploaded_system=self._get_system_key(),
                )
                messagebox.showinfo("Uploaded",
                                    f"Document uploaded (ID: {doc_id}).",
                                    parent=dlg)
                dlg.destroy()
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", f"Upload failed: {e}",
                                     parent=dlg)

        btn_frame = tk.Frame(frm)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Upload", command=_upload).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(
            side="left", padx=5)

    # ------------------------------------------------------------------
    # View / Open
    # ------------------------------------------------------------------

    def _view_document(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a document first.",
                                parent=self)
            return

        doc_id = int(sel[0])
        doc = self._svc.get_document(doc_id)
        if not doc:
            messagebox.showerror("Error", "Document not found.", parent=self)
            return

        file_path = doc.get("file_path", "")
        if file_path and Path(file_path).exists():
            # Open the containing folder
            folder = str(Path(file_path).parent)
            try:
                os.startfile(folder)  # Windows
            except AttributeError:
                try:
                    import subprocess
                    subprocess.Popen(["xdg-open", folder])
                except Exception:
                    messagebox.showinfo(
                        "File Location",
                        f"File is at:\n{file_path}",
                        parent=self,
                    )
        else:
            messagebox.showinfo(
                "Document Info",
                f"Title: {doc['title']}\n"
                f"Student: {doc['student_name']}\n"
                f"Type: {doc['doc_type']}\n"
                f"System: {doc['system']}\n"
                f"Uploaded: {doc.get('created_at', 'N/A')}\n"
                f"File: {file_path or 'No file'}",
                parent=self,
            )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _delete_document(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a document first.",
                                parent=self)
            return

        doc_id = int(sel[0])
        doc = self._svc.get_document(doc_id)
        if not doc:
            messagebox.showerror("Error", "Document not found.", parent=self)
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete document '{doc['title']}' for "
            f"{doc['student_name']}?\n\n"
            f"This will also delete the file from disk.",
            parent=self,
        )
        if confirm:
            if self._svc.delete_document(doc_id):
                messagebox.showinfo("Deleted", "Document deleted.",
                                    parent=self)
                self.refresh()
            else:
                messagebox.showerror("Error", "Failed to delete document.",
                                     parent=self)
