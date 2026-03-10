"""Document management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.admin.documents.services.document_service import DocumentService
import traceback


DOC_CATEGORIES = ["Policy", "Template", "Report", "Letter", "Form", "Other"]
ACCESS_LEVELS = ["All", "Staff", "Admin"]


class _DocumentDialog(tk.Toplevel):
    """Add / Edit document dialog."""

    def __init__(self, parent, db_path, document=None):
        super().__init__(parent)
        self.result = None
        self._document = document
        self.title("Edit Document" if document else "Add Document")
        self.geometry("480x420")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "title", "Title *")
        self._add_combo(frm, "category", "Category *", DOC_CATEGORIES)
        self._add_field(frm, "file_path", "File Path")
        self._add_field(frm, "file_type", "File Type")
        self._add_field(frm, "description", "Description")
        self._add_combo(frm, "access_level", "Access Level", ACCESS_LEVELS)

        if document:
            self._add_combo(frm, "status", "Status", ["Active", "Archived"])

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=15)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if document:
            for key, widget in self._entries.items():
                val = document.get(key)
                if val is None:
                    continue
                if isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, parent, key, label):
        frm = tk.Frame(parent)
        frm.pack(fill="x", pady=3)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", pady=3)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("title"):
            messagebox.showwarning("Validation", "Title is required.", parent=self)
            return
        if not data.get("category"):
            messagebox.showwarning("Validation", "Category is required.", parent=self)
            return
        self.result = data
        self.destroy()


class DocumentFrame(tk.Frame):
    """Main document management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = DocumentService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Document Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Document", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        # Treeview
        columns = ("id", "title", "category", "file_type", "uploaded_by", "access_level", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("id", width=50)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_items()

    def refresh(self):
        self._load_items()

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            docs = self._service.list_documents()
            for d in docs:
                self._tree.insert("", tk.END, iid=d.get("id"), values=(
                    d.get("id", ""), d.get("title", ""), d.get("category", ""),
                    d.get("file_type", ""), d.get("uploaded_by", ""),
                    d.get("access_level", ""), d.get("status", ""),
                ))
            self._status_var.set(f"{len(docs)} document(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load documents: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a document first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _DocumentDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_document(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        did = self._selected_id()
        if not did:
            return
        doc = self._service.get_document(did)
        if not doc:
            messagebox.showerror("Error", "Document not found.")
            return
        dlg = _DocumentDialog(self, self._db_path, document=doc)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_document(did, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        did = self._selected_id()
        if not did:
            return
        if not messagebox.askyesno("Confirm", f"Delete document {did}?"):
            return
        try:
            self._service.delete_document(did)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
