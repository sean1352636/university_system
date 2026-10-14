"""Feature 3 — Syllabus & course materials.

Lets staff attach materials to a course: syllabus documents, textbooks
(with author / ISBN / edition / cost), reading lists, software and links.
A running total of required-material cost is shown so the student cost of a
course is visible at a glance.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import os
import webbrowser

from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.core.ext_common import (
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

#: Types that belong in the Library catalogue and on a course reading list.
LIBRARY_TYPES = ("Textbook", "Reading", "Article")

#: Which fields each material type actually needs, and what to call them.
#:
#: The form used to show the same nine boxes whatever you were adding, so a
#: website asked for an ISBN and an edition, and a piece of software asked for
#: an author. The database columns are unchanged — this only decides which are
#: shown and how they are labelled, so existing rows keep their meaning.
#:
#: ``(column, label)`` per type; ``title`` and ``material_type`` are always
#: present and are not repeated here.
TYPE_FIELDS = {
    "Syllabus":  [("url", "URL / File path:"), ("notes", "Notes:")],
    "Textbook":  [("author", "Author:"), ("isbn", "ISBN:"), ("edition", "Edition:"),
                  ("cost", "Cost:"), ("url", "URL / File path:"), ("notes", "Notes:")],
    "Reading":   [("author", "Author:"), ("isbn", "ISBN (optional):"),
                  ("url", "URL / File path:"), ("notes", "Notes:")],
    "Article":   [("author", "Author:"), ("isbn", "DOI / ISBN:"),
                  ("url", "URL:"), ("notes", "Notes:")],
    "Software":  [("author", "Vendor:"), ("edition", "Version:"),
                  ("url", "Download / licence URL:"), ("cost", "Licence cost:"),
                  ("notes", "Notes:")],
    "Equipment": [("author", "Supplier:"), ("edition", "Model:"),
                  ("cost", "Cost:"), ("notes", "Notes:")],
    "Website":   [("url", "URL:"), ("notes", "Notes:")],
    "Other":     [("author", "Author / Supplier:"), ("url", "URL / File path:"),
                  ("cost", "Cost:"), ("notes", "Notes:")],
}


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
            ttk.Label(sel, text=_t('gui.academics.course_management_gui.core.materials_tab.labels.course', default="Course:")).pack(side=tk.LEFT, padx=5)
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
            ttk.Button(bar, text=_t('gui.academics.course_management_gui.core.materials_tab.buttons.open_link_file', default="Open Link / File"),
                       command=self._open_material).pack(side=tk.LEFT, padx=5)
            # Cross-link: textbooks / reading lists here live in the Library
            # catalogue — jump to the Library to manage holdings and loans.
            ttk.Button(bar, text=_("course_management.buttons.open_library",
                                   default="Open Library →"),
                       command=self._open_library).pack(side=tk.RIGHT, padx=5)
            # No "Add to Library" button: a Textbook / Reading / Article is
            # pushed to the catalogue and this course's reading list as part
            # of saving it (see _sync_material_to_library), so there is no
            # second step to remember.

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
            from education_system.systems.university.domains.academics.interfaces.gui.library import (
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

    def _sync_material_to_library(self, conn, mat, course):
        """Mirror a Textbook / Reading / Article into the Library.

        Called as part of saving the material, so the catalogue and the
        course reading list keep up on their own — this used to be a separate
        "Add selected to Library" button that had to be remembered, and a
        textbook nobody pressed it for simply never reached the Library.

        Takes the caller's open connection so the material and its catalogue
        entry are written in one transaction. Returns a short status list, or
        ``[]`` when the type does not belong in the Library.
        """
        if str(mat.get("type")) not in LIBRARY_TYPES:
            return []
        try:
            import uuid
            if True:
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
            # A material is still a valid material even if the Library push
            # fails, so this reports rather than aborting the save.
            logger.warning("Library sync failed for %r: %s", mat.get("title"), exc)
            return [f"Library: not updated ({exc})"]
        self._ext_audit("add_to_library", "material", course_code=course,
                        title=mat.get("title"))
        parts = ["Library catalogue: " + ("added" if created_book else "already present")]
        if course:
            parts.append("Reading list: " + ("linked" if added_to_list else "already linked"))
        return parts

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

    def _material_fields(self, data=None, material_type=None):
        """Form fields for *material_type*, defaulting to the row's own type.

        Only the fields that type actually uses are shown, with labels that
        suit it — "Vendor" and "Version" for software rather than "Author"
        and "Edition". Every type still writes the same columns, so nothing
        about existing rows changes.
        """
        data = data or {}
        mtype = material_type or data.get("material_type") or "Textbook"
        fields = [
            ("material_type", "Type:", {"type": "combo", "values": MATERIAL_TYPES,
                                        "default": mtype}),
            ("title", "Title:", {"default": data.get("title", "")}),
        ]
        widths = {"edition": 20, "cost": 12, "isbn": 28}
        for column, label in TYPE_FIELDS.get(mtype, TYPE_FIELDS["Other"]):
            spec = {"default": data.get(column, "0.0" if column == "cost" else "")}
            if column in widths:
                spec["width"] = widths[column]
            if column == "notes":
                spec = {"type": "text", "default": data.get("notes", ""), "height": 3}
            fields.append((column, label, spec))
        fields.append(("required", "Required", {"type": "check",
                                                "default": data.get("required", True)}))
        return fields

    def _material_dialog(self, title, data, submit, submit_label):
        """Material form that rebuilds itself when the Type changes.

        ExtFormDialog builds a fixed field list, so switching type has to
        reopen the form. Values already typed are carried across, so changing
        your mind about the type does not lose the title you just entered.
        """
        state = dict(data or {})

        def _open(mtype):
            fields = self._material_fields(state, material_type=mtype)

            def _submit(values):
                # Type changed in the combo: carry the entries over and
                # reopen with the right fields rather than saving a form
                # whose boxes no longer match the type.
                if values.get("material_type") != mtype:
                    state.update({k: v for k, v in values.items()
                                  if k != "material_type"})
                    state["material_type"] = values["material_type"]
                    self.root.after(0, lambda t=values["material_type"]: _open(t))
                    return True
                return submit(values)

            ExtFormDialog(self.root, self, title, fields, _submit,
                          submit_label=submit_label, geometry="560x520")

        _open(state.get("material_type") or "Textbook")

    def _parse_cost(self, values):
        try:
            cost = float(values.get("cost") or 0)
        except (TypeError, ValueError):
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 _t('gui.academics.course_management_gui.core.materials_tab.dialogs.cost_must_be_a_number', default="Cost must be a number."))
            return None
        if cost < 0:
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 _t('gui.academics.course_management_gui.core.materials_tab.dialogs.cost_cannot_be_negative', default="Cost cannot be negative."))
            return None
        return cost

    def _add_material(self):
        if not self._ext_can_edit():
            return
        code = self._current_mat_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   _t('gui.academics.course_management_gui.core.materials_tab.dialogs.select_a_course_first', default="Select a course first."))
            return

        def submit(values):
            title = (values.get("title") or "").strip()
            if not title:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     _t('gui.academics.course_management_gui.core.materials_tab.dialogs.title_is_required', default="Title is required."))
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
                        (code, values["material_type"], title,
                         values.get("author", ""), values.get("isbn", ""),
                         values.get("edition", ""), values.get("url", ""), cost,
                         1 if values.get("required") else 0,
                         values.get("notes", ""),
                         self._ext_now(), self._ext_now()))
                    # Textbooks and reading go to the Library as part of the
                    # same save, in the same transaction.
                    library = self._sync_material_to_library(
                        conn,
                        {"type": values["material_type"], "title": title,
                         "author": values.get("author", ""),
                         "isbn": values.get("isbn", ""),
                         "edition": values.get("edition", ""), "cost": cost},
                        code)
            except Exception as exc:
                self._ext_report_error("add material", exc)
                return False
            self._ext_audit("create", "course_material", course_code=code, title=title)
            self._reload_materials()
            if library:
                messagebox.showinfo(_("common.success", default="Done"),
                                    "Material added.\n\n" + "\n".join(library))
            return True

        self._material_dialog(f"Add Material for {code}", None, submit, "Add")

    def _selected_material(self):
        vals = self._ext_selected_values(self._materials_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   _t('gui.academics.course_management_gui.core.materials_tab.dialogs.select_a_material_first', default="Select a material first."))
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
            messagebox.showerror(_("common.error", default="Error"), _t('gui.academics.course_management_gui.core.materials_tab.dialogs.material_not_found', default="Material not found."))
            return
        data = {"material_type": row[0], "title": row[1], "author": row[2],
                "isbn": row[3], "edition": row[4], "url": row[5],
                "cost": row[6], "required": bool(row[7]), "notes": row[8]}

        def submit(values):
            title = (values.get("title") or "").strip()
            if not title:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     _t('gui.academics.course_management_gui.core.materials_tab.dialogs.title_is_required', default="Title is required."))
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
                        (values["material_type"], title, values.get("author", ""),
                         values.get("isbn", ""), values.get("edition", ""),
                         values.get("url", ""), cost,
                         1 if values.get("required") else 0,
                         values.get("notes", ""), self._ext_now(), mat_id))
                    library = self._sync_material_to_library(
                        conn,
                        {"type": values["material_type"], "title": title,
                         "author": values.get("author", ""),
                         "isbn": values.get("isbn", ""),
                         "edition": values.get("edition", ""), "cost": cost},
                        self._current_mat_course())
            except Exception as exc:
                self._ext_report_error("update material", exc)
                return False
            self._ext_audit("update", "course_material", material_id=mat_id)
            self._reload_materials()
            if library:
                messagebox.showinfo(_("common.success", default="Done"),
                                    "Material updated.\n\n" + "\n".join(library))
            return True

        self._material_dialog("Edit Material", data, submit, "Save")

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
                                _t('gui.academics.course_management_gui.core.materials_tab.dialogs.this_material_has_no_url_or_file_path', default="This material has no URL or file path."))
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
