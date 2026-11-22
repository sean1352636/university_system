"""Communications: SMS, templates, drip, A/B tests, newsletters, open/click tracking."""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.learners.alumni import (
    db as alumni_db,
    messaging as alumni_messaging,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.learners.alumni.models import (
    ACHIEVEMENT_CATEGORIES,
    Alumnus,
    CAMPAIGN_STATUSES,
    APPLICATION_STATUSES,
    BEQUEST_STATUSES,
    CUSTOM_FIELD_TYPES,
    ERASURE_STATUSES,
    WEBHOOK_EVENT_TYPES,
    CHAPTER_ROLES,
    CONNECTION_KINDS,
    DIRECTORY_CONSENT_SCOPE,
    DONOR_STAGES,
    DRIP_STATUSES,
    JOB_STATUSES,
    JOB_TYPES,
    NEET_STATUSES,
    NEWSLETTER_STATUSES,
    PROFICIENCY_LEVELS,
    RECURRING_FREQS,
    RECURRING_STATUSES,
    SAFEGUARDING_STATUSES,
    SOCIAL_PLATFORMS,
    TRACK_KINDS,
    CONSENT_SCOPES,
    DEFAULT_CAMPAIGN_STATUS,
    DEFAULT_DESTINATION,
    DEFAULT_EDUCATION_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_LEAVING_REASON,
    DEFAULT_PLEDGE_STATUS,
    DEFAULT_RSVP_STATUS,
    DEFAULT_STATUS,
    DESTINATION_TYPES,
    EDUCATION_STATUSES,
    EMAIL_LABELS,
    EVENT_STATUSES,
    EVENT_TYPES,
    GENDER_OPTIONS,
    LEAVING_REASONS,
    MENTORSHIP_STATUSES,
    PAYMENT_METHODS,
    PHONE_LABELS,
    PLEDGE_STATUSES,
    RSVP_STATUSES,
    SALARY_BANDS,
    SECTORS,
    SESSION_FORMATS,
    STATUSES,
    VOLUNTEER_ACTIVITY_TYPES,
)
from education_system.systems.sixth_form.domain.learners.alumni.integrations import MEDIA_KINDS
from education_system.systems.sixth_form.domain.learners.alumni.compliance import PROTECTED_CHARS
from education_system.systems.sixth_form.domain.learners.alumni.engagement import (
    CHAPTER_KINDS,
    MILESTONE_KINDS,
)
from education_system.systems.sixth_form.domain.learners.alumni.comms import (
    COMM_CHANNELS,
    COMM_STATUSES,
)
from education_system.systems.sixth_form.domain.learners.alumni.db import ValidationError
from ._common import (
    _ask_choice,
    _pick_alumnus_dialog,
    _prompt_string,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel


# ── Per-alumnus: SMS history + sender ────────────────────────────

class SMSTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="SMS")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Body:").pack(side="left")
        self.body = ttk.Entry(bar, width=46); self.body.pack(side="left",
                                                                   padx=4)
        ttk.Button(bar, text="Send",
                     command=self._send).pack(side="left", padx=4)
        cols = ("id", "sent_at", "status", "body")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "sent_at": 150, "status": 80, "body": 460}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in alumni_messaging.list_sms_for(self.alumni_id):
            self.tree.insert("", "end", iid=str(s.sms_id),
                              values=(s.sms_id, s.sent_at, s.status,
                                      s.body))

    def _send(self) -> None:
        body = self.body.get().strip()
        if not body: return
        try:
            alumni_messaging.send_sms_to_alumnus(self.alumni_id, body)
        except Exception as e:
            messagebox.showerror("Send", str(e)); return
        self.body.delete(0, "end")
        self.refresh()


# ── Top-level: Templates library ─────────────────────────────────

class TemplatesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Templates")
        cols = ("id", "name", "version", "category", "subject")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 200, "version": 70,
                    "category": 140, "subject": 320}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="New",
                     command=self._new).pack(side="left")
        ttk.Button(bar, text="View",
                     command=self._view).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left")
        ttk.Button(bar, text="Preview (per alumnus)",
                     command=self._preview).pack(side="left", padx=12)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for t in alumni_messaging.list_email_templates(latest_only=False):
            self.tree.insert(
                "", "end", iid=str(t.template_id),
                values=(t.template_id, t.name, t.version,
                          t.category or "—", t.subject))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        TemplateDialog(self.frame.winfo_toplevel(),
                          on_save=self.refresh)

    def _view(self) -> None:
        tid = self._selected()
        if tid is None: return
        t = next((x for x in alumni_messaging.list_email_templates(latest_only=False)
                    if x.template_id == tid), None)
        if t is None: return
        win = make_toplevel(self.frame.winfo_toplevel())
        win.title(f"{t.name} v{t.version}")
        win.geometry("700x500")
        ttk.Label(win, text=f"Subject: {t.subject}",
                    font=("TkDefaultFont", 11, "bold")
                    ).pack(anchor="w", padx=8, pady=8)
        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", t.body); txt.configure(state="disabled")

    def _delete(self) -> None:
        tid = self._selected()
        if tid is None: return
        if not messagebox.askyesno("Delete",
                                      f"Delete template #{tid}?"):
            return
        alumni_messaging.delete_email_template(tid)
        self.refresh()

    def _preview(self) -> None:
        tid = self._selected()
        if tid is None: return
        t = next((x for x in alumni_messaging.list_email_templates(latest_only=False)
                    if x.template_id == tid), None)
        if t is None: return
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        try:
            subj, body = alumni_messaging.render_template(t, aid)
        except Exception as e:
            messagebox.showerror("Preview", str(e)); return
        win = make_toplevel(self.frame.winfo_toplevel())
        win.title(f"Preview — {t.name}"); win.geometry("700x500")
        ttk.Label(win, text=f"Subject: {subj}",
                    font=("TkDefaultFont", 11, "bold")
                    ).pack(anchor="w", padx=8, pady=8)
        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", body); txt.configure(state="disabled")


