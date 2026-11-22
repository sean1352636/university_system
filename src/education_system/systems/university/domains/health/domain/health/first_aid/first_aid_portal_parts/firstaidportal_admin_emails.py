"""Methods _admin_emails through _is_staff."""

from .. import first_aid_portal_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class FirstAidPortal:
    def _admin_emails(self):
        """Return the list of admin email addresses from the ``users``
        table (empty list if none / DB unavailable)."""
        try:
            from education_system.systems.university.domains.health.infrastructure.health.storage import (
                get_connection,
            )
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT email FROM users "
                    "WHERE role = 'admin' "
                    "  AND email IS NOT NULL AND email != ''"
                ).fetchall()
            return [str(r[0]).strip() for r in rows if r and r[0]]
        except Exception:
            logger.debug("Could not load admin emails", exc_info=True)
            return []

    def _send_template_email(self, recipient, template, variables):
        """Render a JSON template and queue it to ``recipient``.

        Best-effort — logs and returns False on any failure so the
        calling flow (incident submit / course sign-up) is never blocked
        by email infrastructure."""
        if not recipient:
            return False
        try:
            from education_system.systems.university.infrastructure.email.template_utils import (
                render_template,
            )
            subject, body = render_template(template, variables)
            if not (subject and body):
                logger.warning("Empty render for template %s -> %s",
                               template, recipient)
                return False
        except Exception:
            logger.exception("Failed to render template %s", template)
            return False
        try:
            from education_system.systems.university.infrastructure.utils.email_service import (
                queue_email,
            )
            ok = bool(queue_email(recipient, subject, body))
            if ok:
                logger.info("Queued %s email to %s", template, recipient)
            else:
                logger.warning("queue_email returned falsy for %s -> %s",
                               template, recipient)
            return ok
        except Exception:
            logger.exception("Failed to queue %s email to %s",
                             template, recipient)
            return False

    def _create_footer(self):
        footer = tk.Frame(self.root, bg=self.colors["text"], height=30)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        tk.Label(
            footer,
            text="© 2025 University Health & Safety Department  |  For emergencies, always call 999  |  Urgent advice: NHS 111",
            font=("Segoe UI", 9),
            bg=self.colors["text"],
            fg="white",
        ).pack(pady=6)

    def _filter_conditions(self, *args):
        search = self.search_var.get().lower()
        self.condition_listbox.delete(0, "end")
        for condition in self.first_aid_data.keys():
            if search in condition.lower():
                self.condition_listbox.insert("end", condition)

    def _show_first_aid_instructions(self, event):
        selection = self.condition_listbox.curselection()
        if not selection:
            return
        condition = self.condition_listbox.get(selection[0])
        instructions = self.first_aid_data[condition]

        self.condition_title.config(text=f"🩹  {condition}")
        self.instructions_text.config(state="normal")
        self.instructions_text.delete("1.0", "end")
        self.instructions_text.insert("1.0", instructions)
        self.instructions_text.config(state="disabled")

    def _submit_report(self):
        name = self.form_vars["name"].get().strip()
        description = self.description_text.get("1.0", "end").strip()

        if not name or not description:
            messagebox.showwarning("Incomplete Form", "Please fill in at least your name and a description.")
            logger.warning("Incident submit blocked — missing name or description (user=%s)",
                           self.user_display)
            return

        report_id = self.form_vars["id"].get().strip()
        report_email = self.form_vars["email"].get().strip()
        report_phone = self.form_vars["phone"].get().strip()

        # Validate optional contact fields (only when filled in).
        if report_id and not _is_valid_id(report_id):
            messagebox.showwarning(
                "Invalid ID",
                "Student/Staff ID may only contain letters, numbers and "
                "hyphens.")
            return
        if report_email and not _is_valid_email(report_email):
            messagebox.showwarning(
                "Invalid Email",
                "Please enter a valid email address (or leave it blank).")
            return
        if report_phone and not _is_valid_phone(report_phone):
            messagebox.showwarning(
                "Invalid Phone Number",
                "Please enter a valid contact number with at least 7 "
                "digits (or leave it blank).")
            return

        report = {
            "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reporter_user": self.user_display if self.user else '',
            "reporter_name": name,
            "reporter_id": report_id,
            "phone": report_phone,
            "email": report_email,
            "location": self.form_vars["location"].get().strip(),
            "incident_type": self.form_vars["type"].get(),
            "severity": self.form_vars["severity"].get(),
            "description": description,
            "status": "Open",
        }

        if not self.db:
            messagebox.showerror(
                "Database Unavailable",
                "Cannot save the report — the central database is not "
                "reachable. Please contact IT support.")
            logger.error("Incident submit failed — DB unavailable (user=%s)",
                         self.user_display)
            return

        try:
            new_id = self.db.add(report)
        except sqlite3.Error:
            logger.exception("Incident submit failed — DB error (user=%s)",
                             self.user_display)
            messagebox.showerror("Save Error",
                                 "Could not save the incident report.")
            return

        logger.info("Incident submitted id=%s severity=%s type=%s reporter=%s",
                    new_id, report['severity'], report['incident_type'],
                    self.user_display)

        # Email integration: notify admins of the incident and send the
        # reporter a confirmation receipt. Best-effort — never blocks the
        # submit flow.
        reference = f"INC-{new_id:04d}"
        admin_vars = {
            "reference": reference,
            "incident_type": report["incident_type"],
            "severity": report["severity"],
            "location": report["location"] or "—",
            "submitted_at": report["submitted_at"],
            "reporter_name": report["reporter_name"],
            "reporter_id": report["reporter_id"] or "—",
            "reporter_user": report["reporter_user"] or "—",
            "phone": report["phone"] or "—",
            "description": report["description"],
        }
        admins = self._admin_emails()
        admins_notified = 0
        for admin_email in admins:
            if self._send_template_email(
                    admin_email, "health/first_aid_incident_report", dict(admin_vars)):
                admins_notified += 1

        reporter_email = report["email"] or self._resolve_user_email(
            report["reporter_id"])
        receipt_sent = False
        if reporter_email:
            receipt_sent = self._send_template_email(
                reporter_email, "health/first_aid_incident_receipt", {
                    "reporter_name": report["reporter_name"],
                    "reference": reference,
                    "incident_type": report["incident_type"],
                    "severity": report["severity"],
                    "location": report["location"] or "—",
                    "submitted_at": report["submitted_at"],
                    "description": report["description"],
                })

        if admins_notified:
            notify_line = (f"The Health & Safety team has been notified by "
                           f"email ({admins_notified} recipient"
                           f"{'s' if admins_notified != 1 else ''}).")
        else:
            notify_line = "A first aid officer will be notified."
        if receipt_sent:
            notify_line += f"\nA confirmation receipt was sent to {reporter_email}."

        messagebox.showinfo(
            "Report Submitted",
            f"✓ Incident report submitted successfully.\n\n"
            f"Reference: {reference}\n"
            f"Severity: {report['severity']}\n\n"
            f"{notify_line}",
        )
        self._clear_form()

    def _clear_form(self):
        for var in self.form_vars.values():
            if isinstance(var, tk.StringVar):
                var.set("")
        self.form_vars["type"].set("Minor Injury")
        self.form_vars["severity"].set("Low")
        self.description_text.delete("1.0", "end")

    def _view_incident_log(self):
        from education_system.systems.university.domains.health.application.health import (
            first_aid as _fa_rules,
        )
        log_window = tk.Toplevel(self.root)
        log_window.title("Incident Log")
        log_window.geometry("780x560")
        log_window.configure(bg=self.colors["bg"])

        tk.Label(
            log_window,
            text="📋 Incident Log",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack(pady=10)

        # Filter bar.
        bar = tk.Frame(log_window, bg=self.colors["bg"])
        bar.pack(fill="x", padx=15)
        tk.Label(bar, text="Severity:", font=("Segoe UI", 10, "bold"),
                 bg=self.colors["bg"], fg=self.colors["text"]).pack(side="left")
        sev_var = tk.StringVar(value="All")
        ttk.Combobox(bar, textvariable=sev_var, state="readonly", width=12,
                     values=["All", "Low", "Medium", "High", "Critical"]
                     ).pack(side="left", padx=(5, 15))
        tk.Label(bar, text="Status:", font=("Segoe UI", 10, "bold"),
                 bg=self.colors["bg"], fg=self.colors["text"]).pack(side="left")
        status_var = tk.StringVar(value="All")
        ttk.Combobox(bar, textvariable=status_var, state="readonly", width=12,
                     values=["All", "Open", "Resolved"]
                     ).pack(side="left", padx=5)
        # Archived incidents are hidden; the health team may show them.
        archived_var = tk.BooleanVar(value=False)
        if self._is_health_team():
            tk.Checkbutton(bar, text="Show archived", variable=archived_var,
                           bg=self.colors["bg"], fg=self.colors["text"],
                           command=lambda: _load()).pack(side="left", padx=(15, 0))

        log_text = scrolledtext.ScrolledText(log_window, font=("Consolas", 10), wrap="word")
        log_text.pack(fill="both", expand=True, padx=15, pady=10)

        # Holds the currently-displayed incidents so the action buttons can
        # operate on them.
        state = {"incidents": []}

        def _load():
            sev = None if sev_var.get() == "All" else sev_var.get()
            status = None if status_var.get() == "All" else status_var.get()
            incidents = []
            if self.db:
                try:
                    incidents = self.db.fetch_all(severity=sev, status=status,
                                                  include_archived=archived_var.get())
                except sqlite3.Error:
                    logger.exception("Could not load incident log")
            state["incidents"] = incidents
            log_text.config(state="normal")
            log_text.delete("1.0", "end")
            if not incidents:
                log_text.insert("1.0", "No incidents match the current filters.\n")
            else:
                for rep in incidents:
                    log_text.insert(
                        "end",
                        f"── Incident INC-{rep['id']:04d} "
                        f"[{rep.get('status') or 'Open'}]"
                        f"{' [ARCHIVED: ' + (rep.get('archive_reason') or '') + ']' if rep.get('archived') else ''} ──\n"
                        f"Time:        {rep['submitted_at']}\n"
                        f"Reporter:    {rep['reporter_name']} (ID: {rep['reporter_id'] or '—'})\n"
                        f"Logged by:   {rep['reporter_user'] or '—'}\n"
                        f"Email:       {rep.get('email') or '—'}\n"
                        f"Phone:       {rep['phone'] or '—'}\n"
                        f"Location:    {rep['location'] or '—'}\n"
                        f"Type:        {rep['incident_type'] or '—'}\n"
                        f"Severity:    {rep['severity'] or '—'}\n"
                        f"Person:      {_fa_rules.PERSON_TYPES.get(rep.get('person_type'), '—')}\n"
                        f"RIDDOR:      {_fa_rules.riddor_state(rep)}"
                        f"{'  — ' + _fa_rules.CATEGORIES.get(rep.get('riddor_category'), '') if rep.get('riddor_category') else ''}\n"
                        f"H&S record:  {('HS incident #' + str(rep['hs_incident_id'])) if rep.get('hs_incident_id') else '—'}\n"
                        f"Description: {rep['description']}\n\n",
                    )
            log_text.config(state="disabled")
            logger.info("Incident log viewed by user=%s entries=%s",
                        self.user_display, len(incidents))

        sev_var.trace("w", lambda *a: _load())
        status_var.trace("w", lambda *a: _load())

        def _mark_resolved():
            incidents = [r for r in state["incidents"]
                         if (r.get("status") or "Open") != "Resolved"]
            if not incidents:
                messagebox.showinfo("Incident Log",
                                    "No open incidents to resolve.",
                                    parent=log_window)
                return
            ids = ", ".join(f"INC-{r['id']:04d}" for r in incidents)
            if not messagebox.askyesno(
                    "Mark Resolved",
                    f"Mark the {len(incidents)} currently-listed open "
                    f"incident(s) as Resolved?\n\n{ids}",
                    parent=log_window):
                return
            done = 0
            for r in incidents:
                try:
                    if self.db.update_status(r["id"], "Resolved"):
                        done += 1
                except sqlite3.Error:
                    logger.exception("Could not update status for %s", r["id"])
            logger.info("Marked %s incidents resolved by user=%s",
                        done, self.user_display)
            _load()

        def _export():
            incidents = state["incidents"]
            if not incidents:
                messagebox.showinfo("Export", "Nothing to export.",
                                    parent=log_window)
                return
            import csv
            fname = (f"first_aid_incident_log_"
                     f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            target_dir = downloads if os.path.isdir(downloads) else tempfile.gettempdir()
            path = os.path.join(target_dir, fname)
            cols = ["id", "submitted_at", "incident_date", "status", "severity",
                    "incident_type", "location", "reporter_name",
                    "reporter_id", "reporter_user", "email", "phone",
                    "person_type", "riddor_category", "riddor_status",
                    "riddor_deadline", "hse_reference", "riddor_reported_at",
                    "hs_incident_id", "description"]
            try:
                with open(path, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=cols,
                                            extrasaction="ignore")
                    writer.writeheader()
                    for r in incidents:
                        writer.writerow({c: r.get(c, "") for c in cols})
            except OSError:
                logger.exception("Could not export incident log")
                messagebox.showerror("Export Failed",
                                     "Could not write the export file.",
                                     parent=log_window)
                return
            logger.info("Incident log exported (%s rows) to %s by user=%s",
                        len(incidents), path, self.user_display)
            self._open_path(path)
            messagebox.showinfo("Export Complete",
                                f"✓ Exported {len(incidents)} incident(s) to:"
                                f"\n\n{path}", parent=log_window)

        btns = tk.Frame(log_window, bg=self.colors["bg"])
        btns.pack(fill="x", padx=15, pady=(0, 12))
        # Resolving incidents is an admin/staff action.
        if self._is_staff():
            tk.Button(btns, text="✓ Mark Listed Resolved",
                      font=("Segoe UI", 9, "bold"), bg=self.colors["accent"],
                      fg="white", relief="flat", padx=12, pady=5,
                      cursor="hand2", command=_mark_resolved).pack(side="left")
        tk.Button(btns, text="⤓ Export CSV", font=("Segoe UI", 9, "bold"),
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=12, pady=5, cursor="hand2",
                  command=_export).pack(side="left", padx=8)
        if self._is_staff() or self._is_health_team():
            tk.Button(btns, text="⚖ RIDDOR…", font=("Segoe UI", 9, "bold"),
                      bg=self.colors["primary"], fg="white", relief="flat",
                      padx=12, pady=5, cursor="hand2",
                      command=lambda: self._riddor_pick_and_assess(
                          state["incidents"], log_window, _load)).pack(side="left")
        # Archiving hides an incident (test entries, duplicates) from the
        # log, the RIDDOR queue, reminders and exports; the row is kept and
        # can be restored. Health team only (application/health/first_aid).
        if self._is_health_team():
            tk.Button(btns, text="🗄 Archive incident…", font=("Segoe UI", 9, "bold"),
                      bg=self.colors["warning"], fg="white", relief="flat",
                      padx=12, pady=5, cursor="hand2",
                      command=lambda: self._archive_incident_dialog(
                          state["incidents"], log_window, _load)).pack(side="left", padx=8)
            tk.Button(btns, text="↩ Restore incident…", font=("Segoe UI", 9, "bold"),
                      bg=self.colors["secondary"], fg="white", relief="flat",
                      padx=12, pady=5, cursor="hand2",
                      command=lambda: self._restore_incident_dialog(
                          state["incidents"], log_window, _load, archived_var)
                      ).pack(side="left")

        _load()

    def _pick_listed_incident(self, incidents, parent, title, *, archived):
        """Ask for an incident number from the listed incidents (archived or
        live, as asked); ``None`` when cancelled or not listed."""
        from education_system.platform.delivery.gui.parented_dialogs import simpledialog
        listed = [r for r in incidents if bool(r.get("archived")) == archived]
        if not listed:
            messagebox.showinfo(title, "No archived incidents are listed — tick "
                                       "'Show archived' first." if archived else
                                "No incidents are listed.", parent=parent)
            return None
        typed = simpledialog.askstring(
            title, "Incident number (e.g. 12 for INC-0012):", parent=parent)
        if not typed:
            return None
        digits = "".join(ch for ch in typed if ch.isdigit()).lstrip("0")
        match = next((r for r in listed if str(r["id"]) == digits), None)
        if match is None:
            messagebox.showerror(title, f"INC-{typed} is not in the list.", parent=parent)
        return match

    def _archive_or_restore(self, incident, parent, on_done, *, reason=None):
        """Archive (``reason`` given) or restore one incident, audited in the
        same transaction; a refused or failed audit rolls the change back."""
        from education_system.systems.university.domains.health.application.health import (
            access, first_aid as _fa_rules,
        )
        from education_system.systems.university.domains.health.domain.health.records.db.audit import (
            log_audit_event,
        )
        title = "Archive incident" if reason is not None else "Restore incident"
        if not self.db:
            messagebox.showerror(title, "The incident database is not available.", parent=parent)
            return
        who = access.from_user(self.user)
        conn = self.db._connection()
        try:
            if reason is not None:
                _fa_rules.archive_incident(conn, who, incident["id"], reason)
            else:
                _fa_rules.restore_incident(conn, who, incident["id"])
            log_audit_event(who.username if who else None,
                            "ARCHIVE" if reason is not None else "RESTORE",
                            "first_aid_incident", incident["id"],
                            {"severity": incident.get("severity")}, conn=conn,
                            reason=reason)
            conn.commit()
        except (PermissionError, ValueError) as exc:
            conn.rollback()
            messagebox.showerror(title, str(exc), parent=parent)
            return
        except Exception as exc:
            conn.rollback()
            logger.exception("%s failed for incident %s", title, incident["id"])
            messagebox.showerror(title, f"Nothing was changed: {exc}", parent=parent)
            return
        finally:
            conn.close()
        logger.info("%s INC-%04d by user=%s", title, incident["id"], self.user_display)
        messagebox.showinfo(title, f"INC-{incident['id']:04d} "
                                   f"{'archived' if reason is not None else 'restored'}.",
                            parent=parent)
        if on_done:
            on_done()

    def _archive_incident_dialog(self, incidents, parent, on_done=None):
        from education_system.platform.delivery.gui.parented_dialogs import simpledialog
        incident = self._pick_listed_incident(incidents, parent, "Archive incident",
                                              archived=False)
        if incident is None:
            return
        reason = simpledialog.askstring(
            "Archive incident",
            f"Why is INC-{incident['id']:04d} being archived? (e.g. test entry, duplicate)\n"
            "The incident is kept and can be restored.", parent=parent)
        if not reason:
            return
        self._archive_or_restore(incident, parent, on_done, reason=reason)

    def _restore_incident_dialog(self, incidents, parent, on_done=None, archived_var=None):
        if archived_var is not None and not archived_var.get():
            archived_var.set(True)
            if on_done:
                on_done()
            messagebox.showinfo("Restore incident", "Archived incidents are now shown. "
                                "Press Restore again and enter the incident number.",
                                parent=parent)
            return
        incident = self._pick_listed_incident(incidents, parent, "Restore incident",
                                              archived=True)
        if incident is None:
            return
        if messagebox.askyesno("Restore incident",
                               f"Restore INC-{incident['id']:04d} to the incident log?",
                               parent=parent):
            self._archive_or_restore(incident, parent, on_done)

    def _is_health_team(self):
        """Clinicians and first aiders (application/health/access)."""
        from education_system.systems.university.domains.health.application.health import access
        who = access.from_user(self.user)
        return bool(who and who.is_clinician)

    def _riddor_pick_and_assess(self, incidents, parent, on_done=None):
        if not incidents:
            messagebox.showinfo("RIDDOR", "No incidents are listed.", parent=parent)
            return
        from education_system.platform.delivery.gui.parented_dialogs import simpledialog
        typed = simpledialog.askstring(
            "RIDDOR", "Incident number to assess (e.g. 12 for INC-0012):", parent=parent)
        if not typed:
            return
        digits = "".join(ch for ch in typed if ch.isdigit())
        match = next((r for r in incidents if str(r["id"]) == digits.lstrip("0") or
                      str(r["id"]) == digits), None)
        if match is None:
            messagebox.showerror("RIDDOR", f"INC-{typed} is not in the list.", parent=parent)
            return
        self._riddor_dialog(match, parent, on_done)

    def _is_staff(self):
        """True if the signed-in user is an admin or staff member."""
        role = str((self.user or {}).get("role") or "").lower()
        return role in ("admin", "staff", "superadmin", "super_admin")
