"""Tools tab (telemetry, FTS, pinning, subscriptions, export).

Moved verbatim from ``advanced_search_views``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.learners.advanced_search import (
    _db as search_db,
    history as search_history,
    insights as search_insights,
)
from education_system.systems.sixth_form.domain.learners.advanced_search.models import (
    ValidationError,
)
from ._widgets import (
    _add_page,
    _read_action_log,
)


# ══ Tools tab (telemetry, FTS, pinning, subscriptions, export) ════════

class ToolsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        _add_page(nb, self.frame, "Tools", "Admin")
        self._build()
        # Default the actor boxes to the signed-in user; another user's
        # inbox/pins/digest needs the governance capability.
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        me = access.current().username
        if me:
            for entry in (self.inbox_actor, self.digest_actor, self.pin_actor):
                entry.insert(0, me)

    def _build(self) -> None:
        # Section: Index / cache
        sec1 = ttk.LabelFrame(self.frame, text="Index & cache",
                               padding=8)
        sec1.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Button(sec1, text="Rebuild FTS5 index",
                    command=self._rebuild_index).pack(side="left")
        ttk.Button(sec1, text="Clear search cache",
                    command=self._clear_cache).pack(side="left",
                                                     padx=(6, 0))
        self.fts_var = tk.StringVar(value=self._fts_status())
        ttk.Label(sec1, textvariable=self.fts_var).pack(side="left",
                                                          padx=(12, 0))

        # Section: Subscriptions
        sec2 = ttk.LabelFrame(self.frame, text="Subscriptions",
                               padding=8)
        sec2.pack(fill="x", padx=10, pady=4)
        ttk.Button(sec2, text="Poll now",
                    command=self._poll).pack(side="left")
        ttk.Label(sec2, text="  Inbox for actor:").pack(side="left")
        self.inbox_actor = ttk.Entry(sec2, width=14)
        self.inbox_actor.pack(side="left", padx=(2, 4))
        ttk.Button(sec2, text="Show inbox",
                    command=self._show_inbox).pack(side="left")
        ttk.Label(sec2, text="  Snooze id:").pack(side="left")
        self.snooze_id = ttk.Entry(sec2, width=6)
        self.snooze_id.pack(side="left", padx=(2, 4))
        ttk.Button(sec2, text="Snooze 24h",
                    command=self._snooze).pack(side="left")

        # Section: Alerts & dashboards (items 27, 29)
        sec_a = ttk.LabelFrame(self.frame, text="Alerts & dashboards",
                                padding=8)
        sec_a.pack(fill="x", padx=10, pady=4)
        ttk.Label(sec_a, text="Digest actor:").pack(side="left")
        self.digest_actor = ttk.Entry(sec_a, width=12)
        self.digest_actor.pack(side="left", padx=(2, 4))
        ttk.Button(sec_a, text="Build digest",
                    command=self._digest).pack(side="left")
        ttk.Label(sec_a, text="   Dashboard:").pack(side="left")
        self.dash_name = ttk.Entry(sec_a, width=14)
        self.dash_name.pack(side="left", padx=(2, 4))
        ttk.Button(sec_a, text="Run",
                    command=self._run_dashboard).pack(side="left")
        ttk.Button(sec_a, text="List",
                    command=self._list_dashboards).pack(side="left",
                                                        padx=(4, 0))

        # Section: Scheduled searches (feature 3)
        sec_s = ttk.LabelFrame(self.frame, text="Scheduled searches",
                                padding=8)
        sec_s.pack(fill="x", padx=10, pady=4)
        ttk.Label(sec_s, text="Saved id:").pack(side="left")
        self.sched_saved_id = ttk.Entry(sec_s, width=6)
        self.sched_saved_id.pack(side="left", padx=(2, 4))
        ttk.Label(sec_s, text="Cron:").pack(side="left")
        self.sched_cron = ttk.Combobox(
            sec_s, width=8, state="readonly",
            values=["daily", "hourly", "weekly"])
        self.sched_cron.set("daily")
        self.sched_cron.pack(side="left", padx=(2, 4))
        ttk.Label(sec_s, text="Notify:").pack(side="left")
        self.sched_notify = ttk.Entry(sec_s, width=12)
        self.sched_notify.pack(side="left", padx=(2, 4))
        ttk.Button(sec_s, text="Schedule",
                   command=self._schedule_saved).pack(side="left")
        ttk.Button(sec_s, text="List",
                   command=self._list_schedules).pack(side="left", padx=(4, 0))
        ttk.Label(sec_s, text="  Sched id:").pack(side="left")
        self.sched_id = ttk.Entry(sec_s, width=6)
        self.sched_id.pack(side="left", padx=(2, 4))
        ttk.Button(sec_s, text="Run now",
                   command=self._run_schedule).pack(side="left")
        ttk.Button(sec_s, text="Delete",
                   command=self._delete_schedule).pack(side="left", padx=(4, 0))

        # Section: Data quality & admin (items 33, 41, 43, 44, 45, 46)
        sec_b = ttk.LabelFrame(self.frame, text="Data quality & admin",
                                padding=8)
        sec_b.pack(fill="x", padx=10, pady=4)
        ttk.Button(sec_b, text="Index status",
                    command=self._index_status).pack(side="left")
        ttk.Button(sec_b, text="Refresh stale",
                    command=self._refresh_stale).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Cache stats",
                    command=self._cache_stats).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Duplicate students",
                    command=self._duplicates).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Data gaps",
                    command=self._data_gaps).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Audit log",
                    command=self._audit).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Search volume",
                    command=self._volume).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Operator action log",
                    command=self._action_log).pack(side="left", padx=(4, 0))

        # Section: Saved searches export/import
        sec3 = ttk.LabelFrame(self.frame, text="Saved searches",
                               padding=8)
        sec3.pack(fill="x", padx=10, pady=4)
        ttk.Button(sec3, text="Export to JSON…",
                    command=self._export).pack(side="left")
        ttk.Button(sec3, text="Import from JSON…",
                    command=self._import).pack(side="left", padx=(6, 0))

        # Section: Telemetry
        sec4 = ttk.LabelFrame(self.frame, text="Telemetry",
                               padding=8)
        sec4.pack(fill="both", expand=True, padx=10, pady=4)
        ttk.Button(sec4, text="Refresh",
                    command=self._refresh_telemetry).pack(side="top",
                                                            anchor="w")
        self.telem_txt = tk.Text(sec4, height=18, wrap="word")
        self.telem_txt.pack(fill="both", expand=True, pady=(6, 0))
        self._refresh_telemetry()

        # Section: Pinned
        sec5 = ttk.LabelFrame(self.frame, text="Pinned results",
                               padding=8)
        sec5.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Label(sec5, text="Actor:").pack(side="left")
        self.pin_actor = ttk.Entry(sec5, width=14)
        self.pin_actor.pack(side="left", padx=(2, 4))
        ttk.Button(sec5, text="List",
                    command=self._list_pins).pack(side="left")

    # ── handlers ──────────────────────────────────────────────────

    def _fts_status(self) -> str:
        return ("FTS5: available"
                if search_db._fts_available() else "FTS5: NOT available")

    def _rebuild_index(self) -> None:
        if not search_db._fts_available():
            messagebox.showinfo("FTS5",
                                "SQLite FTS5 is not available.")
            return
        counts = search_insights.refresh_index()
        total = sum(counts.values())
        messagebox.showinfo(
            "Index rebuilt",
            f"Indexed {total} row(s) across {len(counts)} scope(s).")

    def _clear_cache(self) -> None:
        search_db.clear_cache()
        messagebox.showinfo("Cache", "Search cache cleared.")

    def _poll(self) -> None:
        fired = search_history.poll_subscriptions()
        messagebox.showinfo(
            "Subscriptions",
            f"{len(fired)} subscription(s) fired.")

    def _show_inbox(self) -> None:
        actor = self.inbox_actor.get().strip()
        if not actor:
            messagebox.showinfo("Inbox", "Enter an actor id first.")
            return
        rows = search_history.list_subscription_notifications(actor)
        if not rows:
            messagebox.showinfo("Inbox", "(empty)")
            return
        lines = []
        for r in rows[:50]:
            mark = "•" if not r.get("read_at") else " "
            lines.append(
                f"{mark} #{r['notif_id']} +{r['delta']}/{r['total']}  "
                f"{r.get('sample_scope') or ''}: "
                f"{r.get('sample_label') or ''}")
        messagebox.showinfo(f"Inbox for {actor}",
                            "\n".join(lines))

    def _export(self) -> None:
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile="saved_searches.json",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(search_history.export_saved_searches())
            messagebox.showinfo("Export", f"Wrote {path}")
        except OSError as e:
            messagebox.showerror("Export failed", str(e))

    def _import(self) -> None:
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        overwrite = messagebox.askyesno(
            "Import",
            "Overwrite existing saved searches with same name?")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            counts = search_history.import_saved_searches(text,
                                                  overwrite=overwrite)
            messagebox.showinfo("Import", str(counts))
        except (OSError, ValidationError) as e:
            messagebox.showerror("Import failed", str(e))

    def _refresh_telemetry(self) -> None:
        ts = search_insights.telemetry_summary()
        lines = [
            f"Total searches: {ts.total_searches}",
            f"Zero-result:    {ts.zero_result}",
            "",
            "Top queries:",
        ]
        for q, n in ts.top_queries:
            lines.append(f"  {n:>3}×  {q!r}")
        lines.append("")
        lines.append("Slowest scopes (avg ms):")
        for s, ms in ts.slowest_scopes_ms.items():
            lines.append(f"  {s:<22} {ms:>8.1f}")
        if ts.zero_result_queries:
            lines.append("")
            lines.append("Recent zero-result queries:")
            for q in ts.zero_result_queries:
                lines.append(f"  • {q!r}")
        self.telem_txt.configure(state="normal")
        self.telem_txt.delete("1.0", "end")
        self.telem_txt.insert("1.0", "\n".join(lines))
        self.telem_txt.configure(state="disabled")

    def _list_pins(self) -> None:
        actor = self.pin_actor.get().strip() or None
        pins = search_history.list_pinned(actor)
        if not pins:
            messagebox.showinfo("Pinned", "(none)")
            return
        text = "\n".join(
            f"#{p.pin_id}  {p.actor}  {p.scope}/{p.entity_id}  "
            f"{p.label}" for p in pins[:50])
        messagebox.showinfo("Pinned results", text)

    # ── Alerts / dashboards / admin handlers (items 26–50) ────────

    def _show_text(self, title: str, text: str) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.transient(self.frame.winfo_toplevel())
        win.title(title)
        win.geometry("720x460")
        t = tk.Text(win, wrap="none", font=("TkFixedFont", 9))
        t.pack(fill="both", expand=True, padx=8, pady=8)
        t.insert("1.0", text or "(nothing)")
        t.configure(state="disabled")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))

    def _snooze(self) -> None:
        raw = self.snooze_id.get().strip()
        if not raw.isdigit():
            messagebox.showinfo("Snooze", "Enter a notification id.")
            return
        ok = search_history.snooze_notification(int(raw), hours=24)
        messagebox.showinfo("Snooze",
                            "Snoozed 24h." if ok else "Not found.")

    def _digest(self) -> None:
        dg = search_history.build_digest(self.digest_actor.get().strip() or None)
        lines = [f"Digest — {dg.total_new} new across "
                 f"{len(dg.lines)} scheduled search(es)", ""]
        for line in dg.lines:
            lines.append(
                f"{line.new_since_last:>4} new · total {line.total:<5} "
                f"{line.saved_name}  (last {line.last_run_at or '—'})")
        self._show_text("Subscription digest", "\n".join(lines))

    def _run_dashboard(self) -> None:
        name = self.dash_name.get().strip()
        if not name:
            messagebox.showinfo("Dashboard", "Enter a dashboard name/id.")
            return
        try:
            panels = search_history.run_dashboard(name)
        except Exception as e:
            messagebox.showerror("Dashboard", str(e))
            return
        lines = [f"{name}:", ""]
        for p in panels:
            cnt = "err" if p.total < 0 else str(p.total)
            lines.append(f"{cnt:>6}  {p.name}   ({p.query or '(empty)'})")
        self._show_text(f"Dashboard — {name}", "\n".join(lines))

    def _list_dashboards(self) -> None:
        rows = search_history.list_dashboards()
        lines = [f"#{d.dashboard_id}  {d.name}  "
                 f"({len(d.saved_ids)} panel(s))" for d in rows]
        self._show_text("Dashboards", "\n".join(lines) or "(none)")

    def _index_status(self) -> None:
        rows = search_insights.index_status()
        lines = [f"{s.scope:<22} indexed {s.indexed_rows:>5} / current "
                 f"{s.current_rows:>5}  [{'STALE' if s.stale else 'ok'}]  "
                 f"{s.last_refresh or '—'}" for s in rows]
        self._show_text("FTS index status", "\n".join(lines))

    def _refresh_stale(self) -> None:
        counts = search_insights.refresh_index(only_stale=True)
        messagebox.showinfo(
            "Refresh stale",
            f"Refreshed {sum(counts.values())} row(s) across "
            f"{len(counts)} scope(s).")
        self.fts_var.set(self._fts_status())

    def _cache_stats(self) -> None:
        st = search_db.cache_stats()
        messagebox.showinfo(
            "Cache stats",
            f"Entries: {st['entries']}/{st['max_entries']}\n"
            f"Hits: {st['hits']}   Misses: {st['misses']}\n"
            f"Hit-rate: {st['hit_rate']:.0%}   TTL: {st['ttl_seconds']}s")

    def _duplicates(self) -> None:
        groups = search_insights.find_duplicate_students()
        lines = [f"[{g.reason}] {g.key}: {', '.join(g.student_ids)}"
                 for g in groups[:80]]
        self._show_text("Possible duplicate students",
                        "\n".join(lines) or "No likely duplicates.")

    def _data_gaps(self) -> None:
        gaps = search_insights.find_data_gaps("students")
        lines = [f"{g.entity_id}  {g.label[:36]:<36}  "
                 f"missing: {', '.join(g.missing)}" for g in gaps[:120]]
        self._show_text("Student data gaps",
                        "\n".join(lines) or "No data gaps.")

    def _audit(self) -> None:
        rows = search_history.list_search_audit(limit=80)
        lines = []
        for e in rows:
            bg = "  [BREAK-GLASS]" if e.break_glass else ""
            count = f" ×{e.record_count}" if e.record_count is not None else ""
            lines.append(f"{e.ts}  {e.action:<13}{count:<6} "
                         f"{e.actor or '—'}/{e.role or '—'}  "
                         f"{e.query!r}  "
                         f"sens={','.join(e.sensitive_scopes) or '—'}{bg}")
            if e.reason:
                lines.append(f"      reason: {e.reason}")
        self._show_text("Search & export audit",
                        "\n".join(lines) or "(no entries)")

    def _volume(self) -> None:
        rows = search_insights.search_volume_by_day()
        lines = [f"{d}  {'#' * min(n, 50)} {n}" for d, n in rows]
        self._show_text("Searches per day",
                        "\n".join(lines) or "(no history)")

    # ── Scheduled searches (feature 3) ────────────────────────────

    def _schedule_saved(self) -> None:
        raw = self.sched_saved_id.get().strip()
        if not raw.isdigit():
            messagebox.showinfo("Schedule", "Enter a saved-search id.")
            return
        try:
            sc = search_history.schedule_saved_search(
                int(raw), cron=self.sched_cron.get() or "daily",
                notify_actor=self.sched_notify.get().strip() or None)
        except ValidationError as e:
            messagebox.showerror("Schedule", str(e))
            return
        messagebox.showinfo(
            "Schedule",
            f"Scheduled #{sc.schedule_id}: saved #{sc.saved_id} "
            f"every {sc.cron}"
            + (f", notifying {sc.notify_actor}" if sc.notify_actor else ""))

    def _list_schedules(self) -> None:
        rows = search_history.list_scheduled_searches()
        lines = [f"#{s.schedule_id}  saved #{s.saved_id}  {s.cron:<8} "
                 f"{'on' if s.enabled else 'off':<3}  "
                 f"last {s.last_run_at or '—'}  "
                 f"(+{s.new_since_last}/{s.last_count})" for s in rows]
        self._show_text("Scheduled searches",
                        "\n".join(lines) or "(none scheduled)")

    def _run_schedule(self) -> None:
        raw = self.sched_id.get().strip()
        if not raw.isdigit():
            messagebox.showinfo("Run schedule", "Enter a schedule id.")
            return
        try:
            res = search_history.run_scheduled_search(int(raw))
        except ValidationError as e:
            messagebox.showerror("Run schedule", str(e))
            return
        messagebox.showinfo(
            "Run schedule",
            f"Ran schedule #{raw}: {res.total} hit(s).")

    def _delete_schedule(self) -> None:
        raw = self.sched_id.get().strip()
        if not raw.isdigit():
            messagebox.showinfo("Delete schedule", "Enter a schedule id.")
            return
        ok = search_history.delete_scheduled_search(int(raw))
        messagebox.showinfo("Delete schedule",
                            "Deleted." if ok else "Not found.")

    # ── Operator action log viewer (feature 25) ───────────────────

    def _action_log(self) -> None:
        rows = _read_action_log()
        lines = [f"{r.get('ts', ''):<20} {r.get('actor') or '—':<14} "
                 f"{r.get('action', ''):<14} "
                 f"×{r.get('count', 0):<4} {r.get('detail', '')}"
                 for r in reversed(rows[-200:])]
        self._show_text("Operator action log",
                        "\n".join(lines) or "(no actions recorded yet)")
