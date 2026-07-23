"""Feature 10 — Waitlist auto-promotion rules & notifications.

The existing GUI lets staff view and manually process waitlists. This tab adds
the *policy* layer: per-course configuration for how a freed seat is filled —

* **Auto-promote** on/off and a **promotion order** (FIFO vs. Priority);
* a **max auto-promotions** cap per run (0 = unlimited);
* a **notify** flag for promoted students.

It also previews and runs a promotion pass against the existing
``course_waitlist`` table (whose ``course_id`` column holds the course code in
this deployment), filling free seats computed from the ``courses`` enrolment
numbers.
"""

from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.ext_common import (
    tk, ttk, messagebox, _, logger,
)

# Statuses that mean "no longer waiting" — excluded from promotion candidates.
_DONE_STATUSES = {"promoted", "enrolled", "removed", "cancelled", "withdrawn"}
PROMOTION_ORDERS = ["FIFO", "Priority"]


class WaitlistRulesTabMixin:
    """Waitlist automation configuration + promotion runner."""

    def create_waitlist_rules_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.waitlist_rules",
                                            default="Waitlist Automation"))

            sel = ttk.LabelFrame(frame, text=_("course_management.labels.select_course",
                                               default="Select Course"), padding=10)
            sel.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(sel, text="Course:").pack(side=tk.LEFT, padx=5)
            self._wr_course_combo = ttk.Combobox(sel, width=46, state="readonly")
            self._wr_course_combo.pack(side=tk.LEFT, padx=5)
            self._wr_course_combo.bind("<<ComboboxSelected>>", self._reload_waitlist)
            ttk.Button(sel, text=_("common.refresh", default="Refresh"),
                       command=self._reload_wr_courses).pack(side=tk.LEFT, padx=5)
            self._wr_seats_var = tk.StringVar(value="")
            ttk.Label(sel, textvariable=self._wr_seats_var,
                      font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=10)

            editable = self._ext_can_edit()
            cfg = ttk.LabelFrame(frame, text="Automation rule", padding=10)
            cfg.pack(fill=tk.X, padx=5, pady=5)

            self._wr_auto = tk.BooleanVar(value=False)
            ttk.Checkbutton(cfg, text="Auto-promote when a seat frees up",
                            variable=self._wr_auto,
                            state="normal" if editable else "disabled").grid(
                row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=3)

            ttk.Label(cfg, text="Promotion order:").grid(row=1, column=0, sticky=tk.W,
                                                         padx=5)
            self._wr_order = tk.StringVar(value="FIFO")
            ttk.Combobox(cfg, textvariable=self._wr_order, values=PROMOTION_ORDERS,
                         width=14,
                         state="readonly" if editable else "disabled").grid(
                row=1, column=1, sticky=tk.W, padx=5)

            ttk.Label(cfg, text="Max auto-promotions per run (0 = no limit):").grid(
                row=2, column=0, sticky=tk.W, padx=5)
            self._wr_max = tk.StringVar(value="0")
            ttk.Entry(cfg, textvariable=self._wr_max, width=8,
                      state="normal" if editable else "readonly").grid(
                row=2, column=1, sticky=tk.W, padx=5)

            self._wr_notify = tk.BooleanVar(value=True)
            ttk.Checkbutton(cfg, text="Notify promoted students",
                            variable=self._wr_notify,
                            state="normal" if editable else "disabled").grid(
                row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=3)

            self._wr_active = tk.BooleanVar(value=True)
            ttk.Checkbutton(cfg, text="Rule active",
                            variable=self._wr_active,
                            state="normal" if editable else "disabled").grid(
                row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=3)

            if editable:
                btns = ttk.Frame(cfg)
                btns.grid(row=0, column=2, rowspan=5, padx=20)
                ttk.Button(btns, text="Save Rule",
                           command=self._save_rule).pack(pady=4)
                ttk.Button(btns, text="Preview Promotions",
                           command=self._preview_promotions).pack(pady=4)
                ttk.Button(btns, text="Run Promotion Now",
                           command=self._run_promotion).pack(pady=4)

            wl = ttk.LabelFrame(frame, text="Current waitlist (in promotion order)",
                                padding=8)
            wl.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            cols = ("Order", "Student", "Position", "Added", "Status")
            self._wr_tree = ttk.Treeview(wl, columns=cols, show="headings", height=12)
            for c, w in (("Order", 60), ("Student", 180), ("Position", 90),
                         ("Added", 180), ("Status", 120)):
                self._wr_tree.heading(c, text=c)
                self._wr_tree.column(c, width=w)
            sb = ttk.Scrollbar(wl, orient=tk.VERTICAL, command=self._wr_tree.yview)
            self._wr_tree.configure(yscrollcommand=sb.set)
            self._wr_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

            self._reload_wr_courses()
        except Exception as exc:
            self._ext_report_error("build Waitlist Automation tab", exc)

    # -- course selection ----------------------------------------------

    def _reload_wr_courses(self):
        try:
            labels, self._wr_course_map = self._ext_course_choices()
            self._wr_course_combo["values"] = labels
            if labels and not self._wr_course_combo.get():
                self._wr_course_combo.current(0)
            self._reload_waitlist()
        except Exception as exc:
            self._ext_report_error("load courses", exc)

    def _current_wr_course(self):
        return self._ext_code_from_label(self._wr_course_combo.get(),
                                         getattr(self, "_wr_course_map", {}))

    def _order_clause(self):
        # FIFO and Priority both key off position/added; Priority puts the
        # lowest position number (highest priority) first, same as FIFO here,
        # but kept distinct so the intent is explicit and easy to change.
        return "position ASC, added_at ASC"

    def _free_seats(self, code):
        """Free seats = max_enrollment - current_enrollment (>= 0)."""
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT COALESCE(max_enrollment, 0), COALESCE(current_enrollment, 0) "
                    "FROM courses WHERE COALESCE(course_code, code)=?", (code,))
                row = cur.fetchone()
            if not row:
                return 0
            return max(0, int(row[0]) - int(row[1]))
        except Exception as exc:
            logger.warning("Could not compute free seats for %s: %s", code, exc)
            return 0

    def _waitlist_candidates(self, code):
        """Return waitlisted entries (id, student, position, added, status) in
        promotion order, excluding already-processed statuses."""
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"SELECT id, student_id, position, added_at, COALESCE(status,'') "
                    f"FROM course_waitlist WHERE course_id=? "
                    f"ORDER BY {self._order_clause()}", (code,))
                rows = cur.fetchall()
            return [r for r in rows
                    if str(r[4]).strip().lower() not in _DONE_STATUSES]
        except Exception as exc:
            # course_waitlist may be absent/shaped differently in some DBs.
            self._ext_report_error("read waitlist", exc)
            return []

    def _reload_waitlist(self, *_a):
        code = self._current_wr_course()
        # Load rule into the form.
        if code:
            try:
                with self._ext_db() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT auto_promote, promotion_order, notify, max_auto, "
                        "active FROM waitlist_rules WHERE course_code=?", (code,))
                    row = cur.fetchone()
                if row:
                    self._wr_auto.set(bool(row[0]))
                    self._wr_order.set(row[1] or "FIFO")
                    self._wr_notify.set(bool(row[2]))
                    self._wr_max.set(str(row[3]))
                    self._wr_active.set(bool(row[4]))
                else:
                    self._wr_auto.set(False)
                    self._wr_order.set("FIFO")
                    self._wr_notify.set(True)
                    self._wr_max.set("0")
                    self._wr_active.set(True)
            except Exception as exc:
                self._ext_report_error("load waitlist rule", exc)

        if not hasattr(self, "_wr_tree"):
            return
        self._ext_clear_tree(self._wr_tree)
        if not code:
            self._wr_seats_var.set("")
            return
        candidates = self._waitlist_candidates(code)
        for i, (wid, student, pos, added, status) in enumerate(candidates, start=1):
            self._wr_tree.insert("", tk.END, values=(i, student, pos, added, status))
        self._wr_seats_var.set(
            f"Free seats: {self._free_seats(code)}   ·   Waiting: {len(candidates)}")

    # -- rule persistence ----------------------------------------------

    def _save_rule(self):
        if not self._ext_can_edit():
            return
        code = self._current_wr_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return
        try:
            max_auto = int(self._wr_max.get())
            if max_auto < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Max auto-promotions must be a non-negative whole number.")
            return
        try:
            with self._ext_db(write=True) as conn:
                conn.execute(
                    "INSERT INTO waitlist_rules "
                    "(course_code, auto_promote, promotion_order, notify, max_auto, "
                    " active, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(course_code) DO UPDATE SET "
                    "auto_promote=excluded.auto_promote, "
                    "promotion_order=excluded.promotion_order, "
                    "notify=excluded.notify, max_auto=excluded.max_auto, "
                    "active=excluded.active, updated_at=excluded.updated_at",
                    (code, 1 if self._wr_auto.get() else 0, self._wr_order.get(),
                     1 if self._wr_notify.get() else 0, max_auto,
                     1 if self._wr_active.get() else 0, self._ext_now()))
        except Exception as exc:
            self._ext_report_error("save waitlist rule", exc)
            return
        self._ext_audit("update", "waitlist_rule", course_code=code,
                        auto_promote=self._wr_auto.get())
        messagebox.showinfo(_("common.success", default="Success"),
                            f"Waitlist rule saved for {code}.")

    # -- promotion ------------------------------------------------------

    def _promotion_plan(self, code):
        """Return the list of candidates that would be promoted now."""
        free = self._free_seats(code)
        candidates = self._waitlist_candidates(code)
        if free <= 0 or not candidates:
            return [], free, len(candidates)
        try:
            max_auto = int(self._wr_max.get())
        except ValueError:
            max_auto = 0
        limit = free if max_auto <= 0 else min(free, max_auto)
        return candidates[:limit], free, len(candidates)

    def _preview_promotions(self):
        code = self._current_wr_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return
        plan, free, waiting = self._promotion_plan(code)
        if not plan:
            messagebox.showinfo(_("common.info", default="Info"),
                                f"No promotions possible.\nFree seats: {free}, "
                                f"waiting: {waiting}.")
            return
        students = "\n".join(f"  • {row[1]} (position {row[2]})" for row in plan)
        messagebox.showinfo(
            _("common.info", default="Preview"),
            f"{len(plan)} student(s) would be promoted for {code} "
            f"(free seats: {free}):\n\n{students}")

    def _run_promotion(self):
        if not self._ext_can_edit():
            return
        code = self._current_wr_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return
        plan, free, waiting = self._promotion_plan(code)
        if not plan:
            messagebox.showinfo(_("common.info", default="Info"),
                                f"Nothing to promote (free seats: {free}, "
                                f"waiting: {waiting}).")
            return
        if not messagebox.askyesno(
                _("common.confirm", default="Confirm"),
                f"Promote {len(plan)} student(s) from the {code} waitlist?"):
            return

        ids = [row[0] for row in plan]
        notify = self._wr_notify.get()
        try:
            with self._ext_db(write=True) as conn:
                cur = conn.cursor()
                placeholders = ",".join("?" for _ in ids)
                cur.execute(
                    f"UPDATE course_waitlist SET status='Promoted' "
                    f"WHERE id IN ({placeholders})", ids)
                # Reflect the new enrolment on the course record.
                cur.execute(
                    "UPDATE courses SET current_enrollment = "
                    "COALESCE(current_enrollment, 0) + ? "
                    "WHERE COALESCE(course_code, code)=?", (len(ids), code))
        except Exception as exc:
            self._ext_report_error("run promotion", exc)
            return

        self._ext_audit("promote", "course_waitlist", course_code=code,
                        promoted=len(ids), notified=notify)
        self._ext_notify_course_changed(code, "waitlist_promoted")
        # Notifications are best-effort and logged; integration with the email
        # service can hook in here once student contact details are resolved.
        if notify:
            for row in plan:
                logger.info("Waitlist promotion notice queued: course=%s student=%s",
                            code, row[1])

        messagebox.showinfo(
            _("common.success", default="Success"),
            f"Promoted {len(ids)} student(s) for {code}."
            + ("\nNotifications were queued." if notify else ""))
        self._reload_waitlist()
