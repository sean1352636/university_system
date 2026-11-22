"""Engagement: social handles, connections, engagement score, chapters, directory consent, re-engagement, milestones, lost contact, public directory."""

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
    engagement as alumni_engagement,
    models as alumni_models,
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
    _money_str,
    _pick_alumnus_dialog,
)


# ══ Engagement extensions (items 1–8) ═════════════════════════════

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
        for s in alumni_engagement.list_social_handles(self.alumni_id):
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
        cur = next((s for s in alumni_engagement.list_social_handles(self.alumni_id)
                      if s.handle_id == hid), None)
        if cur is None: return
        SocialHandleDialog(self.frame.winfo_toplevel(),
                              alumni_id=self.alumni_id, existing=cur,
                              on_save=self.refresh)

    def _verify(self) -> None:
        hid = self._selected_id()
        if hid is None: return
        try:
            alumni_engagement.verify_social_handle(hid)
        except Exception as e:
            messagebox.showerror("Verify", str(e)); return
        self.refresh()

    def _delete(self) -> None:
        hid = self._selected_id()
        if hid is None: return
        if not messagebox.askyesno("Delete", f"Delete handle #{hid}?"):
            return
        alumni_engagement.delete_social_handle(hid)
        self.refresh()


class SocialHandleDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 existing, on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Social handle")
        self.win.transient(parent); grab_when_viewable(self.win)
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
                alumni_engagement.update_social_handle(
                    self.existing.handle_id,
                    {"handle": self.handle.get(),
                     "url": self.url.get(),
                     "notes": self.notes.get(),
                     "verified": self.verified_var.get()})
            else:
                alumni_engagement.add_social_handle(
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
        for c, other in alumni_engagement.list_connections(self.alumni_id):
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
            alumni_engagement.connect_alumni(self.alumni_id, other, kind=kind)
        except Exception as e:
            messagebox.showerror("Connect", str(e)); return
        self.refresh()

    def _disconnect(self) -> None:
        other = self._selected_other()
        if other is None: return
        if not messagebox.askyesno("Disconnect",
                                      "Remove this connection?"):
            return
        alumni_engagement.disconnect_alumni(self.alumni_id, other)
        self.refresh()

    def _mutuals(self) -> None:
        other = _pick_alumnus_dialog(self.frame.winfo_toplevel(),
                                        exclude=self.alumni_id)
        if other is None: return
        rows = alumni_engagement.mutuals_of(self.alumni_id, other)
        if not rows:
            messagebox.showinfo("Mutuals", "(no mutuals)")
            return
        msg = "\n".join(f"#{a.alumni_id}  {a.full_name}" for a in rows)
        messagebox.showinfo("Mutuals", msg)

    def _degrees(self) -> None:
        other = _pick_alumnus_dialog(self.frame.winfo_toplevel(),
                                        exclude=self.alumni_id)
        if other is None: return
        d = alumni_engagement.degrees_between(self.alumni_id, other)
        messagebox.showinfo(
            "Degrees",
            "Unconnected within depth 6"
            if d is None else f"{d} hop(s) apart")


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
            s = alumni_engagement.compute_engagement_score(self.alumni_id)
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
        for cm, ch in alumni_engagement.list_chapters_for(self.alumni_id,
                                                include_left=True):
            self.tree.insert(
                "", "end", iid=str(ch.chapter_id),
                values=(ch.chapter_id, ch.name, ch.kind, cm.role,
                          cm.joined_on or "—", cm.left_on or "—"))

    def _join(self) -> None:
        all_chapters = alumni_engagement.list_chapters()
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
            alumni_engagement.add_chapter_member(chosen.chapter_id, self.alumni_id,
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
        alumni_engagement.remove_chapter_member(cid, self.alumni_id)
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
        listed = alumni_engagement.is_in_directory(self.alumni_id)
        self.status.configure(
            text=("Listed in public directory ✓"
                    if listed else "Not listed in public directory"),
            foreground=("#2a7" if listed else "#a44"))

    def _opt_in(self) -> None:
        try:
            alumni_engagement.opt_in_directory(self.alumni_id, source="gui",
                                      actor="gui")
        except Exception as e:
            messagebox.showerror("Opt-in", str(e)); return
        self.refresh()

    def _opt_out(self) -> None:
        if not messagebox.askyesno(
                "Opt-out",
                "Withdraw the 'Directory' consent for this alumnus?"):
            return
        alumni_engagement.opt_out_directory(self.alumni_id, actor="gui")
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
        for c in alumni_engagement.list_chapters():
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
        cur = alumni_engagement.get_chapter(cid)
        if cur is None: return
        ChapterDialog(self.frame.winfo_toplevel(),
                        existing=cur, on_save=self.refresh)

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None: return
        if not messagebox.askyesno("Delete",
                                      f"Delete chapter #{cid}?"):
            return
        alumni_engagement.delete_chapter(cid)
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
        self.win.transient(parent); grab_when_viewable(self.win)
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
                alumni_engagement.update_chapter(self.existing.chapter_id, payload)
            else:
                alumni_engagement.create_chapter(
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
        chapter = alumni_engagement.get_chapter(chapter_id)
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
        for cm, al in alumni_engagement.list_chapter_members(
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
            alumni_engagement.add_chapter_member(self.chapter_id, aid, role=role)
        except Exception as e:
            messagebox.showerror("Add", str(e)); return
        self.refresh()

    def _role(self) -> None:
        aid = self._selected()
        if aid is None: return
        role = _ask_choice(self.win, "Role", list(CHAPTER_ROLES))
        if not role: return
        try:
            alumni_engagement.set_chapter_role(self.chapter_id, aid, role)
        except Exception as e:
            messagebox.showerror("Role", str(e)); return
        self.refresh()

    def _remove(self) -> None:
        aid = self._selected()
        if aid is None: return
        if not messagebox.askyesno("Remove",
                                      "Mark this member as left?"):
            return
        alumni_engagement.remove_chapter_member(self.chapter_id, aid)
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
        for c in alumni_engagement.re_engagement_worklist(
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
        for m in alumni_engagement.upcoming_milestones(days=days):
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
        self.thr.insert(0, str(alumni_models.HARD_BOUNCE_THRESHOLD))
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
        for c in alumni_engagement.lost_contact_queue(
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
        for d in alumni_engagement.list_public_directory(
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