class TemplateDialog:
    def __init__(self, parent: tk.Misc, *,
                 on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("New template")
        self.win.transient(parent); grab_when_viewable(self.win)
        frm = ttk.Frame(self.win, padding=10); frm.pack(fill="both",
                                                          expand=True)
        ttk.Label(frm, text="Name:").grid(row=0, column=0, sticky="w")
        self.name = ttk.Entry(frm, width=40); self.name.grid(
            row=0, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Category:").grid(row=1, column=0,
                                                  sticky="w")
        self.cat = ttk.Entry(frm, width=40); self.cat.grid(
            row=1, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Subject:").grid(row=2, column=0, sticky="w")
        self.subj = ttk.Entry(frm, width=40); self.subj.grid(
            row=2, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Body:").grid(row=3, column=0, sticky="nw")
        self.body = tk.Text(frm, width=60, height=14)
        self.body.grid(row=3, column=1, sticky="w", pady=2)
        bar = ttk.Frame(frm); bar.grid(row=4, column=0, columnspan=2,
                                          pady=8, sticky="e")
        ttk.Button(bar, text="Save",
                     command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel",
                     command=self.win.destroy
                     ).pack(side="right", padx=4)

    def _save(self) -> None:
        try:
            alumni_messaging.create_email_template(
                self.name.get(), self.subj.get(),
                self.body.get("1.0", "end").rstrip(),
                category=self.cat.get() or None)
        except Exception as e:
            messagebox.showerror("Save", str(e)); return
        self.on_save(); self.win.destroy()


# ── Top-level: Drip campaigns ────────────────────────────────────

class DripTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Drip")
        cols = ("id", "name", "status", "description")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 220, "status": 90,
                    "description": 400}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="New",
                     command=self._new).pack(side="left")
        ttk.Button(bar, text="Steps…",
                     command=self._steps).pack(side="left", padx=4)
        ttk.Button(bar, text="Set status",
                     command=self._status).pack(side="left")
        ttk.Button(bar, text="Enroll alumnus",
                     command=self._enroll).pack(side="left", padx=4)
        ttk.Button(bar, text="Tick now",
                     command=self._tick).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for d in alumni_messaging.list_drip_campaigns():
            self.tree.insert(
                "", "end", iid=str(d.drip_id),
                values=(d.drip_id, d.name, d.status,
                          d.description or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        name = _prompt_string(self.frame.winfo_toplevel(),
                                 "New drip", "Name:")
        if not name: return
        try:
            alumni_messaging.create_drip_campaign(name)
        except Exception as e:
            messagebox.showerror("Create", str(e)); return
        self.refresh()

    def _steps(self) -> None:
        did = self._selected()
        if did is None: return
        DripStepsDialog(self.frame.winfo_toplevel(), did)

    def _status(self) -> None:
        did = self._selected()
        if did is None: return
        st = _ask_choice(self.frame, "Status", list(DRIP_STATUSES))
        if not st: return
        try:
            alumni_messaging.set_drip_status(did, st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()

    def _enroll(self) -> None:
        did = self._selected()
        if did is None: return
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        try:
            alumni_messaging.enroll_in_drip(did, aid)
        except Exception as e:
            messagebox.showerror("Enroll", str(e)); return

    def _tick(self) -> None:
        ticks = alumni_messaging.tick_drip()
        messagebox.showinfo("Tick", f"{len(ticks)} tick(s) dispatched")


class DripStepsDialog:
    def __init__(self, parent: tk.Misc, drip_id: int) -> None:
        self.drip_id = drip_id
        self.win = tk.Toplevel(parent)
        self.win.title(f"Steps — drip #{drip_id}")
        self.win.transient(parent); self.win.geometry("700x500")
        cols = ("position", "delay_days", "template_id",
                  "subject")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"position": 80, "delay_days": 90,
                    "template_id": 100, "subject": 420}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Button(bar, text="Add step",
                     command=self._add).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in alumni_messaging.list_drip_steps(self.drip_id):
            self.tree.insert(
                "", "end", iid=str(s.step_id),
                values=(s.position, s.delay_days,
                          s.template_id or "—",
                          s.subject or f"(body of step {s.position})"))

    def _add(self) -> None:
        dlg = tk.Toplevel(self.win); dlg.title("Add drip step")
        dlg.transient(self.win); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Position:").grid(row=0, column=0,
                                                  sticky="w")
        pos = ttk.Entry(frm, width=6); pos.grid(row=0, column=1,
                                                      sticky="w")
        ttk.Label(frm, text="Delay days:").grid(row=1, column=0,
                                                   sticky="w")
        delay = ttk.Entry(frm, width=6); delay.insert(0, "0")
        delay.grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="Template id (optional):").grid(
            row=2, column=0, sticky="w")
        tid = ttk.Entry(frm, width=6); tid.grid(row=2, column=1,
                                                      sticky="w")
        ttk.Label(frm, text="Subject (if no template):").grid(
            row=3, column=0, sticky="w")
        subj = ttk.Entry(frm, width=40); subj.grid(row=3, column=1,
                                                         sticky="w", pady=2)
        ttk.Label(frm, text="Body:").grid(row=4, column=0, sticky="nw")
        body = tk.Text(frm, width=40, height=6); body.grid(
            row=4, column=1, sticky="w", pady=2)

        def ok() -> None:
            try:
                alumni_messaging.add_drip_step(
                    self.drip_id,
                    position=int(pos.get() or "0"),
                    delay_days=int(delay.get() or "0"),
                    template_id=int(tid.get()) if tid.get() else None,
                    subject=subj.get() or None,
                    body=body.get("1.0", "end").strip() or None)
            except Exception as e:
                messagebox.showerror("Add step", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=5, column=1, sticky="e", pady=8)


# ── Top-level: A/B tests ─────────────────────────────────────────

class ABTestsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="A/B tests")
        cols = ("id", "name", "sent_at", "variants")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 240, "sent_at": 160,
                    "variants": 300}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="New",
                     command=self._new).pack(side="left")
        ttk.Button(bar, text="Add variant",
                     command=self._variant).pack(side="left", padx=4)
        ttk.Button(bar, text="Assign audience",
                     command=self._assign).pack(side="left")
        ttk.Button(bar, text="Results",
                     command=self._results).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        import sqlite3 as _sq
        with _sq.connect(str(alumni_db.DB_PATH)) as conn:
            conn.row_factory = _sq.Row
            rows = conn.execute(
                "SELECT * FROM alumni_ab_tests "
                "ORDER BY created_at DESC").fetchall()
        for r in rows:
            variants = ", ".join(
                v.label for v in alumni_messaging.list_ab_variants(r["test_id"]))
            self.tree.insert(
                "", "end", iid=str(r["test_id"]),
                values=(r["test_id"], r["name"],
                          r["sent_at"] or "—", variants))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        name = _prompt_string(self.frame.winfo_toplevel(),
                                 "New A/B test", "Name:")
        if not name: return
        try:
            alumni_messaging.create_ab_test(name)
        except Exception as e:
            messagebox.showerror("Create", str(e)); return
        self.refresh()

    def _variant(self) -> None:
        tid = self._selected()
        if tid is None: return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Variant"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Label:").grid(row=0, column=0, sticky="w")
        lbl = ttk.Entry(frm, width=6); lbl.grid(row=0, column=1,
                                                      sticky="w")
        ttk.Label(frm, text="Subject:").grid(row=1, column=0, sticky="w")
        subj = ttk.Entry(frm, width=40); subj.grid(row=1, column=1,
                                                         sticky="w", pady=2)
        ttk.Label(frm, text="Body:").grid(row=2, column=0, sticky="nw")
        body = tk.Text(frm, width=40, height=6); body.grid(
            row=2, column=1, sticky="w", pady=2)

        def ok() -> None:
            try:
                alumni_messaging.add_ab_variant(tid, label=lbl.get(),
                    subject=subj.get(),
                    body=body.get("1.0", "end").rstrip())
            except Exception as e:
                messagebox.showerror("Add", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=3, column=1, sticky="e", pady=8)

    def _assign(self) -> None:
        tid = self._selected()
        if tid is None: return
        try:
            counts = alumni_messaging.assign_ab_audience(tid)
        except Exception as e:
            messagebox.showerror("Assign", str(e)); return
        messagebox.showinfo("Assign", repr(counts))

    def _results(self) -> None:
        tid = self._selected()
        if tid is None: return
        win = make_toplevel(self.frame.winfo_toplevel())
        win.title(f"Results — A/B #{tid}"); win.geometry("520x320")
        cols = ("label", "sent", "opens", "open_rate",
                  "clicks", "click_rate")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=80, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for r in alumni_messaging.ab_test_results(tid):
            tree.insert("", "end",
                          values=(r.label, r.sent, r.opens,
                                  f"{r.open_rate}%",
                                  r.clicks, f"{r.click_rate}%"))


