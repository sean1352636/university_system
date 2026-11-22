"""Tkinter views for Primary School Activity Feed.

Notebook with 3 tabs:
* Feed     — filterable, paginated table of events with auto-refresh.
* Log      — manual entry form for ad-hoc events / annotations.
* Summary  — counts, top actors, top actions.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.primary.interfaces.gui import kit
from education_system.systems.primary.domain.operations.communications.activity_feed import (
    activity_feed as data,
)
from education_system.systems.primary.domain.operations.communications.activity_feed.activity_feed import (
    ACTIONS,
    DEFAULT_SEVERITY,
    Event,
    KNOWN_ENTITY_TYPES,
    SEVERITIES,
    SOURCES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def _known_actors() -> list[str]:
    """Actors already in the feed (most active first) for the drop-downs;
    the boxes stay typeable for anyone not listed yet."""
    try:
        return list(data.summary().by_actor)
    except Exception:  # noqa: BLE001 - an empty list beats a broken screen
        logger.debug("actor list failed", exc_info=True)
        return []


def open_activity_feed_window(parent=None) -> None:
    data.init_db()
    kit.show_page(parent, "Activity Feed", lambda frame: _draw_activity_feed(frame, parent))


def _draw_activity_feed(parent: ttk.Frame, host=None) -> None:
    kit.page_heading(parent, "Activity Feed",
                     "Who did what, and when - filter the audit trail, log an event, "
                     "or see the totals.")
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    FeedTab(nb)
    LogTab(nb)
    SummaryTab(nb)


# ══ Feed tab ═══════════════════════════════════════════════════════

class FeedTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Feed")
        self._auto_job: str | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        # Filter row 1
        bar1 = ttk.Frame(self.frame)
        bar1.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Label(bar1, text="Actor:").pack(side="left")
        self.v_actor = tk.StringVar()
        self.f_actor = kit.ChoiceField(bar1, self.v_actor, choices=_known_actors(),
                                       blank=True, editable=True, width=16)
        self.f_actor.pack(side="left", padx=(2, 8))
        ttk.Label(bar1, text="Action:").pack(side="left")
        self.v_action = tk.StringVar()
        self.f_action = kit.ChoiceField(bar1, self.v_action, choices=ACTIONS, blank=True,
                                        editable=True, width=14)
        self.f_action.pack(side="left", padx=(2, 8))
        ttk.Label(bar1, text="Severity:").pack(side="left")
        self.v_severity = tk.StringVar()
        self.f_severity = kit.ChoiceField(bar1, self.v_severity, choices=SEVERITIES,
                                          blank=True, width=10)
        self.f_severity.pack(side="left", padx=(2, 8))
        ttk.Label(bar1, text="Source:").pack(side="left")
        self.v_source = tk.StringVar()
        self.f_source = kit.ChoiceField(bar1, self.v_source, choices=SOURCES, blank=True,
                                        width=10)
        self.f_source.pack(side="left", padx=(2, 8))

        # Filter row 2
        bar2 = ttk.Frame(self.frame)
        bar2.pack(fill="x", padx=8, pady=(2, 4))
        ttk.Label(bar2, text="Entity type:").pack(side="left")
        self.v_ent_type = tk.StringVar()
        self.f_ent_type = kit.ChoiceField(bar2, self.v_ent_type, choices=KNOWN_ENTITY_TYPES,
                                          blank=True, editable=True, width=18)
        self.f_ent_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar2, text="Entity id:").pack(side="left")
        self.f_ent_id = ttk.Entry(bar2, width=12)
        self.f_ent_id.pack(side="left", padx=(2, 8))
        ttk.Label(bar2, text="Summary contains:").pack(side="left")
        self.f_like = ttk.Entry(bar2, width=20)
        self.f_like.pack(side="left", padx=(2, 8))
        ttk.Label(bar2, text="Limit:").pack(side="left")
        self.v_limit = tk.StringVar(value="200")
        self.f_limit = kit.NumberField(bar2, self.v_limit, from_=1, to=10000, increment=50,
                                       width=6)
        self.f_limit.pack(side="left", padx=(2, 8))
        ttk.Button(bar2, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar2, text="Clear",
                    command=self._clear).pack(side="left")
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Auto-refresh (10s)",
                          variable=self.auto_var,
                          command=self._toggle_auto).pack(side="left",
                                                            padx=(12, 0))

        # Table
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "ts", "severity", "actor", "action",
                "entity", "summary")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {"id": "ID", "ts": "When",
                    "severity": "Sev", "actor": "Actor",
                    "action": "Action", "entity": "Entity",
                    "summary": "Summary"}
        widths = {"id": 60, "ts": 150, "severity": 70, "actor": 130,
                  "action": 110, "entity": 180, "summary": 520}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("warning", background="#fff7d0")
        self.tree.tag_configure("error",   background="#ffd0d0")
        self.tree.tag_configure("info",    background="#eef7ff")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        for v in (self.v_actor, self.v_action, self.v_severity, self.v_source,
                  self.v_ent_type):
            v.set("")
        self.f_ent_id.delete(0, "end")
        self.f_like.delete(0, "end")
        self.v_limit.set("200")
        self.refresh()

    def _toggle_auto(self) -> None:
        if self.auto_var.get():
            self._schedule_auto()
        else:
            if self._auto_job is not None:
                try:
                    self.frame.after_cancel(self._auto_job)
                except tk.TclError:
                    pass
                self._auto_job = None

    def _schedule_auto(self) -> None:
        self._auto_job = self.frame.after(10000, self._auto_tick)

    def _auto_tick(self) -> None:
        if not self.auto_var.get():
            self._auto_job = None
            return
        self.refresh()
        self._schedule_auto()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            limit = int(self.f_limit.get().strip() or "200")
        except ValueError:
            messagebox.showerror("Limit", "Limit must be a number.")
            return
        try:
            rows = data.list_events(
                actor=self.f_actor.get().strip() or None,
                action=self.f_action.get().strip() or None,
                severity=self.f_severity.get() or None,
                source=self.f_source.get() or None,
                entity_type=self.f_ent_type.get().strip() or None,
                entity_id=self.f_ent_id.get().strip() or None,
                summary_like=self.f_like.get().strip() or None,
                limit=limit,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for e in rows:
            ent = (f"{e.entity_type or ''}"
                   f"{('#' + str(e.entity_id)) if e.entity_id else ''}"
                   ) or "—"
            tags = (e.severity,) if e.severity in (
                "info", "warning", "error") else ()
            self.tree.insert("", "end", iid=str(e.event_id), values=(
                e.event_id, e.ts, e.severity, e.actor or "—",
                e.action, ent, e.summary,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} event(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _view_selected(self) -> None:
        eid = self._selected_id()
        if eid is None:
            messagebox.showinfo("View", "Select an event first.")
            return
        e = data.get_event(eid)
        if e is None:
            return
        EventDetailDialog(self.frame.winfo_toplevel(), e)

    def _delete_selected(self) -> None:
        eid = self._selected_id()
        if eid is None:
            messagebox.showinfo("Delete", "Select an event first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete event #{eid}?\n"
                                     "(Activity feed is an audit "
                                     "trail — only delete if necessary.)"):
            return
        try:
            data.delete_event(eid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Log tab (manual event entry) ═══════════════════════════════════

class LogTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Log Event")
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.frame)
        form.pack(fill="x", padx=12, pady=12, anchor="n")
        r = 0

        ttk.Label(form, text="Action:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.action_cb = kit.ChoiceField(form, tk.StringVar(value="system"), choices=ACTIONS,
                                         editable=True, width=18)
        self.action_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Summary:").grid(row=r, column=0,
                                                 sticky="e", pady=4)
        self.summary_e = ttk.Entry(form, width=70)
        self.summary_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Actor:").grid(row=r, column=0,
                                               sticky="e", pady=4)
        self.actor_e = kit.ChoiceField(form, tk.StringVar(), choices=_known_actors(),
                                       blank=True, editable=True, width=22)
        self.actor_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Actor role:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.role_e = ttk.Entry(form, width=22)
        self.role_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Severity:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.sev_cb = kit.ChoiceField(form, tk.StringVar(value=DEFAULT_SEVERITY),
                                      choices=SEVERITIES, width=12)
        self.sev_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Source:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.source_cb = kit.ChoiceField(form, tk.StringVar(value="gui"), choices=SOURCES,
                                         width=12)
        self.source_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Entity type:").grid(row=r, column=0,
                                                     sticky="e", pady=4)
        self.ent_type_cb = kit.ChoiceField(form, tk.StringVar(), choices=KNOWN_ENTITY_TYPES,
                                           blank=True, editable=True, width=22)
        self.ent_type_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Entity id:").grid(row=r, column=0,
                                                   sticky="e", pady=4)
        self.ent_id_e = ttk.Entry(form, width=22)
        self.ent_id_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Metadata (JSON):").grid(row=r, column=0,
                                                        sticky="ne", pady=4)
        self.meta_t = tk.Text(form, width=70, height=6)
        self.meta_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Log event",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left", padx=8)

        self.status_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.status_var,
                   foreground="#555").grid(row=r + 1, column=0,
                                            columnspan=2, sticky="w",
                                            pady=(8, 0))

    def _clear(self) -> None:
        self.summary_e.delete(0, "end")
        self.actor_e.set("")
        self.role_e.delete(0, "end")
        self.ent_type_cb.set("")
        self.ent_id_e.delete(0, "end")
        self.meta_t.delete("1.0", "end")
        self.status_var.set("")

    def _save(self) -> None:
        payload = {
            "action":      self.action_cb.get().strip(),
            "summary":     self.summary_e.get().strip(),
            "actor":       self.actor_e.get().strip() or None,
            "actor_role":  self.role_e.get().strip() or None,
            "severity":    self.sev_cb.get().strip(),
            "source":      self.source_cb.get().strip(),
            "entity_type": self.ent_type_cb.get().strip() or None,
            "entity_id":   self.ent_id_e.get().strip() or None,
            "metadata":    self.meta_t.get("1.0", "end").strip() or None,
        }
        try:
            ev = data.create_event(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Log failed", str(e))
            return
        self.status_var.set(f"✓ Logged event #{ev.event_id} at {ev.ts}")
        self.summary_e.delete(0, "end")
        self.meta_t.delete("1.0", "end")


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Purge old…",
                    command=self._purge_dialog).pack(side="left",
                                                       padx=8)

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        summ = data.summary()
        lines: list[str] = []
        lines.append(f"Total events       : {summ.total}")
        lines.append(f"Most recent        : {summ.most_recent_ts or '—'}")
        lines.append("")
        lines.append("Volume:")
        lines.append(f"  Last 24 hours    : {summ.last_24h}")
        lines.append(f"  Last 7 days      : {summ.last_7d}")
        lines.append(f"  Last 30 days     : {summ.last_30d}")
        lines.append("")
        lines.append("By severity:")
        for s in SEVERITIES:
            lines.append(f"  {s:<10} : {summ.by_severity.get(s, 0)}")
        lines.append("")
        lines.append("By source:")
        for s in SOURCES:
            n = summ.by_source.get(s, 0)
            if n:
                lines.append(f"  {s:<10} : {n}")
        lines.append("")
        lines.append("Top actions:")
        for action, n in list(summ.by_action.items())[:15]:
            lines.append(f"  {action:<16} : {n}")
        if summ.by_actor:
            lines.append("")
            lines.append("Top actors:")
            for actor, n in summ.by_actor.items():
                lines.append(f"  {actor:<22} : {n}")
        if summ.by_entity_type:
            lines.append("")
            lines.append("By entity type:")
            for ent, n in summ.by_entity_type.items():
                lines.append(f"  {ent:<22} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")

    def _purge_dialog(self) -> None:
        PurgeDialog(self.frame.winfo_toplevel(), on_save=self.refresh)


# ══ Dialogs ═══════════════════════════════════════════════════════

class EventDetailDialog:
    def __init__(self, parent: tk.Misc, event: Event) -> None:
        self.win = make_toplevel(parent.winfo_toplevel())
        self.win.title(f"Event #{event.event_id}")
        self.win.geometry("700x520")
        self.win.minsize(560, 400)

        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text=f"#{event.event_id}  ·  {event.ts}",
                   font=("", 11, "bold")).pack(anchor="w")
        ttk.Label(form,
                   text=f"{event.severity}  ·  {event.source}",
                   foreground="#666").pack(anchor="w", pady=(0, 8))

        meta_lines = [
            f"Actor       : {event.actor or '—'}  "
            f"({event.actor_role or '—'})",
            f"IP          : {event.ip_address or '—'}",
            f"Action      : {event.action}",
            f"Entity      : "
            f"{(event.entity_type or '—')}"
            f"{('#' + str(event.entity_id)) if event.entity_id else ''}",
        ]
        for line in meta_lines:
            ttk.Label(form, text=line, foreground="#333").pack(anchor="w")

        ttk.Label(form, text="Summary:",
                   font=("", 10, "bold")).pack(anchor="w", pady=(10, 2))
        summary_t = tk.Text(form, width=80, height=4, wrap="word")
        summary_t.insert("1.0", event.summary)
        summary_t.configure(state="disabled")
        summary_t.pack(fill="x")

        ttk.Label(form, text="Metadata:",
                   font=("", 10, "bold")).pack(anchor="w", pady=(10, 2))
        meta_t = tk.Text(form, height=12, wrap="none",
                            font=("TkFixedFont", 9))
        m = event.metadata_dict
        if m is not None:
            meta_t.insert("1.0", json.dumps(m, indent=2))
        elif event.metadata:
            meta_t.insert("1.0", event.metadata)
        else:
            meta_t.insert("1.0", "(none)")
        meta_t.configure(state="disabled")
        meta_t.pack(fill="both", expand=True)

        ttk.Button(form, text="Close",
                    command=self.win.destroy).pack(pady=(10, 0))


class PurgeDialog:
    def __init__(self, parent: tk.Misc,
                 on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = make_toplevel(parent.winfo_toplevel())
        self.win.title("Purge old events")
        self.win.after_idle(self.win.grab_set)

        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text="Delete activity events older than the given\n"
                         "number of days. This is irreversible.",
                   justify="left").grid(row=0, column=0, columnspan=2,
                                         sticky="w", pady=(0, 8))
        ttk.Label(form, text="Older than (days):").grid(row=1, column=0,
                                                          sticky="e", pady=4)
        self.days_e = kit.NumberField(form, tk.StringVar(value="365"), from_=1, to=36500,
                                      width=8)
        self.days_e.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Purge",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            days = int(self.days_e.get().strip())
        except ValueError:
            messagebox.showerror("Purge", "Must be a whole number.")
            return
        if not messagebox.askyesno(
                "Purge",
                f"Delete every event older than {days} days?\n"
                "This cannot be undone."):
            return
        try:
            n = data.purge(older_than_days=days)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Purge failed", str(e))
            return
        messagebox.showinfo("Purge", f"Removed {n} event(s).")
        self.win.destroy()
        self.on_save()
