"""Feature 3 — Syllabus & course materials.

Lets staff attach materials to a course: syllabus documents, textbooks
(with author / ISBN / edition / cost), reading lists, software and links.
A running total of required-material cost is shown so the student cost of a
course is visible at a glance.
"""

import os
import webbrowser

from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.ext_common import (
    ExtFormDialog, tk, ttk, messagebox, _, logger,
)

# filedialog isn't re-exported from _imports' alias surface, so import lazily.
try:
    from tkinter import filedialog
except Exception:  # pragma: no cover
    filedialog = None

MATERIAL_TYPES = [
    "Syllabus", "Textbook", "Reading", "Article", "Software",
    "Equipment", "Website", "Other",
]


class MaterialsTabMixin:
    """Syllabus & course-materials tab."""

    def create_materials_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.materials",
                                            default="Syllabus & Materials"))

            sel = ttk.LabelFrame(frame, text=_("course_management.labels.select_course",
                                               default="Select Course"), padding=10)
            sel.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(sel, text="Course:").pack(side=tk.LEFT, padx=5)
            self._mat_course_combo = ttk.Combobox(sel, width=50, state="readonly")
            self._mat_course_combo.pack(side=tk.LEFT, padx=5)
            self._mat_course_combo.bind("<<ComboboxSelected>>", self._reload_materials)
            ttk.Button(sel, text=_("common.refresh", default="Refresh"),
                       command=self._reload_mat_courses).pack(side=tk.LEFT, padx=5)
            self._mat_cost_var = tk.StringVar(value="")
            ttk.Label(sel, textvariable=self._mat_cost_var,
                      font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=10)

            bar = ttk.Frame(frame)
            bar.pack(fill=tk.X, padx=5, pady=5)
            if self._ext_can_edit():
                ttk.Button(bar, text=_("common.add", default="Add Material"),
                           command=self._add_material).pack(side=tk.LEFT, padx=5)
                ttk.Button(bar, text=_("common.edit", default="Edit"),
                           command=self._edit_material).pack(side=tk.LEFT, padx=5)
                ttk.Button(bar, text=_("common.delete", default="Delete"),
                           command=self._delete_material).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text="Open Link / File",
                       command=self._open_material).pack(side=tk.LEFT, padx=5)
            # Cross-link: textbooks / reading lists here live in the Library
            # catalogue — jump to the Library to manage holdings and loans.
            ttk.Button(bar, text=_("course_management.buttons.open_library",
                                   default="Open Library →"),
                       command=self._open_library).pack(side=tk.RIGHT, padx=5)
            if self._ext_can_edit():
                # Tie-in: push a textbook/reading material into the Library
                # catalogue and onto this course's reading list.
                ttk.Button(bar, text=_("course_management.buttons.add_to_library",
                                       default="Add selected to Library"),
                           command=self._add_material_to_library).pack(side=tk.LEFT, padx=15)

            # Live Library availability for the selected material (matched by ISBN/title).
            self._mat_lib_var = tk.StringVar(value="")
            ttk.Label(frame, textvariable=self._mat_lib_var,
                      foreground="#2c3e50").pack(fill=tk.X, padx=8, pady=(0, 4))

            list_frame = ttk.Frame(frame)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            cols = ("ID", "Type", "Title", "Author", "ISBN", "Edition",
                    "Cost", "Required")
            self._materials_tree = ttk.Treeview(list_frame, columns=cols,
                                                show="headings", height=16)
            widths = {"ID": 45, "Type": 90, "Title": 260, "Author": 150,
                      "ISBN": 120, "Edition": 80, "Cost": 80, "Required": 80}
            for c in cols:
                self._materials_tree.heading(c, text=c)
                self._materials_tree.column(c, width=widths.get(c, 100))
            self._materials_tree.bind("<Double-1>", lambda _e: self._open_material())
            self._materials_tree.bind("<<TreeviewSelect>>",
                                      lambda _e: self._mat_check_library())
            sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                               command=self._materials_tree.yview)
            self._materials_tree.configure(yscrollcommand=sb.set)
            self._materials_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

            self._reload_mat_courses()
        except Exception as exc:
            self._ext_report_error("build Syllabus & Materials tab", exc)

    # -- course selection ----------------------------------------------

    def _open_library(self):
        """Open the Library Management GUI in its own window."""
        def _build(top):
            from education_system.post_18.university_system.modules.domain.academics.gui.library import (
                LibraryGUI,
            )
            LibraryGUI(top, auth=getattr(self, "auth", None))
        self._ext_launch_window(
            _("course_management.titles.library", default="Library Management"),
            _build, geometry="1400x900", minsize=(1000, 600))

    # -- Library catalogue tie-in --------------------------------------
    def _mat_selected_row(self):
        """Selected material row as a dict, or None.
        Columns: ID, Type, Title, Author, ISBN, Edition, Cost, Required."""
        sel = self._materials_tree.selection()
        if not sel:
            return None
        v = self._materials_tree.item(sel[0]).get("values") or []
        keys = ("id", "type", "title", "author", "isbn", "edition", "cost", "required")
        return dict(zip(keys, v)) if v else None

    def _library_book_for(self, conn, isbn, title):
        """Find a catalogue book by ISBN (preferred) or exact title. Returns row
        (book_id, title, status) or None."""
        cur = conn.cursor()
        if isbn:
            row = cur.execute(
                "SELECT book_id, title, status FROM books WHERE isbn = ?",
                (str(isbn).strip(),)).fetchone()
            if row:
                return row
        if title:
            row = cur.execute(
                "SELECT book_id, title, status FROM books "
                "WHERE LOWER(TRIM(title)) = LOWER(TRIM(?))", (str(title).strip(),)).fetchone()
            if row:
                return row
        return None

    def _mat_check_library(self):
        """Update the availability label for the selected material."""
        if not hasattr(self, "_mat_lib_var"):
            return
        mat = self._mat_selected_row()
        if not mat or str(mat.get("type")) not in ("Textbook", "Reading", "Article"):
            self._mat_lib_var.set("")
            return
        try:
            with self._ext_db() as conn:
                book = self._library_book_for(conn, mat.get("isbn"), mat.get("title"))
                if not book:
                    self._mat_lib_var.set(
                        f"📕 '{mat.get('title')}' is NOT in the Library catalogue.")
                    return
                # On-loan count if a loans table exists (best-effort).
                on_loan = 0
                try:
                    on_loan = conn.execute(
                        "SELECT COUNT(*) FROM book_loans WHERE book_id = ? "
                        "AND (return_date IS NULL OR return_date = '')",
                        (book[0],)).fetchone()[0]
                except Exception:
                    on_loan = 0
                status = book[2] or "unknown"
                extra = f" · {on_loan} on loan" if on_loan else ""
                self._mat_lib_var.set(
                    f"📗 In Library: '{book[1]}' — status {status}{extra}.")
        except Exception:
            self._mat_lib_var.set("")

    def _add_material_to_library(self):
        """Add the selected textbook/reading material to the Library catalogue
        and onto this course's reading list."""
        if not self._ext_can_edit():
            return
        mat = self._mat_selected_row()
        if not mat:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a material first.")
            return
        if str(mat.get("type")) not in ("Textbook", "Reading", "Article"):
            messagebox.showinfo(_("common.info", default="Info"),
                                "Only Textbook / Reading / Article materials can be "
                                "added to the Library.")
            return
        course = self._current_mat_course()
        try:
            import uuid
            with self._ext_db(write=True) as conn:
                cur = conn.cursor()
                book = self._library_book_for(conn, mat.get("isbn"), mat.get("title"))
                if book:
                    book_id = book[0]
                    created_book = False
                else:
                    isbn = (str(mat.get("isbn")).strip() or None) if mat.get("isbn") else None
                    book_id = f"CM-{(isbn or uuid.uuid4().hex[:10])}"
                    try:
                        cost = float(mat.get("cost") or 0)
                    except (TypeError, ValueError):
                        cost = 0.0
                    cur.execute(
                        "INSERT INTO books (book_id, title, author, isbn, edition, "
                        " category, acquisition_cost, status, added_date) "
                        "VALUES (?, ?, ?, ?, ?, 'Course Text', ?, 'available', ?)",
                        (book_id, mat.get("title") or "Untitled",
                         mat.get("author") or "Unknown", isbn,
                         mat.get("edition") or None, cost, self._ext_now()))
                    created_book = True

                # Course reading list (name-keyed, no schema change needed).
                added_to_list = False
                if course:
                    list_name = f"{course} — Reading List"
                    row = cur.execute(
                        "SELECT list_id FROM reading_lists WHERE name = ?",
                        (list_name,)).fetchone()
                    if row:
                        list_id = row[0]
                    else:
                        cur.execute(
                            "INSERT INTO reading_lists (name, description, creator_id, "
                            " created_date, is_public, category) "
                            "VALUES (?, ?, ?, ?, 1, 'Course')",
                            (list_name, f"Reading list for course {course}",
                             self._ext_username(), self._ext_now()))
                        list_id = cur.lastrowid
                    dup = cur.execute(
                        "SELECT 1 FROM reading_list_items WHERE list_id = ? AND book_id = ?",
                        (list_id, book_id)).fetchone()
                    if not dup:
                        cur.execute(
                            "INSERT INTO reading_list_items (list_id, book_id, "
                            " added_date, added_by) VALUES (?, ?, ?, ?)",
                            (list_id, book_id, self._ext_now(), self._ext_username()))
                        added_to_list = True
        except Exception as exc:
            self._ext_report_error("add material to Library", exc)
            return
        self._ext_audit("add_to_library", "material", course_code=course,
                        title=mat.get("title"))
        parts = ["Catalogue: " + ("book added" if created_book else "already present")]
        if course:
            parts.append("Reading list: " + ("linked" if added_to_list else "already linked"))
        messagebox.showinfo(_("common.success", default="Done"), "\n".join(parts))
        self._mat_check_library()

    def _reload_mat_courses(self):
        try:
            labels, self._mat_course_map = self._ext_course_choices()
            self._mat_course_combo["values"] = labels
            if labels and not self._mat_course_combo.get():
                self._mat_course_combo.current(0)
            self._reload_materials()
        except Exception as exc:
            self._ext_report_error("load courses", exc)

    def _current_mat_course(self):
        return self._ext_code_from_label(self._mat_course_combo.get(),
                                         getattr(self, "_mat_course_map", {}))

    def _reload_materials(self, *_a):
        if not hasattr(self, "_materials_tree"):
            return
        self._ext_clear_tree(self._materials_tree)
        code = self._current_mat_course()
        if not code:
            self._mat_cost_var.set("")
            return
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, material_type, title, author, isbn, edition, "
                    "cost, required FROM course_materials "
                    "WHERE course_code=? ORDER BY material_type, title", (code,))
                rows = cur.fetchall()
            required_total = 0.0
            for rid, mtype, title, author, isbn, edition, cost, required in rows:
                cost = cost or 0.0
                if required:
                    required_total += cost
                self._materials_tree.insert("", tk.END, values=(
                    rid, mtype, title, author, isbn, edition,
                    f"{cost:.2f}", "Yes" if required else "No"))
            self._mat_cost_var.set(
                f"Required materials cost: {required_total:.2f}")
            logger.debug("Loaded %d materials for %s", len(rows), code)
        except Exception as exc:
            self._ext_report_error("load materials", exc)

    # -- CRUD -----------------------------------------------------------

    def _material_fields(self, data=None):
        data = data or {}
        return [
            ("material_type", "Type:", {"type": "combo", "values": MATERIAL_TYPES,
                                        "default": data.get("material_type", "Textbook")}),
            ("title", "Title:", {"default": data.get("title", "")}),
            ("author", "Author:", {"default": data.get("author", "")}),
            ("isbn", "ISBN:", {"default": data.get("isbn", "")}),
            ("edition", "Edition:", {"default": data.get("edition", ""), "width": 20}),
            ("url", "URL / File path:", {"default": data.get("url", "")}),
            ("cost", "Cost:", {"default": data.get("cost", "0.0"), "width": 12}),
            ("required", "Required", {"type": "check",
                                      "default": data.get("required", True)}),
            ("notes", "Notes:", {"type": "text", "default": data.get("notes", ""),
                                 "height": 3}),
        ]

    def _parse_cost(self, values):
        try:
            cost = float(values.get("cost") or 0)
        except (TypeError, ValueError):
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Cost must be a number.")
            return None
        if cost < 0:
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Cost cannot be negative.")
            return None
        return cost

    def _add_material(self):
        if not self._ext_can_edit():
            return
        code = self._current_mat_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return

        def submit(values):
            title = (values.get("title") or "").strip()
            if not title:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Title is required.")
                return False
            cost = self._parse_cost(values)
            if cost is None:
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "INSERT INTO course_materials "
                        "(course_code, material_type, title, author, isbn, edition, "
                        " url, cost, required, notes, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (code, values["material_type"], title, values["author"],
                         values["isbn"], values["edition"], values["url"], cost,
                         1 if values.get("required") else 0, values["notes"],
                         self._ext_now(), self._ext_now()))
            except Exception as exc:
                self._ext_report_error("add material", exc)
                return False
            self._ext_audit("create", "course_material", course_code=code, title=title)
            self._reload_materials()
            return True

        ExtFormDialog(self.root, self, f"Add Material for {code}",
                      self._material_fields(), submit,
                      submit_label="Add", geometry="560x500")

    def _selected_material(self):
        vals = self._ext_selected_values(self._materials_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a material first.")
            return None
        return vals

    def _edit_material(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_material()
        if not vals:
            return
        mat_id = vals[0]
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT material_type, title, author, isbn, edition, url, "
                    "cost, required, notes FROM course_materials WHERE id=?",
                    (mat_id,))
                row = cur.fetchone()
        except Exception as exc:
            self._ext_report_error("load material", exc)
            return
        if not row:
            messagebox.showerror(_("common.error", default="Error"), "Material not found.")
            return
        data = {"material_type": row[0], "title": row[1], "author": row[2],
                "isbn": row[3], "edition": row[4], "url": row[5],
                "cost": row[6], "required": bool(row[7]), "notes": row[8]}

        def submit(values):
            title = (values.get("title") or "").strip()
            if not title:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Title is required.")
                return False
            cost = self._parse_cost(values)
            if cost is None:
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "UPDATE course_materials SET material_type=?, title=?, "
                        "author=?, isbn=?, edition=?, url=?, cost=?, required=?, "
                        "notes=?, updated_at=? WHERE id=?",
                        (values["material_type"], title, values["author"],
                         values["isbn"], values["edition"], values["url"], cost,
                         1 if values.get("required") else 0, values["notes"],
                         self._ext_now(), mat_id))
            except Exception as exc:
                self._ext_report_error("update material", exc)
                return False
            self._ext_audit("update", "course_material", material_id=mat_id)
            self._reload_materials()
            return True

        ExtFormDialog(self.root, self, "Edit Material",
                      self._material_fields(data), submit,
                      submit_label="Save", geometry="560x500")

    def _delete_material(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_material()
        if not vals:
            return
        if not messagebox.askyesno(_("common.confirm", default="Confirm"),
                                   f"Delete material '{vals[2]}'?"):
            return
        try:
            with self._ext_db(write=True) as conn:
                conn.execute("DELETE FROM course_materials WHERE id=?", (vals[0],))
        except Exception as exc:
            self._ext_report_error("delete material", exc)
            return
        self._ext_audit("delete", "course_material", material_id=vals[0])
        self._reload_materials()

    def _open_material(self):
        """Open the material's URL in a browser, or a local file path."""
        vals = self._selected_material()
        if not vals:
            return
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT url FROM course_materials WHERE id=?", (vals[0],))
                row = cur.fetchone()
            target = (row[0] if row else "") or ""
        except Exception as exc:
            self._ext_report_error("read material link", exc)
            return
        target = target.strip()
        if not target:
            messagebox.showinfo(_("common.info", default="Info"),
                                "This material has no URL or file path.")
            return
        try:
            if target.lower().startswith(("http://", "https://")):
                webbrowser.open(target)
            elif os.path.exists(target):
                webbrowser.open("file://" + os.path.abspath(target))
            else:
                messagebox.showwarning(_("common.warning", default="Warning"),
                                       f"Cannot locate:\n{target}")
        except Exception as exc:
            self._ext_report_error("open material", exc)
