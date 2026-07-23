"""Feature 8 — Cross-listing & equivalency mapping.

Lets staff declare relationships between courses that the catalog otherwise
can't express:

* **Cross-listed** – the same class offered under two department codes.
* **Equivalent** – courses that count as each other for degree audit.
* **Transfer Equivalent** – an external/transfer course that satisfies this one.

Links are stored reciprocally-aware: when you cross-list A↔B, both directions
are written so each course shows the relationship.
"""

from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.ext_common import (
    ExtFormDialog, tk, ttk, messagebox, _, logger,
)

RELATION_TYPES = ["Cross-listed", "Equivalent", "Transfer Equivalent"]
# Relationships that are symmetric and should be written in both directions.
_SYMMETRIC = {"Cross-listed", "Equivalent"}


class CrosslistingTabMixin:
    """Cross-listing & equivalency tab."""

    def create_crosslisting_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.crosslisting",
                                            default="Cross-listing"))

            sel = ttk.LabelFrame(frame, text=_("course_management.labels.select_course",
                                               default="Select Course"), padding=10)
            sel.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(sel, text="Course:").pack(side=tk.LEFT, padx=5)
            self._xl_course_combo = ttk.Combobox(sel, width=50, state="readonly")
            self._xl_course_combo.pack(side=tk.LEFT, padx=5)
            self._xl_course_combo.bind("<<ComboboxSelected>>", self._reload_crosslistings)
            ttk.Button(sel, text=_("common.refresh", default="Refresh"),
                       command=self._reload_xl_courses).pack(side=tk.LEFT, padx=5)

            bar = ttk.Frame(frame)
            bar.pack(fill=tk.X, padx=5, pady=5)
            if self._ext_can_edit():
                ttk.Button(bar, text="Add Link",
                           command=self._add_crosslisting).pack(side=tk.LEFT, padx=5)
                ttk.Button(bar, text=_("common.delete", default="Remove"),
                           command=self._delete_crosslisting).pack(side=tk.LEFT, padx=5)

            list_frame = ttk.Frame(frame)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            cols = ("ID", "Related Course", "Relation", "Notes")
            self._xl_tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                         height=16)
            for c, w in (("ID", 45), ("Related Course", 180), ("Relation", 150),
                         ("Notes", 360)):
                self._xl_tree.heading(c, text=c)
                self._xl_tree.column(c, width=w)
            sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._xl_tree.yview)
            self._xl_tree.configure(yscrollcommand=sb.set)
            self._xl_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

            self._reload_xl_courses()
        except Exception as exc:
            self._ext_report_error("build Cross-listing tab", exc)

    def _reload_xl_courses(self):
        try:
            labels, self._xl_course_map = self._ext_course_choices()
            self._xl_course_combo["values"] = labels
            if labels and not self._xl_course_combo.get():
                self._xl_course_combo.current(0)
            self._reload_crosslistings()
        except Exception as exc:
            self._ext_report_error("load courses", exc)

    def _current_xl_course(self):
        return self._ext_code_from_label(self._xl_course_combo.get(),
                                         getattr(self, "_xl_course_map", {}))

    def _reload_crosslistings(self, *_a):
        if not hasattr(self, "_xl_tree"):
            return
        self._ext_clear_tree(self._xl_tree)
        code = self._current_xl_course()
        if not code:
            return
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, related_code, relation_type, notes "
                    "FROM course_crosslistings WHERE course_code=? "
                    "ORDER BY relation_type, related_code", (code,))
                rows = cur.fetchall()
            for row in rows:
                self._xl_tree.insert("", tk.END, values=row)
            logger.debug("Loaded %d cross-listings for %s", len(rows), code)
        except Exception as exc:
            self._ext_report_error("load cross-listings", exc)

    def _add_crosslisting(self):
        if not self._ext_can_edit():
            return
        code = self._current_xl_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return
        labels, course_map = self._ext_course_choices()
        labels = [l for l in labels
                  if self._ext_code_from_label(l, course_map) != code]

        def submit(values):
            related = self._ext_code_from_label(values.get("related"), course_map)
            if not related:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Select a related course.")
                return False
            rtype = values.get("relation_type")
            notes = values.get("notes", "")
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO course_crosslistings "
                        "(course_code, related_code, relation_type, notes, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (code, related, rtype, notes, self._ext_now()))
                    # Mirror symmetric relationships so both courses show it.
                    if rtype in _SYMMETRIC:
                        conn.execute(
                            "INSERT OR IGNORE INTO course_crosslistings "
                            "(course_code, related_code, relation_type, notes, created_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (related, code, rtype, notes, self._ext_now()))
            except Exception as exc:
                self._ext_report_error("add cross-listing", exc)
                return False
            self._ext_audit("create", "course_crosslisting", course_code=code,
                            related=related, relation=rtype)
            self._ext_notify_course_changed(code, "crosslisting_added")
            self._reload_crosslistings()
            return True

        ExtFormDialog(
            self.root, self, f"Link a course to {code}",
            [("related", "Related course:", {"type": "combo", "values": labels,
                                             "width": 43}),
             ("relation_type", "Relation:", {"type": "combo",
                                             "values": RELATION_TYPES,
                                             "default": "Cross-listed"}),
             ("notes", "Notes:", {"type": "text", "height": 3})],
            submit, submit_label="Add", geometry="520x300")

    def _delete_crosslisting(self):
        if not self._ext_can_edit():
            return
        vals = self._ext_selected_values(self._xl_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a link to remove.")
            return
        code = self._current_xl_course()
        link_id, related, rtype = vals[0], vals[1], vals[2]
        if not messagebox.askyesno(_("common.confirm", default="Confirm"),
                                   f"Remove {rtype} link to '{related}'?"):
            return
        try:
            with self._ext_db(write=True) as conn:
                conn.execute("DELETE FROM course_crosslistings WHERE id=?", (link_id,))
                # Remove the mirrored row too for symmetric relations.
                if rtype in _SYMMETRIC and code:
                    conn.execute(
                        "DELETE FROM course_crosslistings "
                        "WHERE course_code=? AND related_code=? AND relation_type=?",
                        (related, code, rtype))
        except Exception as exc:
            self._ext_report_error("remove cross-listing", exc)
            return
        self._ext_audit("delete", "course_crosslisting", link_id=link_id)
        self._reload_crosslistings()
