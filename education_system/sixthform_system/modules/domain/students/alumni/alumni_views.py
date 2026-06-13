"""Tkinter views for Sixth Form Alumni."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.students.alumni import (
    alumni as data,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.sixthform_system.modules.domain.students.alumni.alumni import (
    ACHIEVEMENT_CATEGORIES,
    Alumnus,
    CAMPAIGN_STATUSES,
    APPLICATION_STATUSES,
    BEQUEST_STATUSES,
    CUSTOM_FIELD_TYPES,
    ERASURE_STATUSES,
    MEDIA_KINDS,
    PROTECTED_CHARS,
    WEBHOOK_EVENT_TYPES,
    CHAPTER_KINDS,
    CHAPTER_ROLES,
    CONNECTION_KINDS,
    DIRECTORY_CONSENT_SCOPE,
    DONOR_STAGES,
    DRIP_STATUSES,
    JOB_STATUSES,
    JOB_TYPES,
    MILESTONE_KINDS,
    NEET_STATUSES,
    NEWSLETTER_STATUSES,
    PROFICIENCY_LEVELS,
    RECURRING_FREQS,
    RECURRING_STATUSES,
    SAFEGUARDING_STATUSES,
    SOCIAL_PLATFORMS,
    TRACK_KINDS,
    COMM_CHANNELS,
    COMM_STATUSES,
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
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


class _SoloNotebook(ttk.Frame):
    """Frame that quacks like ``ttk.Notebook`` for existing tab
    classes. Each ``…Tab`` class does ``self.frame = ttk.Frame(nb);
    nb.add(self.frame, text=…)``; we accept ``add()`` and just pack
    the child, so the tab renders into a generic content pane with
    no tab-bar chrome."""

    def add(self, child: tk.Widget, text: str = "", **_: object) -> None:
        child.pack(fill="both", expand=True)


def _alumni_nav() -> list[tuple[str, list[tuple[str, type]]]]:
    """Top-level navigation, grouped by purpose. Built lazily so the
    Tab class names below resolve at call time, not import time."""
    return [
        ("Alumni records", [
            ("Alumni",             AlumniTab),
            ("Summary",            SummaryTab),
            ("Unarchived leavers", UnarchivedLeaversTab),
            ("Admin",              AdminTab),
        ]),
        ("Events", [
            ("Events",          EventsTab),
            ("Reunion planner", ReunionPlannerTab),
        ]),
        ("Fundraising", [
            ("Campaigns",      CampaignsTab),
            ("Recurring",      RecurringDonationsTab),
            ("Donor pipeline", DonorPipelineTab),
            ("Funds",          FundsTab),
            ("Bequests",       BequestsTab),
            ("Matched giving", MatchedGivingTab),
        ]),
        ("Career & network", [
            ("Chapters",            ChaptersTab),
            ("Employers",           EmployersTab),
            ("Jobs",                JobsBoardTab),
            ("Internships",         InternshipsBoardTab),
            ("Mentor match",        MentorMatchTab),
            ("Safeguarding alerts", SafeguardingAlertsTab),
        ]),
        ("Engagement & outreach", [
            ("Re-engagement",    ReEngagementTab),
            ("Milestones",       MilestonesTab),
            ("Lost contact",     LostContactTab),
            ("Public directory", DirectoryTab),
        ]),
        ("Communications", [
            ("Templates",   TemplatesTab),
            ("Drip",        DripTab),
            ("A/B tests",   ABTestsTab),
            ("Newsletters", NewslettersTab),
            ("Tracking",    TrackingTab),
        ]),
        ("Outcomes", [
            ("NEET",            NEETTab),
            ("HESA benchmarks", HESATab),
        ]),
        ("Reports & compliance", [
            ("Reports",        ReportsTab),
            ("Data quality",   DataQualityTab),
            ("Dedupe buckets", DedupeBucketsTab),
            ("Erasure",        ErasureTab),
            ("Webhooks",       WebhooksTab),
            ("Custom fields",  CustomFieldsTab),
        ]),
    ]


def open_alumni_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Alumni — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    style = ttk.Style(win)
    # Reuse the main GUI's category-button look-and-feel if it has
    # been registered; otherwise create the style here so the alumni
    # window matches when launched stand-alone.
    try:
        style.configure("Category.TButton",
                          padding=8, font=("", 10, "bold"))
    except tk.TclError:
        pass

    outer = ttk.Frame(win, padding=10)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(0, weight=0)
    outer.columnconfigure(1, weight=1)
    outer.rowconfigure(0, weight=1)

    # ── Left-hand nav (collapsible categories) ──────────────────────
    nav = ttk.LabelFrame(outer, text="Navigation", padding=5)
    nav.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    nav.rowconfigure(0, weight=1)
    nav.columnconfigure(0, weight=1)

    nav_canvas = tk.Canvas(nav, highlightthickness=0, width=240)
    nav_canvas.grid(row=0, column=0, sticky="nsew")
    vs = ttk.Scrollbar(nav, orient="vertical",
                          command=nav_canvas.yview)
    vs.grid(row=0, column=1, sticky="ns")
    nav_canvas.configure(yscrollcommand=vs.set)

    inner = ttk.Frame(nav_canvas)
    nav_window = nav_canvas.create_window(
        (0, 0), window=inner, anchor="nw")
    inner.bind(
        "<Configure>",
        lambda _e: nav_canvas.configure(
            scrollregion=nav_canvas.bbox("all")))
    nav_canvas.bind(
        "<Configure>",
        lambda e: nav_canvas.itemconfigure(nav_window, width=e.width))

    # ── Right-hand content pane ─────────────────────────────────────
    content = ttk.Frame(outer, padding=5)
    content.grid(row=0, column=1, sticky="nsew")

    def _mount(tab_cls: type, label: str) -> None:
        """Clear the content pane and instantiate ``tab_cls`` into
        a fresh _SoloNotebook so the tab class's existing
        ``nb.add(...)`` call works unchanged."""
        for w in content.winfo_children():
            w.destroy()
        title = ttk.Label(content, text=label,
                            font=("", 12, "bold"))
        title.pack(anchor="w", pady=(0, 6))
        host = _SoloNotebook(content)
        host.pack(fill="both", expand=True)
        try:
            tab_cls(host)
        except Exception as exc:  # noqa: BLE001 - surface to user
            logger.exception("Failed to mount %s", tab_cls.__name__)
            messagebox.showerror("Open", str(exc))

    def _make_category(label: str,
                          items: list[tuple[str, type]]) -> None:
        container = ttk.Frame(inner)
        container.pack(fill="x", pady=2, padx=5)
        state = {"expanded": False, "sub": None}
        btn = ttk.Button(container, text=f"{label}  ▶",
                            style="Category.TButton")
        btn.pack(fill="x")

        def toggle() -> None:
            if state["expanded"]:
                if state["sub"] is not None:
                    state["sub"].pack_forget()
                btn.configure(text=f"{label}  ▶")
                state["expanded"] = False
            else:
                if state["sub"] is None:
                    sub = ttk.Frame(container)
                    for item_label, tab_cls in items:
                        ttk.Button(
                            sub, text=item_label,
                            command=lambda c=tab_cls,
                                            lbl=item_label:
                                       _mount(c, lbl)
                            ).pack(fill="x", pady=1, padx=4)
                    state["sub"] = sub
                state["sub"].pack(fill="x", pady=(2, 4))
                btn.configure(text=f"{label}  ▼")
                state["expanded"] = True
            try:
                inner.update_idletasks()
                nav_canvas.configure(
                    scrollregion=nav_canvas.bbox("all"))
            except tk.TclError:
                pass

        btn.configure(command=toggle)

    for cat_label, cat_items in _alumni_nav():
        _make_category(cat_label, cat_items)

    # Open the Alumni list by default so the window isn't blank.
    _mount(AlumniTab, "Alumni")


def _today() -> str:
    return _dt.date.today().isoformat()


def _money_str(pence: int | None) -> str:
    if pence is None:
        return "—"
    return f"£{pence / 100:,.2f}"


# ══ Alumni tab ════════════════════════════════════════════════════

class AlumniTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Alumni")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Search:").pack(side="left")
        self.f_search = ttk.Entry(bar, width=18)
        self.f_search.pack(side="left", padx=(2, 10))
        self.f_search.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Year:").pack(side="left")
        self.f_year = ttk.Entry(bar, width=8)
        self.f_year.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Destination:").pack(side="left")
        self.f_dest = ttk.Combobox(bar, values=("",) + DESTINATION_TYPES,
                                     state="readonly", width=18)
        self.f_dest.current(0)
        self.f_dest.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        self.contactable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Contactable only",
                          variable=self.contactable_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "year", "destination", "detail",
                "employer", "email", "status", "opt_in")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "name": 180, "year": 60,
                  "destination": 130, "detail": 220,
                  "employer": 140, "email": 180,
                  "status": 100, "opt_in": 60}
        headings = {"id": "ID", "name": "Name", "year": "Year",
                    "destination": "Destination", "detail": "Detail",
                    "employer": "Employer", "email": "Email",
                    "status": "Status", "opt_in": "Opt-in"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c in ("year", "opt_in") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Active",       background="#d8f4d8")
        self.tree.tag_configure("Lost Contact", background="#fff7d0")
        self.tree.tag_configure("Deceased",     background="#eeeeee")
        self.tree.tag_configure("Opt-out",      background="#eeeeee")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="New (manual)",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(actions, text="Archive student…",
                    command=self._archive).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Details…",
                    command=self._open_details).pack(side="left", padx=4)
        ttk.Button(actions, text="Audit log",
                    command=self._open_audit).pack(side="left", padx=4)
        ttk.Button(actions, text="Record contact",
                    command=self._record_contact).pack(side="left", padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_search.delete(0, "end")
        self.f_year.delete(0, "end")
        self.f_dest.current(0)
        self.f_status.current(0)
        self.contactable_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_alumni(
                search=self.f_search.get().strip() or None,
                leaving_year=self.f_year.get().strip() or None,
                destination_type=self.f_dest.get() or None,
                status=self.f_status.get() or None,
                contactable_only=self.contactable_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for a in rows:
            tags = (a.status,) if a.status in STATUSES else ()
            self.tree.insert("", "end", iid=str(a.alumni_id), values=(
                a.alumni_id, a.full_name, a.leaving_year or "—",
                a.destination_type,
                a.destination_detail or "—",
                a.current_employer or "—",
                a.email or "—", a.status,
                "✓" if a.opt_in_contact else "",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} alumnus/alumni.")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected(self) -> Alumnus | None:
        aid = self._selected_id()
        if aid is None:
            return None
        return data.get_alumnus(aid)

    def _view_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("View", "Select an alumnus first.")
            return
        lines = [
            f"Alumnus       : #{a.alumni_id}",
            f"Name          : {a.display_name}",
            f"Original id   : {a.original_student_id or '—'}",
            f"DOB           : {a.dob or '—'}",
            f"Leaving year  : {a.leaving_year or '—'}",
            f"Leaving date  : {a.leaving_date or '—'}",
            f"Leaving reason: {a.leaving_reason or '—'}",
            f"Destination   : {a.destination_type}",
            f"  Detail      : {a.destination_detail or '—'}",
            f"Current role  : {a.current_role or '—'}",
            f"Employer      : {a.current_employer or '—'}",
            f"Location      : {a.current_location or '—'}",
            f"Email         : {a.email or '—'}",
            f"Phone         : {a.phone or '—'}",
            f"Address       : {a.address or '—'}",
            f"LinkedIn      : {a.linkedin or '—'}",
            f"Other social  : {a.other_social or '—'}",
            f"Opt-in        : {'yes' if a.opt_in_contact else 'no'}",
            f"Status        : {a.status}",
            f"Last contact  : {a.last_contacted or '—'}",
        ]
        if a.notes:
            lines.append("")
            lines.append("Notes:")
            lines.append(a.notes)
        messagebox.showinfo(f"Alumnus #{a.alumni_id}", "\n".join(lines))

    def _new(self) -> None:
        AlumnusDialog(self.frame.winfo_toplevel(),
                        existing=None, on_save=self.refresh)

    def _archive(self) -> None:
        ArchiveDialog(self.frame.winfo_toplevel(),
                       on_save=self.refresh)

    def _edit_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Edit", "Select an alumnus first.")
            return
        AlumnusDialog(self.frame.winfo_toplevel(),
                        existing=a, on_save=self.refresh)

    def _open_details(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Details", "Select an alumnus first.")
            return
        DetailWindow(self.frame.winfo_toplevel(), a)

    def _open_audit(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Audit log",
                                  "Select an alumnus first.")
            return
        AuditLogDialog(self.frame.winfo_toplevel(), a.alumni_id)

    def _record_contact(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Contact",
                                  "Select an alumnus first.")
            return
        try:
            data.record_contact(a.alumni_id)
        except Exception as e:
            messagebox.showerror("Contact", str(e))
            return
        self.refresh()

    def _status_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Status",
                                  "Select an alumnus first.")
            return
        StatusDialog(self.frame.winfo_toplevel(), a,
                       on_save=self.refresh)

    def _delete_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Delete",
                                  "Select an alumnus first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete alumnus #{a.alumni_id} "
                            f"({a.full_name})?"):
            return
        try:
            data.delete_alumnus(a.alumni_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Button(self.frame, text="Refresh",
                    command=self.refresh).pack(side="top", anchor="w",
                                                 padx=8, pady=(8, 4))
        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        summ = data.summary()
        lines = [
            f"Total alumni      : {summ.total}",
            f"Contactable       : {summ.contactable}",
            f"No contact method : {summ.no_contact_method}",
            f"Most recent year  : {summ.most_recent_year or '—'}",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("By destination:")
        for d in DESTINATION_TYPES:
            n = summ.by_destination.get(d, 0)
            if n:
                lines.append(f"  {d:<18} : {n}")
        if summ.by_leaving_year:
            lines.append("")
            lines.append("By leaving year:")
            for year, n in list(summ.by_leaving_year.items())[:15]:
                lines.append(f"  {year} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Alumnus,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — alumnus #{existing.alumni_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_status(self.existing.alumni_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ArchiveDialog:
    def __init__(self, parent: tk.Misc,
                 on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Archive student → alumni")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        students = sorted(student_data.list_students(),
                           key=lambda s: s.student_id)
        self._ids = [s.student_id for s in students]
        ttk.Label(form, text="Student:").grid(row=0, column=0,
                                                 sticky="e", pady=4)
        self.student_cb = ttk.Combobox(
            form,
            values=[f"{s.student_id} — {s.full_name}"
                     for s in students],
            state="readonly", width=44)
        if students:
            self.student_cb.current(0)
        self.student_cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Leaving year:").grid(row=1, column=0,
                                                      sticky="e", pady=4)
        self.year_e = ttk.Entry(form, width=8)
        self.year_e.insert(0, str(_dt.date.today().year))
        self.year_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Leaving date:").grid(row=2, column=0,
                                                      sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Reason:").grid(row=3, column=0,
                                                sticky="e", pady=4)
        self.reason_cb = ttk.Combobox(form, values=LEAVING_REASONS,
                                         state="readonly", width=22)
        self.reason_cb.set(DEFAULT_LEAVING_REASON)
        self.reason_cb.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Destination:").grid(row=4, column=0,
                                                     sticky="e", pady=4)
        self.dest_cb = ttk.Combobox(form, values=DESTINATION_TYPES,
                                       state="readonly", width=18)
        self.dest_cb.set(DEFAULT_DESTINATION)
        self.dest_cb.grid(row=4, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Destination detail:").grid(row=5, column=0,
                                                            sticky="e",
                                                            pady=4)
        self.detail_e = ttk.Entry(form, width=44)
        self.detail_e.grid(row=5, column=1, sticky="w", padx=6)

        self.delete_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form,
                          text="Also delete the student row "
                                "(cascade-removes history)",
                          variable=self.delete_var).grid(
            row=6, column=1, sticky="w", padx=6, pady=4)

        bar = ttk.Frame(form)
        bar.grid(row=7, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Archive",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.student_cb.current()
        if idx < 0:
            messagebox.showerror("Archive", "Pick a student")
            return
        sid = self._ids[idx]
        try:
            data.archive_student(
                sid,
                leaving_year=self.year_e.get().strip() or None,
                leaving_date=self.date_e.get().strip() or None,
                leaving_reason=self.reason_cb.get().strip() or None,
                destination_type=self.dest_cb.get().strip() or
                                  DEFAULT_DESTINATION,
                destination_detail=self.detail_e.get().strip() or None,
                delete_student=self.delete_var.get(),
            )
        except Exception as e:
            messagebox.showerror("Archive failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AlumnusDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Alumnus | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Alumnus" if existing else "New Alumnus")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        def add_row(label: str, widget: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            widget.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.first_e = ttk.Entry(form, width=24)
        if self.existing:
            self.first_e.insert(0, self.existing.first_name)
        add_row("First name:", self.first_e)

        self.last_e = ttk.Entry(form, width=24)
        if self.existing:
            self.last_e.insert(0, self.existing.last_name)
        add_row("Last name:", self.last_e)

        self.preferred_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.preferred_name:
            self.preferred_e.insert(0, self.existing.preferred_name)
        add_row("Preferred name:", self.preferred_e)

        self.pronouns_e = ttk.Entry(form, width=18)
        if self.existing and self.existing.pronouns:
            self.pronouns_e.insert(0, self.existing.pronouns)
        add_row("Pronouns:", self.pronouns_e)

        self.gender_cb = ttk.Combobox(
            form, values=("",) + GENDER_OPTIONS,
            state="readonly", width=22)
        self.gender_cb.set((self.existing.gender or "")
                              if self.existing else "")
        add_row("Gender:", self.gender_cb)

        self.dob_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.dob:
            self.dob_e.insert(0, self.existing.dob)
        add_row("DOB:", self.dob_e)

        self.year_e = ttk.Entry(form, width=8)
        if self.existing and self.existing.leaving_year:
            self.year_e.insert(0, self.existing.leaving_year)
        add_row("Leaving year:", self.year_e)

        self.date_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.leaving_date:
            self.date_e.insert(0, self.existing.leaving_date)
        add_row("Leaving date:", self.date_e)

        self.reason_cb = ttk.Combobox(form, values=("",) + LEAVING_REASONS,
                                         state="readonly", width=22)
        self.reason_cb.set((self.existing.leaving_reason or "")
                              if self.existing else "")
        add_row("Leaving reason:", self.reason_cb)

        self.dest_cb = ttk.Combobox(form, values=DESTINATION_TYPES,
                                       state="readonly", width=18)
        self.dest_cb.set((self.existing.destination_type
                            if self.existing else DEFAULT_DESTINATION))
        add_row("Destination:", self.dest_cb)

        self.dest_detail_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.destination_detail:
            self.dest_detail_e.insert(0, self.existing.destination_detail)
        add_row("Destination detail:", self.dest_detail_e)

        self.role_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.current_role:
            self.role_e.insert(0, self.existing.current_role)
        add_row("Current role:", self.role_e)

        self.employer_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.current_employer:
            self.employer_e.insert(0, self.existing.current_employer)
        add_row("Employer:", self.employer_e)

        self.sector_cb = ttk.Combobox(
            form, values=("",) + SECTORS, state="readonly", width=22)
        self.sector_cb.set((self.existing.current_sector or "")
                              if self.existing else "")
        add_row("Sector:", self.sector_cb)

        self.location_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.current_location:
            self.location_e.insert(0, self.existing.current_location)
        add_row("Location:", self.location_e)

        self.country_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.country:
            self.country_e.insert(0, self.existing.country)
        add_row("Country:", self.country_e)

        self.region_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.region:
            self.region_e.insert(0, self.existing.region)
        add_row("Region:", self.region_e)

        self.email_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.email:
            self.email_e.insert(0, self.existing.email)
        add_row("Email:", self.email_e)

        self.phone_e = ttk.Entry(form, width=20)
        if self.existing and self.existing.phone:
            self.phone_e.insert(0, self.existing.phone)
        add_row("Phone:", self.phone_e)

        self.linkedin_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.linkedin:
            self.linkedin_e.insert(0, self.existing.linkedin)
        add_row("LinkedIn:", self.linkedin_e)

        self.photo_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.photo_path:
            self.photo_e.insert(0, self.existing.photo_path)
        add_row("Photo path:", self.photo_e)

        ttk.Label(form, text="Bio:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
        self.bio_t = tk.Text(form, width=44, height=3)
        if self.existing and self.existing.bio:
            self.bio_t.insert("1.0", self.existing.bio)
        self.bio_t.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        self.opt_var = tk.BooleanVar(
            value=(self.existing.opt_in_contact
                   if self.existing else False))
        ttk.Checkbutton(form, text="Opt-in to contact",
                          variable=self.opt_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=3)
        r += 1

        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status
                              if self.existing else DEFAULT_STATUS)
        add_row("Status:", self.status_cb)

        self.last_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.last_contacted:
            self.last_e.insert(0, self.existing.last_contacted)
        add_row("Last contacted:", self.last_e)

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        return {
            "first_name":         self.first_e.get().strip(),
            "last_name":          self.last_e.get().strip(),
            "preferred_name":     self.preferred_e.get().strip(),
            "pronouns":           self.pronouns_e.get().strip(),
            "gender":             self.gender_cb.get().strip(),
            "dob":                self.dob_e.get().strip(),
            "leaving_year":       self.year_e.get().strip(),
            "leaving_date":       self.date_e.get().strip(),
            "leaving_reason":     self.reason_cb.get().strip(),
            "destination_type":   self.dest_cb.get().strip(),
            "destination_detail": self.dest_detail_e.get().strip(),
            "current_role":       self.role_e.get().strip(),
            "current_employer":   self.employer_e.get().strip(),
            "current_sector":     self.sector_cb.get().strip(),
            "current_location":   self.location_e.get().strip(),
            "country":            self.country_e.get().strip(),
            "region":             self.region_e.get().strip(),
            "email":              self.email_e.get().strip(),
            "phone":              self.phone_e.get().strip(),
            "linkedin":           self.linkedin_e.get().strip(),
            "photo_path":         self.photo_e.get().strip(),
            "bio":                self.bio_t.get("1.0", "end").strip(),
            "opt_in_contact":     self.opt_var.get(),
            "status":             self.status_cb.get().strip(),
            "last_contacted":     self.last_e.get().strip(),
            "notes":              self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_alumnus(self.existing.alumni_id, payload)
            else:
                data.create_alumnus(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Detail window (per-alumnus sub-tabs) ═══════════════════════════

class DetailWindow:
    """Per-alumnus window with sub-tabs for education, career,
    contacts, tags, achievements."""

    def __init__(self, parent: tk.Misc, alumnus: Alumnus) -> None:
        self.alumnus = alumnus
        self.win = tk.Toplevel(parent)
        self.win.title(f"Alumnus #{alumnus.alumni_id} — "
                         f"{alumnus.display_name}")
        self.win.geometry("1000x650")
        self.win.minsize(800, 500)
        self.win.transient(parent)

        header = ttk.Frame(self.win, padding=8)
        header.pack(fill="x")
        ttk.Label(header,
                    text=f"#{alumnus.alumni_id}  {alumnus.display_name}",
                    font=("TkDefaultFont", 12, "bold")
                    ).pack(side="left")
        bits = []
        if alumnus.pronouns:
            bits.append(alumnus.pronouns)
        if alumnus.current_role and alumnus.current_employer:
            bits.append(f"{alumnus.current_role} @ "
                         f"{alumnus.current_employer}")
        if alumnus.current_sector:
            bits.append(alumnus.current_sector)
        if bits:
            ttk.Label(header, text="  ·  ".join(bits),
                        foreground="#555").pack(side="left", padx=12)
        if alumnus.bio:
            ttk.Label(self.win, text=alumnus.bio,
                        foreground="#444", wraplength=960,
                        padding=(8, 0, 8, 6)).pack(fill="x")

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        EducationTab(nb, alumnus.alumni_id)
        CareerTab(nb, alumnus.alumni_id)
        ContactsTab(nb, alumnus.alumni_id)
        TagsTab(nb, alumnus.alumni_id)
        AchievementsTab(nb, alumnus.alumni_id)
        CommsTab(nb, alumnus.alumni_id)
        ChannelPrefsTab(nb, alumnus.alumni_id)
        ConsentTab(nb, alumnus.alumni_id)
        MentoringTab(nb, alumnus.alumni_id)
        SpeakerTab(nb, alumnus.alumni_id)
        VolunteeringTab(nb, alumnus.alumni_id)
        DonationsTab(nb, alumnus.alumni_id)
        SocialHandlesTab(nb, alumnus.alumni_id)
        ConnectionsTab(nb, alumnus.alumni_id)
        EngagementTab(nb, alumnus.alumni_id)
        ChapterMembershipTab(nb, alumnus.alumni_id)
        DirectoryConsentTab(nb, alumnus.alumni_id)
        SkillsTab(nb, alumnus.alumni_id)
        PromotionTimelineTab(nb, alumnus.alumni_id)
        MentorProfileTab(nb, alumnus.alumni_id)
        SafeguardingTab(nb, alumnus.alumni_id)
        SMSTab(nb, alumnus.alumni_id)
        NEETChecksTab(nb, alumnus.alumni_id)
        GiftAidTab(nb, alumnus.alumni_id)
        ProtectedCharsTab(nb, alumnus.alumni_id)
        CustomValuesTab(nb, alumnus.alumni_id)
        MediaTab(nb, alumnus.alumni_id)


# ── Education sub-tab ─────────────────────────────────────────────

class EducationTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Education")
        cols = ("id", "qualification", "subject", "institution",
                "span", "grade", "status")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings")
        widths = {"id": 40, "qualification": 110, "subject": 140,
                  "institution": 180, "span": 160, "grade": 90,
                  "status": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(bar, text="Add",  command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit", command=self._edit).pack(side="left",
                                                                padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for e in data.list_education(self.alumni_id):
            span = f"{e.start_date or '?'} → {e.end_date or '…'}"
            self.tree.insert("", "end", iid=str(e.education_id), values=(
                e.education_id, e.qualification, e.subject or "—",
                e.institution, span, e.grade or "—", e.status))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        EducationDialog(self.frame.winfo_toplevel(),
                          alumni_id=self.alumni_id, existing=None,
                          on_save=self.refresh)

    def _edit(self) -> None:
        eid = self._selected_id()
        if eid is None:
            return
        cur = next((x for x in data.list_education(self.alumni_id)
                      if x.education_id == eid), None)
        if cur is None:
            return
        EducationDialog(self.frame.winfo_toplevel(),
                          alumni_id=self.alumni_id, existing=cur,
                          on_save=self.refresh)

    def _delete(self) -> None:
        eid = self._selected_id()
        if eid is None:
            return
        if not messagebox.askyesno("Delete",
                                      f"Delete education row #{eid}?"):
            return
        data.delete_education(eid)
        self.refresh()


class EducationDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 existing, on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Education" if existing else "Add Education")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.qual_e = ttk.Entry(form, width=28)
        self.subj_e = ttk.Entry(form, width=28)
        self.inst_e = ttk.Entry(form, width=32)
        self.start_e = ttk.Entry(form, width=14)
        self.end_e   = ttk.Entry(form, width=14)
        self.grade_e = ttk.Entry(form, width=14)
        self.status_cb = ttk.Combobox(form, values=EDUCATION_STATUSES,
                                         state="readonly", width=16)
        self.status_cb.set(DEFAULT_EDUCATION_STATUS)
        self.notes_t = tk.Text(form, width=32, height=3)
        if existing:
            self.qual_e.insert(0, existing.qualification)
            if existing.subject:    self.subj_e.insert(0, existing.subject)
            self.inst_e.insert(0, existing.institution)
            if existing.start_date: self.start_e.insert(0,
                                                          existing.start_date)
            if existing.end_date:   self.end_e.insert(0, existing.end_date)
            if existing.grade:      self.grade_e.insert(0, existing.grade)
            self.status_cb.set(existing.status)
            if existing.notes:      self.notes_t.insert("1.0",
                                                          existing.notes)

        row("Qualification:", self.qual_e)
        row("Subject:",       self.subj_e)
        row("Institution:",   self.inst_e)
        row("Start date:",    self.start_e)
        row("End date:",      self.end_e)
        row("Grade:",         self.grade_e)
        row("Status:",        self.status_cb)
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                                sticky="ne", pady=3)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "qualification": self.qual_e.get().strip(),
            "subject":       self.subj_e.get().strip(),
            "institution":   self.inst_e.get().strip(),
            "start_date":    self.start_e.get().strip(),
            "end_date":      self.end_e.get().strip(),
            "grade":         self.grade_e.get().strip(),
            "status":        self.status_cb.get(),
            "notes":         self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_education(self.existing.education_id, payload)
            else:
                data.add_education(self.alumni_id, payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ── Career sub-tab ────────────────────────────────────────────────

class CareerTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Career")
        cols = ("id", "role", "employer", "sector", "country",
                "span", "current", "salary")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings")
        widths = {"id": 40, "role": 140, "employer": 140, "sector": 130,
                  "country": 110, "span": 160, "current": 70, "salary": 110}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(bar, text="Add",  command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit", command=self._edit).pack(side="left",
                                                                padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for c in data.list_career(self.alumni_id):
            span = (f"{c.start_date or '?'} → "
                     + ("present" if c.is_current
                        else (c.end_date or '?')))
            self.tree.insert("", "end", iid=str(c.career_id), values=(
                c.career_id, c.role, c.employer, c.sector or "—",
                c.country or "—", span,
                "✓" if c.is_current else "",
                c.salary_band or "—"))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        CareerDialog(self.frame.winfo_toplevel(),
                       alumni_id=self.alumni_id, existing=None,
                       on_save=self.refresh)

    def _edit(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        cur = next((x for x in data.list_career(self.alumni_id)
                      if x.career_id == cid), None)
        if cur is None:
            return
        CareerDialog(self.frame.winfo_toplevel(),
                       alumni_id=self.alumni_id, existing=cur,
                       on_save=self.refresh)

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        if not messagebox.askyesno("Delete",
                                      f"Delete career row #{cid}?"):
            return
        data.delete_career(cid)
        self.refresh()


class CareerDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 existing, on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Career" if existing else "Add Career")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.role_e = ttk.Entry(form, width=30)
        self.emp_e  = ttk.Entry(form, width=30)
        self.sector_cb = ttk.Combobox(form,
                                         values=("",) + SECTORS,
                                         state="readonly", width=24)
        self.country_e = ttk.Entry(form, width=24)
        self.loc_e     = ttk.Entry(form, width=30)
        self.start_e   = ttk.Entry(form, width=14)
        self.end_e     = ttk.Entry(form, width=14)
        self.cur_var   = tk.BooleanVar(value=False)
        self.band_cb   = ttk.Combobox(form,
                                          values=("",) + SALARY_BANDS,
                                          state="readonly", width=20)
        self.notes_t   = tk.Text(form, width=32, height=3)
        if existing:
            self.role_e.insert(0, existing.role)
            self.emp_e.insert(0, existing.employer)
            self.sector_cb.set(existing.sector or "")
            if existing.country:  self.country_e.insert(0, existing.country)
            if existing.location: self.loc_e.insert(0, existing.location)
            if existing.start_date:
                self.start_e.insert(0, existing.start_date)
            if existing.end_date:
                self.end_e.insert(0, existing.end_date)
            self.cur_var.set(existing.is_current)
            self.band_cb.set(existing.salary_band or "")
            if existing.notes:    self.notes_t.insert("1.0",
                                                       existing.notes)

        row("Role:",        self.role_e)
        row("Employer:",    self.emp_e)
        row("Sector:",      self.sector_cb)
        row("Country:",     self.country_e)
        row("Location:",    self.loc_e)
        row("Start date:",  self.start_e)
        row("End date:",    self.end_e)
        ttk.Checkbutton(form, text="Current role",
                          variable=self.cur_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=3)
        r += 1
        row("Salary band:", self.band_cb)
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                                sticky="ne", pady=3)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "role":        self.role_e.get().strip(),
            "employer":    self.emp_e.get().strip(),
            "sector":      self.sector_cb.get().strip(),
            "country":     self.country_e.get().strip(),
            "location":    self.loc_e.get().strip(),
            "start_date":  self.start_e.get().strip(),
            "end_date":    self.end_e.get().strip(),
            "is_current":  self.cur_var.get(),
            "salary_band": self.band_cb.get().strip(),
            "notes":       self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_career(self.existing.career_id, payload)
            else:
                data.add_career(self.alumni_id, payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ── Contacts sub-tab (emails + phones) ────────────────────────────

class ContactsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Contacts")
        # Emails
        ttk.Label(self.frame, text="Emails",
                    font=("TkDefaultFont", 10, "bold")
                    ).pack(anchor="w", padx=6, pady=(6, 0))
        self.em_tree = ttk.Treeview(
            self.frame, columns=("id", "label", "email", "primary"),
            show="headings", height=5)
        for c, w in (("id", 40), ("label", 100), ("email", 280),
                      ("primary", 70)):
            self.em_tree.heading(c, text=c.title())
            self.em_tree.column(c, width=w, anchor="w")
        self.em_tree.pack(fill="x", padx=6, pady=4)
        embar = ttk.Frame(self.frame); embar.pack(fill="x", padx=6)
        ttk.Button(embar, text="Add email",
                    command=self._add_email).pack(side="left")
        ttk.Button(embar, text="Make primary",
                    command=self._make_email_primary).pack(side="left",
                                                              padx=4)
        ttk.Button(embar, text="Delete email",
                    command=self._delete_email).pack(side="left")
        # Phones
        ttk.Label(self.frame, text="Phones",
                    font=("TkDefaultFont", 10, "bold")
                    ).pack(anchor="w", padx=6, pady=(12, 0))
        self.ph_tree = ttk.Treeview(
            self.frame, columns=("id", "label", "phone", "primary"),
            show="headings", height=5)
        for c, w in (("id", 40), ("label", 100), ("phone", 200),
                      ("primary", 70)):
            self.ph_tree.heading(c, text=c.title())
            self.ph_tree.column(c, width=w, anchor="w")
        self.ph_tree.pack(fill="x", padx=6, pady=4)
        phbar = ttk.Frame(self.frame); phbar.pack(fill="x", padx=6)
        ttk.Button(phbar, text="Add phone",
                    command=self._add_phone).pack(side="left")
        ttk.Button(phbar, text="Make primary",
                    command=self._make_phone_primary).pack(side="left",
                                                              padx=4)
        ttk.Button(phbar, text="Delete phone",
                    command=self._delete_phone).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.em_tree.get_children(): self.em_tree.delete(i)
        for e in data.list_emails(self.alumni_id):
            self.em_tree.insert("", "end", iid=str(e.email_id), values=(
                e.email_id, e.label, e.email,
                "✓" if e.is_primary else ""))
        for i in self.ph_tree.get_children(): self.ph_tree.delete(i)
        for p in data.list_phones(self.alumni_id):
            self.ph_tree.insert("", "end", iid=str(p.phone_id), values=(
                p.phone_id, p.label, p.phone,
                "✓" if p.is_primary else ""))

    def _ask(self, title: str, *fields: tuple[str, list[str] | None]
                ) -> dict[str, str] | None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(title); win.transient(self.frame.winfo_toplevel())
        win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack(fill="both",
                                                          expand=True)
        widgets: dict[str, tk.Widget] = {}
        for i, (name, choices) in enumerate(fields):
            ttk.Label(form, text=f"{name}:").grid(row=i, column=0,
                                                     sticky="e", pady=3)
            if choices is None:
                w = ttk.Entry(form, width=32)
            else:
                w = ttk.Combobox(form, values=choices,
                                    state="readonly", width=22)
                w.current(0)
            w.grid(row=i, column=1, sticky="w", padx=6)
            widgets[name] = w
        result: dict[str, str] = {}

        def save() -> None:
            for name, w in widgets.items():
                result[name] = w.get().strip()
            win.destroy()

        bar = ttk.Frame(form); bar.grid(row=len(fields), column=0,
                                          columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)
        win.wait_window()
        return result or None

    def _add_email(self) -> None:
        res = self._ask("Add email", ("Email", None),
                          ("Label", list(EMAIL_LABELS)),
                          ("Primary?", ["No", "Yes"]))
        if not res or not res.get("Email"):
            return
        try:
            data.add_email(self.alumni_id, res["Email"],
                             label=res.get("Label") or "Personal",
                             is_primary=(res.get("Primary?") == "Yes"))
        except Exception as e:
            messagebox.showerror("Add email", str(e)); return
        self.refresh()

    def _add_phone(self) -> None:
        res = self._ask("Add phone", ("Phone", None),
                          ("Label", list(PHONE_LABELS)),
                          ("Primary?", ["No", "Yes"]))
        if not res or not res.get("Phone"):
            return
        try:
            data.add_phone(self.alumni_id, res["Phone"],
                             label=res.get("Label") or "Mobile",
                             is_primary=(res.get("Primary?") == "Yes"))
        except Exception as e:
            messagebox.showerror("Add phone", str(e)); return
        self.refresh()

    def _make_email_primary(self) -> None:
        sel = self.em_tree.selection()
        if not sel: return
        data.set_primary_email(int(sel[0])); self.refresh()

    def _make_phone_primary(self) -> None:
        sel = self.ph_tree.selection()
        if not sel: return
        data.set_primary_phone(int(sel[0])); self.refresh()

    def _delete_email(self) -> None:
        sel = self.em_tree.selection()
        if not sel: return
        if messagebox.askyesno("Delete", "Delete this email?"):
            data.delete_email(int(sel[0])); self.refresh()

    def _delete_phone(self) -> None:
        sel = self.ph_tree.selection()
        if not sel: return
        if messagebox.askyesno("Delete", "Delete this phone?"):
            data.delete_phone(int(sel[0])); self.refresh()


# ── Tags sub-tab ──────────────────────────────────────────────────

class TagsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Tags")
        ttk.Label(self.frame, text="Attached tags",
                    font=("TkDefaultFont", 10, "bold")
                    ).pack(anchor="w", padx=6, pady=(6, 0))
        self.tree = ttk.Treeview(self.frame, columns=("id", "name"),
                                    show="headings", height=8)
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Tag")
        self.tree.column("id", width=50, anchor="w")
        self.tree.column("name", width=320, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=6, pady=4)
        self.entry = ttk.Entry(bar, width=30)
        self.entry.pack(side="left")
        ttk.Button(bar, text="Add / attach",
                    command=self._add).pack(side="left", padx=4)
        ttk.Button(bar, text="Remove from alumnus",
                    command=self._remove).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for t in data.list_tags_for(self.alumni_id):
            self.tree.insert("", "end", iid=str(t.tag_id),
                              values=(t.tag_id, t.name))

    def _add(self) -> None:
        name = self.entry.get().strip()
        if not name:
            return
        try:
            data.add_tag(self.alumni_id, name)
        except Exception as e:
            messagebox.showerror("Add tag", str(e)); return
        self.entry.delete(0, "end")
        self.refresh()

    def _remove(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        data.remove_tag(self.alumni_id, int(sel[0]))
        self.refresh()


# ── Achievements sub-tab ──────────────────────────────────────────

class AchievementsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Achievements")
        cols = ("id", "date", "category", "title", "url")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings")
        widths = {"id": 40, "date": 100, "category": 130,
                  "title": 320, "url": 240}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Button(bar, text="Add",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for x in data.list_achievements(self.alumni_id):
            self.tree.insert("", "end", iid=str(x.achievement_id),
                              values=(x.achievement_id, x.date or "—",
                                       x.category or "—", x.title,
                                       x.url or ""))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        AchievementDialog(self.frame.winfo_toplevel(),
                            alumni_id=self.alumni_id, existing=None,
                            on_save=self.refresh)

    def _edit(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        cur = next((x for x in data.list_achievements(self.alumni_id)
                      if x.achievement_id == aid), None)
        if cur is None:
            return
        AchievementDialog(self.frame.winfo_toplevel(),
                            alumni_id=self.alumni_id, existing=cur,
                            on_save=self.refresh)

    def _delete(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        if messagebox.askyesno("Delete",
                                  f"Delete achievement #{aid}?"):
            data.delete_achievement(aid)
            self.refresh()


class AchievementDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 existing, on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Achievement" if existing
                          else "Add Achievement")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.title_e = ttk.Entry(form, width=44)
        self.date_e  = ttk.Entry(form, width=14)
        self.cat_cb  = ttk.Combobox(form,
                                       values=("",) + ACHIEVEMENT_CATEGORIES,
                                       state="readonly", width=22)
        self.url_e   = ttk.Entry(form, width=44)
        self.desc_t  = tk.Text(form, width=44, height=4)
        if existing:
            self.title_e.insert(0, existing.title)
            if existing.date: self.date_e.insert(0, existing.date)
            self.cat_cb.set(existing.category or "")
            if existing.url:  self.url_e.insert(0, existing.url)
            if existing.description:
                self.desc_t.insert("1.0", existing.description)
        row("Title:",    self.title_e)
        row("Date:",     self.date_e)
        row("Category:", self.cat_cb)
        row("URL:",      self.url_e)
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                       sticky="ne", pady=3)
        self.desc_t.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "title":       self.title_e.get().strip(),
            "date":        self.date_e.get().strip(),
            "category":    self.cat_cb.get().strip(),
            "url":         self.url_e.get().strip(),
            "description": self.desc_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_achievement(
                    self.existing.achievement_id, payload)
            else:
                data.add_achievement(self.alumni_id, payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ── Communications sub-tab ────────────────────────────────────────

class CommsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Comms")
        cols = ("id", "date", "channel", "status", "subject")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "date": 100, "channel": 90,
                  "status": 90, "subject": 480}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.bounce_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.bounce_var,
                    foreground="#a64",
                    anchor="w").pack(fill="x", padx=6)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4, pady=4)
        ttk.Button(bar, text="Add",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Send email…",
                    command=self._send_email).pack(side="left", padx=12)
        ttk.Button(bar, text="Record bounce",
                    command=self._bounce).pack(side="left")
        ttk.Button(bar, text="Clear bounces",
                    command=self._clear_bounces).pack(side="left",
                                                         padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in data.list_communications(self.alumni_id):
            when = (c.sent_at or c.received_at or c.created_at or ""
                      )[:16]
            self.tree.insert("", "end", iid=str(c.message_id), values=(
                c.message_id, when, c.channel, c.status,
                c.subject or ""))
        a = data.get_alumnus(self.alumni_id)
        self.bounce_var.set(
            f"Bounce count: {a.bounce_count}" if a else "")

    def _add(self) -> None:
        CommDialog(self.frame.winfo_toplevel(),
                     alumni_id=self.alumni_id,
                     on_save=self.refresh)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        if messagebox.askyesno("Delete",
                                  f"Delete comm #{sel[0]}?"):
            data.delete_communication(int(sel[0]))
            self.refresh()

    def _send_email(self) -> None:
        SendEmailDialog(self.frame.winfo_toplevel(),
                         alumni_id=self.alumni_id,
                         on_save=self.refresh)

    def _bounce(self) -> None:
        if messagebox.askyesno("Bounce",
                                  "Record a hard bounce for this "
                                  "alumnus?"):
            data.record_bounce(self.alumni_id, hard=True)
            self.refresh()

    def _clear_bounces(self) -> None:
        data.clear_bounces(self.alumni_id)
        self.refresh()


class CommDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Add communication")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12); form.pack(fill="both",
                                                              expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.channel_cb = ttk.Combobox(form, values=COMM_CHANNELS,
                                          state="readonly", width=14)
        self.channel_cb.set("Email")
        self.status_cb = ttk.Combobox(form, values=COMM_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set("Sent")
        self.staff_e = ttk.Entry(form, width=20)
        self.subj_e  = ttk.Entry(form, width=44)
        self.summ_t  = tk.Text(form, width=44, height=4)
        row("Date:",    self.date_e)
        row("Channel:", self.channel_cb)
        row("Status:",  self.status_cb)
        row("Staff id:", self.staff_e)
        row("Subject:", self.subj_e)
        ttk.Label(form, text="Summary:").grid(row=r, column=0,
                                                  sticky="ne", pady=3)
        self.summ_t.grid(row=r, column=1, sticky="w", padx=6); r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.add_communication(self.alumni_id, {
                "date":     self.date_e.get().strip(),
                "channel":  self.channel_cb.get(),
                "status":   self.status_cb.get(),
                "staff_id": self.staff_e.get().strip(),
                "subject":  self.subj_e.get().strip(),
                "summary":  self.summ_t.get("1.0", "end").strip(),
            })
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        self.win.destroy()
        self.on_save()


class SendEmailDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Send email")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12); form.pack(fill="both",
                                                              expand=True)
        ttk.Label(form,
                    text=("Placeholders: {first_name} {last_name} "
                           "{preferred_name} {leaving_year}"),
                    foreground="#666"
                    ).grid(row=0, column=0, columnspan=2,
                            sticky="w", pady=(0, 6))
        ttk.Label(form, text="Subject:").grid(row=1, column=0,
                                                  sticky="e", pady=3)
        self.subj_e = ttk.Entry(form, width=60)
        self.subj_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Staff id:").grid(row=2, column=0,
                                                  sticky="e", pady=3)
        self.staff_e = ttk.Entry(form, width=20)
        self.staff_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Body:").grid(row=3, column=0,
                                               sticky="ne", pady=3)
        self.body_t = tk.Text(form, width=60, height=10)
        self.body_t.grid(row=3, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Send",
                    command=self._send).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _send(self) -> None:
        try:
            ok = data.send_email_to_alumnus(
                self.alumni_id, self.subj_e.get().strip(),
                self.body_t.get("1.0", "end").strip(),
                staff_id=self.staff_e.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Send failed", str(e)); return
        messagebox.showinfo(
            "Sent" if ok else "Logged",
            "Delivered via shared email infra" if ok
            else "Logged (no shared email infra available)")
        self.win.destroy()
        self.on_save()


# ── Channel-prefs sub-tab ─────────────────────────────────────────

class ChannelPrefsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Channels")
        wrap = ttk.Frame(self.frame, padding=12); wrap.pack(fill="x")
        self.email_var = tk.BooleanVar()
        self.post_var  = tk.BooleanVar()
        self.phone_var = tk.BooleanVar()
        self.sms_var   = tk.BooleanVar()
        ttk.Label(wrap, text="Channel preferences",
                    font=("TkDefaultFont", 10, "bold")
                    ).grid(row=0, column=0, columnspan=2,
                            sticky="w", pady=(0, 6))
        ttk.Checkbutton(wrap, text="Email",
                          variable=self.email_var).grid(
            row=1, column=0, sticky="w")
        ttk.Checkbutton(wrap, text="Post",
                          variable=self.post_var).grid(
            row=2, column=0, sticky="w")
        ttk.Checkbutton(wrap, text="Phone",
                          variable=self.phone_var).grid(
            row=3, column=0, sticky="w")
        ttk.Checkbutton(wrap, text="SMS",
                          variable=self.sms_var).grid(
            row=4, column=0, sticky="w")
        ttk.Button(wrap, text="Save",
                    command=self._save).grid(row=5, column=0,
                                                pady=(10, 0))
        self.refresh()

    def refresh(self) -> None:
        p = data.get_channel_prefs(self.alumni_id)
        self.email_var.set(p.opt_in_email)
        self.post_var.set(p.opt_in_post)
        self.phone_var.set(p.opt_in_phone)
        self.sms_var.set(p.opt_in_sms)

    def _save(self) -> None:
        try:
            data.update_channel_prefs(
                self.alumni_id,
                opt_in_email=self.email_var.get(),
                opt_in_post=self.post_var.get(),
                opt_in_phone=self.phone_var.get(),
                opt_in_sms=self.sms_var.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        messagebox.showinfo("Saved", "Channel preferences updated.")


# ── Consent sub-tab ───────────────────────────────────────────────

class ConsentTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Consent")
        cols = ("id", "scope", "version", "granted_at",
                "withdrawn_at", "source")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "scope": 130, "version": 70,
                  "granted_at": 160, "withdrawn_at": 160,
                  "source": 200}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4, pady=4)
        self.scope_cb = ttk.Combobox(bar, values=CONSENT_SCOPES,
                                        state="readonly", width=18)
        self.scope_cb.set(CONSENT_SCOPES[0])
        self.scope_cb.pack(side="left")
        self.source_e = ttk.Entry(bar, width=22)
        self.source_e.pack(side="left", padx=4)
        ttk.Button(bar, text="Grant",
                    command=self._grant).pack(side="left", padx=4)
        ttk.Button(bar, text="Withdraw selected",
                    command=self._withdraw).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in data.list_consents(self.alumni_id):
            self.tree.insert("", "end", iid=str(c.consent_id),
                              values=(c.consent_id, c.scope, c.version,
                                       c.granted_at,
                                       c.withdrawn_at or "—",
                                       c.source or ""))

    def _grant(self) -> None:
        try:
            data.grant_consent(self.alumni_id,
                                 self.scope_cb.get(),
                                 source=self.source_e.get().strip()
                                          or None)
        except Exception as e:
            messagebox.showerror("Grant failed", str(e)); return
        self.source_e.delete(0, "end")
        self.refresh()

    def _withdraw(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        try:
            data.withdraw_consent(int(sel[0]))
        except Exception as e:
            messagebox.showerror("Withdraw failed", str(e)); return
        self.refresh()


# ── Unarchived leavers tab ────────────────────────────────────────

class UnarchivedLeaversTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Unarchived Leavers")
        ttk.Label(
            self.frame,
            text=("Students who look like leavers — UCAS final "
                   "decision or past exam year — but have no alumni "
                   "row yet."),
            foreground="#555", anchor="w"
        ).pack(fill="x", padx=8, pady=(8, 4))
        cols = ("sid", "name", "email", "ucas_year",
                "exam_year", "destination")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"sid": 90, "name": 200, "email": 220,
                  "ucas_year": 80, "exam_year": 80,
                  "destination": 360}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Archive selected (auto-enrich)",
                    command=self._archive).pack(side="left", padx=4)
        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                    anchor="w").pack(fill="x", padx=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        rows = data.find_unarchived_leavers()
        for r in rows:
            self.tree.insert("", "end", iid=r.student_id, values=(
                r.student_id, r.full_name, r.email or "—",
                r.ucas_cycle_year or "—",
                r.last_exam_year or "—",
                r.final_destination or "—"))
        self.count_var.set(f"{len(rows)} flagged.")

    def _archive(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        sid = sel[0]
        if not messagebox.askyesno(
                "Archive",
                f"Archive student {sid} as an alumnus "
                "(auto-enriching from UCAS / exam results / "
                "bursaries)?"):
            return
        try:
            a = data.archive_student_enriched(sid)
        except Exception as e:
            messagebox.showerror("Archive failed", str(e))
            return
        messagebox.showinfo(
            "Archived",
            f"Archived as alumnus #{a.alumni_id}\n"
            f"Destination: {a.destination_type} — "
            f"{a.destination_detail or '—'}\n"
            f"Tags: "
            f"{', '.join(t.name for t in data.list_tags_for(a.alumni_id)) or '—'}\n"
            f"Education rows seeded: "
            f"{len(data.list_education(a.alumni_id))}")
        self.refresh()


# ══ Events tab (top-level) ══════════════════════════════════════

class EventsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Events")
        cols = ("id", "name", "type", "date", "location",
                "capacity", "cost", "status")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 220, "type": 110, "date": 100,
                  "location": 160, "capacity": 70, "cost": 90,
                  "status": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<Double-1>", lambda _e: self._open_rsvps())
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="New event",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="RSVPs / Attendance",
                    command=self._open_rsvps).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for e in data.list_events():
            self.tree.insert("", "end", iid=str(e.event_id), values=(
                e.event_id, e.name, e.event_type,
                e.event_date or "—", e.location or "—",
                e.capacity if e.capacity is not None else "—",
                _money_str(e.cost_pence), e.status))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        EventDialog(self.frame.winfo_toplevel(), existing=None,
                      on_save=self.refresh)

    def _edit(self) -> None:
        eid = self._selected_id()
        if eid is None: return
        ev = data.get_event(eid)
        if ev is None: return
        EventDialog(self.frame.winfo_toplevel(), existing=ev,
                      on_save=self.refresh)

    def _open_rsvps(self) -> None:
        eid = self._selected_id()
        if eid is None:
            messagebox.showinfo("RSVPs", "Select an event first.")
            return
        EventRsvpDialog(self.frame.winfo_toplevel(), eid,
                          on_save=self.refresh)

    def _delete(self) -> None:
        eid = self._selected_id()
        if eid is None: return
        if messagebox.askyesno("Delete event",
                                  f"Delete event #{eid} and all RSVPs?"):
            data.delete_event(eid)
            self.refresh()


class EventDialog:
    def __init__(self, parent: tk.Misc, *, existing,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit event" if existing else "New event")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12); form.pack(fill="both",
                                                              expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.name_e = ttk.Entry(form, width=44)
        self.type_cb = ttk.Combobox(form, values=EVENT_TYPES,
                                       state="readonly", width=22)
        self.type_cb.set(EVENT_TYPES[0])
        self.date_e = ttk.Entry(form, width=14)
        self.loc_e  = ttk.Entry(form, width=44)
        self.cap_e  = ttk.Entry(form, width=8)
        self.cost_e = ttk.Entry(form, width=10)
        self.cost_e.insert(0, "0")
        self.status_cb = ttk.Combobox(form, values=EVENT_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(DEFAULT_EVENT_STATUS)
        self.notes_t = tk.Text(form, width=44, height=3)

        if existing:
            self.name_e.insert(0, existing.name)
            self.type_cb.set(existing.event_type)
            if existing.event_date:
                self.date_e.insert(0, existing.event_date)
            if existing.location: self.loc_e.insert(0, existing.location)
            if existing.capacity is not None:
                self.cap_e.insert(0, str(existing.capacity))
            self.cost_e.delete(0, "end")
            self.cost_e.insert(0, f"{existing.cost_pence / 100:.2f}")
            self.status_cb.set(existing.status)
            if existing.notes:
                self.notes_t.insert("1.0", existing.notes)

        row("Name:",     self.name_e)
        row("Type:",     self.type_cb)
        row("Date:",     self.date_e)
        row("Location:", self.loc_e)
        row("Capacity:", self.cap_e)
        row("Cost £:",   self.cost_e)
        row("Status:",   self.status_cb)
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                                sticky="ne", pady=3)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6); r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "name":       self.name_e.get().strip(),
            "event_type": self.type_cb.get(),
            "event_date": self.date_e.get().strip(),
            "location":   self.loc_e.get().strip(),
            "capacity":   self.cap_e.get().strip() or None,
            "cost":       self.cost_e.get().strip() or 0,
            "status":     self.status_cb.get(),
            "notes":      self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_event(self.existing.event_id, payload)
            else:
                data.create_event(payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        self.win.destroy()
        self.on_save()


class EventRsvpDialog:
    def __init__(self, parent: tk.Misc, event_id: int,
                 on_save: Callable[[], None]) -> None:
        self.event_id = event_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"RSVPs for event #{event_id}")
        self.win.geometry("760x520")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)

        ev = data.get_event(event_id)
        if ev:
            ttk.Label(self.win,
                        text=f"{ev.name}  ·  {ev.event_date or '—'}  "
                              f"·  {ev.location or '—'}",
                        font=("TkDefaultFont", 11, "bold"),
                        padding=8).pack(fill="x")
        self.att_var = tk.StringVar(value="")
        ttk.Label(self.win, textvariable=self.att_var,
                    padding=(8, 0, 8, 4)).pack(fill="x")

        cols = ("rsvp", "alumni", "name", "status", "guests",
                "attended")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"rsvp": 60, "alumni": 60, "name": 200,
                  "status": 110, "guests": 70, "attended": 70}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Button(bar, text="Add / update RSVP",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Toggle attended",
                    command=self._toggle_attended).pack(side="left",
                                                          padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self._close).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in data.list_rsvps_for_event(self.event_id):
            a = data.get_alumnus(r.alumni_id)
            name = a.full_name if a else f"#{r.alumni_id}"
            self.tree.insert("", "end", iid=str(r.rsvp_id), values=(
                r.rsvp_id, r.alumni_id, name, r.status, r.guests,
                "✓" if r.attended else ""))
        att = data.event_attendance(self.event_id)
        self.att_var.set(
            f"Invited {att.invited}  ·  Accepted {att.accepted}  "
            f"·  Declined {att.declined}  ·  Attended {att.attended}  "
            f"(headcount {att.headcount})")

    def _add(self) -> None:
        RsvpDialog(self.win, event_id=self.event_id,
                     on_save=self.refresh)

    def _toggle_attended(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        rid = int(sel[0])
        rows = data.list_rsvps_for_event(self.event_id)
        r = next((x for x in rows if x.rsvp_id == rid), None)
        if r is None: return
        data.set_rsvp(self.event_id, r.alumni_id,
                        status=r.status, attended=not r.attended,
                        guests=r.guests)
        self.refresh()

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        data.delete_rsvp(int(sel[0]))
        self.refresh()

    def _close(self) -> None:
        self.win.destroy()
        self.on_save()


class RsvpDialog:
    def __init__(self, parent: tk.Misc, *, event_id: int,
                 on_save: Callable[[], None]) -> None:
        self.event_id = event_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Add / update RSVP")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12); form.pack(fill="both",
                                                              expand=True)
        alumni = data.list_alumni()
        self._ids = [a.alumni_id for a in alumni]
        ttk.Label(form, text="Alumnus:").grid(row=0, column=0,
                                                  sticky="e", pady=3)
        self.cb = ttk.Combobox(form, state="readonly", width=40,
                                  values=[f"#{a.alumni_id} {a.full_name}"
                                            for a in alumni])
        if alumni: self.cb.current(0)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Status:").grid(row=1, column=0,
                                                  sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=RSVP_STATUSES,
                                          state="readonly", width=14)
        self.status_cb.set(DEFAULT_RSVP_STATUS)
        self.status_cb.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Guests:").grid(row=2, column=0,
                                                  sticky="e", pady=3)
        self.guests_e = ttk.Entry(form, width=6)
        self.guests_e.insert(0, "0")
        self.guests_e.grid(row=2, column=1, sticky="w", padx=6)
        self.attended_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Attended",
                          variable=self.attended_var).grid(
            row=3, column=1, sticky="w", padx=6, pady=3)
        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.cb.current()
        if idx < 0:
            return
        try:
            data.set_rsvp(
                self.event_id, self._ids[idx],
                status=self.status_cb.get(),
                guests=int(self.guests_e.get() or 0),
                attended=self.attended_var.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        self.win.destroy()
        self.on_save()


# ══ Campaigns tab (top-level) ════════════════════════════════════

class CampaignsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Campaigns")
        cols = ("id", "name", "status", "target", "raised",
                "pledged", "donors")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 240, "status": 110,
                  "target": 110, "raised": 110, "pledged": 110,
                  "donors": 80}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="New campaign",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Set status",
                    command=self._set_status).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in data.list_campaigns():
            t = data.campaign_totals(c.campaign_id)
            self.tree.insert("", "end", iid=str(c.campaign_id),
                              values=(c.campaign_id, c.name, c.status,
                                       _money_str(c.target_pence),
                                       _money_str(t.raised_pence),
                                       _money_str(t.pledged_open_pence),
                                       t.donor_count))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        CampaignDialog(self.frame.winfo_toplevel(),
                         on_save=self.refresh)

    def _set_status(self) -> None:
        cid = self._selected_id()
        if cid is None: return
        StatusPickerDialog(
            self.frame.winfo_toplevel(),
            title="Campaign status",
            options=CAMPAIGN_STATUSES,
            on_pick=lambda s: (
                data.update_campaign_status(cid, s), self.refresh()))

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None: return
        if messagebox.askyesno(
                "Delete campaign",
                "Donations / pledges will keep their history but "
                "lose the campaign link. Continue?"):
            data.delete_campaign(cid)
            self.refresh()


class CampaignDialog:
    def __init__(self, parent: tk.Misc,
                 on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("New campaign")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12); form.pack(fill="both",
                                                              expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.name_e = ttk.Entry(form, width=40)
        self.desc_t = tk.Text(form, width=40, height=3)
        self.target_e = ttk.Entry(form, width=12)
        self.start_e = ttk.Entry(form, width=14)
        self.end_e = ttk.Entry(form, width=14)
        self.status_cb = ttk.Combobox(form, values=CAMPAIGN_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(DEFAULT_CAMPAIGN_STATUS)
        row("Name:",      self.name_e)
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                       sticky="ne",
                                                       pady=3)
        self.desc_t.grid(row=r, column=1, sticky="w", padx=6); r += 1
        row("Target £:",  self.target_e)
        row("Start:",     self.start_e)
        row("End:",       self.end_e)
        row("Status:",    self.status_cb)
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.create_campaign({
                "name":        self.name_e.get().strip(),
                "description": self.desc_t.get("1.0", "end").strip(),
                "target":      self.target_e.get().strip() or None,
                "start_on":    self.start_e.get().strip(),
                "end_on":      self.end_e.get().strip(),
                "status":      self.status_cb.get(),
            })
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        self.win.destroy()
        self.on_save()


class StatusPickerDialog:
    def __init__(self, parent: tk.Misc, *, title: str,
                 options: tuple[str, ...] | list[str],
                 on_pick: Callable[[str], None]) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12); form.pack()
        cb = ttk.Combobox(form, values=list(options),
                             state="readonly", width=18)
        cb.current(0)
        cb.pack()
        bar = ttk.Frame(form); bar.pack(pady=(8, 0))
        ttk.Button(bar, text="Save", command=lambda: (
            on_pick(cb.get()), self.win.destroy())
            ).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)


# ══ Mentoring sub-tab ════════════════════════════════════════════

class MentoringTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Mentoring")
        cols = ("id", "mentee", "topic", "started", "ended", "status")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "mentee": 100, "topic": 220,
                  "started": 100, "ended": 100, "status": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Button(bar, text="Start mentorship",
                    command=self._start).pack(side="left")
        ttk.Button(bar, text="Sessions…",
                    command=self._sessions).pack(side="left", padx=4)
        ttk.Button(bar, text="End",
                    command=self._end).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for m in data.list_mentorships_by_mentor(self.alumni_id):
            self.tree.insert("", "end", iid=str(m.mentorship_id),
                              values=(m.mentorship_id,
                                       m.mentee_student_id,
                                       m.topic or "—",
                                       m.started_on,
                                       m.ended_on or "—",
                                       m.status))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _start(self) -> None:
        MentorshipDialog(self.frame.winfo_toplevel(),
                           alumni_id=self.alumni_id,
                           on_save=self.refresh)

    def _sessions(self) -> None:
        mid = self._selected_id()
        if mid is None: return
        MentorSessionsDialog(self.frame.winfo_toplevel(),
                                mentorship_id=mid)

    def _end(self) -> None:
        mid = self._selected_id()
        if mid is None: return
        StatusPickerDialog(
            self.frame.winfo_toplevel(),
            title="End mentorship — final status",
            options=MENTORSHIP_STATUSES,
            on_pick=lambda s: (
                data.end_mentorship(mid, status=s), self.refresh()))

    def _delete(self) -> None:
        mid = self._selected_id()
        if mid is None: return
        if messagebox.askyesno(
                "Delete mentorship",
                "Delete mentorship and all its sessions?"):
            data.delete_mentorship(mid)
            self.refresh()


class MentorshipDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Start mentorship")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12); form.pack()
        ttk.Label(form, text="Mentee student id:").grid(
            row=0, column=0, sticky="e", pady=3)
        self.mentee_e = ttk.Entry(form, width=20)
        self.mentee_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Topic:").grid(row=1, column=0,
                                                sticky="e", pady=3)
        self.topic_e = ttk.Entry(form, width=40)
        self.topic_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Notes:").grid(row=2, column=0,
                                                sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=40, height=3)
        self.notes_t.grid(row=2, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Start",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.start_mentorship(
                self.alumni_id, self.mentee_e.get().strip(),
                topic=self.topic_e.get().strip() or None,
                notes=self.notes_t.get("1.0", "end").strip() or None)
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        self.win.destroy()
        self.on_save()


class MentorSessionsDialog:
    def __init__(self, parent: tk.Misc, *, mentorship_id: int) -> None:
        self.mentorship_id = mentorship_id
        self.win = tk.Toplevel(parent)
        self.win.title(f"Sessions for mentorship #{mentorship_id}")
        self.win.geometry("760x440")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        cols = ("id", "date", "mins", "format", "summary")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"id": 50, "date": 100, "mins": 60, "format": 90,
                  "summary": 460}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Button(bar, text="Log session",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in data.list_mentor_sessions(self.mentorship_id):
            self.tree.insert("", "end", iid=str(s.session_id),
                              values=(s.session_id, s.session_date,
                                       s.duration_minutes or 0,
                                       s.format or "—",
                                       (s.summary or "")[:100]))

    def _add(self) -> None:
        win = tk.Toplevel(self.win); win.title("Log session")
        win.transient(self.win); win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack()
        date_e = ttk.Entry(form, width=14); date_e.insert(0, _today())
        dur_e  = ttk.Entry(form, width=8)
        fmt_cb = ttk.Combobox(form, values=("",) + SESSION_FORMATS,
                                 state="readonly", width=14)
        summ_t = tk.Text(form, width=40, height=4)
        for i, (lbl, w) in enumerate((("Date", date_e),
                                       ("Duration (min)", dur_e),
                                       ("Format", fmt_cb))):
            ttk.Label(form, text=lbl + ":").grid(row=i, column=0,
                                                     sticky="e", pady=3)
            w.grid(row=i, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Summary:").grid(row=3, column=0,
                                                  sticky="ne", pady=3)
        summ_t.grid(row=3, column=1, sticky="w", padx=6)

        def save() -> None:
            try:
                data.log_mentor_session(self.mentorship_id, {
                    "session_date":     date_e.get().strip(),
                    "duration_minutes": dur_e.get().strip(),
                    "format":           fmt_cb.get(),
                    "summary":          summ_t.get("1.0",
                                                       "end").strip(),
                })
            except Exception as e:
                messagebox.showerror("Save failed", str(e)); return
            win.destroy()
            self.refresh()

        bar = ttk.Frame(form); bar.grid(row=4, column=0, columnspan=2,
                                          pady=(12, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        data.delete_mentor_session(int(sel[0]))
        self.refresh()


# ══ Speaker sub-tab ══════════════════════════════════════════════

class SpeakerTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Speaker")
        wrap = ttk.Frame(self.frame, padding=12); wrap.pack(fill="x")
        ttk.Label(wrap, text="Speaker register profile",
                    font=("TkDefaultFont", 10, "bold")
                    ).grid(row=0, column=0, columnspan=2,
                            sticky="w", pady=(0, 6))
        self.topics_e = ttk.Entry(wrap, width=56)
        self.years_e  = ttk.Entry(wrap, width=24)
        self.avail_t  = tk.Text(wrap, width=56, height=4)
        ttk.Label(wrap, text="Topics:").grid(row=1, column=0,
                                                  sticky="e", pady=3)
        self.topics_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(wrap, text="Year groups:").grid(row=2, column=0,
                                                       sticky="e",
                                                       pady=3)
        self.years_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(wrap, text="Availability:").grid(row=3, column=0,
                                                       sticky="ne",
                                                       pady=3)
        self.avail_t.grid(row=3, column=1, sticky="w", padx=6)
        self.conf_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(wrap, text="Confirm willingness today",
                          variable=self.conf_var).grid(
            row=4, column=1, sticky="w", padx=6, pady=4)
        self.last_var = tk.StringVar(value="")
        ttk.Label(wrap, textvariable=self.last_var,
                    foreground="#555").grid(row=5, column=1,
                                               sticky="w", padx=6)
        bbar = ttk.Frame(wrap); bbar.grid(row=6, column=0,
                                              columnspan=2,
                                              pady=(10, 0),
                                              sticky="w")
        ttk.Button(bbar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bbar, text="Remove from register",
                    command=self._remove).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        p = data.get_speaker(self.alumni_id)
        self.topics_e.delete(0, "end")
        self.years_e.delete(0, "end")
        self.avail_t.delete("1.0", "end")
        self.conf_var.set(False)
        if p:
            if p.topics: self.topics_e.insert(0, p.topics)
            if p.year_groups: self.years_e.insert(0, p.year_groups)
            if p.availability_notes:
                self.avail_t.insert("1.0", p.availability_notes)
            self.last_var.set(
                f"Last confirmed: {p.last_confirmed_at or 'never'}")
        else:
            self.last_var.set("Not on register yet.")

    def _save(self) -> None:
        try:
            data.upsert_speaker(
                self.alumni_id,
                topics=self.topics_e.get(),
                year_groups=self.years_e.get(),
                availability_notes=self.avail_t.get("1.0", "end"),
                confirm=self.conf_var.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        messagebox.showinfo("Saved", "Speaker profile updated.")
        self.refresh()

    def _remove(self) -> None:
        if messagebox.askyesno(
                "Remove",
                "Remove this alumnus from the speaker register?"):
            data.remove_speaker(self.alumni_id)
            self.refresh()


# ══ Volunteering sub-tab ═════════════════════════════════════════

class VolunteeringTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Volunteering")
        cols = ("id", "date", "hours", "activity", "event", "notes")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "date": 100, "hours": 70,
                  "activity": 160, "event": 80, "notes": 360}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.total_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.total_var,
                    foreground="#444",
                    padding=(8, 0, 8, 4)).pack(fill="x")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4,
                                                  pady=4)
        ttk.Button(bar, text="Log hours",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for v in data.list_volunteer_hours(self.alumni_id):
            self.tree.insert("", "end", iid=str(v.volunteer_id),
                              values=(v.volunteer_id,
                                       v.activity_date,
                                       f"{v.hours:g}",
                                       v.activity_type,
                                       f"#{v.event_id}"
                                          if v.event_id else "—",
                                       v.notes or ""))
        self.total_var.set(
            f"Total: {data.total_volunteer_hours(self.alumni_id):g}h")

    def _add(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Log hours")
        win.transient(self.frame.winfo_toplevel()); win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack()
        date_e   = ttk.Entry(form, width=14); date_e.insert(0, _today())
        hours_e  = ttk.Entry(form, width=8)
        type_cb  = ttk.Combobox(
            form, values=VOLUNTEER_ACTIVITY_TYPES,
            state="readonly", width=22)
        type_cb.set(VOLUNTEER_ACTIVITY_TYPES[0])
        events = data.list_events()
        event_choices = ["(no event)"] + [
            f"#{e.event_id} {e.name[:30]}" for e in events]
        event_cb = ttk.Combobox(form, values=event_choices,
                                   state="readonly", width=40)
        event_cb.current(0)
        notes_e = ttk.Entry(form, width=40)
        for i, (lbl, w) in enumerate((("Date", date_e),
                                       ("Hours", hours_e),
                                       ("Activity", type_cb),
                                       ("Attach event", event_cb),
                                       ("Notes", notes_e))):
            ttk.Label(form, text=lbl + ":").grid(row=i, column=0,
                                                     sticky="e", pady=3)
            w.grid(row=i, column=1, sticky="w", padx=6)

        def save() -> None:
            idx = event_cb.current()
            ev_id = events[idx - 1].event_id if idx > 0 else None
            try:
                data.log_volunteer_hours(
                    self.alumni_id,
                    float(hours_e.get() or 0),
                    activity_type=type_cb.get(),
                    activity_date=date_e.get().strip(),
                    event_id=ev_id,
                    notes=notes_e.get().strip() or None)
            except Exception as e:
                messagebox.showerror("Save failed", str(e)); return
            win.destroy()
            self.refresh()

        bar = ttk.Frame(form); bar.grid(row=5, column=0, columnspan=2,
                                          pady=(12, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        data.delete_volunteer_entry(int(sel[0]))
        self.refresh()


# ══ Donations & pledges sub-tab ══════════════════════════════════

class DonationsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Donations")

        ttk.Label(self.frame, text="Donations",
                    font=("TkDefaultFont", 10, "bold")
                    ).pack(anchor="w", padx=6, pady=(6, 0))
        self.don_tree = ttk.Treeview(
            self.frame,
            columns=("id", "date", "amount", "campaign", "gift_aid",
                      "method"),
            show="headings", height=8)
        widths = {"id": 50, "date": 100, "amount": 100,
                  "campaign": 200, "gift_aid": 70, "method": 130}
        for c in ("id", "date", "amount", "campaign", "gift_aid",
                   "method"):
            self.don_tree.heading(c, text=c.title())
            self.don_tree.column(c, width=widths[c], anchor="w")
        self.don_tree.pack(fill="x", padx=6, pady=4)
        dbar = ttk.Frame(self.frame); dbar.pack(fill="x", padx=6)
        ttk.Button(dbar, text="Record donation",
                    command=self._add_donation).pack(side="left")
        ttk.Button(dbar, text="Delete",
                    command=self._delete_donation).pack(side="left",
                                                           padx=4)

        ttk.Label(self.frame, text="Pledges",
                    font=("TkDefaultFont", 10, "bold")
                    ).pack(anchor="w", padx=6, pady=(12, 0))
        self.pl_tree = ttk.Treeview(
            self.frame,
            columns=("id", "pledged_on", "amount", "campaign",
                      "due_by", "status"),
            show="headings", height=6)
        widths_p = {"id": 50, "pledged_on": 110, "amount": 100,
                    "campaign": 200, "due_by": 110, "status": 100}
        for c in ("id", "pledged_on", "amount", "campaign",
                   "due_by", "status"):
            self.pl_tree.heading(c, text=c.title())
            self.pl_tree.column(c, width=widths_p[c], anchor="w")
        self.pl_tree.pack(fill="x", padx=6, pady=4)
        pbar = ttk.Frame(self.frame); pbar.pack(fill="x", padx=6,
                                                    pady=(0, 6))
        ttk.Button(pbar, text="Add pledge",
                    command=self._add_pledge).pack(side="left")
        ttk.Button(pbar, text="Set status",
                    command=self._set_pledge_status).pack(
            side="left", padx=4)
        ttk.Button(pbar, text="Delete",
                    command=self._delete_pledge).pack(side="left",
                                                         padx=4)
        self.refresh()

    def _campaign_label(self, cid: int | None) -> str:
        if cid is None:
            return "—"
        c = data.get_campaign(cid)
        return f"#{cid} {c.name}" if c else f"#{cid}"

    def refresh(self) -> None:
        for i in self.don_tree.get_children(): self.don_tree.delete(i)
        for d in data.list_donations(alumni_id=self.alumni_id):
            self.don_tree.insert("", "end", iid=str(d.donation_id),
                                  values=(d.donation_id, d.donation_date,
                                           _money_str(d.amount_pence),
                                           self._campaign_label(
                                               d.campaign_id),
                                           "✓" if d.gift_aid else "",
                                           d.payment_method or "—"))
        for i in self.pl_tree.get_children(): self.pl_tree.delete(i)
        for p in data.list_pledges(alumni_id=self.alumni_id):
            self.pl_tree.insert("", "end", iid=str(p.pledge_id),
                                 values=(p.pledge_id, p.pledged_on,
                                          _money_str(p.amount_pence),
                                          self._campaign_label(
                                              p.campaign_id),
                                          p.due_by or "—", p.status))

    def _pick_campaign(self, parent: tk.Misc
                          ) -> int | None:
        campaigns = data.list_campaigns()
        if not campaigns:
            return None
        win = tk.Toplevel(parent); win.title("Campaign")
        win.transient(parent); win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack()
        choices = ["(none)"] + [f"#{c.campaign_id} {c.name}"
                                  for c in campaigns]
        cb = ttk.Combobox(form, values=choices, state="readonly",
                             width=40)
        cb.current(0)
        cb.pack()
        chosen: dict[str, int | None] = {"id": None}

        def ok() -> None:
            idx = cb.current()
            chosen["id"] = (campaigns[idx - 1].campaign_id
                              if idx > 0 else None)
            win.destroy()

        bar = ttk.Frame(form); bar.pack(pady=(8, 0))
        ttk.Button(bar, text="Pick", command=ok).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)
        win.wait_window()
        return chosen["id"]

    def _add_donation(self) -> None:
        cid = self._pick_campaign(self.frame.winfo_toplevel())
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Record donation")
        win.transient(self.frame.winfo_toplevel()); win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack()
        date_e = ttk.Entry(form, width=14); date_e.insert(0, _today())
        amt_e  = ttk.Entry(form, width=12)
        method_cb = ttk.Combobox(form, values=("",) + PAYMENT_METHODS,
                                    state="readonly", width=18)
        ga_var  = tk.BooleanVar(value=False)
        an_var  = tk.BooleanVar(value=False)
        rest_e  = ttk.Entry(form, width=30)
        notes_e = ttk.Entry(form, width=30)
        rows = (("Date", date_e), ("Amount £", amt_e),
                ("Payment method", method_cb),
                ("Restricted to", rest_e), ("Notes", notes_e))
        for i, (lbl, w) in enumerate(rows):
            ttk.Label(form, text=lbl + ":").grid(row=i, column=0,
                                                      sticky="e",
                                                      pady=3)
            w.grid(row=i, column=1, sticky="w", padx=6)
        ttk.Checkbutton(form, text="Gift Aid",
                          variable=ga_var).grid(row=len(rows),
                                                  column=1,
                                                  sticky="w", padx=6)
        ttk.Checkbutton(form, text="Anonymous",
                          variable=an_var).grid(row=len(rows) + 1,
                                                  column=1,
                                                  sticky="w", padx=6)

        def save() -> None:
            try:
                data.record_donation(self.alumni_id, {
                    "amount":         amt_e.get().strip(),
                    "campaign_id":    cid,
                    "donation_date":  date_e.get().strip(),
                    "gift_aid":       ga_var.get(),
                    "payment_method": method_cb.get() or None,
                    "anonymous":      an_var.get(),
                    "restricted_to":  rest_e.get().strip(),
                    "notes":          notes_e.get().strip(),
                })
            except Exception as e:
                messagebox.showerror("Save failed", str(e)); return
            win.destroy()
            self.refresh()

        bar = ttk.Frame(form); bar.grid(row=len(rows) + 2, column=0,
                                          columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _delete_donation(self) -> None:
        sel = self.don_tree.selection()
        if not sel: return
        if messagebox.askyesno("Delete",
                                  "Delete this donation? Irreversible."):
            data.delete_donation(int(sel[0]))
            self.refresh()

    def _add_pledge(self) -> None:
        cid = self._pick_campaign(self.frame.winfo_toplevel())
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Add pledge")
        win.transient(self.frame.winfo_toplevel()); win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack()
        amt_e  = ttk.Entry(form, width=12)
        pdate_e = ttk.Entry(form, width=14); pdate_e.insert(0, _today())
        due_e  = ttk.Entry(form, width=14)
        status_cb = ttk.Combobox(form, values=PLEDGE_STATUSES,
                                    state="readonly", width=14)
        status_cb.set(DEFAULT_PLEDGE_STATUS)
        notes_e = ttk.Entry(form, width=30)
        for i, (lbl, w) in enumerate((("Amount £", amt_e),
                                       ("Pledged on", pdate_e),
                                       ("Due by", due_e),
                                       ("Status", status_cb),
                                       ("Notes", notes_e))):
            ttk.Label(form, text=lbl + ":").grid(row=i, column=0,
                                                      sticky="e",
                                                      pady=3)
            w.grid(row=i, column=1, sticky="w", padx=6)

        def save() -> None:
            try:
                data.add_pledge(self.alumni_id, {
                    "amount":      amt_e.get().strip(),
                    "campaign_id": cid,
                    "pledged_on":  pdate_e.get().strip(),
                    "due_by":      due_e.get().strip(),
                    "status":      status_cb.get(),
                    "notes":       notes_e.get().strip(),
                })
            except Exception as e:
                messagebox.showerror("Save failed", str(e)); return
            win.destroy()
            self.refresh()

        bar = ttk.Frame(form); bar.grid(row=5, column=0, columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _set_pledge_status(self) -> None:
        sel = self.pl_tree.selection()
        if not sel: return
        pid = int(sel[0])
        StatusPickerDialog(
            self.frame.winfo_toplevel(),
            title="Pledge status",
            options=PLEDGE_STATUSES,
            on_pick=lambda s: (
                data.update_pledge_status(pid, s), self.refresh()))

    def _delete_pledge(self) -> None:
        sel = self.pl_tree.selection()
        if not sel: return
        data.delete_pledge(int(sel[0]))
        self.refresh()


# ══ Reports tab (top-level) ══════════════════════════════════════

class ReportsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Reports")
        wrap = ttk.Frame(self.frame, padding=14)
        wrap.pack(fill="both", expand=True)
        ttk.Label(wrap, text="Alumni reports & analytics",
                    font=("TkDefaultFont", 12, "bold")
                    ).pack(anchor="w", pady=(0, 10))
        ttk.Label(wrap,
                    text=("Run a report to see the data, then use "
                           "Export where supported."),
                    foreground="#555"
                    ).pack(anchor="w", pady=(0, 8))

        reports: list[tuple[str, Callable[[], None]]] = [
            ("KS5 destinations CSV (DfE-style)",  self._ks5),
            ("Sustained destinations (1/3/5y)",  self._sustained),
            ("Cohort comparison",                  self._cohort),
            ("University success rates",           self._uni),
            ("Apprenticeship outcomes",            self._appren),
            ("Disadvantage gap",                   self._gap),
            ("Geographic distribution",            self._geo),
            ("Sector breakdown",                   self._sector),
            ("'Where are they now' site",         self._wan),
        ]
        grid = ttk.Frame(wrap); grid.pack(fill="x")
        for i, (label, cb) in enumerate(reports):
            ttk.Button(grid, text=label, command=cb, width=42
                         ).grid(row=i // 2, column=i % 2,
                                  padx=6, pady=4, sticky="w")

    # report launchers ------------------------------------------------

    def _prompt_year(self, title: str = "Leaving year"
                       ) -> str | None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(title); win.transient(self.frame.winfo_toplevel())
        win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack()
        ttk.Label(form, text="Leaving year (YYYY):").grid(
            row=0, column=0, sticky="e", padx=4)
        e = ttk.Entry(form, width=10); e.grid(row=0, column=1,
                                                  sticky="w")
        result: dict[str, str | None] = {"y": None}

        def ok() -> None:
            v = e.get().strip()
            if v: result["y"] = v
            win.destroy()

        bar = ttk.Frame(form); bar.grid(row=1, column=0, columnspan=2,
                                          pady=(8, 0))
        ttk.Button(bar, text="OK", command=ok).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)
        win.wait_window()
        return result["y"]

    def _ks5(self) -> None:
        year = self._prompt_year()
        if not year: return
        try:
            rows = data.ks5_destinations_rows(leaving_year=year)
        except ValidationError as e:
            messagebox.showerror("KS5 destinations", str(e)); return
        cols = ["uln", "surname", "forename", "dob",
                "destination_category", "destination_type",
                "destination_detail", "country", "region"]
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title=f"KS5 destinations {year}",
            columns=cols,
            rows=[[r.get(c, "") for c in cols] for r in rows],
            csv_export=lambda path: data.ks5_destinations_csv(
                leaving_year=year, out_path=path))

    def _sustained(self) -> None:
        year = self._prompt_year()
        if not year: return
        try:
            rows = data.sustained_destinations(leaving_year=year)
        except ValidationError as e:
            messagebox.showerror("Sustained destinations",
                                    str(e)); return
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title=f"Sustained destinations — cohort {year}",
            columns=["alumni_id", "name", "+1y", "+3y", "+5y"],
            rows=[[r.alumni_id, r.full_name,
                    r.year_plus_1, r.year_plus_3, r.year_plus_5]
                   for r in rows])

    def _cohort(self) -> None:
        cc = data.cohort_comparison()
        cols = ["year", "total"] + list(cc.destinations)
        rs: list[list] = []
        for y in cc.years:
            row = [y, cc.totals[y]]
            for d in cc.destinations:
                row.append(cc.counts.get(y, {}).get(d, 0))
            rs.append(row)
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title="Cohort comparison",
            columns=cols, rows=rs)

    def _uni(self) -> None:
        rows = data.university_success_rates()

        def pct(n: int, total: int) -> str:
            return f"{100 * n / total:.0f}%" if total else "—"

        rs = [[r.leaving_year, r.uni_total,
                f"{r.russell} ({pct(r.russell, r.uni_total)})",
                f"{r.oxbridge} ({pct(r.oxbridge, r.uni_total)})",
                f"{r.top_third} ({pct(r.top_third, r.uni_total)})"]
               for r in rows]
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title="University success rates",
            columns=["year", "uni_total", "russell",
                      "oxbridge", "top_third"],
            rows=rs)

    def _appren(self) -> None:
        rows = data.apprenticeship_outcomes()
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title="Apprenticeship outcomes",
            columns=["year", "level", "provider", "count"],
            rows=[[r.leaving_year, r.level, r.provider, r.count]
                   for r in rows])

    def _gap(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Disadvantage gap")
        win.transient(self.frame.winfo_toplevel()); win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack()
        ttk.Label(form, text="Tag:").grid(row=0, column=0,
                                              sticky="e", padx=4)
        tag_e = ttk.Entry(form, width=24)
        tag_e.insert(0, "Bursary recipient")
        tag_e.grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="Year (blank = all):").grid(
            row=1, column=0, sticky="e", padx=4)
        year_e = ttk.Entry(form, width=10)
        year_e.grid(row=1, column=1, sticky="w")

        def go() -> None:
            tag = tag_e.get().strip() or "Bursary recipient"
            year = year_e.get().strip() or None
            try:
                rows = data.disadvantage_gap(tag_name=tag,
                                                 leaving_year=year)
            except ValidationError as e:
                messagebox.showerror("Disadvantage gap", str(e))
                return
            win.destroy()
            ReportTableDialog(
                self.frame.winfo_toplevel(),
                title=(f"Disadvantage gap — {tag}"
                         + (f", {year}" if year else "")),
                columns=["destination", "cohort",
                          "cohort %", "tagged", "tagged %", "gap %"],
                rows=[[r.destination_type, r.cohort_count,
                        f"{r.cohort_pct:.1f}%",
                        r.tagged_count,
                        f"{r.tagged_pct:.1f}%",
                        f"{r.gap_pct:+.1f}%"] for r in rows])

        bar = ttk.Frame(form); bar.grid(row=2, column=0, columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Run", command=go).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _geo(self) -> None:
        rows = data.geographic_distribution()
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title="Geographic distribution",
            columns=["country", "region", "count"],
            rows=[[g.country, g.region, g.count] for g in rows])

    def _sector(self) -> None:
        rows = data.sector_breakdown()
        ReportTableDialog(
            self.frame.winfo_toplevel(),
            title="Sector breakdown",
            columns=["sector", "count", "%"],
            rows=[[r.sector, r.count, f"{r.pct:.1f}%"]
                   for r in rows])

    def _wan(self) -> None:
        from tkinter import filedialog
        out = filedialog.askdirectory(
            parent=self.frame.winfo_toplevel(),
            title="Choose output folder")
        if not out: return
        try:
            n = data.generate_where_are_they_now(out)
        except Exception as e:
            messagebox.showerror("Generation failed", str(e))
            return
        messagebox.showinfo(
            "Generated",
            f"Wrote {n} profile page(s) + index.html to:\n{out}\n\n"
            "Only alumni with active 'Photo Use' consent are "
            "included.")


class ReportTableDialog:
    """Generic results window — a treeview + Export CSV button. Pass
    ``csv_export`` to override the default in-memory CSV with a
    bespoke writer (e.g. the DfE one)."""

    def __init__(self, parent: tk.Misc, *, title: str,
                 columns: list[str], rows: list[list],
                 csv_export: Callable[[str], str] | None = None
                 ) -> None:
        self.columns = columns
        self.rows = rows
        self.csv_export = csv_export
        self.win = tk.Toplevel(parent)
        self.win.title(title); self.win.geometry("1000x600")
        self.win.transient(parent)
        tree = ttk.Treeview(self.win, columns=columns,
                               show="headings")
        for c in columns:
            tree.heading(c, text=str(c).replace("_", " ").title())
            tree.column(c, width=max(90, min(360,
                                              len(str(c)) * 18)),
                         anchor="w")
        for r in rows:
            tree.insert("", "end", values=tuple(r))
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Label(self.win, text=f"{len(rows)} row(s)",
                    foreground="#555",
                    padding=(8, 0)).pack(anchor="w")
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(4, 8))
        ttk.Button(bar, text="Export CSV…",
                    command=self._export).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

    def _export(self) -> None:
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            if self.csv_export is not None:
                self.csv_export(path)
            else:
                # Generic CSV from displayed columns/rows
                import csv as _csv
                with open(path, "w", newline="",
                            encoding="utf-8") as f:
                    w = _csv.writer(f)
                    w.writerow(self.columns)
                    for r in self.rows:
                        w.writerow(r)
        except Exception as e:
            messagebox.showerror("Export failed", str(e)); return
        messagebox.showinfo("Exported", f"Wrote {path}")


# ══ Audit log dialog ═════════════════════════════════════════════

class AuditLogDialog:
    def __init__(self, parent: tk.Misc, alumni_id: int) -> None:
        a = data.get_alumnus(alumni_id)
        self.win = tk.Toplevel(parent)
        self.win.title(f"Audit log — #{alumni_id} "
                         f"{a.display_name if a else ''}")
        self.win.geometry("960x520"); self.win.transient(parent)
        cols = ("changed_at", "changed_by", "field",
                "old_value", "new_value")
        tree = ttk.Treeview(self.win, columns=cols, show="headings")
        widths = {"changed_at": 160, "changed_by": 110,
                  "field": 180, "old_value": 220,
                  "new_value": 220}
        for c in cols:
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=widths[c], anchor="w")
        for r in data.list_audit_log(alumni_id):
            tree.insert("", "end", values=(
                r["changed_at"], r["changed_by"] or "—",
                r["field"], r["old_value"] or "",
                r["new_value"] or ""))
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(self.win, text="Close",
                    command=self.win.destroy).pack(pady=(0, 8))


# ══ Admin tab (top-level) ════════════════════════════════════════

class AdminTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Admin")
        wrap = ttk.Frame(self.frame, padding=14)
        wrap.pack(fill="both", expand=True)
        ttk.Label(wrap, text="Operational tools",
                    font=("TkDefaultFont", 12, "bold")
                    ).pack(anchor="w", pady=(0, 10))
        ttk.Label(
            wrap,
            text=("Bulk import / export, deduplication, soft-delete "
                   "trash, saved searches and surveys."),
            foreground="#555"
        ).pack(anchor="w", pady=(0, 8))
        buttons: list[tuple[str, Callable[[], None]]] = [
            ("Bulk CSV import…",  self._import),
            ("Bulk CSV export…",  self._export),
            ("Find duplicates",    self._dedupe),
            ("Merge by id…",       self._merge),
            ("Soft-delete trash",   self._trash),
            ("Saved searches",     self._saved),
            ("Surveys",             self._surveys),
        ]
        grid = ttk.Frame(wrap); grid.pack(fill="x")
        for i, (label, cb) in enumerate(buttons):
            ttk.Button(grid, text=label, width=32,
                         command=cb
                         ).grid(row=i // 2, column=i % 2,
                                  padx=6, pady=4, sticky="w")

    # action handlers --------------------------------------------------

    def _import(self) -> None:
        ImportCsvDialog(self.frame.winfo_toplevel())

    def _export(self) -> None:
        ExportCsvDialog(self.frame.winfo_toplevel())

    def _dedupe(self) -> None:
        DuplicatesDialog(self.frame.winfo_toplevel())

    def _merge(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Merge alumni")
        win.transient(self.frame.winfo_toplevel()); win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack()
        ttk.Label(form, text="Keep #id (survivor):").grid(
            row=0, column=0, sticky="e", padx=4, pady=3)
        keep_e = ttk.Entry(form, width=10); keep_e.grid(
            row=0, column=1, sticky="w")
        ttk.Label(form, text="Merge #id (absorbed):").grid(
            row=1, column=0, sticky="e", padx=4, pady=3)
        other_e = ttk.Entry(form, width=10); other_e.grid(
            row=1, column=1, sticky="w")

        def go() -> None:
            try:
                keep = int(keep_e.get().strip())
                other = int(other_e.get().strip())
            except ValueError:
                messagebox.showerror("Merge", "IDs must be integers")
                return
            if not messagebox.askyesno(
                    "Merge", f"Merge #{other} into #{keep}? "
                                "Irreversible."):
                return
            try:
                data.merge_alumni(keep, other)
            except Exception as e:
                messagebox.showerror("Merge failed", str(e)); return
            messagebox.showinfo("Merged",
                                  f"Result: alumnus #{keep}")
            win.destroy()

        bar = ttk.Frame(form); bar.grid(row=2, column=0,
                                          columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Merge", command=go).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _trash(self) -> None:
        TrashDialog(self.frame.winfo_toplevel())

    def _saved(self) -> None:
        SavedSearchesDialog(self.frame.winfo_toplevel())

    def _surveys(self) -> None:
        SurveysDialog(self.frame.winfo_toplevel())


# ── Import dialog ────────────────────────────────────────────────

class ImportCsvDialog:
    def __init__(self, parent: tk.Misc) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=parent, title="Choose CSV to import",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.rows = data.parse_import_csv(path)
        except Exception as e:
            messagebox.showerror("Import", str(e)); return
        if not self.rows:
            messagebox.showinfo("Import", "CSV is empty.")
            return
        self.headers = list(self.rows[0].keys())
        self.mapping = data.suggest_import_mapping(self.headers)
        self.win = tk.Toplevel(parent); self.win.title(
            f"Bulk import — {len(self.rows)} row(s)")
        self.win.geometry("780x540")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)

        top = ttk.Frame(self.win, padding=10); top.pack(fill="x")
        ttk.Label(top,
                    text=("Map CSV columns to alumnus fields. "
                           "Leave blank to ignore a column."),
                    foreground="#555"
                    ).pack(anchor="w")
        ttk.Label(top,
                    text=f"Source: {path}",
                    foreground="#888").pack(anchor="w", pady=(2, 0))

        body = ttk.Frame(self.win, padding=(10, 4, 10, 4))
        body.pack(fill="both", expand=True)
        self.combos: dict[str, ttk.Combobox] = {}
        field_options = ("",) + tuple(
            f for f in data._AUDITABLE_FIELDS) + (
            "original_student_id",)
        # Dedup the options (original_student_id is in
        # _AUDITABLE_FIELDS already on this codebase, but include
        # explicitly for safety).
        seen: set[str] = set()
        options: list[str] = []
        for f in field_options:
            if f not in seen:
                seen.add(f); options.append(f)
        for i, h in enumerate(self.headers):
            ttk.Label(body, text=h,
                        anchor="e").grid(row=i, column=0,
                                            sticky="e", padx=4,
                                            pady=2)
            cb = ttk.Combobox(body, values=options,
                                 state="readonly", width=24)
            cb.set(self.mapping.get(h, ""))
            cb.grid(row=i, column=1, sticky="w", padx=4)
            self.combos[h] = cb

        bar = ttk.Frame(self.win, padding=10); bar.pack(fill="x")
        ttk.Button(bar, text="Dry-run preview",
                    command=self._preview).pack(side="left")
        ttk.Button(bar, text="Commit import",
                    command=self._apply).pack(side="left", padx=6)
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

    def _current_mapping(self) -> dict[str, str]:
        return {h: cb.get().strip()
                  for h, cb in self.combos.items() if cb.get().strip()}

    def _preview(self) -> None:
        try:
            prev = data.preview_import(
                self.rows, self._current_mapping())
        except Exception as e:
            messagebox.showerror("Preview failed", str(e)); return
        msg = (f"create: {prev.will_create}\n"
                f"update: {prev.will_update}\n"
                f"skip:   {prev.will_skip}")
        if prev.errors:
            msg += "\n\nFirst issues:\n" + "\n".join(
                f"  row {r}: {m}" for r, m in prev.errors[:5])
        messagebox.showinfo("Dry-run preview", msg)

    def _apply(self) -> None:
        if not messagebox.askyesno(
                "Commit",
                "Apply this import? The dry-run will run first."):
            return
        mapping = self._current_mapping()
        try:
            prev = data.preview_import(self.rows, mapping)
            if prev.errors and not messagebox.askyesno(
                    "Continue?",
                    f"{prev.will_skip} row(s) will be skipped due "
                    "to errors. Continue?"):
                return
            result = data.apply_import(self.rows, mapping)
        except Exception as e:
            messagebox.showerror("Import failed", str(e)); return
        messagebox.showinfo(
            "Imported",
            f"created={result.created}  updated={result.updated}  "
            f"skipped={result.skipped}")
        self.win.destroy()


# ── Export dialog ────────────────────────────────────────────────

class ExportCsvDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Bulk CSV export"); self.win.geometry(
            "500x520")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        ttk.Label(self.win,
                    text="Pick the columns to include in the export.",
                    foreground="#555", padding=(12, 10, 12, 4)
                    ).pack(anchor="w")
        body = ttk.Frame(self.win, padding=(12, 4, 12, 4))
        body.pack(fill="both", expand=True)
        self.vars: dict[str, tk.BooleanVar] = {}
        for i, (field, sens) in enumerate(data.EXPORT_FIELDS):
            v = tk.BooleanVar(value=sens not in
                                ("internal", "sensitive"))
            ttk.Checkbutton(body, text=f"{field} ({sens})",
                              variable=v
                              ).grid(row=i // 2, column=i % 2,
                                       sticky="w", padx=6, pady=1)
            self.vars[field] = v
        self.redact_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.win,
                          text="Apply consent-based PII redaction",
                          variable=self.redact_var).pack(
            anchor="w", padx=12, pady=(6, 0))
        bar = ttk.Frame(self.win, padding=12); bar.pack(fill="x")
        ttk.Button(bar, text="Export…",
                    command=self._export).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

    def _export(self) -> None:
        from tkinter import filedialog
        cols = [f for f, v in self.vars.items() if v.get()]
        if not cols:
            messagebox.showerror("Export", "Pick at least one column.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            data.export_alumni_csv(
                out_path=path, columns=cols,
                respect_consent=self.redact_var.get())
        except Exception as e:
            messagebox.showerror("Export failed", str(e)); return
        messagebox.showinfo("Exported", f"Wrote {path}")
        self.win.destroy()


# ── Duplicates dialog ────────────────────────────────────────────

class DuplicatesDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Duplicate candidates")
        self.win.geometry("900x520")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        top = ttk.Frame(self.win, padding=8); top.pack(fill="x")
        ttk.Label(top, text="Threshold:").pack(side="left")
        self.thresh_e = ttk.Entry(top, width=6)
        self.thresh_e.insert(0, "0.85")
        self.thresh_e.pack(side="left", padx=4)
        ttk.Button(top, text="Scan",
                    command=self.refresh).pack(side="left")
        cols = ("score", "keep", "keep_name", "keep_dob",
                "merge", "merge_name", "merge_dob")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"score": 60, "keep": 50, "keep_name": 180,
                  "keep_dob": 100, "merge": 60,
                  "merge_name": 180, "merge_dob": 100}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win, padding=8); bar.pack(fill="x")
        ttk.Button(bar, text="Merge selected (keep → absorb)",
                    command=self._merge).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        try:
            t = float(self.thresh_e.get())
        except ValueError:
            t = 0.85
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in data.find_duplicates(threshold=t):
            self.tree.insert("", "end",
                              iid=f"{c.primary.alumni_id}:"
                                    f"{c.other.alumni_id}",
                              values=(f"{c.score:.2f}",
                                       c.primary.alumni_id,
                                       c.primary.full_name,
                                       c.primary.dob or "—",
                                       c.other.alumni_id,
                                       c.other.full_name,
                                       c.other.dob or "—"))

    def _merge(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        keep_id, other_id = sel[0].split(":")
        if not messagebox.askyesno(
                "Merge", f"Merge #{other_id} into #{keep_id}? "
                            "Irreversible."):
            return
        try:
            data.merge_alumni(int(keep_id), int(other_id))
        except Exception as e:
            messagebox.showerror("Merge failed", str(e)); return
        self.refresh()


# ── Trash dialog ─────────────────────────────────────────────────

class TrashDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Soft-delete trash"); self.win.geometry(
            "780x440")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        cols = ("id", "name", "leaving_year", "deleted_at")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"id": 60, "name": 220, "leaving_year": 100,
                  "deleted_at": 200}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win, padding=8); bar.pack(fill="x")
        ttk.Button(bar, text="Restore",
                    command=self._restore).pack(side="left")
        ttk.Button(bar, text="Purge",
                    command=self._purge).pack(side="left", padx=4)
        ttk.Button(bar, text="Purge all expired",
                    command=self._purge_expired).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for a in data.list_soft_deleted():
            self.tree.insert("", "end", iid=str(a.alumni_id),
                              values=(a.alumni_id, a.full_name,
                                       a.leaving_year or "—",
                                       a.deleted_at or "—"))

    def _restore(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        try:
            data.restore_alumnus(int(sel[0]))
        except Exception as e:
            messagebox.showerror("Restore failed", str(e)); return
        self.refresh()

    def _purge(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        if not messagebox.askyesno(
                "Purge", "Permanently delete this alumnus? "
                            "Irreversible."):
            return
        data.purge_alumnus(int(sel[0]))
        self.refresh()

    def _purge_expired(self) -> None:
        n = data.purge_expired_soft_deletes()
        messagebox.showinfo(
            "Purged", f"Removed {n} alumnus/alumni older than "
                       f"{data.SOFT_DELETE_UNDO_DAYS} days.")
        self.refresh()


# ── Saved searches dialog ────────────────────────────────────────

class SavedSearchesDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent
        self.win = tk.Toplevel(parent)
        self.win.title("Saved searches"); self.win.geometry(
            "780x440")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        cols = ("id", "name", "filters", "owner", "created_at")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 180, "filters": 300,
                  "owner": 80, "created_at": 160}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win, padding=8); bar.pack(fill="x")
        ttk.Button(bar, text="New…",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Run",
                    command=self._run).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in data.list_saved_searches():
            self.tree.insert(
                "", "end", iid=str(s.search_id),
                values=(s.search_id, s.name,
                         ", ".join(f"{k}={v}" for k, v
                                    in s.filters.items()),
                         s.owner_staff_id or "",
                         s.created_at))

    def _selected_name(self) -> str | None:
        sel = self.tree.selection()
        if not sel: return None
        sid = int(sel[0])
        rows = data.list_saved_searches()
        m = next((s for s in rows if s.search_id == sid), None)
        return m.name if m else None

    def _new(self) -> None:
        win = tk.Toplevel(self.win); win.title("New saved search")
        win.transient(self.win); win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack()
        entries: dict[str, ttk.Widget] = {}

        def row(label: str, w: tk.Widget) -> None:
            r = len(entries)
            ttk.Label(form, text=label + ":").grid(
                row=r, column=0, sticky="e", padx=4, pady=2)
            w.grid(row=r, column=1, sticky="w", padx=4)
            entries[label] = w

        row("Name",        ttk.Entry(form, width=28))
        row("Year",        ttk.Entry(form, width=12))
        dest_cb = ttk.Combobox(form, values=("",) + DESTINATION_TYPES,
                                  state="readonly", width=22)
        row("Destination", dest_cb)
        row("Employer",    ttk.Entry(form, width=28))
        row("University",  ttk.Entry(form, width=28))
        sec_cb = ttk.Combobox(form, values=("",) + SECTORS,
                                 state="readonly", width=22)
        row("Sector",      sec_cb)
        row("Country",     ttk.Entry(form, width=20))
        row("Tag",         ttk.Entry(form, width=20))
        opt_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Contactable only",
                          variable=opt_var).grid(
            row=len(entries), column=1, sticky="w", padx=4)

        def get(label: str) -> str:
            w = entries[label]
            if isinstance(w, ttk.Combobox):
                return w.get().strip()
            return w.get().strip()  # type: ignore[attr-defined]

        def save() -> None:
            name = get("Name")
            if not name:
                messagebox.showerror("Save", "Name is required")
                return
            filters: dict[str, Any] = {}
            mappings = (
                ("Year",        "leaving_year"),
                ("Destination", "destination_type"),
                ("Employer",    "employer"),
                ("University",  "university"),
                ("Sector",      "sector"),
                ("Country",     "country"),
                ("Tag",         "tag"),
            )
            for lbl, key in mappings:
                v = get(lbl)
                if v:
                    filters[key] = v
            if opt_var.get():
                filters["contactable_only"] = True
            try:
                data.save_search(name, filters, replace=True)
            except Exception as e:
                messagebox.showerror("Save failed", str(e))
                return
            win.destroy(); self.refresh()

        bar = ttk.Frame(form); bar.grid(row=len(entries) + 1,
                                          column=0, columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _run(self) -> None:
        name = self._selected_name()
        if not name: return
        try:
            rows = data.run_saved_search(name)
        except Exception as e:
            messagebox.showerror("Run failed", str(e)); return
        ReportTableDialog(
            self.win, title=f"Saved search — {name}",
            columns=["id", "name", "year", "destination",
                      "employer", "email", "status"],
            rows=[[a.alumni_id, a.full_name, a.leaving_year or "—",
                    a.destination_type,
                    a.current_employer or "—", a.email or "—",
                    a.status] for a in rows])

    def _delete(self) -> None:
        name = self._selected_name()
        if not name: return
        if not messagebox.askyesno(
                "Delete", f"Delete saved search '{name}'?"):
            return
        data.delete_saved_search(name)
        self.refresh()


# ── Surveys dialog ───────────────────────────────────────────────

class SurveysDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent
        self.win = tk.Toplevel(parent)
        self.win.title("Surveys"); self.win.geometry("860x500")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        cols = ("id", "name", "status", "invited", "sent",
                "completed", "created_at")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 220, "status": 90,
                  "invited": 70, "sent": 70, "completed": 80,
                  "created_at": 160}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win, padding=8); bar.pack(fill="x")
        ttk.Button(bar, text="New survey…",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Invite cohort…",
                    command=self._invite).pack(side="left", padx=4)
        ttk.Button(bar, text="Responses",
                    command=self._responses).pack(side="left",
                                                     padx=4)
        ttk.Button(bar, text="Close survey",
                    command=self._close).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in data.list_surveys():
            st = data.survey_stats(s.survey_id)
            self.tree.insert("", "end", iid=str(s.survey_id),
                              values=(s.survey_id, s.name, s.status,
                                       st.invited, st.sent,
                                       st.completed, s.created_at))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        win = tk.Toplevel(self.win); win.title("New survey")
        win.transient(self.win); win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack(fill="both",
                                                          expand=True)
        ttk.Label(form, text="Name:").grid(row=0, column=0,
                                                sticky="e", padx=4,
                                                pady=3)
        name_e = ttk.Entry(form, width=40)
        name_e.grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(form, text="Description:").grid(
            row=1, column=0, sticky="ne", padx=4, pady=3)
        desc_t = tk.Text(form, width=40, height=2)
        desc_t.grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(form,
                    text="Questions (one per line: key | prompt | "
                          "type):",
                    foreground="#555").grid(
            row=2, column=0, columnspan=2,
            sticky="w", padx=4, pady=(8, 0))
        ttk.Label(form,
                    text=(f"Allowed types: "
                           f"{', '.join(sorted(data.SURVEY_QUESTION_TARGETS))}"),
                    foreground="#888").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=4)
        qs_t = tk.Text(form, width=60, height=10)
        qs_t.insert("1.0",
                       "role | What's your current role? | "
                       "current_role\n"
                       "employer | Who do you work for? | "
                       "current_employer\n"
                       "feedback | Anything to share? | freeform\n")
        qs_t.grid(row=4, column=0, columnspan=2,
                    sticky="w", padx=4)

        def save() -> None:
            qs: list[dict[str, str]] = []
            for line in qs_t.get("1.0", "end").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 2:
                    continue
                qs.append({
                    "key":    parts[0],
                    "prompt": parts[1],
                    "type":   parts[2] if len(parts) >= 3
                                else "freeform",
                })
            try:
                data.create_survey(
                    name_e.get().strip(), qs,
                    description=desc_t.get("1.0",
                                              "end").strip() or None)
            except Exception as e:
                messagebox.showerror("Save failed", str(e))
                return
            win.destroy(); self.refresh()

        bar = ttk.Frame(form); bar.grid(row=5, column=0,
                                          columnspan=2,
                                          pady=(12, 0))
        ttk.Button(bar, text="Create",
                    command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _invite(self) -> None:
        sid = self._selected_id()
        if sid is None: return
        win = tk.Toplevel(self.win); win.title("Invite cohort")
        win.transient(self.win); win.after_idle(win.grab_set)
        form = ttk.Frame(win, padding=12); form.pack()
        ttk.Label(form, text="Leaving year (blank = all):").grid(
            row=0, column=0, sticky="e", padx=4, pady=3)
        year_e = ttk.Entry(form, width=8)
        year_e.grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="Sender staff id:").grid(
            row=1, column=0, sticky="e", padx=4, pady=3)
        staff_e = ttk.Entry(form, width=12)
        staff_e.grid(row=1, column=1, sticky="w")

        def go() -> None:
            filters: dict[str, Any] = {"status": "Active"}
            if year_e.get().strip():
                filters["leaving_year"] = year_e.get().strip()
            try:
                sent, skipped = data.send_survey_invitations(
                    sid, filters,
                    staff_id=staff_e.get().strip() or None)
            except Exception as e:
                messagebox.showerror("Invite failed", str(e))
                return
            messagebox.showinfo(
                "Invitations sent",
                f"sent={sent}  skipped={skipped}")
            win.destroy(); self.refresh()

        bar = ttk.Frame(form); bar.grid(row=2, column=0,
                                          columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Send", command=go).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _responses(self) -> None:
        sid = self._selected_id()
        if sid is None: return
        resps = data.list_survey_responses(sid)
        win = tk.Toplevel(self.win)
        win.title(f"Responses — survey #{sid}")
        win.geometry("760x500"); win.transient(self.win)
        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        if not resps:
            txt.insert("end", "(no responses)")
        for r in resps:
            txt.insert("end",
                          f"Invitation #{r.invitation_id}  "
                          f"submitted {r.submitted_at}\n")
            for k, v in r.answers.items():
                txt.insert("end", f"  {k}: {v}\n")
            txt.insert("end", "\n")
        txt.configure(state="disabled")
        ttk.Button(win, text="Close",
                    command=win.destroy).pack(pady=(0, 8))

    def _close(self) -> None:
        sid = self._selected_id()
        if sid is None: return
        try:
            data.close_survey(sid)
        except Exception as e:
            messagebox.showerror("Close failed", str(e)); return
        self.refresh()

    def _delete(self) -> None:
        sid = self._selected_id()
        if sid is None: return
        if not messagebox.askyesno(
                "Delete",
                "Delete survey + invitations + responses?"):
            return
        data.delete_survey(sid)
        self.refresh()


# ══ Engagement extensions (items 1–8) ═════════════════════════════

def _pick_alumnus_dialog(parent: tk.Misc, *,
                            exclude: int | None = None) -> int | None:
    """Modal alumnus picker. Returns the chosen alumni_id or None."""
    rows = [a for a in data.list_alumni() if a.alumni_id != exclude]
    if not rows:
        messagebox.showinfo("Pick alumnus", "No alumni available.")
        return None
    dlg = tk.Toplevel(parent)
    dlg.title("Pick alumnus")
    dlg.transient(parent)
    dlg.after_idle(dlg.grab_set)
    tk.Label(dlg, text="Search:").pack(anchor="w", padx=8, pady=(8, 0))
    sv = tk.StringVar()
    ent = ttk.Entry(dlg, textvariable=sv, width=40)
    ent.pack(fill="x", padx=8)
    tree = ttk.Treeview(dlg, columns=("id", "name", "year"),
                          show="headings", height=12)
    tree.heading("id", text="ID")
    tree.heading("name", text="Name")
    tree.heading("year", text="Year")
    tree.column("id", width=60)
    tree.column("name", width=260)
    tree.column("year", width=70)
    tree.pack(fill="both", expand=True, padx=8, pady=8)
    chosen: dict[str, int | None] = {"id": None}

    def repopulate(*_: object) -> None:
        q = sv.get().strip().lower()
        for i in tree.get_children():
            tree.delete(i)
        for a in rows:
            if q and q not in a.full_name.lower() \
                    and q not in (a.leaving_year or ""):
                continue
            tree.insert("", "end", iid=str(a.alumni_id),
                         values=(a.alumni_id, a.full_name,
                                 a.leaving_year or "—"))
    sv.trace_add("write", repopulate)
    repopulate()

    def accept(_e: object = None) -> None:
        sel = tree.selection()
        if not sel: return
        chosen["id"] = int(sel[0])
        dlg.destroy()
    tree.bind("<Double-1>", accept)
    bar = ttk.Frame(dlg); bar.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Button(bar, text="OK", command=accept).pack(side="right")
    ttk.Button(bar, text="Cancel",
                 command=dlg.destroy).pack(side="right", padx=4)
    ent.focus_set()
    parent.wait_window(dlg)
    return chosen["id"]


# ── Per-alumnus: Social handles ───────────────────────────────────

class SocialHandlesTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Social")
        cols = ("id", "platform", "handle", "verified", "url")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "platform": 110, "handle": 200,
                    "verified": 70, "url": 320}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Button(bar, text="Add",
                     command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit",
                     command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="Verify",
                     command=self._verify).pack(side="left")
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in data.list_social_handles(self.alumni_id):
            self.tree.insert("", "end", iid=str(s.handle_id),
                              values=(s.handle_id, s.platform, s.handle,
                                      "✓" if s.verified else "",
                                      s.url or ""))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        SocialHandleDialog(self.frame.winfo_toplevel(),
                              alumni_id=self.alumni_id, existing=None,
                              on_save=self.refresh)

    def _edit(self) -> None:
        hid = self._selected_id()
        if hid is None: return
        cur = next((s for s in data.list_social_handles(self.alumni_id)
                      if s.handle_id == hid), None)
        if cur is None: return
        SocialHandleDialog(self.frame.winfo_toplevel(),
                              alumni_id=self.alumni_id, existing=cur,
                              on_save=self.refresh)

    def _verify(self) -> None:
        hid = self._selected_id()
        if hid is None: return
        try:
            data.verify_social_handle(hid)
        except Exception as e:
            messagebox.showerror("Verify", str(e)); return
        self.refresh()

    def _delete(self) -> None:
        hid = self._selected_id()
        if hid is None: return
        if not messagebox.askyesno("Delete", f"Delete handle #{hid}?"):
            return
        data.delete_social_handle(hid)
        self.refresh()


class SocialHandleDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 existing, on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Social handle")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        frm = ttk.Frame(self.win, padding=10); frm.pack(fill="both",
                                                          expand=True)
        ttk.Label(frm, text="Platform:").grid(row=0, column=0,
                                                sticky="w")
        self.platform = ttk.Combobox(frm, values=list(SOCIAL_PLATFORMS),
                                        state="readonly", width=24)
        self.platform.grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Handle:").grid(row=1, column=0, sticky="w")
        self.handle = ttk.Entry(frm, width=40)
        self.handle.grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="URL:").grid(row=2, column=0, sticky="w")
        self.url = ttk.Entry(frm, width=40)
        self.url.grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Notes:").grid(row=3, column=0, sticky="w")
        self.notes = ttk.Entry(frm, width=40)
        self.notes.grid(row=3, column=1, sticky="w", pady=2)
        self.verified_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Verified",
                          variable=self.verified_var
                          ).grid(row=4, column=1, sticky="w")
        if existing:
            self.platform.set(existing.platform)
            self.platform.configure(state="disabled")
            self.handle.insert(0, existing.handle)
            self.url.insert(0, existing.url or "")
            self.notes.insert(0, existing.notes or "")
            self.verified_var.set(existing.verified)
        else:
            self.platform.set("LinkedIn")
        bar = ttk.Frame(frm); bar.grid(row=5, column=0, columnspan=2,
                                          pady=8, sticky="e")
        ttk.Button(bar, text="Save",
                     command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel",
                     command=self.win.destroy
                     ).pack(side="right", padx=4)

    def _save(self) -> None:
        try:
            if self.existing:
                data.update_social_handle(
                    self.existing.handle_id,
                    {"handle": self.handle.get(),
                     "url": self.url.get(),
                     "notes": self.notes.get(),
                     "verified": self.verified_var.get()})
            else:
                data.add_social_handle(
                    self.alumni_id,
                    self.platform.get(), self.handle.get(),
                    url=self.url.get() or None,
                    verified=self.verified_var.get(),
                    notes=self.notes.get() or None)
        except Exception as e:
            messagebox.showerror("Save", str(e)); return
        self.on_save()
        self.win.destroy()


# ── Per-alumnus: Connections ──────────────────────────────────────

class ConnectionsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Connections")
        cols = ("id", "other_id", "name", "kind", "since")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "other_id": 70, "name": 240,
                    "kind": 110, "since": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Button(bar, text="Connect…",
                     command=self._connect).pack(side="left")
        ttk.Button(bar, text="Disconnect",
                     command=self._disconnect).pack(side="left", padx=4)
        ttk.Button(bar, text="Mutuals with…",
                     command=self._mutuals).pack(side="left")
        ttk.Button(bar, text="Degrees-between…",
                     command=self._degrees).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for c, other in data.list_connections(self.alumni_id):
            self.tree.insert(
                "", "end", iid=str(c.connection_id),
                values=(c.connection_id, other.alumni_id,
                          other.full_name, c.kind, c.since or "—"))

    def _selected_other(self) -> int | None:
        sel = self.tree.selection()
        if not sel: return None
        vals = self.tree.item(sel[0], "values")
        return int(vals[1])

    def _connect(self) -> None:
        other = _pick_alumnus_dialog(self.frame.winfo_toplevel(),
                                        exclude=self.alumni_id)
        if other is None: return
        kind = _ask_choice(self.frame, "Kind",
                              list(CONNECTION_KINDS), default="Friend")
        if not kind: return
        try:
            data.connect_alumni(self.alumni_id, other, kind=kind)
        except Exception as e:
            messagebox.showerror("Connect", str(e)); return
        self.refresh()

    def _disconnect(self) -> None:
        other = self._selected_other()
        if other is None: return
        if not messagebox.askyesno("Disconnect",
                                      "Remove this connection?"):
            return
        data.disconnect_alumni(self.alumni_id, other)
        self.refresh()

    def _mutuals(self) -> None:
        other = _pick_alumnus_dialog(self.frame.winfo_toplevel(),
                                        exclude=self.alumni_id)
        if other is None: return
        rows = data.mutuals_of(self.alumni_id, other)
        if not rows:
            messagebox.showinfo("Mutuals", "(no mutuals)")
            return
        msg = "\n".join(f"#{a.alumni_id}  {a.full_name}" for a in rows)
        messagebox.showinfo("Mutuals", msg)

    def _degrees(self) -> None:
        other = _pick_alumnus_dialog(self.frame.winfo_toplevel(),
                                        exclude=self.alumni_id)
        if other is None: return
        d = data.degrees_between(self.alumni_id, other)
        messagebox.showinfo(
            "Degrees",
            "Unconnected within depth 6"
            if d is None else f"{d} hop(s) apart")


def _ask_choice(parent: tk.Misc, title: str, options: list[str], *,
                  default: str | None = None) -> str | None:
    dlg = tk.Toplevel(parent.winfo_toplevel())
    dlg.title(title); dlg.transient(parent.winfo_toplevel())
    dlg.after_idle(dlg.grab_set)
    ttk.Label(dlg, text=title + ":").pack(anchor="w",
                                              padx=8, pady=(8, 0))
    var = tk.StringVar(value=default or options[0])
    cb = ttk.Combobox(dlg, values=options, textvariable=var,
                        state="readonly", width=24)
    cb.pack(padx=8, pady=8)
    out: dict[str, str | None] = {"v": None}

    def accept() -> None:
        out["v"] = var.get(); dlg.destroy()
    ttk.Button(dlg, text="OK",
                 command=accept).pack(pady=(0, 8))
    parent.winfo_toplevel().wait_window(dlg)
    return out["v"]


# ── Per-alumnus: Engagement score ────────────────────────────────

class EngagementTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Engagement")
        self.text = tk.Text(self.frame, height=20, wrap="word",
                              state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        try:
            s = data.compute_engagement_score(self.alumni_id)
        except Exception as e:
            text = f"Error: {e}"
        else:
            text = (f"Score:                {s.score}\n"
                      f"Decay multiplier:     {s.decay}\n"
                      f"Months since contact: "
                      f"{s.months_since_contact if s.months_since_contact is not None else '—'}\n\n"
                      f"Comms opens:          {s.comms_opens}\n"
                      f"Events attended:      {s.events_attended}\n"
                      f"Donations:            {s.donations_count} "
                      f"({_money_str(s.donation_total_pence)})\n"
                      f"Volunteer hours:      {s.volunteer_hours}\n")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.configure(state="disabled")


# ── Per-alumnus: Chapter memberships ─────────────────────────────

class ChapterMembershipTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Chapters")
        cols = ("chapter_id", "name", "kind", "role", "joined", "left")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"chapter_id": 70, "name": 220, "kind": 90,
                    "role": 110, "joined": 90, "left": 90}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Button(bar, text="Join chapter…",
                     command=self._join).pack(side="left")
        ttk.Button(bar, text="Leave",
                     command=self._leave).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for cm, ch in data.list_chapters_for(self.alumni_id,
                                                include_left=True):
            self.tree.insert(
                "", "end", iid=str(ch.chapter_id),
                values=(ch.chapter_id, ch.name, ch.kind, cm.role,
                          cm.joined_on or "—", cm.left_on or "—"))

    def _join(self) -> None:
        all_chapters = data.list_chapters()
        if not all_chapters:
            messagebox.showinfo("Join chapter", "No chapters exist.")
            return
        names = [c.name for c in all_chapters]
        pick = _ask_choice(self.frame, "Chapter", names)
        if not pick: return
        chosen = next(c for c in all_chapters if c.name == pick)
        role = _ask_choice(self.frame, "Role",
                              list(CHAPTER_ROLES), default="Member")
        if not role: return
        try:
            data.add_chapter_member(chosen.chapter_id, self.alumni_id,
                                       role=role)
        except Exception as e:
            messagebox.showerror("Join", str(e)); return
        self.refresh()

    def _leave(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        cid = int(sel[0])
        if not messagebox.askyesno("Leave",
                                      "Mark as left this chapter?"):
            return
        data.remove_chapter_member(cid, self.alumni_id)
        self.refresh()


# ── Per-alumnus: Directory consent ────────────────────────────────

class DirectoryConsentTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Directory")
        self.status = ttk.Label(self.frame, text="",
                                  font=("TkDefaultFont", 11, "bold"))
        self.status.pack(anchor="w", padx=12, pady=(12, 6))
        ttk.Label(self.frame,
                    text=("Public directory listing publishes the "
                          "alumnus's name, year, role, employer, sector "
                          "and (optionally) LinkedIn / bio. DOB, email, "
                          "phone and address are never published."),
                    wraplength=600, foreground="#555"
                    ).pack(anchor="w", padx=12, pady=(0, 12))
        bar = ttk.Frame(self.frame); bar.pack(anchor="w", padx=12)
        ttk.Button(bar, text="Opt-in",
                     command=self._opt_in).pack(side="left")
        ttk.Button(bar, text="Opt-out",
                     command=self._opt_out).pack(side="left", padx=8)
        self.refresh()

    def refresh(self) -> None:
        listed = data.is_in_directory(self.alumni_id)
        self.status.configure(
            text=("Listed in public directory ✓"
                    if listed else "Not listed in public directory"),
            foreground=("#2a7" if listed else "#a44"))

    def _opt_in(self) -> None:
        try:
            data.opt_in_directory(self.alumni_id, source="gui",
                                      actor="gui")
        except Exception as e:
            messagebox.showerror("Opt-in", str(e)); return
        self.refresh()

    def _opt_out(self) -> None:
        if not messagebox.askyesno(
                "Opt-out",
                "Withdraw the 'Directory' consent for this alumnus?"):
            return
        data.opt_out_directory(self.alumni_id, actor="gui")
        self.refresh()


# ── Top-level: Chapters ──────────────────────────────────────────

class ChaptersTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Chapters")
        cols = ("id", "name", "kind", "region", "status")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 280, "kind": 110, "region": 160,
                    "status": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="New",
                     command=self._new).pack(side="left")
        ttk.Button(bar, text="Edit",
                     command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left")
        ttk.Button(bar, text="Members…",
                     command=self._members).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in data.list_chapters():
            self.tree.insert("", "end", iid=str(c.chapter_id),
                              values=(c.chapter_id, c.name, c.kind,
                                      c.region or "—", c.status))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        ChapterDialog(self.frame.winfo_toplevel(),
                        existing=None, on_save=self.refresh)

    def _edit(self) -> None:
        cid = self._selected_id()
        if cid is None: return
        cur = data.get_chapter(cid)
        if cur is None: return
        ChapterDialog(self.frame.winfo_toplevel(),
                        existing=cur, on_save=self.refresh)

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None: return
        if not messagebox.askyesno("Delete",
                                      f"Delete chapter #{cid}?"):
            return
        data.delete_chapter(cid)
        self.refresh()

    def _members(self) -> None:
        cid = self._selected_id()
        if cid is None: return
        ChapterMembersDialog(self.frame.winfo_toplevel(), cid)


class ChapterDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing, on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Chapter")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        frm = ttk.Frame(self.win, padding=10); frm.pack(fill="both",
                                                          expand=True)
        ttk.Label(frm, text="Name:").grid(row=0, column=0, sticky="w")
        self.name = ttk.Entry(frm, width=40)
        self.name.grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Kind:").grid(row=1, column=0, sticky="w")
        self.kind = ttk.Combobox(frm, values=list(CHAPTER_KINDS),
                                    state="readonly", width=20)
        self.kind.grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Region:").grid(row=2, column=0, sticky="w")
        self.region = ttk.Entry(frm, width=40)
        self.region.grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Description:").grid(row=3, column=0,
                                                    sticky="nw")
        self.desc = tk.Text(frm, width=40, height=4)
        self.desc.grid(row=3, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Status:").grid(row=4, column=0, sticky="w")
        self.status = ttk.Combobox(frm, values=["Active", "Archived"],
                                      state="readonly", width=20)
        self.status.grid(row=4, column=1, sticky="w", pady=2)
        if existing:
            self.name.insert(0, existing.name)
            self.kind.set(existing.kind)
            self.region.insert(0, existing.region or "")
            self.desc.insert("1.0", existing.description or "")
            self.status.set(existing.status)
        else:
            self.kind.set("Regional")
            self.status.set("Active")
        bar = ttk.Frame(frm); bar.grid(row=5, column=0, columnspan=2,
                                          pady=8, sticky="e")
        ttk.Button(bar, text="Save",
                     command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel",
                     command=self.win.destroy
                     ).pack(side="right", padx=4)

    def _save(self) -> None:
        payload = {
            "name": self.name.get().strip(),
            "kind": self.kind.get(),
            "region": self.region.get(),
            "description": self.desc.get("1.0", "end").strip(),
            "status": self.status.get(),
        }
        try:
            if self.existing:
                data.update_chapter(self.existing.chapter_id, payload)
            else:
                data.create_chapter(
                    payload["name"], kind=payload["kind"],
                    region=payload["region"] or None,
                    description=payload["description"] or None)
        except Exception as e:
            messagebox.showerror("Save", str(e)); return
        self.on_save()
        self.win.destroy()


class ChapterMembersDialog:
    def __init__(self, parent: tk.Misc, chapter_id: int) -> None:
        self.chapter_id = chapter_id
        chapter = data.get_chapter(chapter_id)
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Chapter members — {chapter.name if chapter else chapter_id}")
        self.win.transient(parent); self.win.geometry("700x500")
        cols = ("alumni_id", "name", "role", "joined", "left")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"alumni_id": 70, "name": 260, "role": 110,
                    "joined": 100, "left": 100}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.include_left = tk.BooleanVar(value=False)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Checkbutton(bar, text="Include former members",
                          variable=self.include_left,
                          command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Add member…",
                     command=self._add).pack(side="left", padx=12)
        ttk.Button(bar, text="Set role…",
                     command=self._role).pack(side="left")
        ttk.Button(bar, text="Remove",
                     command=self._remove).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for cm, al in data.list_chapter_members(
                self.chapter_id,
                include_left=self.include_left.get()):
            self.tree.insert(
                "", "end", iid=str(al.alumni_id),
                values=(al.alumni_id, al.full_name, cm.role,
                          cm.joined_on or "—", cm.left_on or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        aid = _pick_alumnus_dialog(self.win)
        if aid is None: return
        role = _ask_choice(self.win, "Role",
                              list(CHAPTER_ROLES), default="Member")
        if not role: return
        try:
            data.add_chapter_member(self.chapter_id, aid, role=role)
        except Exception as e:
            messagebox.showerror("Add", str(e)); return
        self.refresh()

    def _role(self) -> None:
        aid = self._selected()
        if aid is None: return
        role = _ask_choice(self.win, "Role", list(CHAPTER_ROLES))
        if not role: return
        try:
            data.set_chapter_role(self.chapter_id, aid, role)
        except Exception as e:
            messagebox.showerror("Role", str(e)); return
        self.refresh()

    def _remove(self) -> None:
        aid = self._selected()
        if aid is None: return
        if not messagebox.askyesno("Remove",
                                      "Mark this member as left?"):
            return
        data.remove_chapter_member(self.chapter_id, aid)
        self.refresh()


# ── Top-level: Re-engagement worklist ────────────────────────────

class ReEngagementTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Re-engagement")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Score <").pack(side="left")
        self.thr = ttk.Entry(bar, width=6); self.thr.insert(0, "5")
        self.thr.pack(side="left", padx=4)
        ttk.Label(bar, text="OR quiet ≥").pack(side="left", padx=(8, 0))
        self.months = ttk.Entry(bar, width=6)
        self.months.insert(0, "18"); self.months.pack(side="left", padx=4)
        ttk.Label(bar, text="months   Year:").pack(side="left",
                                                       padx=(0, 0))
        self.year = ttk.Entry(bar, width=8)
        self.year.pack(side="left", padx=4)
        ttk.Button(bar, text="Run",
                     command=self.refresh).pack(side="left", padx=8)
        cols = ("score", "alumni_id", "name", "year", "months", "reason")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"score": 70, "alumni_id": 70, "name": 240,
                    "year": 60, "months": 70, "reason": 360}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            thr = float(self.thr.get() or "5")
            months = int(self.months.get() or "18")
        except ValueError:
            messagebox.showerror("Inputs",
                                    "Threshold/months must be numeric")
            return
        year = self.year.get().strip() or None
        for c in data.re_engagement_worklist(
                score_threshold=thr, months_quiet=months,
                leaving_year=year):
            self.tree.insert(
                "", "end", iid=str(c.alumnus.alumni_id),
                values=(c.score, c.alumnus.alumni_id,
                          c.alumnus.full_name,
                          c.alumnus.leaving_year or "—",
                          c.months_since_contact
                            if c.months_since_contact is not None else "—",
                          c.reason))


# ── Top-level: Milestones ────────────────────────────────────────

class MilestonesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Milestones")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Days ahead:").pack(side="left")
        self.days = ttk.Entry(bar, width=6); self.days.insert(0, "30")
        self.days.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=8)
        cols = ("when", "kind", "years", "alumni_id", "name", "detail")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"when": 110, "kind": 170, "years": 60,
                    "alumni_id": 70, "name": 240, "detail": 320}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            days = int(self.days.get() or "30")
        except ValueError:
            messagebox.showerror("Days", "Must be a number"); return
        for m in data.upcoming_milestones(days=days):
            self.tree.insert(
                "", "end",
                values=(m.when, m.kind, m.years or "",
                          m.alumni_id, m.full_name, m.detail or ""))


# ── Top-level: Lost contact queue ────────────────────────────────

class LostContactTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Lost contact")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Bounce threshold:").pack(side="left")
        self.thr = ttk.Entry(bar, width=6)
        self.thr.insert(0, str(data.HARD_BOUNCE_THRESHOLD))
        self.thr.pack(side="left", padx=4)
        self.no_phone = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Require no phone",
                          variable=self.no_phone
                          ).pack(side="left", padx=8)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=8)
        cols = ("alumni_id", "name", "bounces", "email",
                "phone", "addr", "last_contacted")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"alumni_id": 70, "name": 240, "bounces": 70,
                    "email": 60, "phone": 60, "addr": 60,
                    "last_contacted": 130}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            thr = int(self.thr.get() or "3")
        except ValueError:
            messagebox.showerror("Threshold",
                                    "Must be a number"); return
        for c in data.lost_contact_queue(
                bounce_threshold=thr,
                require_no_phone=self.no_phone.get()):
            self.tree.insert(
                "", "end", iid=str(c.alumnus.alumni_id),
                values=(c.alumnus.alumni_id, c.alumnus.full_name,
                          c.bounce_count,
                          "Y" if c.has_email else "N",
                          "Y" if c.has_phone else "N",
                          "Y" if c.has_address else "N",
                          c.last_contacted or "—"))


# ── Top-level: Public directory ──────────────────────────────────

class DirectoryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Directory")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year = ttk.Entry(bar, width=8)
        self.year.pack(side="left", padx=4)
        ttk.Label(bar, text="Sector:").pack(side="left", padx=(8, 0))
        self.sector = ttk.Entry(bar, width=14)
        self.sector.pack(side="left", padx=4)
        ttk.Label(bar, text="Search:").pack(side="left", padx=(8, 0))
        self.q = ttk.Entry(bar, width=22)
        self.q.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=8)
        cols = ("alumni_id", "name", "year", "role",
                "employer", "sector", "country")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"alumni_id": 70, "name": 220, "year": 60,
                    "role": 170, "employer": 170, "sector": 130,
                    "country": 100}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for d in data.list_public_directory(
                leaving_year=self.year.get().strip() or None,
                sector=self.sector.get().strip() or None,
                q=self.q.get().strip() or None):
            self.tree.insert(
                "", "end", iid=str(d.alumni_id),
                values=(d.alumni_id, d.display_name,
                          d.leaving_year or "—",
                          d.current_role or "—",
                          d.current_employer or "—",
                          d.current_sector or "—",
                          d.country or "—"))


# ══ Career-cluster extensions (items 9–16) ════════════════════════

# ── Per-alumnus: Skills ───────────────────────────────────────────

class SkillsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Skills")
        cols = ("id", "name", "proficiency", "years")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 240, "proficiency": 130,
                    "years": 80}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Label(bar, text="Skill:").pack(side="left")
        self.entry = ttk.Entry(bar, width=20); self.entry.pack(side="left",
                                                                   padx=4)
        self.prof = ttk.Combobox(bar, values=list(PROFICIENCY_LEVELS),
                                    state="readonly", width=12)
        self.prof.set("Intermediate"); self.prof.pack(side="left")
        ttk.Label(bar, text="Years:").pack(side="left", padx=(8, 0))
        self.years = ttk.Entry(bar, width=6); self.years.pack(side="left",
                                                                   padx=4)
        ttk.Button(bar, text="Add / update",
                     command=self._add).pack(side="left", padx=4)
        ttk.Button(bar, text="Remove selected",
                     command=self._remove).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in data.list_skills_for(self.alumni_id):
            self.tree.insert(
                "", "end", iid=str(s.skill_id),
                values=(s.skill_id, s.skill_name, s.proficiency,
                          s.years if s.years is not None else "—"))

    def _add(self) -> None:
        name = self.entry.get().strip()
        if not name: return
        yrs_raw = self.years.get().strip()
        try:
            yrs = float(yrs_raw) if yrs_raw else None
            data.add_skill_to_alumnus(self.alumni_id, name,
                                          proficiency=self.prof.get(),
                                          years=yrs)
        except Exception as e:
            messagebox.showerror("Add skill", str(e)); return
        self.entry.delete(0, "end"); self.years.delete(0, "end")
        self.refresh()

    def _remove(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        data.remove_skill_from_alumnus(self.alumni_id, int(sel[0]))
        self.refresh()


# ── Per-alumnus: Promotion timeline ──────────────────────────────

class PromotionTimelineTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Timeline")
        cols = ("start", "end", "role", "employer", "current")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"start": 100, "end": 100, "role": 220,
                    "employer": 220, "current": 80}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        ttk.Button(self.frame, text="Refresh",
                     command=self.refresh).pack(anchor="w",
                                                  padx=4, pady=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in data.promotion_timeline(self.alumni_id):
            self.tree.insert(
                "", "end",
                values=(s.start_date or "—", s.end_date or "—",
                          s.role, s.employer,
                          "✓" if s.is_current else ""))


# ── Top-level: Employers directory ───────────────────────────────

class EmployersTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Employers")
        cols = ("id", "name", "sector", "website", "country")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 260, "sector": 130,
                    "website": 220, "country": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Add / update",
                     command=self._upsert).pack(side="left")
        ttk.Button(bar, text="Add alias",
                     command=self._alias).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left")
        ttk.Button(bar, text="Top employers report",
                     command=self._top).pack(side="left", padx=12)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for e in data.list_employers():
            self.tree.insert(
                "", "end", iid=str(e.employer_id),
                values=(e.employer_id, e.canonical_name,
                          e.sector or "—", e.website or "—",
                          e.country or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _upsert(self) -> None:
        EmployerDialog(self.frame.winfo_toplevel(),
                          existing=None, on_save=self.refresh)

    def _alias(self) -> None:
        eid = self._selected()
        if eid is None: return
        alias = _prompt_string(self.frame.winfo_toplevel(),
                                  "Alias", "Alias name:")
        if not alias: return
        try:
            data.add_employer_alias(alias, eid)
        except Exception as e:
            messagebox.showerror("Alias", str(e)); return
        messagebox.showinfo("Alias", f"Alias '{alias}' → #{eid}")

    def _delete(self) -> None:
        eid = self._selected()
        if eid is None: return
        if not messagebox.askyesno("Delete",
                                      f"Delete employer #{eid}?"):
            return
        data.delete_employer(eid)
        self.refresh()

    def _top(self) -> None:
        TopEmployersDialog(self.frame.winfo_toplevel())


class EmployerDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing, on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Employer")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        frm = ttk.Frame(self.win, padding=10); frm.pack(fill="both",
                                                          expand=True)
        ttk.Label(frm, text="Canonical name:").grid(row=0, column=0,
                                                       sticky="w")
        self.name = ttk.Entry(frm, width=40); self.name.grid(
            row=0, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Sector:").grid(row=1, column=0, sticky="w")
        self.sector = ttk.Combobox(frm, values=list(SECTORS), width=22)
        self.sector.grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Website:").grid(row=2, column=0, sticky="w")
        self.web = ttk.Entry(frm, width=40); self.web.grid(
            row=2, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Country:").grid(row=3, column=0, sticky="w")
        self.country = ttk.Entry(frm, width=22); self.country.grid(
            row=3, column=1, sticky="w", pady=2)
        bar = ttk.Frame(frm); bar.grid(row=4, column=0, columnspan=2,
                                          pady=8, sticky="e")
        ttk.Button(bar, text="Save",
                     command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel",
                     command=self.win.destroy
                     ).pack(side="right", padx=4)

    def _save(self) -> None:
        try:
            data.upsert_employer(self.name.get(),
                                     sector=self.sector.get() or None,
                                     website=self.web.get() or None,
                                     country=self.country.get() or None)
        except Exception as e:
            messagebox.showerror("Save", str(e)); return
        self.on_save()
        self.win.destroy()


class TopEmployersDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Top employers")
        self.win.transient(parent); self.win.geometry("600x500")
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year = ttk.Entry(bar, width=8); self.year.pack(side="left",
                                                                padx=4)
        ttk.Label(bar, text="Limit:").pack(side="left", padx=(8, 0))
        self.limit = ttk.Entry(bar, width=6); self.limit.insert(0, "25")
        self.limit.pack(side="left", padx=4)
        ttk.Button(bar, text="Run",
                     command=self.refresh).pack(side="left", padx=8)
        cols = ("count", "employer")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        self.tree.heading("count", text="#")
        self.tree.heading("employer", text="Employer")
        self.tree.column("count", width=60, anchor="w")
        self.tree.column("employer", width=420, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            lim = int(self.limit.get() or "25")
        except ValueError:
            messagebox.showerror("Limit", "Must be a number"); return
        year = self.year.get().strip() or None
        for r in data.top_employers(limit=lim, leaving_year=year):
            self.tree.insert("", "end",
                               values=(r.alumni_count, r.employer))


def _prompt_string(parent: tk.Misc, title: str,
                      label: str) -> str | None:
    dlg = tk.Toplevel(parent)
    dlg.title(title); dlg.transient(parent); dlg.after_idle(dlg.grab_set)
    ttk.Label(dlg, text=label).pack(padx=8, pady=(8, 0), anchor="w")
    var = tk.StringVar()
    ent = ttk.Entry(dlg, textvariable=var, width=30)
    ent.pack(padx=8, pady=8); ent.focus_set()
    out: dict[str, str | None] = {"v": None}

    def ok() -> None:
        out["v"] = var.get().strip() or None
        dlg.destroy()
    ent.bind("<Return>", lambda _e: ok())
    ttk.Button(dlg, text="OK", command=ok).pack(pady=(0, 8))
    parent.wait_window(dlg)
    return out["v"]


# ── Top-level: Job postings board ────────────────────────────────

class JobsBoardTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Jobs")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.status = ttk.Combobox(
            bar, values=["(all)", *JOB_STATUSES],
            state="readonly", width=10)
        self.status.set("Open"); self.status.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Post (per alumnus)…",
                     command=self._post).pack(side="left", padx=12)
        ttk.Button(bar, text="Set status…",
                     command=self._set_status).pack(side="left")
        ttk.Button(bar, text="Applicants…",
                     command=self._applicants).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left")
        cols = ("id", "title", "employer", "type", "salary",
                "status", "deadline")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "title": 200, "employer": 160,
                    "type": 100, "salary": 110, "status": 80,
                    "deadline": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        s = self.status.get()
        status = None if s == "(all)" else s
        for j in data.list_jobs(status=status):
            self.tree.insert(
                "", "end", iid=str(j.job_id),
                values=(j.job_id, j.title, j.employer or "—",
                          j.job_type, j.salary_band or "—",
                          j.status, j.deadline or "—"))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _post(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        JobDialog(self.frame.winfo_toplevel(), alumni_id=aid,
                     on_save=self.refresh)

    def _set_status(self) -> None:
        jid = self._selected_id()
        if jid is None: return
        st = _ask_choice(self.frame, "Status", list(JOB_STATUSES))
        if not st: return
        try:
            data.set_job_status(jid, st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()

    def _applicants(self) -> None:
        jid = self._selected_id()
        if jid is None: return
        JobApplicantsDialog(self.frame.winfo_toplevel(), jid)

    def _delete(self) -> None:
        jid = self._selected_id()
        if jid is None: return
        if not messagebox.askyesno("Delete", f"Delete job #{jid}?"):
            return
        data.delete_job(jid)
        self.refresh()


class JobDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Post a job"); self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        frm = ttk.Frame(self.win, padding=10); frm.pack(fill="both",
                                                          expand=True)
        rows = [
            ("Title", "title", None),
            ("Employer", "employer", None),
            ("Sector", "sector", list(SECTORS)),
            ("Location", "location", None),
            ("Job type", "job_type", list(JOB_TYPES)),
            ("Salary band", "salary_band", list(SALARY_BANDS)),
            ("Apply URL", "apply_url", None),
            ("Deadline (YYYY-MM-DD)", "deadline", None),
        ]
        self.widgets: dict[str, tk.Widget] = {}
        for i, (lbl, key, opts) in enumerate(rows):
            ttk.Label(frm, text=lbl + ":").grid(row=i, column=0,
                                                   sticky="w")
            if opts:
                w = ttk.Combobox(frm, values=opts, width=24)
            else:
                w = ttk.Entry(frm, width=40)
            w.grid(row=i, column=1, sticky="w", pady=2)
            self.widgets[key] = w
        ttk.Label(frm, text="Description:").grid(row=len(rows),
                                                    column=0, sticky="nw")
        self.desc = tk.Text(frm, width=40, height=4)
        self.desc.grid(row=len(rows), column=1, sticky="w", pady=2)
        if "Graduate" in JOB_TYPES:
            self.widgets["job_type"].set("Graduate")
        bar = ttk.Frame(frm); bar.grid(row=len(rows) + 1, column=0,
                                          columnspan=2, pady=8,
                                          sticky="e")
        ttk.Button(bar, text="Post",
                     command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel",
                     command=self.win.destroy
                     ).pack(side="right", padx=4)

    def _save(self) -> None:
        payload = {k: (w.get() if not isinstance(w, tk.Text)
                          else w.get("1.0", "end").strip())
                    for k, w in self.widgets.items()}
        payload["description"] = self.desc.get("1.0", "end").strip()
        try:
            data.post_job(self.alumni_id, payload)
        except Exception as e:
            messagebox.showerror("Post", str(e)); return
        self.on_save(); self.win.destroy()


class JobApplicantsDialog:
    def __init__(self, parent: tk.Misc, job_id: int) -> None:
        self.job_id = job_id
        self.win = tk.Toplevel(parent)
        self.win.title(f"Applicants — job #{job_id}")
        self.win.transient(parent); self.win.geometry("700x400")
        cols = ("app_id", "kind", "applicant", "applied", "status")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"app_id": 60, "kind": 80, "applicant": 120,
                    "applied": 120, "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Button(bar, text="Set status",
                     command=self._status).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in data.list_job_applications(self.job_id):
            self.tree.insert(
                "", "end", iid=str(r.application_id),
                values=(r.application_id, r.applicant_kind,
                          r.applicant_id, r.applied_on, r.status))

    def _status(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        st = _ask_choice(self.win, "Application status",
                            list(APPLICATION_STATUSES))
        if not st: return
        try:
            data.set_job_application_status(int(sel[0]), st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()


# ── Top-level: Internships board ─────────────────────────────────

class InternshipsBoardTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Internships")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.status = ttk.Combobox(
            bar, values=["(all)", *JOB_STATUSES],
            state="readonly", width=10)
        self.status.set("Open"); self.status.pack(side="left", padx=4)
        self.paid_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Paid only",
                          variable=self.paid_only,
                          command=self.refresh
                          ).pack(side="left", padx=8)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Post (per alumnus)…",
                     command=self._post).pack(side="left", padx=12)
        ttk.Button(bar, text="Set status",
                     command=self._set_status).pack(side="left")
        ttk.Button(bar, text="Applicants…",
                     command=self._applicants).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left")
        cols = ("id", "title", "employer", "weeks", "paid",
                "hourly", "status", "deadline")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "title": 200, "employer": 160,
                    "weeks": 70, "paid": 60, "hourly": 90,
                    "status": 80, "deadline": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        s = self.status.get()
        status = None if s == "(all)" else s
        for ip in data.list_internships(
                status=status, paid_only=self.paid_only.get()):
            self.tree.insert(
                "", "end", iid=str(ip.internship_id),
                values=(ip.internship_id, ip.title,
                          ip.employer or "—",
                          ip.duration_weeks or "—",
                          "Y" if ip.paid else "N",
                          _money_str(ip.hourly_pence),
                          ip.status, ip.deadline or "—"))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _post(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        InternshipDialog(self.frame.winfo_toplevel(),
                            alumni_id=aid, on_save=self.refresh)

    def _set_status(self) -> None:
        iid = self._selected_id()
        if iid is None: return
        st = _ask_choice(self.frame, "Status", list(JOB_STATUSES))
        if not st: return
        try:
            data.set_internship_status(iid, st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()

    def _applicants(self) -> None:
        iid = self._selected_id()
        if iid is None: return
        InternshipApplicantsDialog(self.frame.winfo_toplevel(), iid)

    def _delete(self) -> None:
        iid = self._selected_id()
        if iid is None: return
        if not messagebox.askyesno("Delete",
                                      f"Delete internship #{iid}?"):
            return
        data.delete_internship(iid)
        self.refresh()


class InternshipDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Post an internship")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        frm = ttk.Frame(self.win, padding=10); frm.pack(fill="both",
                                                          expand=True)
        rows = [
            ("Title", "title", None),
            ("Employer", "employer", None),
            ("Sector", "sector", list(SECTORS)),
            ("Location", "location", None),
            ("Duration weeks", "duration_weeks", None),
            ("Hourly pay £ (e.g. 12.50)", "hourly_pay", None),
            ("Start window", "start_window", None),
            ("Apply URL", "apply_url", None),
            ("Deadline (YYYY-MM-DD)", "deadline", None),
        ]
        self.widgets: dict[str, tk.Widget] = {}
        for i, (lbl, key, opts) in enumerate(rows):
            ttk.Label(frm, text=lbl + ":").grid(row=i, column=0,
                                                   sticky="w")
            if opts:
                w = ttk.Combobox(frm, values=opts, width=24)
            else:
                w = ttk.Entry(frm, width=40)
            w.grid(row=i, column=1, sticky="w", pady=2)
            self.widgets[key] = w
        self.paid_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Paid",
                          variable=self.paid_var
                          ).grid(row=len(rows), column=1,
                                  sticky="w", pady=2)
        ttk.Label(frm, text="Requirements:").grid(
            row=len(rows) + 1, column=0, sticky="nw")
        self.req = tk.Text(frm, width=40, height=4)
        self.req.grid(row=len(rows) + 1, column=1, sticky="w", pady=2)
        bar = ttk.Frame(frm); bar.grid(row=len(rows) + 2, column=0,
                                          columnspan=2, pady=8,
                                          sticky="e")
        ttk.Button(bar, text="Post",
                     command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel",
                     command=self.win.destroy
                     ).pack(side="right", padx=4)

    def _save(self) -> None:
        payload: dict[str, object] = {
            k: w.get() for k, w in self.widgets.items()}
        payload["paid"] = self.paid_var.get()
        payload["requirements"] = self.req.get("1.0", "end").strip()
        try:
            data.post_internship(self.alumni_id, payload)
        except Exception as e:
            messagebox.showerror("Post", str(e)); return
        self.on_save(); self.win.destroy()


class InternshipApplicantsDialog:
    def __init__(self, parent: tk.Misc, internship_id: int) -> None:
        self.internship_id = internship_id
        self.win = tk.Toplevel(parent)
        self.win.title(f"Applicants — internship #{internship_id}")
        self.win.transient(parent); self.win.geometry("700x400")
        cols = ("app_id", "student", "applied", "status")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"app_id": 60, "student": 120,
                    "applied": 120, "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Button(bar, text="Set status",
                     command=self._status).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in data.list_internship_applications(self.internship_id):
            self.tree.insert(
                "", "end", iid=str(r.application_id),
                values=(r.application_id, r.student_id,
                          r.applied_on, r.status))

    def _status(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        st = _ask_choice(self.win, "Application status",
                            list(APPLICATION_STATUSES))
        if not st: return
        try:
            data.set_internship_application_status(int(sel[0]), st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()


# ── Top-level: Mentor matching ───────────────────────────────────

class MentorMatchTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Mentor match")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.student = ttk.Entry(bar, width=12)
        self.student.pack(side="left", padx=4)
        ttk.Button(bar, text="Pick…",
                     command=self._pick_student).pack(side="left")
        ttk.Label(bar, text="Limit:").pack(side="left", padx=(8, 0))
        self.limit = ttk.Entry(bar, width=4); self.limit.insert(0, "10")
        self.limit.pack(side="left", padx=4)
        self.require_consent = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Require Mentoring consent",
                          variable=self.require_consent
                          ).pack(side="left", padx=8)
        ttk.Button(bar, text="Run",
                     command=self.refresh).pack(side="left", padx=8)
        cols = ("score", "alumni_id", "name", "sector", "reasons")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"score": 70, "alumni_id": 70, "name": 220,
                    "sector": 140, "reasons": 600}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _pick_student(self) -> None:
        rows = student_data.list_students()
        if not rows:
            messagebox.showinfo("Pick", "No current students.")
            return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Pick student"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        lb = tk.Listbox(dlg, width=50, height=20)
        for s in rows:
            lb.insert("end", f"{s.student_id}  {s.full_name}")
        lb.pack(padx=8, pady=8)

        def ok() -> None:
            sel = lb.curselection()
            if not sel: return
            sid = rows[sel[0]].student_id
            self.student.delete(0, "end")
            self.student.insert(0, sid)
            dlg.destroy()
        ttk.Button(dlg, text="OK", command=ok).pack(pady=(0, 8))
        self.frame.winfo_toplevel().wait_window(dlg)

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        sid = self.student.get().strip()
        if not sid:
            messagebox.showinfo("Run", "Pick a student first."); return
        try:
            lim = int(self.limit.get() or "10")
        except ValueError:
            messagebox.showerror("Limit", "Must be a number"); return
        for m in data.match_mentors_for_student(
                sid, limit=lim,
                require_consent=self.require_consent.get()):
            self.tree.insert(
                "", "end", iid=str(m.alumnus.alumni_id),
                values=(m.score, m.alumnus.alumni_id,
                          m.alumnus.full_name,
                          m.alumnus.current_sector or "—",
                          "; ".join(m.reasons)))


# ══ Mentor + comms extensions (items 17–26) ═══════════════════════

# ── Per-alumnus: Mentor profile (capacity & availability) ─────────

class MentorProfileTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Mentor profile")
        frm = ttk.Frame(self.frame, padding=10); frm.pack(fill="x")
        ttk.Label(frm, text="max_mentees:").grid(row=0, column=0,
                                                    sticky="w")
        self.mx = ttk.Entry(frm, width=8); self.mx.grid(row=0, column=1,
                                                          sticky="w")
        ttk.Label(frm, text="available_from:").grid(row=1, column=0,
                                                       sticky="w")
        self.af = ttk.Entry(frm, width=14); self.af.grid(row=1, column=1,
                                                            sticky="w")
        ttk.Label(frm, text="available_until:").grid(row=2, column=0,
                                                        sticky="w")
        self.au = ttk.Entry(frm, width=14); self.au.grid(row=2, column=1,
                                                            sticky="w")
        self.paused = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="paused", variable=self.paused
                          ).grid(row=3, column=1, sticky="w")
        ttk.Label(frm, text="bio:").grid(row=4, column=0, sticky="nw")
        self.bio = tk.Text(frm, width=42, height=4); self.bio.grid(
            row=4, column=1, sticky="w", pady=2)
        self.status = ttk.Label(frm, text="", foreground="#666")
        self.status.grid(row=5, column=0, columnspan=2,
                           sticky="w", pady=(6, 0))
        bar = ttk.Frame(frm); bar.grid(row=6, column=0, columnspan=2,
                                          pady=8, sticky="w")
        ttk.Button(bar, text="Save",
                     command=self._save).pack(side="left")
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        p = data.get_mentor_profile(self.alumni_id)
        self.mx.delete(0, "end"); self.af.delete(0, "end")
        self.au.delete(0, "end"); self.bio.delete("1.0", "end")
        if p is None:
            self.mx.insert(0, "3")
            self.paused.set(False)
            self.status.configure(text="(no profile yet)")
        else:
            self.mx.insert(0, str(p.max_mentees))
            if p.available_from: self.af.insert(0, p.available_from)
            if p.available_until: self.au.insert(0, p.available_until)
            self.paused.set(p.paused)
            if p.bio: self.bio.insert("1.0", p.bio)
            cap = "has capacity" if data.mentor_has_capacity(
                self.alumni_id) else "FULL / unavailable"
            self.status.configure(
                text=f"active mentees: "
                     f"{data.active_mentee_count(self.alumni_id)} — {cap}")

    def _save(self) -> None:
        try:
            data.upsert_mentor_profile(
                self.alumni_id,
                max_mentees=int(self.mx.get() or "0"),
                available_from=self.af.get() or None,
                available_until=self.au.get() or None,
                paused=self.paused.get(),
                bio=self.bio.get("1.0", "end").strip() or None)
        except Exception as e:
            messagebox.showerror("Save", str(e)); return
        self.refresh()


# ── Per-alumnus: Safeguarding ────────────────────────────────────

class SafeguardingTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Safeguarding")
        frm = ttk.Frame(self.frame, padding=10); frm.pack(fill="x")
        rows = [
            ("DBS reference", "dbs_reference"),
            ("DBS issued (YYYY-MM-DD)", "dbs_issued_on"),
            ("DBS expires (YYYY-MM-DD)", "dbs_expires_on"),
            ("Training done (YYYY-MM-DD)", "training_done_on"),
            ("Training expires (YYYY-MM-DD)", "training_expires_on"),
            ("Notes", "notes"),
        ]
        self.entries: dict[str, ttk.Entry] = {}
        for i, (lbl, key) in enumerate(rows):
            ttk.Label(frm, text=lbl + ":").grid(row=i, column=0,
                                                    sticky="w")
            e = ttk.Entry(frm, width=32); e.grid(row=i, column=1,
                                                       sticky="w", pady=2)
            self.entries[key] = e
        self.status_lbl = ttk.Label(frm, text="",
                                       font=("TkDefaultFont", 11, "bold"))
        self.status_lbl.grid(row=len(rows), column=0, columnspan=2,
                               sticky="w", pady=(8, 0))
        bar = ttk.Frame(frm); bar.grid(row=len(rows) + 1, column=0,
                                          columnspan=2, pady=8,
                                          sticky="w")
        ttk.Button(bar, text="Save",
                     command=self._save).pack(side="left")
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        sg = data.get_mentor_safeguarding(self.alumni_id)
        for e in self.entries.values():
            e.delete(0, "end")
        if sg is None:
            self.status_lbl.configure(text="(no record)",
                                          foreground="#888")
        else:
            self.entries["dbs_reference"].insert(0, sg.dbs_reference or "")
            self.entries["dbs_issued_on"].insert(0, sg.dbs_issued_on or "")
            self.entries["dbs_expires_on"].insert(0, sg.dbs_expires_on or "")
            self.entries["training_done_on"].insert(
                0, sg.training_done_on or "")
            self.entries["training_expires_on"].insert(
                0, sg.training_expires_on or "")
            self.entries["notes"].insert(0, sg.notes or "")
            colour = {
                "Cleared": "#2a7", "Pending": "#888",
                "Expiring Soon": "#c80", "Expired": "#a33",
                "Suspended": "#a33"}.get(sg.status, "#666")
            self.status_lbl.configure(text=f"Status: {sg.status}",
                                          foreground=colour)

    def _save(self) -> None:
        try:
            data.upsert_mentor_safeguarding(
                self.alumni_id,
                **{k: (e.get() or None)
                    for k, e in self.entries.items()})
        except Exception as e:
            messagebox.showerror("Save", str(e)); return
        self.refresh()


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
        for s in data.list_sms_for(self.alumni_id):
            self.tree.insert("", "end", iid=str(s.sms_id),
                              values=(s.sms_id, s.sent_at, s.status,
                                      s.body))

    def _send(self) -> None:
        body = self.body.get().strip()
        if not body: return
        try:
            data.send_sms_to_alumnus(self.alumni_id, body)
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
        for t in data.list_email_templates(latest_only=False):
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
        t = next((x for x in data.list_email_templates(latest_only=False)
                    if x.template_id == tid), None)
        if t is None: return
        win = tk.Toplevel(self.frame.winfo_toplevel())
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
        data.delete_email_template(tid)
        self.refresh()

    def _preview(self) -> None:
        tid = self._selected()
        if tid is None: return
        t = next((x for x in data.list_email_templates(latest_only=False)
                    if x.template_id == tid), None)
        if t is None: return
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        try:
            subj, body = data.render_template(t, aid)
        except Exception as e:
            messagebox.showerror("Preview", str(e)); return
        win = tk.Toplevel(self.frame.winfo_toplevel())
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
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
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
            data.create_email_template(
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
        for d in data.list_drip_campaigns():
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
            data.create_drip_campaign(name)
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
            data.set_drip_status(did, st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()

    def _enroll(self) -> None:
        did = self._selected()
        if did is None: return
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        try:
            data.enroll_in_drip(did, aid)
        except Exception as e:
            messagebox.showerror("Enroll", str(e)); return

    def _tick(self) -> None:
        ticks = data.tick_drip()
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
        for s in data.list_drip_steps(self.drip_id):
            self.tree.insert(
                "", "end", iid=str(s.step_id),
                values=(s.position, s.delay_days,
                          s.template_id or "—",
                          s.subject or f"(body of step {s.position})"))

    def _add(self) -> None:
        dlg = tk.Toplevel(self.win); dlg.title("Add drip step")
        dlg.transient(self.win); dlg.after_idle(dlg.grab_set)
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
                data.add_drip_step(
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
        with _sq.connect(str(data.DB_PATH)) as conn:
            conn.row_factory = _sq.Row
            rows = conn.execute(
                "SELECT * FROM alumni_ab_tests "
                "ORDER BY created_at DESC").fetchall()
        for r in rows:
            variants = ", ".join(
                v.label for v in data.list_ab_variants(r["test_id"]))
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
            data.create_ab_test(name)
        except Exception as e:
            messagebox.showerror("Create", str(e)); return
        self.refresh()

    def _variant(self) -> None:
        tid = self._selected()
        if tid is None: return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Variant"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
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
                data.add_ab_variant(tid, label=lbl.get(),
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
            counts = data.assign_ab_audience(tid)
        except Exception as e:
            messagebox.showerror("Assign", str(e)); return
        messagebox.showinfo("Assign", repr(counts))

    def _results(self) -> None:
        tid = self._selected()
        if tid is None: return
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(f"Results — A/B #{tid}"); win.geometry("520x320")
        cols = ("label", "sent", "opens", "open_rate",
                  "clicks", "click_rate")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=80, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for r in data.ab_test_results(tid):
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
        for n in data.list_newsletters():
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
        dlg.transient(self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Issue:").grid(row=0, column=0, sticky="w")
        issue = ttk.Entry(frm, width=24); issue.grid(row=0, column=1,
                                                          sticky="w")
        ttk.Label(frm, text="Title:").grid(row=1, column=0, sticky="w")
        title = ttk.Entry(frm, width=40); title.grid(row=1, column=1,
                                                          sticky="w")

        def ok() -> None:
            try:
                data.create_newsletter(issue.get(), title.get())
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
            data.publish_newsletter(nid)
        except Exception as e:
            messagebox.showerror("Publish", str(e)); return
        self.refresh()

    def _preview(self) -> None:
        nid = self._selected()
        if nid is None: return
        try:
            html = data.render_newsletter_html(nid)
        except Exception as e:
            messagebox.showerror("Preview", str(e)); return
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(f"Preview — newsletter #{nid}")
        win.geometry("800x600")
        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", html); txt.configure(state="disabled")

    def _audience(self) -> None:
        nid = self._selected()
        if nid is None: return
        try:
            rows = data.newsletter_audience(nid)
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
        for s in data.list_newsletter_sections(self.newsletter_id):
            self.tree.insert(
                "", "end", iid=str(s.section_id),
                values=(s.position, s.heading))

    def _add(self) -> None:
        dlg = tk.Toplevel(self.win); dlg.title("Section")
        dlg.transient(self.win); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Heading:").grid(row=0, column=0, sticky="w")
        heading = ttk.Entry(frm, width=40); heading.grid(row=0, column=1,
                                                              sticky="w")
        ttk.Label(frm, text="Body:").grid(row=1, column=0, sticky="nw")
        body = tk.Text(frm, width=60, height=10)
        body.grid(row=1, column=1, sticky="w", pady=2)

        def ok() -> None:
            try:
                data.add_newsletter_section(
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
        with _sq.connect(str(data.DB_PATH)) as conn:
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
        s = data.tracking_summary(campaign_ref=ref)
        self.summary.configure(
            text=f"sends={s.sends}  opens={s.opens}  "
                 f"clicks={s.clicks}  unique_opens={s.unique_opens}")

    def _pixel(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        ref = self.ref.get().strip() or None
        tok = data.create_tracking_pixel(aid, campaign_ref=ref)
        messagebox.showinfo("Token", tok)
        self.refresh()

    def _link(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        url = _prompt_string(self.frame.winfo_toplevel(),
                                "Tracked link", "Target URL:")
        if not url: return
        ref = self.ref.get().strip() or None
        tok = data.create_tracked_link(url, alumni_id=aid,
                                          campaign_ref=ref)
        messagebox.showinfo("Token", tok)
        self.refresh()


# ── Top-level: Safeguarding alerts (cross-alumni) ────────────────

class SafeguardingAlertsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Safeguarding alerts")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Within days:").pack(side="left")
        self.days = ttk.Entry(bar, width=6); self.days.insert(0, "60")
        self.days.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        cols = ("alumni_id", "status", "dbs_expires",
                  "training_expires", "notes")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"alumni_id": 80, "status": 130,
                    "dbs_expires": 120, "training_expires": 130,
                    "notes": 360}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            d = int(self.days.get() or "60")
        except ValueError:
            messagebox.showerror("Days", "Must be a number"); return
        for s in data.list_safeguarding_alerts(days=d):
            self.tree.insert(
                "", "end", iid=str(s.alumni_id),
                values=(s.alumni_id, s.status,
                          s.dbs_expires_on or "—",
                          s.training_expires_on or "—",
                          s.notes or ""))


# ══ Events / fundraising / outcomes (items 27–40) ═════════════════

# ── Top-level: Reunion planner ───────────────────────────────────

class ReunionPlannerTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Reunions")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Horizon (months):").pack(side="left")
        self.months = ttk.Entry(bar, width=6); self.months.insert(0, "18")
        self.months.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Create draft events",
                     command=self._create).pack(side="left", padx=12)
        cols = ("proposed_date", "name", "years", "cohort")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"proposed_date": 130, "name": 360, "years": 70,
                    "cohort": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            m = int(self.months.get() or "18")
        except ValueError:
            return
        for s in data.suggest_reunions(horizon_months=m):
            self.tree.insert("", "end",
                values=(s.proposed_date, s.proposed_name,
                          s.years_since, s.cohort_size))

    def _create(self) -> None:
        try:
            m = int(self.months.get() or "18")
        except ValueError:
            return
        created = data.create_reunion_events(horizon_months=m)
        messagebox.showinfo("Reunion planner",
                               f"Created {len(created)} draft event(s)")


# ── Top-level: Recurring donations ───────────────────────────────

class RecurringDonationsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Recurring")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.status = ttk.Combobox(bar,
            values=["(all)", *RECURRING_STATUSES],
            state="readonly", width=10)
        self.status.set("Active"); self.status.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                     command=self._new).pack(side="left", padx=12)
        ttk.Button(bar, text="Set status",
                     command=self._status).pack(side="left")
        ttk.Button(bar, text="Tick now",
                     command=self._tick).pack(side="left", padx=4)
        cols = ("id", "alumni_id", "amount", "frequency",
                  "next_charge_on", "status", "fails")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "alumni_id": 80, "amount": 100,
                    "frequency": 100, "next_charge_on": 130,
                    "status": 90, "fails": 60}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        s = self.status.get()
        status = None if s == "(all)" else s
        for r in data.list_recurring(status=status):
            self.tree.insert("", "end", iid=str(r.schedule_id),
                values=(r.schedule_id, r.alumni_id,
                          _money_str(r.amount_pence), r.frequency,
                          r.next_charge_on, r.status, r.failure_count))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("New recurring"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Amount pence:").grid(row=0, column=0,
                                                     sticky="w")
        amt = ttk.Entry(frm, width=10); amt.grid(row=0, column=1,
                                                       sticky="w")
        ttk.Label(frm, text="Frequency:").grid(row=1, column=0,
                                                  sticky="w")
        freq = ttk.Combobox(frm, values=list(RECURRING_FREQS),
                                state="readonly", width=14)
        freq.set("Monthly"); freq.grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="Next charge (YYYY-MM-DD):").grid(
            row=2, column=0, sticky="w")
        nxt = ttk.Entry(frm, width=14); nxt.grid(row=2, column=1,
                                                       sticky="w")
        ttk.Label(frm, text="Fund code:").grid(row=3, column=0,
                                                  sticky="w")
        fund = ttk.Entry(frm, width=14); fund.grid(row=3, column=1,
                                                         sticky="w")
        ttk.Label(frm, text="Payment method:").grid(row=4, column=0,
                                                       sticky="w")
        pm = ttk.Entry(frm, width=14); pm.grid(row=4, column=1,
                                                     sticky="w")

        def ok() -> None:
            try:
                data.create_recurring(aid,
                    amount_pence=int(amt.get() or "0"),
                    frequency=freq.get(),
                    next_charge_on=nxt.get() or None,
                    fund_code=fund.get() or None,
                    payment_method=pm.get() or None)
            except Exception as e:
                messagebox.showerror("Create", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=5, column=1, sticky="e", pady=8)

    def _status(self) -> None:
        sid = self._selected()
        if sid is None: return
        st = _ask_choice(self.frame, "Status", list(RECURRING_STATUSES))
        if not st: return
        try:
            data.set_recurring_status(sid, st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()

    def _tick(self) -> None:
        ticks = data.tick_recurring()
        ok = sum(1 for t in ticks if t.success)
        messagebox.showinfo("Tick", f"{ok}/{len(ticks)} succeeded")
        self.refresh()


# ── Top-level: Donor pipeline ────────────────────────────────────

class DonorPipelineTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Donor pipeline")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Stage:").pack(side="left")
        self.stage = ttk.Combobox(bar,
            values=["(all)", *DONOR_STAGES],
            state="readonly", width=18)
        self.stage.set("(all)"); self.stage.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Set stage…",
                     command=self._set_stage).pack(side="left", padx=12)
        cols = ("alumni_id", "stage", "owner", "next_action",
                  "next_action_on", "capacity")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"alumni_id": 80, "stage": 140, "owner": 100,
                    "next_action": 240, "next_action_on": 130,
                    "capacity": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        s = self.stage.get()
        stage = None if s == "(all)" else s
        for p in data.list_donor_pipeline(stage=stage):
            self.tree.insert("", "end", iid=str(p.alumni_id),
                values=(p.alumni_id, p.stage,
                          p.owner_staff_id or "—",
                          p.next_action or "—",
                          p.next_action_on or "—",
                          _money_str(p.capacity_pence)
                          if p.capacity_pence else "—"))

    def _set_stage(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Donor stage"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Stage:").grid(row=0, column=0, sticky="w")
        stage = ttk.Combobox(frm, values=list(DONOR_STAGES),
                                 state="readonly", width=20)
        stage.set("Identification"); stage.grid(row=0, column=1,
                                                      sticky="w")
        ttk.Label(frm, text="Owner staff id:").grid(row=1, column=0,
                                                       sticky="w")
        owner = ttk.Entry(frm, width=20); owner.grid(row=1, column=1,
                                                           sticky="w")
        ttk.Label(frm, text="Next action:").grid(row=2, column=0,
                                                    sticky="w")
        action = ttk.Entry(frm, width=40); action.grid(row=2, column=1,
                                                             sticky="w")
        ttk.Label(frm, text="Next action on:").grid(row=3, column=0,
                                                       sticky="w")
        action_on = ttk.Entry(frm, width=14)
        action_on.grid(row=3, column=1, sticky="w")
        ttk.Label(frm, text="Capacity pence:").grid(row=4, column=0,
                                                       sticky="w")
        cap = ttk.Entry(frm, width=14); cap.grid(row=4, column=1,
                                                       sticky="w")

        def ok() -> None:
            try:
                data.set_donor_stage(aid, stage.get(),
                    owner_staff_id=owner.get() or None,
                    next_action=action.get() or None,
                    next_action_on=action_on.get() or None,
                    capacity_pence=int(cap.get()) if cap.get() else None)
            except Exception as e:
                messagebox.showerror("Save", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=5, column=1, sticky="e", pady=8)


# ── Top-level: Funds ─────────────────────────────────────────────

class FundsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Funds")
        cols = ("id", "code", "name", "restricted")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "code": 120, "name": 260, "restricted": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Upsert",
                     command=self._upsert).pack(side="left")
        ttk.Button(bar, text="Totals",
                     command=self._totals).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for f in data.list_funds():
            self.tree.insert("", "end", iid=str(f.fund_id),
                values=(f.fund_id, f.code, f.name,
                          "Yes" if f.restricted else "No"))

    def _upsert(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Fund"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Code:").grid(row=0, column=0, sticky="w")
        code = ttk.Entry(frm, width=14); code.grid(row=0, column=1,
                                                         sticky="w")
        ttk.Label(frm, text="Name:").grid(row=1, column=0, sticky="w")
        name = ttk.Entry(frm, width=30); name.grid(row=1, column=1,
                                                         sticky="w")
        restr = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Restricted",
                          variable=restr).grid(row=2, column=1, sticky="w")

        def ok() -> None:
            try:
                data.upsert_fund(code.get(), name.get(),
                                    restricted=restr.get())
            except Exception as e:
                messagebox.showerror("Save", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=3, column=1, sticky="e", pady=8)

    def _totals(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Fund totals"); win.geometry("600x400")
        cols = ("code", "name", "restricted", "raised")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        widths = {"code": 120, "name": 220, "restricted": 100,
                    "raised": 120}
        for c in cols:
            tree.heading(c, text=c.title())
            tree.column(c, width=widths[c], anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for t in data.fund_totals():
            tree.insert("", "end",
                values=(t.fund_code, t.fund_name,
                          "Yes" if t.restricted else "No",
                          _money_str(t.raised_pence)))


# ── Top-level: Bequests ──────────────────────────────────────────

class BequestsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Bequests")
        cols = ("id", "alumni_id", "estimated", "status",
                  "confirmed_on", "realised_on", "executor")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "alumni_id": 80, "estimated": 120,
                    "status": 100, "confirmed_on": 120,
                    "realised_on": 120, "executor": 200}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Add",
                     command=self._add).pack(side="left")
        ttk.Button(bar, text="Set status",
                     command=self._status).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for b in data.list_bequests():
            self.tree.insert("", "end", iid=str(b.bequest_id),
                values=(b.bequest_id, b.alumni_id,
                          _money_str(b.estimated_pence) if b.estimated_pence
                          else "—",
                          b.status, b.confirmed_on or "—",
                          b.realised_on or "—",
                          b.executor_name or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Bequest"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Estimated pence:").grid(row=0, column=0,
                                                        sticky="w")
        est = ttk.Entry(frm, width=14); est.grid(row=0, column=1,
                                                       sticky="w")
        ttk.Label(frm, text="Executor name:").grid(row=1, column=0,
                                                      sticky="w")
        en = ttk.Entry(frm, width=30); en.grid(row=1, column=1,
                                                     sticky="w")
        ttk.Label(frm, text="Executor email:").grid(row=2, column=0,
                                                       sticky="w")
        ee = ttk.Entry(frm, width=30); ee.grid(row=2, column=1,
                                                     sticky="w")
        ttk.Label(frm, text="Confirmed on:").grid(row=3, column=0,
                                                     sticky="w")
        co = ttk.Entry(frm, width=14); co.grid(row=3, column=1,
                                                     sticky="w")

        def ok() -> None:
            try:
                data.add_bequest(aid,
                    estimated_pence=int(est.get()) if est.get() else None,
                    executor_name=en.get() or None,
                    executor_email=ee.get() or None,
                    confirmed_on=co.get() or None)
            except Exception as e:
                messagebox.showerror("Add", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=4, column=1, sticky="e", pady=8)

    def _status(self) -> None:
        bid = self._selected()
        if bid is None: return
        st = _ask_choice(self.frame, "Status", list(BEQUEST_STATUSES))
        if not st: return
        rdate = _prompt_string(self.frame.winfo_toplevel(),
                                  "Realised on (optional)",
                                  "YYYY-MM-DD or blank:")
        try:
            data.set_bequest_status(bid, st, realised_on=rdate)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()


# ── Top-level: Matched giving ────────────────────────────────────

class MatchedGivingTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Matched giving")
        cols = ("id", "employer", "multiplier", "cap", "notes")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "employer": 240, "multiplier": 100,
                    "cap": 120, "notes": 240}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Upsert",
                     command=self._upsert).pack(side="left")
        ttk.Button(bar, text="Apply to donation…",
                     command=self._apply).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in data.list_matched_schemes():
            self.tree.insert("", "end", iid=str(s.scheme_id),
                values=(s.scheme_id, s.employer,
                          f"×{s.multiplier}",
                          _money_str(s.cap_pence) if s.cap_pence else "—",
                          s.notes or ""))

    def _upsert(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Matched giving scheme"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Employer:").grid(row=0, column=0,
                                                  sticky="w")
        emp = ttk.Entry(frm, width=30); emp.grid(row=0, column=1,
                                                       sticky="w")
        ttk.Label(frm, text="Multiplier:").grid(row=1, column=0,
                                                   sticky="w")
        mult = ttk.Entry(frm, width=10); mult.insert(0, "1.0")
        mult.grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="Cap pence (optional):").grid(
            row=2, column=0, sticky="w")
        cap = ttk.Entry(frm, width=14); cap.grid(row=2, column=1,
                                                       sticky="w")

        def ok() -> None:
            try:
                data.upsert_matched_scheme(emp.get(),
                    multiplier=float(mult.get() or "1.0"),
                    cap_pence=int(cap.get()) if cap.get() else None)
            except Exception as e:
                messagebox.showerror("Save", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=3, column=1, sticky="e", pady=8)

    def _apply(self) -> None:
        did = _prompt_string(self.frame.winfo_toplevel(),
                                "Donation id", "ID:")
        if not did: return
        try:
            matched = data.auto_apply_matched_giving(int(did))
        except Exception as e:
            messagebox.showerror("Apply", str(e)); return
        messagebox.showinfo("Apply",
                               f"Matched {_money_str(matched)}")


# ── Top-level: NEET tracking ─────────────────────────────────────

class NEETTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="NEET")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Leaving year:").pack(side="left")
        self.year = ttk.Entry(bar, width=8); self.year.pack(side="left",
                                                                 padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Record check…",
                     command=self._record).pack(side="left", padx=12)
        cols = ("months", "cohort", "neet", "not_neet",
                  "unknown", "rate")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"months": 80, "cohort": 80, "neet": 80,
                    "not_neet": 100, "unknown": 80, "rate": 100}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in data.neet_breakdown(
                leaving_year=self.year.get().strip() or None):
            self.tree.insert("", "end",
                values=(f"{r.months_after}m", r.cohort, r.neet,
                          r.not_neet, r.unknown,
                          f"{r.neet_rate_pct}%"))

    def _record(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("NEET check"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Months after:").grid(row=0, column=0,
                                                     sticky="w")
        m = ttk.Combobox(frm, values=["3", "6", "12", "24"],
                            state="readonly", width=6)
        m.set("3"); m.grid(row=0, column=1, sticky="w")
        ttk.Label(frm, text="Status:").grid(row=1, column=0, sticky="w")
        st = ttk.Combobox(frm, values=list(NEET_STATUSES),
                              state="readonly", width=20)
        st.set("In Education"); st.grid(row=1, column=1, sticky="w")

        def ok() -> None:
            try:
                data.record_neet_check(aid,
                    months_after=int(m.get()), status=st.get())
            except Exception as e:
                messagebox.showerror("Record", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=2, column=1, sticky="e", pady=8)


# ── Per-alumnus: NEET checks ─────────────────────────────────────

class NEETChecksTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="NEET")
        cols = ("months", "status", "checked_on", "notes")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings", height=6)
        widths = {"months": 80, "status": 140,
                    "checked_on": 130, "notes": 320}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Label(bar, text="Months:").pack(side="left")
        self.m = ttk.Combobox(bar, values=["3", "6", "12", "24"],
                                 state="readonly", width=5)
        self.m.set("3"); self.m.pack(side="left", padx=4)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.st = ttk.Combobox(bar, values=list(NEET_STATUSES),
                                  state="readonly", width=20)
        self.st.set("In Education"); self.st.pack(side="left", padx=4)
        ttk.Button(bar, text="Record",
                     command=self._add).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in data.list_neet_checks(self.alumni_id):
            self.tree.insert("", "end",
                values=(f"{c.months_after}m", c.status,
                          c.checked_on, c.notes or ""))

    def _add(self) -> None:
        try:
            data.record_neet_check(self.alumni_id,
                months_after=int(self.m.get()),
                status=self.st.get())
        except Exception as e:
            messagebox.showerror("Record", str(e)); return
        self.refresh()


# ── Per-alumnus: Gift Aid ────────────────────────────────────────

class GiftAidTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Gift Aid")
        self.status_lbl = ttk.Label(self.frame, text="",
                                       font=("TkDefaultFont", 11, "bold"))
        self.status_lbl.pack(anchor="w", padx=8, pady=(8, 4))
        frm = ttk.Frame(self.frame, padding=8); frm.pack(fill="x")
        ttk.Label(frm, text="Valid from:").grid(row=0, column=0,
                                                   sticky="w")
        self.vfrom = ttk.Entry(frm, width=14); self.vfrom.grid(
            row=0, column=1, sticky="w")
        ttk.Label(frm, text="Valid until:").grid(row=1, column=0,
                                                    sticky="w")
        self.vuntil = ttk.Entry(frm, width=14); self.vuntil.grid(
            row=1, column=1, sticky="w")
        ttk.Label(frm, text="Full name:").grid(row=2, column=0,
                                                  sticky="w")
        self.name = ttk.Entry(frm, width=30); self.name.grid(
            row=2, column=1, sticky="w")
        ttk.Label(frm, text="Address:").grid(row=3, column=0, sticky="w")
        self.addr = ttk.Entry(frm, width=30); self.addr.grid(
            row=3, column=1, sticky="w")
        ttk.Label(frm, text="Postcode:").grid(row=4, column=0,
                                                 sticky="w")
        self.pc = ttk.Entry(frm, width=14); self.pc.grid(
            row=4, column=1, sticky="w")
        bar = ttk.Frame(frm); bar.grid(row=5, column=0, columnspan=2,
                                          pady=8, sticky="w")
        ttk.Button(bar, text="Add declaration",
                     command=self._add).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        g = data.get_active_gift_aid(self.alumni_id)
        if g:
            self.status_lbl.configure(
                text=f"Active declaration #{g.declaration_id} "
                     f"({g.valid_from} → "
                     f"{g.valid_until or 'open'})",
                foreground="#2a7")
        else:
            self.status_lbl.configure(
                text="No active declaration", foreground="#a44")

    def _add(self) -> None:
        try:
            data.add_gift_aid_declaration(self.alumni_id,
                valid_from=self.vfrom.get(),
                valid_until=self.vuntil.get() or None,
                full_name=self.name.get(),
                address=self.addr.get(),
                postcode=self.pc.get())
        except Exception as e:
            messagebox.showerror("Add", str(e)); return
        for w in (self.vfrom, self.vuntil, self.name,
                    self.addr, self.pc):
            w.delete(0, "end")
        self.refresh()


# ══ Final cluster (items 41–50) ═══════════════════════════════════

# ── Top-level: Data quality dashboard ────────────────────────────

class DataQualityTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Quality")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, height=18, wrap="word",
                              state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        q = data.data_quality_report()
        body = (
            f"Total active alumni: {q.total}\n\n"
            f"  Email on file:               {q.with_email_pct}%\n"
            f"  Phone on file:               {q.with_phone_pct}%\n"
            f"  Postal address on file:      {q.with_address_pct}%\n"
            f"  Missing destination:         {q.missing_destination_pct}%\n"
            f"  Stale (no contact > 24mo):   {q.stale_24mo_pct}%\n"
            f"  Hard bounces:                {q.bounce_rate_pct}%\n"
            f"  Opt-in to contact:           {q.opt_in_pct}%\n"
            f"  'Data Storage' consent:      {q.consent_data_storage_pct}%\n"
        )
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", body)
        self.text.configure(state="disabled")


# ── Top-level: Dedupe confidence buckets ─────────────────────────

class DedupeBucketsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Dedupe buckets")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Batch-merge selected",
                     command=self._batch).pack(side="left", padx=8)
        cols = ("bucket", "score", "keep_id", "merge_id",
                  "keep_name", "merge_name")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"bucket": 110, "score": 70,
                    "keep_id": 70, "merge_id": 70,
                    "keep_name": 220, "merge_name": 220}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        buckets = data.dedupe_buckets()
        for label, rows in (("Very high", buckets.very_high),
                                ("High",      buckets.high),
                                ("Medium",    buckets.medium)):
            for c in rows:
                kp = data.get_alumnus(c.keep_id)
                mg = data.get_alumnus(c.merge_id)
                self.tree.insert("", "end",
                    iid=f"{c.keep_id}-{c.merge_id}",
                    values=(label, f"{c.score:.2f}",
                              c.keep_id, c.merge_id,
                              kp.full_name if kp else "—",
                              mg.full_name if mg else "—"))

    def _batch(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        pairs: list[tuple[int, int]] = []
        for iid in sel:
            vals = self.tree.item(iid, "values")
            pairs.append((int(vals[2]), int(vals[3])))
        if not messagebox.askyesno(
                "Batch merge",
                f"Merge {len(pairs)} pair(s)? This is irreversible."):
            return
        ok, errs = data.batch_confirm_merges(pairs)
        messagebox.showinfo("Batch merge",
                               f"Merged {ok}, {len(errs)} error(s)")
        self.refresh()


# ── Top-level: Erasure workflow ──────────────────────────────────

class ErasureTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Erasure")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.status = ttk.Combobox(bar,
            values=["(all)", *ERASURE_STATUSES],
            state="readonly", width=18)
        self.status.set("(all)"); self.status.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New request",
                     command=self._new).pack(side="left", padx=12)
        ttk.Button(bar, text="Review",
                     command=self._review).pack(side="left")
        ttk.Button(bar, text="Complete",
                     command=self._complete).pack(side="left", padx=4)
        cols = ("id", "alumni_id", "status", "requested_at",
                  "reviewer", "completed_at")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "alumni_id": 80, "status": 130,
                    "requested_at": 170, "reviewer": 130,
                    "completed_at": 170}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        s = self.status.get()
        status = None if s == "(all)" else s
        for r in data.list_erasure_requests(status=status):
            self.tree.insert("", "end", iid=str(r.request_id),
                values=(r.request_id, r.alumni_id, r.status,
                          r.requested_at, r.reviewer or "—",
                          r.completed_at or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        reason = _prompt_string(self.frame.winfo_toplevel(),
                                   "Reason", "Reason (optional):")
        try:
            data.request_erasure(aid, reason=reason)
        except Exception as e:
            messagebox.showerror("Request", str(e)); return
        self.refresh()

    def _review(self) -> None:
        rid = self._selected()
        if rid is None: return
        reviewer = _prompt_string(self.frame.winfo_toplevel(),
                                     "Reviewer", "Reviewer id:")
        if not reviewer: return
        decision = _ask_choice(self.frame, "Decision",
                                  ["Approved", "Rejected"])
        if not decision: return
        try:
            data.review_erasure(rid, reviewer=reviewer,
                                    decision=decision)
        except Exception as e:
            messagebox.showerror("Review", str(e)); return
        self.refresh()

    def _complete(self) -> None:
        rid = self._selected()
        if rid is None: return
        if not messagebox.askyesno(
                "Complete erasure",
                "Anonymise this alumnus's record now? "
                "This cannot be undone."):
            return
        try:
            data.complete_erasure(rid)
        except Exception as e:
            messagebox.showerror("Complete", str(e)); return
        self.refresh()


# ── Top-level: Webhooks ──────────────────────────────────────────

class WebhooksTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Webhooks")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="New",
                     command=self._new).pack(side="left")
        ttk.Button(bar, text="Toggle active",
                     command=self._toggle).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left")
        ttk.Button(bar, text="Recent events",
                     command=self._events).pack(side="left", padx=12)
        cols = ("id", "url", "active", "event_types")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "url": 320, "active": 70,
                    "event_types": 400}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for w in data.list_webhooks():
            self.tree.insert("", "end", iid=str(w.webhook_id),
                values=(w.webhook_id, w.url,
                          "Yes" if w.active else "No",
                          ", ".join(w.event_types)))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Register webhook"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="URL:").grid(row=0, column=0, sticky="w")
        url = ttk.Entry(frm, width=40); url.grid(row=0, column=1,
                                                       sticky="w")
        ttk.Label(frm, text="Secret (optional):").grid(row=1, column=0,
                                                          sticky="w")
        secret = ttk.Entry(frm, width=30); secret.grid(row=1, column=1,
                                                             sticky="w")
        ttk.Label(frm, text="Event types:").grid(row=2, column=0,
                                                    sticky="nw")
        lb = tk.Listbox(frm, selectmode="multiple",
                          height=min(len(WEBHOOK_EVENT_TYPES), 10),
                          exportselection=False)
        for ev in WEBHOOK_EVENT_TYPES:
            lb.insert("end", ev)
        lb.grid(row=2, column=1, sticky="w", pady=2)

        def ok() -> None:
            events = [WEBHOOK_EVENT_TYPES[i] for i in lb.curselection()]
            if not events:
                messagebox.showerror("Events",
                                        "Pick at least one event type")
                return
            try:
                data.register_webhook(url.get(),
                    event_types=events, secret=secret.get() or None)
            except Exception as e:
                messagebox.showerror("Save", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=3, column=1, sticky="e", pady=8)

    def _toggle(self) -> None:
        wid = self._selected()
        if wid is None: return
        vals = self.tree.item(str(wid), "values")
        active = (vals[2] != "Yes")
        try:
            data.set_webhook_active(wid, active)
        except Exception as e:
            messagebox.showerror("Toggle", str(e)); return
        self.refresh()

    def _delete(self) -> None:
        wid = self._selected()
        if wid is None: return
        if not messagebox.askyesno("Delete",
                                      f"Delete webhook #{wid}?"):
            return
        data.delete_webhook(wid)
        self.refresh()

    def _events(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Recent webhook events"); win.geometry("800x500")
        cols = ("id", "queued_at", "event_type",
                  "delivered_at", "last_error")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        widths = {"id": 60, "queued_at": 160, "event_type": 180,
                    "delivered_at": 160, "last_error": 220}
        for c in cols:
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=widths[c], anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for ev in data.list_recent_webhook_events(limit=100):
            tree.insert("", "end",
                values=(ev["event_id"], ev["queued_at"],
                          ev["event_type"],
                          ev["delivered_at"] or "—",
                          ev["last_error"] or ""))


# ── Top-level: Custom fields ─────────────────────────────────────

class CustomFieldsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Custom fields")
        cols = ("id", "name", "label", "type")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 180, "label": 240, "type": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Add",
                     command=self._add).pack(side="left")
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for f in data.list_custom_fields():
            self.tree.insert("", "end", iid=str(f.field_id),
                values=(f.field_id, f.name, f.label, f.type))

    def _add(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Custom field"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Name (machine):").grid(row=0, column=0,
                                                       sticky="w")
        name = ttk.Entry(frm, width=24); name.grid(row=0, column=1,
                                                         sticky="w")
        ttk.Label(frm, text="Label:").grid(row=1, column=0, sticky="w")
        label = ttk.Entry(frm, width=30); label.grid(row=1, column=1,
                                                          sticky="w")
        ttk.Label(frm, text="Type:").grid(row=2, column=0, sticky="w")
        tp = ttk.Combobox(frm, values=list(CUSTOM_FIELD_TYPES),
                              state="readonly", width=12)
        tp.set("text"); tp.grid(row=2, column=1, sticky="w")

        def ok() -> None:
            try:
                data.add_custom_field(name.get(), label.get(),
                                          type=tp.get())
            except Exception as e:
                messagebox.showerror("Add", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=3, column=1, sticky="e", pady=8)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        fid = int(sel[0])
        if not messagebox.askyesno("Delete",
                                      f"Delete field #{fid} and all "
                                      "associated values?"):
            return
        data.delete_custom_field(fid)
        self.refresh()


# ── Top-level: HESA benchmarks ───────────────────────────────────

class HESATab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="HESA")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Compare year:").pack(side="left")
        self.year = ttk.Entry(bar, width=8)
        self.year.pack(side="left", padx=4)
        ttk.Button(bar, text="Compare",
                     command=self._compare).pack(side="left", padx=4)
        ttk.Button(bar, text="Upsert benchmark…",
                     command=self._upsert).pack(side="left", padx=12)
        cols = ("metric", "school", "hesa", "delta")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"metric": 180, "school": 100, "hesa": 100,
                    "delta": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _compare(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        year = self.year.get().strip()
        if not year:
            messagebox.showerror("Year", "Pick a year"); return
        for d in data.compare_with_hesa(year):
            sign = "+" if d.delta_pct >= 0 else ""
            self.tree.insert("", "end",
                values=(d.metric, f"{d.school_rate_pct}%",
                          f"{d.hesa_rate_pct}%",
                          f"{sign}{d.delta_pct}%"))

    def _upsert(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("HESA benchmark"); dlg.transient(
            self.frame.winfo_toplevel()); dlg.after_idle(dlg.grab_set)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Leaving year:").grid(row=0, column=0,
                                                     sticky="w")
        yr = ttk.Entry(frm, width=10); yr.grid(row=0, column=1,
                                                     sticky="w")
        ttk.Label(frm, text="Metric:").grid(row=1, column=0, sticky="w")
        metric = ttk.Combobox(frm, values=[
            "he_entry", "russell_group", "oxbridge", "postgraduate"],
            state="readonly", width=18)
        metric.grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="Rate %:").grid(row=2, column=0, sticky="w")
        rate = ttk.Entry(frm, width=10); rate.grid(row=2, column=1,
                                                         sticky="w")
        ttk.Label(frm, text="Source:").grid(row=3, column=0, sticky="w")
        src = ttk.Entry(frm, width=30); src.grid(row=3, column=1,
                                                       sticky="w")

        def ok() -> None:
            try:
                data.upsert_hesa_benchmark(yr.get(), metric.get(),
                    float(rate.get() or "0"), source=src.get() or None)
            except Exception as e:
                messagebox.showerror("Save", str(e)); return
            dlg.destroy()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=4, column=1, sticky="e", pady=8)


# ── Per-alumnus: Protected characteristics ───────────────────────

class ProtectedCharsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Protected")
        ttk.Label(self.frame,
                    text="Protected characteristics (used for gap reports).",
                    foreground="#666"
                    ).pack(anchor="w", padx=8, pady=(8, 4))
        frm = ttk.Frame(self.frame, padding=8); frm.pack(fill="x")
        self.vars: dict[str, tk.BooleanVar] = {}
        for i, char in enumerate(PROTECTED_CHARS):
            v = tk.BooleanVar(value=False)
            self.vars[char] = v
            ttk.Checkbutton(frm, text=char, variable=v,
                              command=lambda c=char, vv=v:
                                  self._toggle(c, vv)
                              ).grid(row=i, column=0, sticky="w", pady=2)
        ttk.Label(frm, text="Ethnicity:").grid(row=len(PROTECTED_CHARS),
                                                  column=0, sticky="w",
                                                  pady=(8, 0))
        self.ethnicity = ttk.Entry(frm, width=24)
        self.ethnicity.grid(row=len(PROTECTED_CHARS), column=1,
                                sticky="w", pady=(8, 0))
        ttk.Button(frm, text="Save ethnicity",
                     command=self._save_eth
                     ).grid(row=len(PROTECTED_CHARS) + 1, column=1,
                              sticky="w", pady=8)
        self.refresh()

    def refresh(self) -> None:
        a = data.get_alumnus(self.alumni_id)
        if a is None: return
        for char, v in self.vars.items():
            v.set(bool(getattr(a, char, 0)))
        self.ethnicity.delete(0, "end")
        self.ethnicity.insert(0, getattr(a, "ethnicity", "") or "")

    def _toggle(self, char: str, v: tk.BooleanVar) -> None:
        try:
            data.set_protected_characteristic(self.alumni_id, char,
                                                  v.get())
        except Exception as e:
            messagebox.showerror("Save", str(e)); self.refresh()

    def _save_eth(self) -> None:
        try:
            data.set_ethnicity(self.alumni_id,
                                  self.ethnicity.get() or None)
        except Exception as e:
            messagebox.showerror("Save", str(e))


# ── Per-alumnus: Custom values ───────────────────────────────────

class CustomValuesTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Custom")
        cols = ("name", "value", "type")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings", height=8)
        widths = {"name": 180, "value": 280, "type": 90}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Label(bar, text="Field:").pack(side="left")
        self.name = ttk.Combobox(bar, state="readonly", width=20)
        self.name.pack(side="left", padx=4)
        ttk.Label(bar, text="Value:").pack(side="left")
        self.value = ttk.Entry(bar, width=24)
        self.value.pack(side="left", padx=4)
        ttk.Button(bar, text="Set",
                     command=self._set).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        fields = data.list_custom_fields()
        types = {f.name: f.type for f in fields}
        self.name.configure(values=[f.name for f in fields])
        for i in self.tree.get_children(): self.tree.delete(i)
        for k, v in data.get_custom_values(self.alumni_id).items():
            self.tree.insert("", "end",
                values=(k, v, types.get(k, "?")))

    def _set(self) -> None:
        if not self.name.get(): return
        try:
            data.set_custom_value(self.alumni_id,
                                      self.name.get(),
                                      self.value.get())
        except Exception as e:
            messagebox.showerror("Set", str(e)); return
        self.value.delete(0, "end")
        self.refresh()


# ── Per-alumnus: Media attachments ───────────────────────────────

class MediaTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Media")
        cols = ("id", "kind", "profile", "consent",
                  "exif_stripped", "file_path")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings", height=8)
        widths = {"id": 50, "kind": 100, "profile": 70,
                    "consent": 70, "exif_stripped": 100,
                    "file_path": 360}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Button(bar, text="Attach…",
                     command=self._attach).pack(side="left")
        ttk.Button(bar, text="Set as profile",
                     command=self._profile).pack(side="left", padx=4)
        ttk.Button(bar, text="Toggle consent",
                     command=self._consent).pack(side="left")
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for m in data.list_media(self.alumni_id):
            self.tree.insert("", "end", iid=str(m.media_id),
                values=(m.media_id, m.kind,
                          "★" if m.is_profile else "",
                          "Y" if m.consent_granted else "N",
                          "Y" if m.exif_stripped else "N",
                          m.file_path))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _attach(self) -> None:
        from tkinter import filedialog as _fd
        path = _fd.askopenfilename(parent=self.frame.winfo_toplevel())
        if not path: return
        kind = _ask_choice(self.frame, "Kind", list(MEDIA_KINDS),
                              default="photo")
        if not kind: return
        consent = messagebox.askyesno("Consent",
                                          "Has the alumnus granted "
                                          "consent for this image?")
        try:
            data.attach_media(self.alumni_id, path, kind=kind,
                consent_granted=consent, strip_exif=True)
        except Exception as e:
            messagebox.showerror("Attach", str(e)); return
        self.refresh()

    def _profile(self) -> None:
        mid = self._selected()
        if mid is None: return
        try:
            data.set_profile_media(self.alumni_id, mid)
        except Exception as e:
            messagebox.showerror("Profile", str(e)); return
        self.refresh()

    def _consent(self) -> None:
        mid = self._selected()
        if mid is None: return
        m = next((x for x in data.list_media(self.alumni_id)
                    if x.media_id == mid), None)
        if not m: return
        try:
            data.set_media_consent(mid, not m.consent_granted)
        except Exception as e:
            messagebox.showerror("Consent", str(e)); return
        self.refresh()

    def _delete(self) -> None:
        mid = self._selected()
        if mid is None: return
        delfile = messagebox.askyesno("Delete",
                                          "Also delete file from disk?")
        data.delete_media(mid, delete_file=delfile)
        self.refresh()

