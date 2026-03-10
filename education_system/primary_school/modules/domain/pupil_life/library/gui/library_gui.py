"""Library management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pupil_life.library.services.library_service import LibraryService
import traceback


class _BookDialog(tk.Toplevel):
    """Add / Edit book dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Book" if record else "Add Book")
        self.geometry("450x380")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("title", "Title *")
        self._add_field("author", "Author *")
        self._add_field("isbn", "ISBN")
        self._add_field("category", "Category")
        self._add_field("reading_level", "Reading Level")
        self._add_field("location", "Location")
        self._add_field("copies", "Copies", default="1")

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        if record:
            for key, widget in self._entries.items():
                val = record.get(key)
                if val is None:
                    continue
                widget.delete(0, tk.END)
                widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, key, label, default=""):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            data[key] = widget.get().strip()
        if not data.get("title"):
            messagebox.showwarning("Validation", "Title is required.", parent=self)
            return
        if not data.get("author"):
            messagebox.showwarning("Validation", "Author is required.", parent=self)
            return
        self.result = data
        self.destroy()


class LibraryFrame(tk.Frame):
    """Main library management screen with Books and Loans tabs."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = LibraryService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Library Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Notebook tabs
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self._build_books_tab()
        self._build_loans_tab()

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_books()
        self._load_loans()

    def _build_books_tab(self):
        tab = tk.Frame(self._notebook)
        self._notebook.add(tab, text="Books")

        toolbar = tk.Frame(tab, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="Add Book", command=self._on_add_book).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit_book).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete_book).pack(side="left", padx=3)

        columns = ("book_id", "title", "author", "category", "reading_level",
                   "copies", "available", "status")
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._book_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._book_tree.heading(col, text=col.replace("_", " ").title())
            self._book_tree.column(col, width=100)
        self._book_tree.column("book_id", width=70)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._book_tree.yview)
        self._book_tree.configure(yscrollcommand=vsb.set)
        self._book_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_loans_tab(self):
        tab = tk.Frame(self._notebook)
        self._notebook.add(tab, text="Loans")

        toolbar = tk.Frame(tab, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="Loan Book", command=self._on_loan_book).pack(side="left", padx=3)
        tk.Button(toolbar, text="Return Book", command=self._on_return_book).pack(side="left", padx=3)

        columns = ("loan_id", "book_title", "pupil_id", "loan_date",
                   "due_date", "return_date", "status")
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._loan_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._loan_tree.heading(col, text=col.replace("_", " ").title())
            self._loan_tree.column(col, width=100)
        self._loan_tree.column("loan_id", width=70)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._loan_tree.yview)
        self._loan_tree.configure(yscrollcommand=vsb.set)
        self._loan_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def refresh(self):
        self._load_books()
        self._load_loans()

    def _load_books(self):
        for item in self._book_tree.get_children():
            self._book_tree.delete(item)
        try:
            records = self._service.list_books()
            for r in records:
                rid = r.get("book_id", r.get("id"))
                self._book_tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("title", ""), r.get("author", ""),
                    r.get("category", ""), r.get("reading_level", ""),
                    r.get("copies", ""), r.get("available", ""),
                    r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} book(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load books: {e}")

    def _load_loans(self):
        for item in self._loan_tree.get_children():
            self._loan_tree.delete(item)
        try:
            records = self._service.get_loans()
            for r in records:
                rid = r.get("loan_id", r.get("id"))
                self._loan_tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("book_title", r.get("title", "")),
                    r.get("pupil_id", ""), r.get("loan_date", ""),
                    r.get("due_date", ""), r.get("return_date", ""),
                    r.get("status", ""),
                ))
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load loans: {e}")

    def _on_add_book(self):
        dlg = _BookDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.add_book(**dlg.result)
                self._load_books()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit_book(self):
        sel = self._book_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a book first.")
            return
        rid = sel[0]
        record = self._service.get_book(rid)
        if not record:
            messagebox.showerror("Error", "Book not found.")
            return
        dlg = _BookDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_book(rid, **dlg.result)
                self._load_books()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete_book(self):
        sel = self._book_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a book first.")
            return
        rid = sel[0]
        if not messagebox.askyesno("Confirm", f"Delete book {rid}?"):
            return
        try:
            self._service.delete_book(rid)
            self._load_books()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_loan_book(self):
        dlg = tk.Toplevel(self)
        dlg.title("Loan Book")
        dlg.geometry("350x200")
        dlg.resizable(False, False)
        dlg.grab_set()

        entries = {}
        for key, label in [("book_id", "Book ID *"), ("pupil_id", "Pupil ID *"),
                           ("due_date", "Due Date (YYYY-MM-DD)")]:
            frm = tk.Frame(dlg)
            frm.pack(fill="x", padx=10, pady=2)
            tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
            e = tk.Entry(frm, width=25)
            e.pack(side="left", fill="x", expand=True)
            entries[key] = e

        def save():
            book_id = entries["book_id"].get().strip()
            pupil_id = entries["pupil_id"].get().strip()
            due_date = entries["due_date"].get().strip()
            if not book_id or not pupil_id:
                messagebox.showwarning("Validation", "Book ID and Pupil ID are required.", parent=dlg)
                return
            try:
                self._service.loan_book(book_id=book_id, pupil_id=pupil_id, due_date=due_date)
                dlg.destroy()
                self._load_loans()
                self._load_books()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e), parent=dlg)

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Loan", command=save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=dlg.destroy, width=12).pack(side="right", padx=5)

        dlg.transient(self)
        dlg.wait_visibility()
        dlg.grab_set()

    def _on_return_book(self):
        sel = self._loan_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a loan first.")
            return
        rid = sel[0]
        if not messagebox.askyesno("Confirm", f"Return book for loan {rid}?"):
            return
        try:
            self._service.return_book(rid)
            self._load_loans()
            self._load_books()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
