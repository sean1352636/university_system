"""Library Management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.student_life.library.services.library_service import (
    LibraryService, CATEGORIES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class LibraryFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = LibraryService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Library", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        # --- Books tab ---
        books_tab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(books_tab, text="Catalogue")
        bt = tk.Frame(books_tab, bg=MAIN_BG, pady=8)
        bt.pack(fill="x", padx=10)
        ttk.Button(bt, text="Add Book", command=self._on_add_book).pack(side="left", padx=4)
        ttk.Button(bt, text="Delete", command=self._on_delete_book).pack(side="left", padx=4)
        tk.Label(bt, text="Search:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._search_var = tk.StringVar()
        se = ttk.Entry(bt, textvariable=self._search_var, width=18)
        se.pack(side="left", padx=4)
        se.bind("<Return>", lambda *_: self._load_books())
        ttk.Button(bt, text="Go", command=self._load_books).pack(side="left", padx=2)

        tree_frame = tk.Frame(books_tab)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("title", "author", "isbn", "category", "location", "available", "total")
        self._books_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("title", "Title", 180), ("author", "Author", 120), ("isbn", "ISBN", 100),
                           ("category", "Category", 80), ("location", "Location", 70),
                           ("available", "Avail", 45), ("total", "Total", 45)]:
            self._books_tree.heading(col, text=h)
            self._books_tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._books_tree.yview)
        self._books_tree.configure(yscrollcommand=vsb.set)
        self._books_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- Loans tab ---
        loans_tab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(loans_tab, text="Loans")
        lt = tk.Frame(loans_tab, bg=MAIN_BG, pady=8)
        lt.pack(fill="x", padx=10)
        ttk.Button(lt, text="Issue Loan", command=self._on_issue).pack(side="left", padx=4)
        ttk.Button(lt, text="Return", command=self._on_return).pack(side="left", padx=4)
        ttk.Button(lt, text="View Overdue", command=self._on_overdue).pack(side="left", padx=4)

        loan_frame = tk.Frame(loans_tab)
        loan_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        lcols = ("book", "student", "borrowed", "due", "returned", "status")
        self._loans_tree = ttk.Treeview(loan_frame, columns=lcols, show="headings", selectmode="browse")
        for col, h, w in [("book", "Book", 180), ("student", "Student", 130), ("borrowed", "Borrowed", 90),
                           ("due", "Due", 80), ("returned", "Returned", 90), ("status", "Status", 65)]:
            self._loans_tree.heading(col, text=h)
            self._loans_tree.column(col, width=w, anchor="center")
        lvsb = ttk.Scrollbar(loan_frame, orient="vertical", command=self._loans_tree.yview)
        self._loans_tree.configure(yscrollcommand=lvsb.set)
        self._loans_tree.pack(side="left", fill="both", expand=True)
        lvsb.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_books()
        self._load_loans()

    def _load_books(self):
        self._books_tree.delete(*self._books_tree.get_children())
        try:
            books = self._svc.list_books(search=self._search_var.get().strip() or None)
            for b in books:
                self._books_tree.insert("", "end", iid=b["id"], values=(
                    b["title"], b.get("author") or "", b.get("isbn") or "",
                    b.get("category") or "", b.get("location") or "",
                    b["copies_available"], b["copies_total"]))
            self._status_var.set(f"{len(books)} book(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_loans(self):
        self._loans_tree.delete(*self._loans_tree.get_children())
        try:
            loans = self._svc.list_loans()
            for ln in loans:
                self._loans_tree.insert("", "end", iid=ln["id"], values=(
                    ln["book_title"], f"{ln['first_name']} {ln['last_name']}",
                    ln["borrowed_at"][:10] if ln.get("borrowed_at") else "",
                    ln["due_date"], ln.get("returned_at", "")[:10] if ln.get("returned_at") else "",
                    ln["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add_book(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Book")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        for row, (l, k, d, vals) in enumerate([
            ("Title", "title", "", None), ("Author", "author", "", None),
            ("ISBN", "isbn", "", None), ("Category", "category", "fiction", list(CATEGORIES)),
            ("Location", "location", "", None), ("Copies", "copies", "1", None)]):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=22).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=row, column=1, **pad)
        result = [None]

        def save():
            t = vars_["title"].get().strip()
            if not t:
                messagebox.showwarning("Validation", "Title required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Save", command=save).grid(row=6, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            copies = int(d["copies"]) if d["copies"] else 1
        except ValueError:
            copies = 1
        try:
            self._svc.add_book(d["title"], d["author"] or None, d["isbn"] or None,
                               d["category"] or None, d["location"] or None, copies)
            self._load_books()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete_book(self):
        sel = self._books_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this book?"):
            self._svc.delete_book(int(sel[0]))
            self._load_books()

    def _on_issue(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        books = self._svc.list_books()
        students = StudentService(self._db_path).list_students(status="active")
        if not books or not students:
            messagebox.showinfo("Info", "Need books and students.")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Issue Loan")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        book_names = [f"{b['id']}: {b['title']}" for b in books if b["copies_available"] > 0]
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        tk.Label(c, text="Book", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        book_var = tk.StringVar()
        ttk.Combobox(c, textvariable=book_var, values=book_names, state="readonly", width=30).grid(row=0, column=1, **pad)
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        stu_var = tk.StringVar()
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=30).grid(row=1, column=1, **pad)
        tk.Label(c, text="Loan Days", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        days_var = tk.StringVar(value="14")
        ttk.Entry(c, textvariable=days_var, width=10).grid(row=2, column=1, sticky="w", **pad)
        result = [None]

        def save():
            bv = book_var.get()
            sv = stu_var.get()
            if not bv or not sv:
                messagebox.showwarning("Validation", "Select book and student.")
                return
            bid = int(bv.split(":")[0])
            sid_str = sv.split(" - ")[0]
            spk = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            try:
                days = int(days_var.get().strip())
            except ValueError:
                days = 14
            result[0] = {"book_id": bid, "student_id": spk, "days": days}
            dlg.destroy()
        ttk.Button(c, text="Issue", command=save).grid(row=3, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.issue_loan(d["book_id"], d["student_id"], d["days"])
            messagebox.showinfo("Success", "Loan issued.")
            self._load_books()
            self._load_loans()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_return(self):
        sel = self._loans_tree.selection()
        if not sel:
            return
        try:
            self._svc.return_book(int(sel[0]))
            messagebox.showinfo("Success", "Book returned.")
            self._load_books()
            self._load_loans()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_overdue(self):
        try:
            overdue = self._svc.overdue_loans()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        dlg = tk.Toplevel(self)
        dlg.title(f"Overdue Loans ({len(overdue)})")
        dlg.geometry("550x300")
        cols = ("book", "student", "due")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("book", "Book", 200), ("student", "Student", 150), ("due", "Due Date", 100)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for o in overdue:
            tree.insert("", "end", values=(
                o["book_title"], f"{o['first_name']} {o['last_name']}", o["due_date"]))
        tree.pack(fill="both", expand=True, padx=10, pady=10)
