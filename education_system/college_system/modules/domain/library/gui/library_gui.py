"""Library GUI for managing library items and loans."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.library.services.library_service import LibraryService
from education_system.college_system.core.i18n import t


class LibraryFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = LibraryService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("library.management"), font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._catalogue_tab = tk.Frame(self._nb)
        self._nb.add(self._catalogue_tab, text=t("library.catalogue"))
        self._build_catalogue_tab()

        self._loans_tab = tk.Frame(self._nb)
        self._nb.add(self._loans_tab, text=t("library.loans"))
        self._build_loans_tab()

        self._overdue_tab = tk.Frame(self._nb)
        self._nb.add(self._overdue_tab, text=t("library.overdue_items"))
        self._build_overdue_tab()

    def _build_catalogue_tab(self):
        toolbar = tk.Frame(self._catalogue_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        tk.Label(toolbar, text=t("common.search_colon")).pack(side="left", padx=5)
        self._search_var = tk.Entry(toolbar, width=20)
        self._search_var.pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.search"), command=self._load_catalogue).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("library.add_book"), command=self._add_item).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_catalogue_csv).pack(side="right", padx=5)

        cols = ("id", "title", "author", "isbn", "type", "available", "total")
        self._cat_tree = ttk.Treeview(self._catalogue_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 200, 150, 120, 80, 70, 70)):
            self._cat_tree.heading(c, text=c.title())
            self._cat_tree.column(c, width=w)
        self._cat_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_loans_tab(self):
        toolbar = tk.Frame(self._loans_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_loans).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("library.checkout"), command=self._checkout).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("library.return_book"), command=self._return_item).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("library.renew"), command=self._renew).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_loans_csv).pack(side="right", padx=5)

        cols = ("id", "title", "borrower", "loan_date", "due_date", "renewals", "status")
        self._loan_tree = ttk.Treeview(self._loans_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 200, 100, 100, 100, 70, 80)):
            self._loan_tree.heading(c, text=c.replace("_", " ").title())
            self._loan_tree.column(c, width=w)
        self._loan_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_overdue_tab(self):
        toolbar = tk.Frame(self._overdue_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_overdue).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_overdue_csv).pack(side="right", padx=5)

        cols = ("id", "title", "borrower", "due_date", "days_overdue")
        self._od_tree = ttk.Treeview(self._overdue_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 200, 120, 100, 100)):
            self._od_tree.heading(c, text=c.replace("_", " ").title())
            self._od_tree.column(c, width=w)
        self._od_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _export_catalogue_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._cat_tree, "library_catalogue.csv")

    def _export_loans_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._loan_tree, "library_loans.csv")

    def _export_overdue_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._od_tree, "library_overdue.csv")

    def _load_catalogue(self):
        for item in self._cat_tree.get_children():
            self._cat_tree.delete(item)
        try:
            search = self._search_var.get().strip()
            items = self._svc.list_items(search=search if search else None)
            for i in items:
                self._cat_tree.insert("", "end", values=(
                    i["id"], i.get("title", ""), i.get("author", ""),
                    i.get("isbn", ""), i.get("item_type", ""),
                    i.get("available_copies", 0), i.get("total_copies", 0)))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_loans(self):
        for item in self._loan_tree.get_children():
            self._loan_tree.delete(item)
        try:
            loans = self._svc.list_loans(status="on_loan")
            for l in loans:
                self._loan_tree.insert("", "end", iid=str(l["id"]), values=(
                    l["id"], l.get("title", ""), l.get("borrower_id", ""),
                    l.get("loan_date", ""), l.get("due_date", ""),
                    l.get("renewals", 0), l.get("status", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_overdue(self):
        for item in self._od_tree.get_children():
            self._od_tree.delete(item)
        try:
            overdue = self._svc.get_overdue()
            for o in overdue:
                self._od_tree.insert("", "end", iid=str(o["id"]), values=(
                    o["id"], o.get("title", ""), o.get("borrower_id", ""),
                    o.get("due_date", ""), ""))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _add_item(self):
        win = tk.Toplevel(self)
        win.title(t("library.add_book"))
        win.geometry("400x350")
        fields = {}
        row = 0
        for label, key in [(t("common.title") + "*:", "title"), (t("library.author") + ":", "author"),
                           (t("library.isbn") + ":", "isbn"), (t("common.category") + ":", "category"),
                           (t("library.location", default="Location") + ":", "location"), (t("library.copies", default="Copies") + ":", "total_copies")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        fields["total_copies"].insert(0, "1")
        tk.Label(win, text=t("common.type") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_var = tk.StringVar(value="book")
        ttk.Combobox(win, textvariable=type_var,
                      values=["book", "journal", "dvd", "digital", "other"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                copies = fields["total_copies"].get().strip()
                self._svc.add_item(
                    title=fields["title"].get().strip(),
                    author=fields["author"].get().strip() or None,
                    isbn=fields["isbn"].get().strip() or None,
                    item_type=type_var.get(),
                    category=fields["category"].get().strip() or None,
                    location=fields["location"].get().strip() or None,
                    total_copies=int(copies) if copies else 1)
                messagebox.showinfo(t("common.success"), t("library.item_added"))
                win.destroy()
                self._load_catalogue()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _checkout(self):
        win = tk.Toplevel(self)
        win.title(t("library.checkout"))
        win.geometry("300x200")
        fields = {}
        row = 0
        for label, key in [(t("library.item_id", default="Item ID") + "*:", "item_id"), (t("library.borrower_id", default="Borrower ID") + "*:", "borrower_id"),
                           (t("library.due_date", default="Due Date") + ":", "due_date")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=20)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                self._svc.checkout(
                    item_id=int(fields["item_id"].get().strip()),
                    borrower_id=int(fields["borrower_id"].get().strip()),
                    due_date=fields["due_date"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("library.item_checked_out"))
                win.destroy()
                self._load_loans()
                self._load_catalogue()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("library.checkout"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _return_item(self):
        sel = self._loan_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("library.select_loan_to_return"))
            return
        try:
            self._svc.return_item(int(sel[0]))
            messagebox.showinfo(t("common.success"), t("library.item_returned"))
            self._load_loans()
            self._load_catalogue()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _renew(self):
        sel = self._loan_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("library.select_loan_to_renew"))
            return
        try:
            self._svc.renew_loan(int(sel[0]))
            messagebox.showinfo(t("common.success"), t("library.loan_renewed"))
            self._load_loans()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def refresh(self):
        self._load_catalogue()
        self._load_loans()
