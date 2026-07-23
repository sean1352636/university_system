"""Feature 7 — Term rollover / clone.

Setting up a new term means re-creating each course section by hand. This tab
copies every section (and its meeting times) from a *source* term into a
*target* term in one action, optionally resetting enrolment and carrying
meeting times forward — the common registrar "roll the term forward" task.
"""

from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.ext_common import (
    tk, ttk, messagebox, _, logger,
)


class RolloverTabMixin:
    """Clone an entire term's sections into another term."""

    def create_rollover_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.rollover",
                                            default="Term Rollover"))

            if not self._ext_can_edit():
                ttk.Label(frame, text="Term rollover is available to staff and "
                                      "administrators only.",
                          font=("Arial", 11), foreground="#6b7280").pack(pady=40)
                return

            ctl = ttk.LabelFrame(frame, text="Roll sections forward", padding=12)
            ctl.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(ctl, text="Copy FROM term:").grid(row=0, column=0, sticky=tk.W,
                                                        padx=5, pady=6)
            self._ro_src = ttk.Combobox(ctl, width=34, state="readonly")
            self._ro_src.grid(row=0, column=1, padx=5, pady=6)
            self._ro_src.bind("<<ComboboxSelected>>", self._refresh_rollover_preview)

            ttk.Label(ctl, text="Copy TO term:").grid(row=1, column=0, sticky=tk.W,
                                                      padx=5, pady=6)
            self._ro_dst = ttk.Combobox(ctl, width=34, state="readonly")
            self._ro_dst.grid(row=1, column=1, padx=5, pady=6)

            self._ro_reset_enrol = tk.BooleanVar(value=True)
            ttk.Checkbutton(ctl, text="Reset enrolment to 0 in copies",
                            variable=self._ro_reset_enrol).grid(
                row=2, column=1, sticky=tk.W, padx=5)
            self._ro_copy_meetings = tk.BooleanVar(value=True)
            ttk.Checkbutton(ctl, text="Copy meeting times too",
                            variable=self._ro_copy_meetings).grid(
                row=3, column=1, sticky=tk.W, padx=5)
            self._ro_skip_existing = tk.BooleanVar(value=True)
            ttk.Checkbutton(ctl, text="Skip sections that already exist in target",
                            variable=self._ro_skip_existing).grid(
                row=4, column=1, sticky=tk.W, padx=5)

            ttk.Button(ctl, text="Refresh", command=self._reload_rollover_terms).grid(
                row=0, column=2, padx=10)
            ttk.Button(ctl, text="Run Rollover", command=self._run_rollover).grid(
                row=1, column=2, padx=10)

            prev = ttk.LabelFrame(frame, text="Preview (sections in source term)",
                                  padding=8)
            prev.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            cols = ("Course", "Section", "Instructor", "Cap", "Mode", "Status")
            self._ro_tree = ttk.Treeview(prev, columns=cols, show="headings", height=12)
            for c, w in (("Course", 100), ("Section", 80), ("Instructor", 160),
                         ("Cap", 60), ("Mode", 100), ("Status", 90)):
                self._ro_tree.heading(c, text=c)
                self._ro_tree.column(c, width=w)
            sb = ttk.Scrollbar(prev, orient=tk.VERTICAL, command=self._ro_tree.yview)
            self._ro_tree.configure(yscrollcommand=sb.set)
            self._ro_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

            self._reload_rollover_terms()
        except Exception as exc:
            self._ext_report_error("build Term Rollover tab", exc)

    def _reload_rollover_terms(self):
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM academic_terms "
                            "ORDER BY academic_year DESC, name")
                rows = cur.fetchall()
            self._ro_term_map = {name: tid for tid, name in rows}
            names = list(self._ro_term_map.keys())
            self._ro_src["values"] = names
            self._ro_dst["values"] = names
            self._refresh_rollover_preview()
        except Exception as exc:
            self._ext_report_error("load terms for rollover", exc)

    def _refresh_rollover_preview(self, *_a):
        if not hasattr(self, "_ro_tree"):
            return
        self._ext_clear_tree(self._ro_tree)
        src_id = getattr(self, "_ro_term_map", {}).get(self._ro_src.get())
        if src_id is None:
            return
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT course_code, section_number, instructor, capacity, "
                    "delivery_mode, status FROM course_sections "
                    "WHERE term_id=? ORDER BY course_code, section_number", (src_id,))
                rows = cur.fetchall()
            for row in rows:
                self._ro_tree.insert("", tk.END, values=row)
        except Exception as exc:
            self._ext_report_error("preview rollover", exc)

    def _run_rollover(self):
        if not self._ext_can_edit():
            return
        src_name, dst_name = self._ro_src.get(), self._ro_dst.get()
        src_id = getattr(self, "_ro_term_map", {}).get(src_name)
        dst_id = self._ro_term_map.get(dst_name) if hasattr(self, "_ro_term_map") else None
        if src_id is None or dst_id is None:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Choose both a source and a target term.")
            return
        if src_id == dst_id:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Source and target term must differ.")
            return
        if not messagebox.askyesno(
                _("common.confirm", default="Confirm"),
                f"Copy all sections from '{src_name}' into '{dst_name}'?"):
            return

        reset = self._ro_reset_enrol.get()
        copy_meetings = self._ro_copy_meetings.get()
        skip_existing = self._ro_skip_existing.get()
        copied = skipped = meetings_copied = 0
        try:
            with self._ext_db(write=True) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, course_code, section_number, instructor, capacity, "
                    "enrolled, delivery_mode, location, status, notes "
                    "FROM course_sections WHERE term_id=?", (src_id,))
                source_rows = cur.fetchall()

                for row in source_rows:
                    (old_id, code, sec, instructor, cap, enrolled, mode,
                     location, status, notes) = row
                    if skip_existing:
                        cur.execute(
                            "SELECT 1 FROM course_sections "
                            "WHERE course_code=? AND term_id=? AND section_number=?",
                            (code, dst_id, sec))
                        if cur.fetchone():
                            skipped += 1
                            continue
                    try:
                        cur.execute(
                            "INSERT INTO course_sections "
                            "(course_code, term_id, section_number, instructor, "
                            " capacity, enrolled, delivery_mode, location, status, "
                            " notes, created_at, updated_at) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (code, dst_id, sec, instructor, cap,
                             0 if reset else enrolled, mode, location, status, notes,
                             self._ext_now(), self._ext_now()))
                    except Exception:
                        # UNIQUE clash when skip_existing is off — count + skip.
                        logger.exception("Rollover insert failed for %s %s", code, sec)
                        skipped += 1
                        continue
                    new_id = cur.lastrowid
                    copied += 1
                    if copy_meetings:
                        cur.execute(
                            "SELECT day_of_week, start_time, end_time, location "
                            "FROM section_meetings WHERE section_id=?", (old_id,))
                        for day, start, end, loc in cur.fetchall():
                            cur.execute(
                                "INSERT INTO section_meetings "
                                "(section_id, day_of_week, start_time, end_time, "
                                " location, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                (new_id, day, start, end, loc, self._ext_now()))
                            meetings_copied += 1
        except Exception as exc:
            self._ext_report_error("run term rollover", exc)
            return

        self._ext_audit("rollover", "course_section", source_term=src_id,
                        target_term=dst_id, copied=copied, skipped=skipped)
        msg = (f"Rollover complete.\n\nSections copied: {copied}\n"
               f"Skipped (already existed): {skipped}\n"
               f"Meeting times copied: {meetings_copied}")
        messagebox.showinfo(_("common.success", default="Success"), msg)
        self.update_status(_("course_management.status.rollover_done",
                             default="Rollover: {c} copied, {s} skipped.").format(
                               c=copied, s=skipped))
        # Refresh sibling views if present.
        for fn in ("_reload_sections", "_reload_timetable"):
            cb = getattr(self, fn, None)
            if cb:
                try:
                    cb()
                except Exception:
                    logger.debug("Post-rollover refresh %s failed", fn, exc_info=True)