# ── Top-level: Newsletters ───────────────────────────────────────

class NewslettersTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Newsletters")
        cols = ("id", "issue", "title", "status", "published_at")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "issue": 140, "title": 300,
                    "status": 90, "published_at": 160}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="New",
                     command=self._new).pack(side="left")
        ttk.Button(bar, text="Sections…",
                     command=self._sections).pack(side="left", padx=4)
        ttk.Button(bar, text="Publish",
                     command=self._publish).pack(side="left")
        ttk.Button(bar, text="HTML preview",
                     command=self._preview).pack(side="left", padx=4)
        ttk.Button(bar, text="Audience",
                     command=self._audience).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for n in alumni_messaging.list_newsletters():
            self.tree.insert(
                "", "end", iid=str(n.newsletter_id),
                values=(n.newsletter_id, n.issue, n.title,
                          n.status, n.published_at or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("New newsletter")
        dlg.transient(self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Issue:").grid(row=0, column=0, sticky="w")
        issue = ttk.Entry(frm, width=24); issue.grid(row=0, column=1,
                                                          sticky="w")
        ttk.Label(frm, text="Title:").grid(row=1, column=0, sticky="w")
        title = ttk.Entry(frm, width=40); title.grid(row=1, column=1,
                                                          sticky="w")

        def ok() -> None:
            try:
                alumni_messaging.create_newsletter(issue.get(), title.get())
            except Exception as e:
                messagebox.showerror("Create", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=2, column=1, sticky="e", pady=8)

    def _sections(self) -> None:
        nid = self._selected()
        if nid is None: return
        NewsletterSectionsDialog(self.frame.winfo_toplevel(), nid)

    def _publish(self) -> None:
        nid = self._selected()
        if nid is None: return
        if not messagebox.askyesno("Publish",
                                      f"Publish newsletter #{nid}?"):
            return
        try:
            alumni_messaging.publish_newsletter(nid)
        except Exception as e:
            messagebox.showerror("Publish", str(e)); return
        self.refresh()

    def _preview(self) -> None:
        nid = self._selected()
        if nid is None: return
        try:
            html = alumni_messaging.render_newsletter_html(nid)
        except Exception as e:
            messagebox.showerror("Preview", str(e)); return
        win = make_toplevel(self.frame.winfo_toplevel())
        win.title(f"Preview — newsletter #{nid}")
        win.geometry("800x600")
        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", html); txt.configure(state="disabled")

    def _audience(self) -> None:
        nid = self._selected()
        if nid is None: return
        try:
            rows = alumni_messaging.newsletter_audience(nid)
        except Exception as e:
            messagebox.showerror("Audience", str(e)); return
        messagebox.showinfo("Audience",
                                f"{len(rows)} alumni would receive this")


class NewsletterSectionsDialog:
    def __init__(self, parent: tk.Misc, newsletter_id: int) -> None:
        self.newsletter_id = newsletter_id
        self.win = tk.Toplevel(parent)
        self.win.title(f"Sections — newsletter #{newsletter_id}")
        self.win.transient(parent); self.win.geometry("700x500")
        cols = ("position", "heading")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"position": 80, "heading": 600}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Button(bar, text="Add",
                     command=self._add).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in alumni_messaging.list_newsletter_sections(self.newsletter_id):
            self.tree.insert(
                "", "end", iid=str(s.section_id),
                values=(s.position, s.heading))

    def _add(self) -> None:
        dlg = tk.Toplevel(self.win); dlg.title("Section")
        dlg.transient(self.win); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Heading:").grid(row=0, column=0, sticky="w")
        heading = ttk.Entry(frm, width=40); heading.grid(row=0, column=1,
                                                              sticky="w")
        ttk.Label(frm, text="Body:").grid(row=1, column=0, sticky="nw")
        body = tk.Text(frm, width=60, height=10)
        body.grid(row=1, column=1, sticky="w", pady=2)

        def ok() -> None:
            try:
                alumni_messaging.add_newsletter_section(
                    self.newsletter_id, heading=heading.get(),
                    body=body.get("1.0", "end").rstrip())
            except Exception as e:
                messagebox.showerror("Add", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=2, column=1, sticky="e", pady=8)


# ── Top-level: Open/click tracking ───────────────────────────────

class TrackingTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Tracking")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Campaign ref:").pack(side="left")
        self.ref = ttk.Entry(bar, width=20); self.ref.pack(side="left",
                                                                padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Mint pixel…",
                     command=self._pixel).pack(side="left", padx=12)
        ttk.Button(bar, text="Mint link…",
                     command=self._link).pack(side="left")
        self.summary = ttk.Label(self.frame, text="",
                                    font=("TkDefaultFont", 11, "bold"))
        self.summary.pack(anchor="w", padx=8, pady=(0, 8))
        cols = ("token", "kind", "target_url", "campaign_ref",
                  "created_at")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"token": 220, "kind": 70, "target_url": 280,
                    "campaign_ref": 140, "created_at": 160}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        ref = self.ref.get().strip() or None
        import sqlite3 as _sq
        with _sq.connect(str(alumni_db.DB_PATH)) as conn:
            conn.row_factory = _sq.Row
            if ref:
                rows = conn.execute(
                    "SELECT * FROM alumni_track_links "
                    "WHERE campaign_ref = ? "
                    "ORDER BY created_at DESC", (ref,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM alumni_track_links "
                    "ORDER BY created_at DESC LIMIT 200").fetchall()
        for r in rows:
            self.tree.insert(
                "", "end",
                values=(r["token"], r["kind"],
                          r["target_url"] or "—",
                          r["campaign_ref"] or "—",
                          r["created_at"]))
        s = alumni_messaging.tracking_summary(campaign_ref=ref)
        self.summary.configure(
            text=f"sends={s.sends}  opens={s.opens}  "
                 f"clicks={s.clicks}  unique_opens={s.unique_opens}")

    def _pixel(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        ref = self.ref.get().strip() or None
        tok = alumni_messaging.create_tracking_pixel(aid, campaign_ref=ref)
        messagebox.showinfo("Token", tok)
        self.refresh()

    def _link(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        url = _prompt_string(self.frame.winfo_toplevel(),
                                "Tracked link", "Target URL:")
        if not url: return
        ref = self.ref.get().strip() or None
        tok = alumni_messaging.create_tracked_link(url, alumni_id=aid,
                                          campaign_ref=ref)
        messagebox.showinfo("Token", tok)
        self.refresh()
