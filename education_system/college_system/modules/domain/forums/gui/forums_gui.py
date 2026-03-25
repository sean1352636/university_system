"""Discussion Forums GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.forums.services.forums_service import ForumService


class ForumFrame(tk.Frame):
    """Discussion Forums management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ForumService(db_path)
        self._build_ui()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("forums.management"),
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Notebook
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_categories_tab()
        self._build_threads_tab()
        self._build_posts_tab()
        self._build_stats_tab()

    # -- Tab 1: Categories --------------------------------------------------

    def _build_categories_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("forums.category"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text=t("common.refresh"),
                   command=self._load_categories).pack(side="left")
        ttk.Button(toolbar, text=t("common.new"),
                   command=self._on_new_category).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.edit"),
                   command=self._on_edit_category).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.delete"),
                   command=self._on_delete_category).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Export CSV",
                   command=self._export_categories_csv).pack(side="left", padx=5)

        cols = ("id", "name", "description", "sort_order", "active", "created")
        self._cat_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                       height=12)
        for col, heading, w in [
            ("id", t("common.id"), 40), ("name", t("common.name"), 180),
            ("description", t("common.description"), 250),
            ("sort_order", t("common.order"), 50), ("active", t("common.active"), 50),
            ("created", t("common.created"), 130),
        ]:
            self._cat_tree.heading(col, text=heading)
            self._cat_tree.column(col, width=w, anchor="center")
        self._cat_tree.pack(fill="both", expand=True)

    # -- Tab 2: Threads -----------------------------------------------------

    def _build_threads_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("forums.threads"))

        # Filter bar
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text=t("forums.category") + ":", bg="#ecf0f1").pack(side="left")
        self._thread_cat_var = tk.StringVar(value=t("common.all"))
        self._thread_cat_combo = ttk.Combobox(
            filt, textvariable=self._thread_cat_var, state="readonly", width=18,
        )
        self._thread_cat_combo.pack(side="left", padx=5)

        tk.Label(filt, text=t("common.search") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._thread_search_var = tk.StringVar()
        ttk.Entry(filt, textvariable=self._thread_search_var,
                  width=20).pack(side="left", padx=5)

        ttk.Button(filt, text=t("common.refresh"),
                   command=self._load_threads).pack(side="left", padx=5)

        # Toolbar
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text=t("common.new"),
                   command=self._on_new_thread).pack(side="left")
        ttk.Button(toolbar, text=t("common.view"),
                   command=self._on_view_thread).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.edit"),
                   command=self._on_edit_thread).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("forums.pin_unpin"),
                   command=self._on_pin_thread).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("forums.lock_unlock"),
                   command=self._on_lock_thread).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.delete"),
                   command=self._on_delete_thread).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Export CSV",
                   command=self._export_csv).pack(side="left", padx=4)

        cols = ("id", "category", "title", "author", "replies", "views",
                "pinned", "locked", "status", "created")
        self._thread_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                          height=12)
        for col, heading, w in [
            ("id", t("common.id"), 40), ("category", t("forums.category"), 120),
            ("title", t("common.title"), 220), ("author", t("common.author"), 100),
            ("replies", t("forums.replies"), 55), ("views", t("forums.views"), 55),
            ("pinned", t("forums.pin"), 35), ("locked", t("forums.lock"), 35),
            ("status", t("common.status"), 60), ("created", t("common.created"), 120),
        ]:
            self._thread_tree.heading(col, text=heading)
            self._thread_tree.column(col, width=w, anchor="center")
        self._thread_tree.pack(fill="both", expand=True)

    # -- Tab 3: Posts -------------------------------------------------------

    def _build_posts_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("forums.posts"))

        # Thread selector
        sel_row = tk.Frame(tab, bg="#ecf0f1")
        sel_row.pack(fill="x", pady=(0, 5))
        tk.Label(sel_row, text=t("forums.thread_id") + ":", bg="#ecf0f1").pack(side="left")
        self._post_thread_var = tk.StringVar()
        ttk.Entry(sel_row, textvariable=self._post_thread_var,
                  width=8).pack(side="left", padx=5)
        ttk.Button(sel_row, text=t("forums.load_posts"),
                   command=self._load_posts).pack(side="left", padx=5)

        # Toolbar
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text=t("forums.new_post"),
                   command=self._on_new_post).pack(side="left")
        ttk.Button(toolbar, text=t("common.edit"),
                   command=self._on_edit_post).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.delete"),
                   command=self._on_delete_post).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("forums.mark_solution"),
                   command=self._on_mark_solution).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Export CSV",
                   command=self._export_posts_csv).pack(side="left", padx=5)

        cols = ("id", "author", "content", "solution", "edited", "created")
        self._post_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                        height=12)
        for col, heading, w in [
            ("id", t("common.id"), 40), ("author", t("common.author"), 100),
            ("content", t("forums.content"), 350), ("solution", t("forums.solution"), 35),
            ("edited", t("common.edited"), 120), ("created", t("common.created"), 120),
        ]:
            self._post_tree.heading(col, text=heading)
            self._post_tree.column(col, width=w, anchor="center")
        self._post_tree.pack(fill="both", expand=True)

    # -- Tab 4: Statistics --------------------------------------------------

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("common.statistics"))

        self._stats_frame = tk.Frame(tab, bg="#ecf0f1")
        self._stats_frame.pack(fill="both", expand=True)

        ttk.Button(tab, text=t("common.refresh_statistics"),
                   command=self._load_stats).pack(pady=10)

    # -- Data loading -------------------------------------------------------

    def refresh(self):
        """Reload all tab data."""
        self._load_categories()
        self._load_threads()
        self._load_stats()

    def _load_categories(self):
        self._cat_tree.delete(*self._cat_tree.get_children())
        try:
            cats = self._svc.list_categories()
            for c in cats:
                self._cat_tree.insert("", "end", values=(
                    c["id"], c["name"], c.get("description", ""),
                    c.get("sort_order", 0),
                    t("common.yes") if c.get("is_active", 1) else t("common.no"),
                    c["created_at"][:16] if c.get("created_at") else "",
                ))
            # Update category combo on threads tab
            names = [t("common.all")] + [c["name"] for c in cats]
            self._thread_cat_combo["values"] = names
            self._cat_id_map = {c["name"]: c["id"] for c in cats}
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_threads(self):
        self._thread_tree.delete(*self._thread_tree.get_children())
        try:
            cat_name = self._thread_cat_var.get()
            cat_id = None
            if cat_name != t("common.all") and hasattr(self, "_cat_id_map"):
                cat_id = self._cat_id_map.get(cat_name)
            search = self._thread_search_var.get().strip() or None
            threads = self._svc.list_threads(category_id=cat_id, search=search)
            for th in threads:
                self._thread_tree.insert("", "end", values=(
                    th["id"],
                    th.get("category_name", ""),
                    th["title"],
                    th.get("author_name", ""),
                    th.get("reply_count", 0),
                    th.get("view_count", 0),
                    "Y" if th.get("is_pinned") else "",
                    "Y" if th.get("is_locked") else "",
                    th.get("status", "open"),
                    th["created_at"][:16] if th.get("created_at") else "",
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_posts(self):
        self._post_tree.delete(*self._post_tree.get_children())
        tid = self._post_thread_var.get().strip()
        if not tid:
            messagebox.showwarning(t("common.input"), t("forums.enter_thread_id"))
            return
        try:
            posts = self._svc.list_posts(int(tid))
            for p in posts:
                content_preview = (p.get("content", "")[:80]
                                   .replace("\n", " "))
                self._post_tree.insert("", "end", values=(
                    p["id"],
                    p.get("author_name", ""),
                    content_preview,
                    "Y" if p.get("is_solution") else "",
                    p["edited_at"][:16] if p.get("edited_at") else "",
                    p["created_at"][:16] if p.get("created_at") else "",
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        try:
            stats = self._svc.get_stats()
            row = 0
            for label, key in [
                (t("forums.total_categories") + ":", "total_categories"),
                (t("forums.total_threads") + ":", "total_threads"),
                (t("forums.total_posts") + ":", "total_posts"),
                (t("forums.active_threads") + ":", "active_threads"),
            ]:
                tk.Label(self._stats_frame, text=label, bg="#ecf0f1",
                         font=("Helvetica", 11, "bold"), anchor="e"
                         ).grid(row=row, column=0, sticky="e", padx=(20, 10), pady=5)
                tk.Label(self._stats_frame, text=str(stats.get(key, 0)),
                         bg="#ecf0f1", font=("Helvetica", 11), anchor="w"
                         ).grid(row=row, column=1, sticky="w", pady=5)
                row += 1
        except Exception as e:
            tk.Label(self._stats_frame, text=f"{t('common.error')}: {e}", bg="#ecf0f1",
                     fg="red").pack(pady=20)

    # -- Helpers ------------------------------------------------------------

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._thread_tree, "forums_threads_export.csv")

    def _export_categories_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._cat_tree, "forums_categories_export.csv")

    def _export_posts_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._post_tree, "forums_posts_export.csv")

    def _get_user_id(self) -> int:
        if self._auth and self._auth.current_user:
            return self._auth.current_user["user_id"]
        return 0

    def _selected_tree_id(self, tree) -> int | None:
        sel = tree.selection()
        if not sel:
            return None
        return int(tree.item(sel[0], "values")[0])

    # -- Category actions ---------------------------------------------------

    def _on_new_category(self):
        dlg = _CategoryDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._svc.create_category(**dlg.result)
                messagebox.showinfo(t("common.success"), t("forums.category_created"))
                self._load_categories()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

    def _on_edit_category(self):
        cid = self._selected_tree_id(self._cat_tree)
        if cid is None:
            messagebox.showwarning(t("common.select"), t("forums.select_category"))
            return
        cat = self._svc.get_category(cid)
        if not cat:
            messagebox.showerror(t("common.error"), t("forums.category_not_found"))
            return
        dlg = _CategoryDialog(self, cat)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._svc.update_category(cid, **dlg.result)
                messagebox.showinfo(t("common.success"), t("forums.category_updated"))
                self._load_categories()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

    def _on_delete_category(self):
        cid = self._selected_tree_id(self._cat_tree)
        if cid is None:
            messagebox.showwarning(t("common.select"), t("forums.select_category"))
            return
        if not messagebox.askyesno(t("common.confirm"), t("forums.confirm_delete_category")):
            return
        try:
            self._svc.delete_category(cid)
            messagebox.showinfo(t("common.success"), t("forums.category_deleted"))
            self._load_categories()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- Thread actions -----------------------------------------------------

    def _on_new_thread(self):
        cats = self._svc.list_categories(active_only=True)
        if not cats:
            messagebox.showwarning(t("common.warning"),
                                   t("forums.create_category_first"))
            return
        dlg = _ThreadDialog(self, cats)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._svc.create_thread(
                    category_id=dlg.result["category_id"],
                    title=dlg.result["title"],
                    author_id=self._get_user_id(),
                )
                messagebox.showinfo(t("common.success"), t("forums.thread_created"))
                self._load_threads()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

    def _on_view_thread(self):
        tid = self._selected_tree_id(self._thread_tree)
        if tid is None:
            messagebox.showwarning(t("common.select"), t("forums.select_thread"))
            return
        # Switch to Posts tab with that thread loaded
        self._post_thread_var.set(str(tid))
        self._nb.select(2)  # Posts tab index
        self._load_posts()

    def _on_edit_thread(self):
        tid = self._selected_tree_id(self._thread_tree)
        if tid is None:
            messagebox.showwarning(t("common.select"), t("forums.select_thread"))
            return
        thread = self._svc.get_thread(tid)
        if not thread:
            messagebox.showerror(t("common.error"), t("forums.thread_not_found"))
            return
        cats = self._svc.list_categories(active_only=True)
        dlg = _ThreadDialog(self, cats, thread)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._svc.update_thread(tid, **dlg.result)
                messagebox.showinfo(t("common.success"), t("forums.thread_updated"))
                self._load_threads()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

    def _on_pin_thread(self):
        tid = self._selected_tree_id(self._thread_tree)
        if tid is None:
            messagebox.showwarning(t("common.select"), t("forums.select_thread"))
            return
        sel = self._thread_tree.selection()
        is_pinned = self._thread_tree.item(sel[0], "values")[6] == "Y"
        try:
            self._svc.pin_thread(tid, pinned=not is_pinned)
            self._load_threads()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_lock_thread(self):
        tid = self._selected_tree_id(self._thread_tree)
        if tid is None:
            messagebox.showwarning(t("common.select"), t("forums.select_thread"))
            return
        sel = self._thread_tree.selection()
        is_locked = self._thread_tree.item(sel[0], "values")[7] == "Y"
        try:
            self._svc.lock_thread(tid, locked=not is_locked)
            self._load_threads()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_delete_thread(self):
        tid = self._selected_tree_id(self._thread_tree)
        if tid is None:
            messagebox.showwarning(t("common.select"), t("forums.select_thread"))
            return
        if not messagebox.askyesno(t("common.confirm"),
                                   t("forums.confirm_delete_thread")):
            return
        try:
            self._svc.delete_thread(tid)
            messagebox.showinfo(t("common.success"), t("forums.thread_deleted"))
            self._load_threads()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- Post actions -------------------------------------------------------

    def _on_new_post(self):
        tid = self._post_thread_var.get().strip()
        if not tid:
            messagebox.showwarning(t("common.input"), t("forums.load_thread_first"))
            return
        dlg = _PostDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._svc.create_post(
                    thread_id=int(tid),
                    author_id=self._get_user_id(),
                    content=dlg.result["content"],
                )
                messagebox.showinfo(t("common.success"), t("forums.post_created"))
                self._load_posts()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

    def _on_edit_post(self):
        pid = self._selected_tree_id(self._post_tree)
        if pid is None:
            messagebox.showwarning(t("common.select"), t("forums.select_post"))
            return
        # Fetch existing content
        sel = self._post_tree.selection()
        existing_content = self._post_tree.item(sel[0], "values")[2]
        dlg = _PostDialog(self, existing_content=existing_content)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._svc.update_post(pid, content=dlg.result["content"])
                messagebox.showinfo(t("common.success"), t("forums.post_updated"))
                self._load_posts()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

    def _on_delete_post(self):
        pid = self._selected_tree_id(self._post_tree)
        if pid is None:
            messagebox.showwarning(t("common.select"), t("forums.select_post"))
            return
        if not messagebox.askyesno(t("common.confirm"), t("forums.confirm_delete_post")):
            return
        try:
            self._svc.delete_post(pid)
            messagebox.showinfo(t("common.success"), t("forums.post_deleted"))
            self._load_posts()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_mark_solution(self):
        pid = self._selected_tree_id(self._post_tree)
        if pid is None:
            messagebox.showwarning(t("common.select"), t("forums.select_post"))
            return
        sel = self._post_tree.selection()
        is_solution = self._post_tree.item(sel[0], "values")[3] == "Y"
        try:
            self._svc.mark_solution(pid, is_solution=not is_solution)
            self._load_posts()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))


