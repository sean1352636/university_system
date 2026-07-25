"""Course ⇄ Module Links — admin panel for the scheduling bridge.

The university runs two parallel scheduling models (section-based course
management vs module-based module scheduling). The ``course_module_map`` table
(see ``services.timetable_bridge``) reconciles them so a student's "My
Timetable" can surface section meetings and either scheduler can warn about the
other's room clashes.

This tab lets staff view and curate those links: identity links (where a
course_code equals a module_code) are auto-seeded, and non-identity links can be
added/removed here.
"""

from education_system.systems.university.interfaces.gui.academics.course_management_gui.core.ext_common import (
    tk, ttk, messagebox, _, logger,
)
from education_system.systems.university.domain.academics.services import (
    timetable_bridge as _bridge,
)


class CourseModuleLinksTabMixin:
    """Tab to manage the course_code ↔ module_code mapping."""

    def create_course_module_links_tab(self):
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.course_module_links",
                                            default="Course ⇄ Module Links"))

            ttk.Label(
                frame,
                text=_("course_management.labels.course_module_links_intro",
                       default="Links let a student's timetable show section meetings "
                               "and let both schedulers warn about shared-room clashes.\n"
                               "Identity matches (same code) are linked automatically."),
                justify=tk.LEFT, foreground="#555",
            ).pack(fill=tk.X, padx=8, pady=(8, 4))

            can_edit = self._ext_can_edit() if hasattr(self, "_ext_can_edit") else True

            # ── Add-link row ──
            if can_edit:
                add = ttk.LabelFrame(frame, text=_("common.add", default="Add link"),
                                     padding=8)
                add.pack(fill=tk.X, padx=8, pady=4)
                ttk.Label(add, text="Course:").pack(side=tk.LEFT, padx=4)
                self._cml_course = ttk.Combobox(add, width=28, state="readonly")
                self._cml_course.pack(side=tk.LEFT, padx=4)
                ttk.Label(add, text="Module:").pack(side=tk.LEFT, padx=4)
                self._cml_module = ttk.Combobox(add, width=28, state="readonly")
                self._cml_module.pack(side=tk.LEFT, padx=4)
                ttk.Button(add, text=_("common.add", default="Add"),
                           command=self._cml_add_link).pack(side=tk.LEFT, padx=6)

            # ── Links table ──
            table = ttk.LabelFrame(frame, text=_("common.existing", default="Existing links"),
                                   padding=6)
            table.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
            cols = ("course", "module", "source")
            self._cml_tree = ttk.Treeview(table, columns=cols, show="headings", height=14)
            for c, txt, w in (("course", "Course code", 200),
                              ("module", "Module code", 200),
                              ("source", "Link source", 120)):
                self._cml_tree.heading(c, text=txt)
                self._cml_tree.column(c, width=w, anchor="w")
            self._cml_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self._cml_tree.yview)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            self._cml_tree.configure(yscrollcommand=sb.set)

            # ── Action buttons ──
            btns = ttk.Frame(frame, padding=8)
            btns.pack(fill=tk.X)
            ttk.Button(btns, text=_("common.refresh", default="Refresh"),
                       command=self._cml_reload).pack(side=tk.LEFT, padx=4)
            if can_edit:
                ttk.Button(btns, text=_("common.delete", default="Remove selected"),
                           command=self._cml_remove_link).pack(side=tk.LEFT, padx=4)
                ttk.Button(btns, text=_("course_management.buttons.auto_link",
                                        default="Auto-link matching codes"),
                           command=self._cml_auto_link).pack(side=tk.LEFT, padx=4)

            self._cml_reload()
        except Exception:
            logger.exception("Failed to build Course ⇄ Module Links tab")

    # ------------------------------------------------------------------
    def _cml_reload(self):
        """Refresh the links table and the course/module pickers."""
        try:
            for item in self._cml_tree.get_children():
                self._cml_tree.delete(item)
            for link in _bridge.list_links():
                self._cml_tree.insert("", tk.END, values=(
                    link["course_code"], link["module_code"], link["link_source"]))
        except Exception as exc:
            self._cml_report("load links", exc)

        # Populate pickers from the catalogues (best-effort).
        try:
            if hasattr(self, "_cml_course"):
                with self._ext_db() as conn:
                    courses = [r[0] for r in conn.execute(
                        "SELECT course_code FROM courses ORDER BY course_code").fetchall()]
                    modules = [r[0] for r in conn.execute(
                        "SELECT module_code FROM modules ORDER BY module_code").fetchall()]
                self._cml_course["values"] = courses
                self._cml_module["values"] = modules
        except Exception:
            logger.debug("Could not populate course/module pickers", exc_info=True)

    def _cml_add_link(self):
        course = (self._cml_course.get() or "").strip()
        module = (self._cml_module.get() or "").strip()
        if not course or not module:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Pick both a course and a module.")
            return
        if _bridge.link_course_module(course, module):
            self._cml_reload()
        else:
            messagebox.showerror(_("common.error", default="Error"),
                                 "Could not save the link.")

    def _cml_remove_link(self):
        sel = self._cml_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a link to remove.")
            return
        course, module, source = self._cml_tree.item(sel[0])["values"]
        if not messagebox.askyesno(_("common.confirm", default="Confirm"),
                                   f"Remove link {course} ⇄ {module}?"):
            return
        if _bridge.unlink_course_module(str(course), str(module)):
            self._cml_reload()

    def _cml_auto_link(self):
        try:
            from education_system.systems.university.infrastructure.database.db import (
                get_connection,
            )
            conn = get_connection()
            try:
                _bridge.ensure_bridge_schema(conn)
                n = _bridge.auto_link_matching_codes(conn)
            finally:
                conn.close()
            messagebox.showinfo(_("common.info", default="Done"),
                                f"Added {n} new identity link(s).")
            self._cml_reload()
        except Exception as exc:
            self._cml_report("auto-link", exc)

    def _cml_report(self, ctx, exc):
        if hasattr(self, "_ext_report_error"):
            self._ext_report_error(ctx, exc)
        else:
            logger.exception("Course-module links: %s failed", ctx)
            messagebox.showerror(_("common.error", default="Error"), str(exc))
