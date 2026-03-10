"""Student Portal GUI frame for managing portal pages and quick links."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.student_portal.services.student_portal_service import StudentPortalService


class StudentPortalFrame(tk.Frame):
    """Student Portal management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = StudentPortalService(db_path)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Student Portal",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_pages_tab()
        self._build_links_tab()
        self._build_stats_tab()

    # ── Pages Tab ──

    def _build_pages_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text="Portal Pages")

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        ttk.Button(toolbar, text="New", command=self._new_page).pack(side="left", padx=2)
        ttk.Button(toolbar, text="View", command=self._view_page).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_page).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Toggle Publish", command=self._toggle_publish).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete", command=self._delete_page).pack(side="left", padx=2)

        filter_frame = tk.Frame(toolbar, bg="#ecf0f1")
        filter_frame.pack(side="right")

        tk.Label(filter_frame, text="Category:", bg="#ecf0f1").pack(side="left", padx=2)
        self._page_cat_var = tk.StringVar(value="All")
        page_cat_combo = ttk.Combobox(filter_frame, textvariable=self._page_cat_var,
                                       values=["All", "general", "academic", "support",
                                                "events", "news", "faq"],
                                       width=12, state="readonly")
        page_cat_combo.pack(side="left", padx=2)
        page_cat_combo.bind("<<ComboboxSelected>>", lambda e: self._load_pages())

        tk.Label(filter_frame, text="Search:", bg="#ecf0f1").pack(side="left", padx=2)
        self._page_search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self._page_search_var, width=15)
        search_entry.pack(side="left", padx=2)
        search_entry.bind("<Return>", lambda e: self._load_pages())
        ttk.Button(filter_frame, text="Go", command=self._load_pages).pack(side="left", padx=2)

        cols = ("id", "title", "slug", "category", "published", "sort_order")
        self._pages_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c, heading, w in zip(cols,
                                  ("ID", "Title", "Slug", "Category", "Published", "Sort Order"),
                                  (50, 200, 150, 100, 80, 80)):
            self._pages_tree.heading(c, text=heading)
            self._pages_tree.column(c, width=w)
        self._pages_tree.pack(fill="both", expand=True, padx=5, pady=5)

        sb = ttk.Scrollbar(tab, orient="vertical", command=self._pages_tree.yview)
        self._pages_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _load_pages(self):
        for item in self._pages_tree.get_children():
            self._pages_tree.delete(item)
        try:
            cat = self._page_cat_var.get()
            category = None if cat == "All" else cat
            search = self._page_search_var.get().strip() or None
            pages = self._svc.list_pages(category=category, search=search)
            for p in pages:
                pub = "Yes" if p.get("is_published") else "No"
                self._pages_tree.insert("", "end", values=(
                    p["id"], p.get("page_title", ""), p.get("page_slug", ""),
                    p.get("category", ""), pub, p.get("sort_order", 0)))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_page_id(self):
        sel = self._pages_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a page.")
            return None
        return self._pages_tree.item(sel[0], "values")[0]

    def _new_page(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Portal Page")
        dlg.geometry("500x450")
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, default in [
            ("Title*:", "page_title", ""),
            ("Slug*:", "page_slug", ""),
            ("Category:", "category", "general"),
            ("Sort Order:", "sort_order", "0"),
        ]:
            tk.Label(dlg, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=5)
            fields[key] = var
            row += 1

        tk.Label(dlg, text="Content:").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        content_text = tk.Text(dlg, width=40, height=10)
        content_text.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        pub_var = tk.IntVar(value=1)
        ttk.Checkbutton(dlg, text="Published", variable=pub_var).grid(
            row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        def save():
            title = fields["page_title"].get().strip()
            slug = fields["page_slug"].get().strip()
            if not title or not slug:
                messagebox.showwarning("Validation", "Title and Slug are required.", parent=dlg)
                return
            try:
                so = int(fields["sort_order"].get() or 0)
            except ValueError:
                so = 0
            try:
                self._svc.create_page(
                    title, slug,
                    content=content_text.get("1.0", "end-1c").strip() or None,
                    category=fields["category"].get().strip() or "general",
                    sort_order=so,
                    is_published=pub_var.get(),
                )
                dlg.destroy()
                self._load_pages()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).grid(row=row, column=1, padx=10, pady=10, sticky="e")

    def _view_page(self):
        pid = self._selected_page_id()
        if pid is None:
            return
        try:
            page = self._svc.get_page(int(pid))
            if not page:
                messagebox.showinfo("Not Found", "Page not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Page: {page.get('page_title', '')}")
        dlg.geometry("500x400")
        dlg.grab_set()

        info_frame = tk.Frame(dlg)
        info_frame.pack(fill="x", padx=10, pady=5)
        for label, val in [
            ("Title:", page.get("page_title", "")),
            ("Slug:", page.get("page_slug", "")),
            ("Category:", page.get("category", "")),
            ("Published:", "Yes" if page.get("is_published") else "No"),
            ("Sort Order:", page.get("sort_order", 0)),
            ("Created:", page.get("created_at", "")),
            ("Updated:", page.get("updated_at", "")),
        ]:
            row_frame = tk.Frame(info_frame)
            row_frame.pack(fill="x", pady=1)
            tk.Label(row_frame, text=label, font=("Helvetica", 10, "bold"), width=12, anchor="e").pack(side="left")
            tk.Label(row_frame, text=str(val), anchor="w").pack(side="left", padx=5)

        tk.Label(dlg, text="Content:", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        content_text = tk.Text(dlg, width=60, height=10, state="normal")
        content_text.pack(fill="both", expand=True, padx=10, pady=5)
        content_text.insert("1.0", page.get("content") or "")
        content_text.configure(state="disabled")

        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=5)

    def _edit_page(self):
        pid = self._selected_page_id()
        if pid is None:
            return
        try:
            page = self._svc.get_page(int(pid))
            if not page:
                messagebox.showinfo("Not Found", "Page not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit Page #{pid}")
        dlg.geometry("500x450")
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, default in [
            ("Title*:", "page_title", page.get("page_title", "")),
            ("Slug*:", "page_slug", page.get("page_slug", "")),
            ("Category:", "category", page.get("category", "general")),
            ("Sort Order:", "sort_order", str(page.get("sort_order", 0))),
        ]:
            tk.Label(dlg, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=5)
            fields[key] = var
            row += 1

        tk.Label(dlg, text="Content:").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        content_text = tk.Text(dlg, width=40, height=10)
        content_text.grid(row=row, column=1, padx=10, pady=5)
        content_text.insert("1.0", page.get("content") or "")
        row += 1

        pub_var = tk.IntVar(value=1 if page.get("is_published") else 0)
        ttk.Checkbutton(dlg, text="Published", variable=pub_var).grid(
            row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        def save():
            title = fields["page_title"].get().strip()
            slug = fields["page_slug"].get().strip()
            if not title or not slug:
                messagebox.showwarning("Validation", "Title and Slug are required.", parent=dlg)
                return
            try:
                so = int(fields["sort_order"].get() or 0)
            except ValueError:
                so = 0
            try:
                self._svc.update_page(
                    int(pid),
                    page_title=title,
                    page_slug=slug,
                    content=content_text.get("1.0", "end-1c").strip() or None,
                    category=fields["category"].get().strip() or "general",
                    sort_order=so,
                    is_published=pub_var.get(),
                )
                dlg.destroy()
                self._load_pages()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).grid(row=row, column=1, padx=10, pady=10, sticky="e")

    def _toggle_publish(self):
        pid = self._selected_page_id()
        if pid is None:
            return
        try:
            page = self._svc.toggle_publish(int(pid))
            status = "Published" if page.get("is_published") else "Draft"
            messagebox.showinfo("Toggled", f"Page is now: {status}")
            self._load_pages()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_page(self):
        pid = self._selected_page_id()
        if pid is None:
            return
        if not messagebox.askyesno("Confirm", f"Delete page #{pid}?"):
            return
        try:
            self._svc.delete_page(int(pid))
            self._load_pages()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Links Tab ──

    def _build_links_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text="Quick Links")

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        ttk.Button(toolbar, text="New", command=self._new_link).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_link).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Toggle Active", command=self._toggle_active).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete", command=self._delete_link).pack(side="left", padx=2)

        filter_frame = tk.Frame(toolbar, bg="#ecf0f1")
        filter_frame.pack(side="right")

        tk.Label(filter_frame, text="Category:", bg="#ecf0f1").pack(side="left", padx=2)
        self._link_cat_var = tk.StringVar(value="All")
        link_cat_combo = ttk.Combobox(filter_frame, textvariable=self._link_cat_var,
                                       values=["All", "useful_links", "academic",
                                                "support", "external", "social"],
                                       width=12, state="readonly")
        link_cat_combo.pack(side="left", padx=2)
        link_cat_combo.bind("<<ComboboxSelected>>", lambda e: self._load_links())

        cols = ("id", "title", "url", "category", "active", "sort_order")
        self._links_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c, heading, w in zip(cols,
                                  ("ID", "Title", "URL", "Category", "Active", "Sort Order"),
                                  (50, 180, 200, 100, 70, 80)):
            self._links_tree.heading(c, text=heading)
            self._links_tree.column(c, width=w)
        self._links_tree.pack(fill="both", expand=True, padx=5, pady=5)

        sb = ttk.Scrollbar(tab, orient="vertical", command=self._links_tree.yview)
        self._links_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _load_links(self):
        for item in self._links_tree.get_children():
            self._links_tree.delete(item)
        try:
            cat = self._link_cat_var.get()
            category = None if cat == "All" else cat
            links = self._svc.list_links(category=category)
            for lnk in links:
                active = "Yes" if lnk.get("is_active") else "No"
                self._links_tree.insert("", "end", values=(
                    lnk["id"], lnk.get("link_title", ""), lnk.get("url", ""),
                    lnk.get("category", ""), active, lnk.get("sort_order", 0)))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_link_id(self):
        sel = self._links_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a link.")
            return None
        return self._links_tree.item(sel[0], "values")[0]

    def _new_link(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Quick Link")
        dlg.geometry("450x350")
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, default in [
            ("Title*:", "link_title", ""),
            ("URL*:", "url", ""),
            ("Category:", "category", "useful_links"),
            ("Description:", "description", ""),
            ("Icon:", "icon", ""),
            ("Sort Order:", "sort_order", "0"),
        ]:
            tk.Label(dlg, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=35).grid(row=row, column=1, padx=10, pady=5)
            fields[key] = var
            row += 1

        active_var = tk.IntVar(value=1)
        ttk.Checkbutton(dlg, text="Active", variable=active_var).grid(
            row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        def save():
            title = fields["link_title"].get().strip()
            url = fields["url"].get().strip()
            if not title or not url:
                messagebox.showwarning("Validation", "Title and URL are required.", parent=dlg)
                return
            try:
                so = int(fields["sort_order"].get() or 0)
            except ValueError:
                so = 0
            try:
                self._svc.create_link(
                    title, url,
                    category=fields["category"].get().strip() or "useful_links",
                    description=fields["description"].get().strip() or None,
                    icon=fields["icon"].get().strip() or None,
                    sort_order=so,
                    is_active=active_var.get(),
                )
                dlg.destroy()
                self._load_links()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).grid(row=row, column=1, padx=10, pady=10, sticky="e")

    def _edit_link(self):
        lid = self._selected_link_id()
        if lid is None:
            return
        try:
            link = self._svc.get_link(int(lid))
            if not link:
                messagebox.showinfo("Not Found", "Link not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit Link #{lid}")
        dlg.geometry("450x350")
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, default in [
            ("Title*:", "link_title", link.get("link_title", "")),
            ("URL*:", "url", link.get("url", "")),
            ("Category:", "category", link.get("category", "useful_links")),
            ("Description:", "description", link.get("description") or ""),
            ("Icon:", "icon", link.get("icon") or ""),
            ("Sort Order:", "sort_order", str(link.get("sort_order", 0))),
        ]:
            tk.Label(dlg, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=35).grid(row=row, column=1, padx=10, pady=5)
            fields[key] = var
            row += 1

        active_var = tk.IntVar(value=1 if link.get("is_active") else 0)
        ttk.Checkbutton(dlg, text="Active", variable=active_var).grid(
            row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        def save():
            title = fields["link_title"].get().strip()
            url = fields["url"].get().strip()
            if not title or not url:
                messagebox.showwarning("Validation", "Title and URL are required.", parent=dlg)
                return
            try:
                so = int(fields["sort_order"].get() or 0)
            except ValueError:
                so = 0
            try:
                self._svc.update_link(
                    int(lid),
                    link_title=title,
                    url=url,
                    category=fields["category"].get().strip() or "useful_links",
                    description=fields["description"].get().strip() or None,
                    icon=fields["icon"].get().strip() or None,
                    sort_order=so,
                    is_active=active_var.get(),
                )
                dlg.destroy()
                self._load_links()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).grid(row=row, column=1, padx=10, pady=10, sticky="e")

    def _toggle_active(self):
        lid = self._selected_link_id()
        if lid is None:
            return
        try:
            link = self._svc.toggle_active(int(lid))
            status = "Active" if link.get("is_active") else "Inactive"
            messagebox.showinfo("Toggled", f"Link is now: {status}")
            self._load_links()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_link(self):
        lid = self._selected_link_id()
        if lid is None:
            return
        if not messagebox.askyesno("Confirm", f"Delete link #{lid}?"):
            return
        try:
            self._svc.delete_link(int(lid))
            self._load_links()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Statistics Tab ──

    def _build_stats_tab(self):
        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text="Statistics")

        ttk.Button(self._stats_tab, text="Refresh Statistics",
                   command=self._load_stats).pack(pady=10)

        self._stats_frame = tk.Frame(self._stats_tab, bg="#ecf0f1")
        self._stats_frame.pack(fill="both", expand=True, padx=20, pady=10)

    def _load_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        try:
            stats = self._svc.get_stats()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        # Pages section
        pages_frame = tk.LabelFrame(self._stats_frame, text="Portal Pages",
                                     bg="#ecf0f1", font=("Helvetica", 11, "bold"))
        pages_frame.pack(fill="x", pady=5)

        tk.Label(pages_frame, text=f"Total Pages: {stats['total_pages']}",
                 bg="#ecf0f1", font=("Helvetica", 10)).pack(anchor="w", padx=15, pady=2)
        tk.Label(pages_frame, text=f"Published: {stats['published']}",
                 bg="#ecf0f1", font=("Helvetica", 10)).pack(anchor="w", padx=15, pady=2)
        tk.Label(pages_frame, text=f"Draft: {stats['draft']}",
                 bg="#ecf0f1", font=("Helvetica", 10)).pack(anchor="w", padx=15, pady=2)

        if stats["pages_by_category"]:
            tk.Label(pages_frame, text="By Category:",
                     bg="#ecf0f1", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=15, pady=(5, 2))
            for cat, cnt in stats["pages_by_category"].items():
                tk.Label(pages_frame, text=f"  {cat}: {cnt}",
                         bg="#ecf0f1", font=("Helvetica", 10)).pack(anchor="w", padx=25, pady=1)

        # Links section
        links_frame = tk.LabelFrame(self._stats_frame, text="Quick Links",
                                     bg="#ecf0f1", font=("Helvetica", 11, "bold"))
        links_frame.pack(fill="x", pady=5)

        tk.Label(links_frame, text=f"Total Links: {stats['total_links']}",
                 bg="#ecf0f1", font=("Helvetica", 10)).pack(anchor="w", padx=15, pady=2)
        tk.Label(links_frame, text=f"Active: {stats['active_links']}",
                 bg="#ecf0f1", font=("Helvetica", 10)).pack(anchor="w", padx=15, pady=2)
        tk.Label(links_frame, text=f"Inactive: {stats['inactive_links']}",
                 bg="#ecf0f1", font=("Helvetica", 10)).pack(anchor="w", padx=15, pady=2)

        if stats["links_by_category"]:
            tk.Label(links_frame, text="By Category:",
                     bg="#ecf0f1", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=15, pady=(5, 2))
            for cat, cnt in stats["links_by_category"].items():
                tk.Label(links_frame, text=f"  {cat}: {cnt}",
                         bg="#ecf0f1", font=("Helvetica", 10)).pack(anchor="w", padx=25, pady=1)

    # ── Refresh ──

    def refresh(self):
        self._load_pages()
        self._load_links()
        self._load_stats()