# -- Dialogs ----------------------------------------------------------------


class _CategoryDialog(tk.Toplevel):
    """Create / edit forum category dialog."""

    def __init__(self, parent, existing=None):
        super().__init__(parent)
        self.title(t("forums.edit_category") if existing else t("forums.new_category"))
        self.geometry("400x220")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._existing = existing

        frame = tk.Frame(self, padx=15, pady=15)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=t("common.name") + ":").grid(row=0, column=0, sticky="w", pady=3)
        self._name_var = tk.StringVar(
            value=existing["name"] if existing else "")
        ttk.Entry(frame, textvariable=self._name_var, width=30).grid(
            row=0, column=1, pady=3)

        tk.Label(frame, text=t("common.description") + ":").grid(
            row=1, column=0, sticky="nw", pady=3)
        self._desc_text = tk.Text(frame, width=23, height=3)
        self._desc_text.grid(row=1, column=1, pady=3)
        if existing and existing.get("description"):
            self._desc_text.insert("1.0", existing["description"])

        tk.Label(frame, text=t("common.order") + ":").grid(
            row=2, column=0, sticky="w", pady=3)
        self._order_var = tk.StringVar(
            value=str(existing.get("sort_order", 0)) if existing else "0")
        ttk.Entry(frame, textvariable=self._order_var, width=8).grid(
            row=2, column=1, sticky="w", pady=3)

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._save).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(
            side="left", padx=5)

    def _save(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning(t("common.input"), t("forums.name_required"), parent=self)
            return
        try:
            order = int(self._order_var.get())
        except ValueError:
            messagebox.showwarning(t("common.input"), t("forums.order_must_be_number"),
                                   parent=self)
            return
        self.result = {
            "name": name,
            "description": self._desc_text.get("1.0", "end").strip(),
            "sort_order": order,
        }
        self.destroy()


class _ThreadDialog(tk.Toplevel):
    """Create / edit forum thread dialog."""

    def __init__(self, parent, categories, existing=None):
        super().__init__(parent)
        self.title(t("forums.edit_thread") if existing else t("forums.new_thread"))
        self.geometry("430x200")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._categories = categories
        self._existing = existing

        frame = tk.Frame(self, padx=15, pady=15)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=t("forums.category") + ":").grid(
            row=0, column=0, sticky="w", pady=3)
        cat_names = [c["name"] for c in categories]
        self._cat_var = tk.StringVar()
        if existing:
            self._cat_var.set(existing.get("category_name", cat_names[0]))
        else:
            self._cat_var.set(cat_names[0] if cat_names else "")
        ttk.Combobox(frame, textvariable=self._cat_var, values=cat_names,
                     state="readonly", width=22).grid(
            row=0, column=1, sticky="w", pady=3)

        tk.Label(frame, text=t("common.title") + ":").grid(
            row=1, column=0, sticky="w", pady=3)
        self._title_var = tk.StringVar(
            value=existing["title"] if existing else "")
        ttk.Entry(frame, textvariable=self._title_var, width=35).grid(
            row=1, column=1, pady=3)

        if existing:
            tk.Label(frame, text=t("common.status") + ":").grid(
                row=2, column=0, sticky="w", pady=3)
            self._status_var = tk.StringVar(
                value=existing.get("status", "open"))
            ttk.Combobox(frame, textvariable=self._status_var,
                         values=["open", "closed", "resolved"],
                         state="readonly", width=12).grid(
                row=2, column=1, sticky="w", pady=3)

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._save).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(
            side="left", padx=5)

    def _save(self):
        title = self._title_var.get().strip()
        if not title:
            messagebox.showwarning(t("common.input"), t("forums.title_required"), parent=self)
            return
        cat_name = self._cat_var.get()
        cat_id = None
        for c in self._categories:
            if c["name"] == cat_name:
                cat_id = c["id"]
                break
        if cat_id is None:
            messagebox.showwarning(t("common.input"), t("forums.select_a_category"), parent=self)
            return
        self.result = {"title": title, "category_id": cat_id}
        if self._existing and hasattr(self, "_status_var"):
            self.result["status"] = self._status_var.get()
        self.destroy()


class _PostDialog(tk.Toplevel):
    """Create / edit forum post dialog."""

    def __init__(self, parent, existing_content=None):
        super().__init__(parent)
        self.title(t("forums.edit_post") if existing_content else t("forums.new_post"))
        self.geometry("450x280")
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        frame = tk.Frame(self, padx=15, pady=15)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=t("forums.content") + ":").pack(anchor="w")
        self._content_text = tk.Text(frame, width=50, height=10)
        self._content_text.pack(fill="both", expand=True, pady=5)
        if existing_content:
            self._content_text.insert("1.0", existing_content)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=(5, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._save).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(
            side="left", padx=5)

    def _save(self):
        content = self._content_text.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning(t("common.input"), t("forums.content_required"),
                                   parent=self)
            return
        self.result = {"content": content}
        self.destroy()
