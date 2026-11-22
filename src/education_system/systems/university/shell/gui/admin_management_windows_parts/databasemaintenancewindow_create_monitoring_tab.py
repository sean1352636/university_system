"""Methods create_monitoring_tab through view_live_stats."""

from .. import admin_management_windows_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class DatabaseMaintenanceWindow:
    def create_monitoring_tab(self, parent):
        """Create monitoring tab"""
        # Monitoring controls
        monitor_controls = ttk.LabelFrame(parent, text=_("admin_windows.database.monitoring.title"), padding="15")
        monitor_controls.pack(fill='x', padx=15, pady=15)

        # Monitoring options
        monitor_options = ttk.Frame(monitor_controls)
        monitor_options.pack(fill='x', pady=(0, 15))

        ttk.Label(monitor_options, text=_("admin_windows.database.monitoring.interval")).pack(side='left', padx=(0, 10))
        self.monitor_interval_var = tk.StringVar(value=_("admin_windows.database.monitoring.intervals.5min"))
        ttk.Combobox(monitor_options, textvariable=self.monitor_interval_var,
                    values=[_("admin_windows.database.monitoring.intervals.30sec"), _("admin_windows.database.monitoring.intervals.1min"), _("admin_windows.database.monitoring.intervals.5min"), _("admin_windows.database.monitoring.intervals.15min"), _("admin_windows.database.monitoring.intervals.1hour")],
                    width=15).pack(side='left', padx=(0, 20))

        self.alert_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(monitor_options, text=_("admin_windows.database.monitoring.enable_alerts"),
                       variable=self.alert_enabled_var).pack(side='left', padx=(0, 20))

        # Monitoring actions
        monitor_actions = ttk.Frame(monitor_controls)
        monitor_actions.pack(fill='x')

        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.start"),
                  command=self.start_monitoring).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.stop"),
                  command=self.stop_monitoring).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.configure"),
                  command=self.configure_alerts).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.live_stats"),
                  command=self.view_live_stats).pack(side='left')

        # Monitoring display
        monitor_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.monitoring.realtime"), padding="15")
        monitor_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        self.monitor_text = scrolledtext.ScrolledText(monitor_frame, height=18, wrap='word')
        self.monitor_text.pack(fill='both', expand=True)
        self._monitor_job = None
        self._monitor_history = []
        self._alert_thresholds = {"wal_mb": 64.0, "free_pct": 20.0}
        self._render_monitor(status="Not running - press Start to sample every interval.")

    # ── Status (real database facts) ──────────────────────────────────────
    def _inspect(self, integrity="quick"):
        from education_system.systems.university.infrastructure.database.db_inspector import inspect_database
        return inspect_database(integrity=integrity)

    @staticmethod
    def _set_text(widget, text):
        widget.config(state='normal')
        widget.delete('1.0', tk.END)
        widget.insert('1.0', text)
        widget.config(state='disabled')

    def _render_status(self, show_message=True):
        from education_system.systems.university.infrastructure.database.db_inspector import (
            fmt_bytes, format_report,
        )
        self.window.config(cursor='watch')
        self.window.update_idletasks()
        try:
            info = self._inspect("quick")
        finally:
            self.window.config(cursor='')
        self._last_status = info
        ok = not info.get("errors")
        integ = info.get("integrity") or {}
        values = {
            "connection": _("admin_windows.database.status.values.connected") if ok else "Unavailable",
            "health": ("Integrity ok" if integ.get("ok") else "Check failed") if integ else "-",
            "size": fmt_bytes(info.get("file_size", 0)),
            "tables": str(info.get("tables", "-")),
            "connections": str(len(info.get("other_processes") or [])),
            "wal": fmt_bytes(info.get("wal_size", 0)),
        }
        for key, label in getattr(self, "_status_labels", {}).items():
            label.config(text=values.get(key, "-"))
        self._set_text(self.status_text, format_report(info))
        if show_message:
            messagebox.showinfo(_("admin_windows.database.messages.status_refreshed_title"),
                                _("admin_windows.database.messages.status_refreshed_body"),
                                parent=self.window)

    def refresh_status(self):
        """Re-read the database status."""
        self._render_status(show_message=True)

    def test_connection(self):
        """Open the database read-only and time a trivial query."""
        import time as _time
        from education_system.systems.university.infrastructure.database.db_inspector import default_db_path
        path = default_db_path()
        t0 = _time.perf_counter()
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
            try:
                conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror(_("admin_windows.database.messages.connection_test_title"),
                                 f"Could not open {path}:\n{exc}", parent=self.window)
            return
        ms = (_time.perf_counter() - t0) * 1000
        messagebox.showinfo(_("admin_windows.database.messages.connection_test_title"),
                            f"Connected to {path}\nOpen + query: {ms:.1f} ms", parent=self.window)

    def export_status(self):
        """Save the current status report as text."""
        from education_system.systems.university.infrastructure.database.db_inspector import format_report
        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title=_("admin_windows.database.messages.export_status_title"),
            defaultextension=".txt",
            filetypes=[(_("admin_windows.filetypes.txt"), "*.txt"), (_("admin_windows.filetypes.all"), "*.*")]
        )
        if not filename:
            return
        info = getattr(self, "_last_status", None) or self._inspect("quick")
        try:
            with open(filename, "w", encoding="utf-8") as handle:
                handle.write(format_report(info))
        except OSError as exc:
            messagebox.showerror(_("admin_windows.database.messages.export_status_title"),
                                 f"Could not write {filename}: {exc}", parent=self.window)
            return
        messagebox.showinfo(_("admin_windows.messages.export_complete"),
                            _("admin_windows.database.messages.status_exported", filename=filename),
                            parent=self.window)

    # ── Backup history (real files under var/backups) ─────────────────────
    def refresh_backup_history(self):
        """List the backups actually on disk, newest first."""
        from education_system.systems.university.infrastructure.database.data_backup.listing import (
            list_university_backups,
        )
        for item in self.backup_tree.get_children():
            self.backup_tree.delete(item)
        try:
            backups = list_university_backups()
        except Exception as exc:
            self.backup_status_var.set(f"Could not read the backup folders: {exc}")
            return
        verified = getattr(self, '_verified_backups', {})
        for entry in backups:
            self.backup_tree.insert('', 'end', values=(
                entry['date'], entry['kind'], entry['size'], entry['duration'] or "-",
                verified.get(entry['path'], "Not verified"), entry['location'],
            ), tags=(entry['path'],))
        if backups:
            self.backup_status_var.set(
                f"{len(backups)} backup file(s) found. Newest: {backups[0]['date']}.")
        else:
            self.backup_status_var.set(
                "No database backups found yet. Use Create Backup to make the first one.")

    def _selected_backup_path(self, warn_key):
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _(warn_key),
                                   parent=self.window)
            return None
        tags = self.backup_tree.item(selection[0]).get('tags') or ()
        return tags[0] if tags else None

    def create_backup(self):
        """Create a database backup with the university backup service."""
        from education_system.systems.university.infrastructure.database.data_backup import operations as _ops
        from education_system.systems.university.infrastructure.database.data_backup.config import config as _cfg

        labels = [_("admin_windows.database.backup.types.full"),
                  _("admin_windows.database.backup.types.incremental"),
                  _("admin_windows.database.backup.types.schema"),
                  _("admin_windows.database.backup.types.data")]
        chosen = self.backup_type_var.get()
        kind = {labels[0]: "full", labels[1]: "incremental",
                labels[2]: "schema", labels[3]: "selective"}.get(chosen, "full")
        tables = _ops.get_database_tables() if kind == "selective" else None

        previous = _cfg.get("compression_enabled")
        _cfg["compression_enabled"] = bool(self.compression_var.get())
        self.window.config(cursor='watch')
        self.window.update_idletasks()
        try:
            path = _ops.create_enhanced_backup(manual=True, backup_type=kind, tables=tables)
        except Exception as exc:
            path = None
            error = str(exc)
        else:
            error = ""
        finally:
            _cfg["compression_enabled"] = previous
            self.window.config(cursor='')

        if path:
            messagebox.showinfo(_("admin_windows.database.messages.backup_started_title"),
                                f"Backup created:\n{path}", parent=self.window)
        else:
            messagebox.showerror(_("admin_windows.database.messages.backup_started_title"),
                                 "The backup was not created. " + (error or "See the application log for the reason."),
                                 parent=self.window)
        self.refresh_backup_history()

    def schedule_backup(self):
        """Show the real backup schedule from the backup configuration."""
        try:
            from education_system.systems.university.infrastructure.database.data_backup.config import config as _cfg
            body = (f"Automatic backups: {'on' if _cfg.get('auto_backup_enabled') else 'off'}\n"
                    f"Frequency: {_cfg.get('backup_frequency', 'not set')} at "
                    f"{_cfg.get('scheduled_backup_time', 'not set')}\n"
                    f"Backups kept: {_cfg.get('max_backups', 'not set')}\n"
                    f"Folder: {_cfg.get('backup_directory', '')}\n\n"
                    "Change these under Data Backup > Configure Backups.")
        except Exception as exc:
            body = f"Could not read the backup configuration: {exc}"
        messagebox.showinfo(_("admin_windows.database.messages.backup_schedule_title"), body,
                            parent=self.window)

    def verify_backup(self):
        """Verify the selected backup can be opened and read."""
        path = self._selected_backup_path("admin_windows.database.messages.select_backup_verify")
        if not path:
            return
        from education_system.systems.university.infrastructure.database.data_backup.analysis import validate_backup
        self.window.config(cursor='watch')
        self.window.update_idletasks()
        try:
            result = validate_backup(path) or {}
        except Exception as exc:
            result = {"errors": [str(exc)]}
        finally:
            self.window.config(cursor='')
        ok = bool(result.get("database_valid")) and not result.get("errors")
        self._verified_backups = getattr(self, '_verified_backups', {})
        self._verified_backups[path] = "Valid" if ok else "Failed"
        lines = [f"{k.replace('_', ' ')}: {'yes' if v else 'no'}"
                 for k, v in result.items() if isinstance(v, bool)]
        if result.get("errors"):
            lines.append("")
            lines.extend(f"- {e}" for e in result["errors"])
        (messagebox.showinfo if ok else messagebox.showwarning)(
            _("admin_windows.database.messages.backup_verify_title"),
            f"{os.path.basename(path)}\n\n" + "\n".join(lines), parent=self.window)
        self.refresh_backup_history()

    def _restore(self, path):
        from education_system.systems.university.infrastructure.database.data_backup.operations import restore_from_backup
        self.window.config(cursor='watch')
        self.window.update_idletasks()
        try:
            ok = restore_from_backup(path)
        except Exception as exc:
            ok = False
            logging_detail = str(exc)
        else:
            logging_detail = ""
        finally:
            self.window.config(cursor='')
        if ok:
            messagebox.showinfo(_("admin_windows.database.messages.restore_started_title"),
                                "Database restored. A copy of the database as it was before the "
                                "restore was saved first.\n\nRestart the application so every "
                                "window reads the restored data.", parent=self.window)
        else:
            messagebox.showerror(_("admin_windows.database.messages.restore_started_title"),
                                 "The restore did not complete. " + (logging_detail or "See the application log."),
                                 parent=self.window)
        self.refresh_backup_history()

    def restore_backup(self):
        """Restore the database from the selected backup."""
        path = self._selected_backup_path("admin_windows.database.messages.select_backup_restore")
        if not path:
            return
        item = self.backup_tree.item(self.backup_tree.selection()[0])
        backup_date = item['values'][0]
        if not messagebox.askyesno(_("admin_windows.database.messages.confirm_restore_title"),
                                   _("admin_windows.database.messages.confirm_restore_body", backup_date=backup_date)
                                   + f"\n\n{path}\n\nThis replaces the live university database.",
                                   parent=self.window):
            return
        self._restore(path)

    def download_backup(self):
        """Save a copy of the selected backup file somewhere else."""
        path = self._selected_backup_path("admin_windows.database.messages.select_backup_download")
        if not path:
            return
        base = os.path.basename(path)
        ext = base[base.index('.'):] if '.' in base else ''
        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title=_("admin_windows.database.messages.save_backup_title"),
            initialfile=base,
            defaultextension=ext,
            filetypes=[(_("admin_windows.filetypes.all"), "*.*")]
        )
        if not filename:
            return
        import shutil
        try:
            shutil.copy2(path, filename)
        except OSError as exc:
            messagebox.showerror(_("admin_windows.database.messages.download_complete_title"),
                                 f"Could not copy the backup: {exc}", parent=self.window)
            return
        messagebox.showinfo(_("admin_windows.database.messages.download_complete_title"),
                            _("admin_windows.database.messages.download_complete_body", filename=filename),
                            parent=self.window)

    def delete_backup(self):
        """Delete the selected backup file (and its metadata sidecar)."""
        from education_system.systems.university.infrastructure.database.data_backup.listing import is_inside_backup_tree
        path = self._selected_backup_path("admin_windows.database.messages.select_backup_delete")
        if not path:
            return
        if not is_inside_backup_tree(path):
            messagebox.showerror(_("admin_windows.database.messages.backup_deleted_title"),
                                 "Only files inside the backups folder can be deleted here.",
                                 parent=self.window)
            return
        item = self.backup_tree.item(self.backup_tree.selection()[0])
        backup_date = item['values'][0]
        if not messagebox.askyesno(_("admin_windows.database.messages.confirm_delete_title"),
                                   _("admin_windows.database.messages.confirm_delete_body", backup_date=backup_date)
                                   + f"\n\n{path}\n\nThis cannot be undone.",
                                   parent=self.window):
            return
        try:
            os.remove(path)
            sidecar = path + ".meta.json"
            if os.path.exists(sidecar):
                os.remove(sidecar)
        except OSError as exc:
            messagebox.showerror(_("admin_windows.database.messages.backup_deleted_title"),
                                 f"Could not delete the backup: {exc}", parent=self.window)
            return
        messagebox.showinfo(_("admin_windows.database.messages.backup_deleted_title"),
                            _("admin_windows.database.messages.backup_deleted_body"), parent=self.window)
        self.refresh_backup_history()

    def restore_from_file(self):
        """Restore the database from a backup file chosen on disk."""
        filename = filedialog.askopenfilename(
            parent=self.window,
            title=_("admin_windows.database.messages.select_backup_file"),
            filetypes=[("SQLite backups", "*.db *.db.gz *.db.zip *.encrypted"), (_("admin_windows.filetypes.all"), "*.*")]
        )
        if not filename:
            return
        if not messagebox.askyesno(_("admin_windows.database.messages.confirm_restore_title"),
                                   _("admin_windows.database.messages.confirm_restore_file", filename=filename)
                                   + "\n\nThis replaces the live university database.",
                                   parent=self.window):
            return
        self._restore(filename)

    # ── Optimization (acts only when the button is clicked) ───────────────
    def _show_optimization_overview(self):
        from education_system.systems.university.infrastructure.database.db_inspector import fmt_bytes
        info = self._inspect(None)
        has_stats = False
        try:
            from education_system.systems.university.infrastructure.database.db_inspector import default_db_path
            conn = sqlite3.connect(f"file:{default_db_path()}?mode=ro", uri=True, timeout=5)
            try:
                has_stats = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE name = 'sqlite_stat1'").fetchone() is not None
            finally:
                conn.close()
        except Exception:
            pass
        lines = [
            "DATABASE OPTIMIZATION",
            "=====================",
            "Nothing has been run in this window yet. Choose the operations above and press Run.",
            "",
            "CURRENT STATE:",
            f"- File size: {fmt_bytes(info.get('file_size', 0))}",
            f"- Free pages: {info.get('freelist_count')} of {info.get('page_count')} "
            f"({info.get('free_pct', 0)}%) - VACUUM reclaims these",
            f"- WAL file: {fmt_bytes(info.get('wal_size', 0))} - cleanup checkpoints it",
            f"- Query planner statistics (ANALYZE): {'present' if has_stats else 'never gathered'}",
            f"- Indexes: {info.get('indexes')} ({fmt_bytes(info.get('index_bytes', 0))})",
            f"- Auto-vacuum mode: {info.get('auto_vacuum')}",
            "",
            "WHAT EACH OPTION DOES:",
            "- Cleanup: PRAGMA wal_checkpoint(TRUNCATE) - writes the WAL back and truncates it",
            "- ANALYZE: refreshes the statistics the query planner uses",
            "- REINDEX: rebuilds every index",
            "- VACUUM: rewrites the whole file to drop free pages; refused while another",
            "  process has the database open",
        ]
        self._set_text(self.opt_text, "\n".join(lines) + "\n")

    def run_optimization(self):
        """Run the ticked maintenance operations against the live database."""
        operations = []
        if self.cleanup_var.get():
            operations.append("checkpoint")
        if self.analyze_var.get():
            operations.append("analyze")
        if self.reindex_var.get():
            operations.append("reindex")
        if self.vacuum_var.get():
            operations.append("vacuum")

        if not operations:
            messagebox.showwarning(_("admin_windows.database.messages.no_operations_title"),
                                   _("admin_windows.database.messages.no_operations_body"),
                                   parent=self.window)
            return

        names = {"checkpoint": "CLEANUP", "analyze": "ANALYZE", "reindex": "REINDEX", "vacuum": "VACUUM"}
        operations_text = ", ".join(names[o] for o in operations)
        if not messagebox.askyesno(_("admin_windows.database.messages.confirm_optimize_title"),
                                   _("admin_windows.database.messages.confirm_optimize_body", operations=operations_text),
                                   parent=self.window):
            return

        from education_system.systems.university.infrastructure.database.db_inspector import run_maintenance
        self._set_text(self.opt_text, f"Running {operations_text}... (VACUUM can take several seconds)\n")
        self.window.config(cursor='watch')
        state = {}

        def work():
            try:
                state["result"] = run_maintenance(operations)
            except Exception as exc:
                state["error"] = str(exc)

        worker = threading.Thread(target=work, daemon=True)
        worker.start()

        def poll():
            if worker.is_alive():
                self.window.after(200, poll)
                return
            self.window.config(cursor='')
            if "error" in state:
                self._set_text(self.opt_text, f"Maintenance failed: {state['error']}\n")
                return
            self._show_optimization_result(state["result"])

        self.window.after(200, poll)

    def _show_optimization_result(self, result):
        from education_system.systems.university.infrastructure.database.db_inspector import fmt_bytes
        before, after = result["before"], result["after"]
        lines = ["DATABASE OPTIMIZATION REPORT", "============================",
                 f"Run: {after.get('generated', '')}", "", "STEPS:"]
        for name, ok, message in result["steps"]:
            lines.append(f"- {name}: {'ok' if ok else 'NOT DONE'} - {message}")
        lines += ["", "BEFORE -> AFTER:",
                  f"- File size: {fmt_bytes(before.get('file_size', 0))} -> {fmt_bytes(after.get('file_size', 0))}",
                  f"- WAL file: {fmt_bytes(before.get('wal_size', 0))} -> {fmt_bytes(after.get('wal_size', 0))}",
                  f"- Pages: {before.get('page_count')} -> {after.get('page_count')}",
                  f"- Free pages: {before.get('freelist_count')} -> {after.get('freelist_count')}"]
        self._set_text(self.opt_text, "\n".join(lines) + "\n")
        try:
            from education_system.systems.university.infrastructure.utils.activity_logger import log_activity
            log_activity("database_maintenance", "database",
                         details="; ".join(f"{n}: {'ok' if ok else m}" for n, ok, m in result["steps"]))
        except Exception:
            pass
        self._render_status(show_message=False)

    def schedule_maintenance(self):
        """Say honestly what automatic maintenance exists."""
        info = self._inspect(None)
        messagebox.showinfo(
            _("admin_windows.database.messages.maintenance_schedule_title"),
            "No scheduled maintenance job exists for the university database.\n\n"
            f"SQLite auto-vacuum mode: {info.get('auto_vacuum')}\n"
            f"Journal mode: {info.get('journal_mode')} (SQLite checkpoints the WAL automatically)\n\n"
            "Run cleanup / ANALYZE / VACUUM from this tab when needed.",
            parent=self.window)

    def check_integrity(self):
        """Run the full PRAGMA integrity_check and foreign-key check."""
        self.window.config(cursor='watch')
        self.window.update_idletasks()
        try:
            info = self._inspect("full")
        finally:
            self.window.config(cursor='')
        integ = info.get("integrity") or {}
        body = (f"PRAGMA integrity_check: {'ok' if integ.get('ok') else 'problems found'} "
                f"({integ.get('ms', '-')} ms)\n")
        if integ and not integ.get("ok"):
            body += "\n".join(f"- {m}" for m in integ.get("messages", [])[:20]) + "\n"
        body += f"Foreign key violations: {info.get('fk_violations')}"
        (messagebox.showinfo if integ.get("ok") else messagebox.showwarning)(
            _("admin_windows.database.messages.integrity_title"), body, parent=self.window)

    # ── Monitoring (samples on a timer while the window is open) ──────────
    _INTERVALS = (("admin_windows.database.monitoring.intervals.30sec", 30),
                  ("admin_windows.database.monitoring.intervals.1min", 60),
                  ("admin_windows.database.monitoring.intervals.5min", 300),
                  ("admin_windows.database.monitoring.intervals.15min", 900),
                  ("admin_windows.database.monitoring.intervals.1hour", 3600))

    def _interval_seconds(self):
        chosen = self.monitor_interval_var.get()
        for key, seconds in self._INTERVALS:
            if _(key) == chosen:
                return seconds
        return 300

    def _sample(self):
        info = self._inspect("quick")
        sample = {
            "time": info.get("generated", ""),
            "file_size": info.get("file_size", 0),
            "wal_size": info.get("wal_size", 0),
            "free_pct": info.get("free_pct", 0),
            "others": len(info.get("other_processes") or []),
            "integrity_ok": (info.get("integrity") or {}).get("ok"),
            "open_ms": info.get("open_ms"),
            "info": info,
        }
        self._monitor_history.append(sample)
        self._monitor_history = self._monitor_history[-50:]
        return sample

    def _alerts_for(self, sample):
        alerts = []
        if not self.alert_enabled_var.get():
            return alerts
        t = self._alert_thresholds
        if sample["wal_size"] > t["wal_mb"] * 1024 * 1024:
            alerts.append(f"WAL file above {t['wal_mb']:.0f} MB - run cleanup")
        if (sample["free_pct"] or 0) > t["free_pct"]:
            alerts.append(f"free pages above {t['free_pct']:.0f}% - consider VACUUM")
        if sample["integrity_ok"] is False:
            alerts.append("quick_check reported problems - run Check Integrity")
        return alerts

    def _render_monitor(self, status):
        from education_system.systems.university.infrastructure.database.db_inspector import fmt_bytes
        lines = ["DATABASE MONITORING", "===================", f"Status: {status}", ""]
        if self._monitor_history:
            latest = self._monitor_history[-1]
            info = latest["info"]
            lines += ["LATEST SAMPLE:",
                      f"- Time: {latest['time']}",
                      f"- Database file: {fmt_bytes(latest['file_size'])}",
                      f"- WAL file: {fmt_bytes(latest['wal_size'])}",
                      f"- Free pages: {latest['free_pct']}%",
                      f"- quick_check: {'ok' if latest['integrity_ok'] else 'problems'}",
                      f"- Read-only open + query: {latest['open_ms']} ms",
                      f"- Other processes with the database open: {latest['others']}"]
            for p in info.get("other_processes") or []:
                lines.append(f"    pid {p['pid']}: {p['command']}")
            alerts = self._alerts_for(latest)
            lines += ["", "ALERTS:"] + ([f"- {a}" for a in alerts] or ["- none"])
            lines += ["", f"HISTORY (this window, {len(self._monitor_history)} sample(s)):"]
            for s in reversed(self._monitor_history[-20:]):
                lines.append(f"- {s['time']}  file {fmt_bytes(s['file_size'])}  "
                             f"WAL {fmt_bytes(s['wal_size'])}  free {s['free_pct']}%  "
                             f"others {s['others']}")
        else:
            lines.append("No samples taken yet.")
        lines += ["", "SQLite keeps no query or connection history, so only what can be "
                      "measured from the file and PRAGMAs is shown."]
        self._set_text(self.monitor_text, "\n".join(lines) + "\n")

    def _monitor_tick(self):
        try:
            self._sample()
            seconds = self._interval_seconds()
            self._render_monitor(status=f"Running - sampling every {seconds}s")
            self._monitor_job = self.window.after(seconds * 1000, self._monitor_tick)
        except tk.TclError:
            self._monitor_job = None  # window closed

    def start_monitoring(self):
        """Sample the database now and then on the chosen interval."""
        if self._monitor_job is not None:
            self.window.after_cancel(self._monitor_job)
        self._monitor_tick()

    def stop_monitoring(self):
        """Stop sampling."""
        if self._monitor_job is None:
            messagebox.showinfo(_("admin_windows.database.messages.monitoring_stopped_title"),
                                "Monitoring is not running.", parent=self.window)
            return
        if not messagebox.askyesno(_("admin_windows.database.messages.stop_monitoring_title"),
                                   _("admin_windows.database.messages.stop_monitoring_body"),
                                   parent=self.window):
            return
        self.window.after_cancel(self._monitor_job)
        self._monitor_job = None
        self._render_monitor(status="Stopped")

    def configure_alerts(self):
        """Set the WAL-size and free-page thresholds that raise an alert."""
        from tkinter import simpledialog
        wal = simpledialog.askfloat(_("admin_windows.database.messages.alert_config_title"),
                                    "Alert when the WAL file is larger than (MB):",
                                    parent=self.window, minvalue=1,
                                    initialvalue=self._alert_thresholds["wal_mb"])
        if wal is None:
            return
        free = simpledialog.askfloat(_("admin_windows.database.messages.alert_config_title"),
                                     "Alert when free pages exceed (% of file):",
                                     parent=self.window, minvalue=1, maxvalue=100,
                                     initialvalue=self._alert_thresholds["free_pct"])
        if free is None:
            return
        self._alert_thresholds = {"wal_mb": wal, "free_pct": free}
        self._render_monitor(status="Running" if self._monitor_job else "Not running")

    def view_live_stats(self):
        """Take one sample now and show it."""
        from education_system.systems.university.infrastructure.database.db_inspector import fmt_bytes
        sample = self._sample()
        self._render_monitor(status="Running" if self._monitor_job else "Not running (one-off sample)")
        alerts = self._alerts_for(sample)
        messagebox.showinfo(
            _("admin_windows.database.messages.live_stats_title"),
            f"Database file: {fmt_bytes(sample['file_size'])}\n"
            f"WAL file: {fmt_bytes(sample['wal_size'])}\n"
            f"Free pages: {sample['free_pct']}%\n"
            f"quick_check: {'ok' if sample['integrity_ok'] else 'problems'}\n"
            f"Other processes with it open: {sample['others']}\n"
            f"Alerts: {', '.join(alerts) or 'none'}",
            parent=self.window)
