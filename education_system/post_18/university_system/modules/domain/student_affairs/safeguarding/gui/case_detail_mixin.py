import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, scrolledtext, filedialog

logger = logging.getLogger(__name__)

from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.api import (
    _CUMULATIVE_WINDOW_DAYS,
    _LANG_NAMES,
    add_action_item,
    add_case_note,
    add_referral,
    assign_case,
    audit_log,
    complete_action_item,
    cumulative_concern,
    find_linked_cases,
    list_action_items,
    list_assignments,
    list_case_notes,
    list_referrals,
    notify_reporter_on_status_change,
    update_submission_status,
)


class CaseDetailMixin:
    def _render_overview_tab(
        self,
        host,
        sid,
        name,
        username,
        ts,
        sev,
        cats_json,
        status,
        content,
        reviewer,
        note,
        reviewed_at,
        extra,
    ):
        pad = dict(padx=12, pady=4)

        if extra.get("anonymous"):
            student_label = "(anonymous)"
        elif extra.get("on_behalf_of"):
            student_label = (
                f"{name} ({username})  "
                f"— reported by {extra.get('reporter_username') or '?'}"
                f" ({extra.get('subject_relation') or 'relation unspecified'})"
            )
        else:
            student_label = f"{name} ({username})"

        meta = f"Student: {student_label}\nSubmitted: {ts.replace('T', ' ')[:19]}\nStatus: {status}"
        if extra.get("language"):
            meta += f"\nLanguage: {_LANG_NAMES.get(extra['language'], extra['language'])}"
        if extra.get("case_location") or extra.get("case_department"):
            meta += (
                f"\nLocation: {extra.get('case_location') or '?'}"
                f"  |  Department: {extra.get('case_department') or '?'}"
            )
        if extra.get("assigned_to"):
            meta += f"\nAssigned to: {extra['assigned_to']}"
        if extra.get("sla_due_at"):
            meta += f"\nSLA due: {extra['sla_due_at'].replace('T', ' ')[:19]}"
        if extra.get("duplicate_of"):
            meta += f"\n⚠ Possible duplicate of #{extra['duplicate_of']}"
        if reviewer:
            meta += f"\nLast reviewed by: {reviewer} at {reviewed_at[:19]}"
        tk.Label(host, text=meta, bg="white", justify="left", font=("Segoe UI", 9)).pack(
            anchor="w", **pad
        )

        # Vulnerability flag chips
        try:
            vflags = json.loads(extra.get("vulnerability_flags_json") or "null") or []
        except (TypeError, ValueError):
            vflags = []
        if vflags:
            chip_row = tk.Frame(host, bg="white")
            chip_row.pack(anchor="w", padx=12, pady=(0, 4))
            tk.Label(
                chip_row, text="Vulnerability:", bg="white", font=("Segoe UI", 9, "bold")
            ).pack(side="left")
            for f in vflags:
                tk.Label(
                    chip_row,
                    text=f" {f} ",
                    bg="#fff3e0",
                    fg="#b71c1c",
                    font=("Segoe UI", 8, "bold"),
                    padx=4,
                    pady=1,
                    bd=1,
                    relief="solid",
                ).pack(side="left", padx=2)

        # Attachments + audio + transcription block
        try:
            atts = json.loads(extra.get("attachments_json") or "null") or []
        except (TypeError, ValueError):
            atts = []
        if atts or extra.get("audio_path") or extra.get("transcription"):
            tk.Label(host, text="Attachments:", bg="white", font=("Segoe UI", 9, "bold")).pack(
                anchor="w", **pad
            )
            for a in atts:
                row = tk.Frame(host, bg="white")
                row.pack(anchor="w", padx=24, pady=1)
                tk.Label(
                    row,
                    text="📎 " + (a.get("orig_name") or "(file)"),
                    bg="white",
                    font=("Segoe UI", 9),
                ).pack(side="left")
                if a.get("stored"):
                    ttk.Button(
                        row,
                        text="Open",
                        command=lambda s=a["stored"]: self._open_attachment(s),
                    ).pack(side="left", padx=4)
            if extra.get("audio_path"):
                row = tk.Frame(host, bg="white")
                row.pack(anchor="w", padx=24, pady=1)
                tk.Label(row, text="🎙 audio note", bg="white", font=("Segoe UI", 9)).pack(
                    side="left"
                )
                ttk.Button(
                    row,
                    text="Open",
                    command=lambda s=extra["audio_path"]: self._open_attachment(s),
                ).pack(side="left", padx=4)
            if extra.get("transcription"):
                tk.Label(host, text="Transcript:", bg="white", font=("Segoe UI", 9, "bold")).pack(
                    anchor="w", **pad
                )
                tk.Label(
                    host,
                    text=extra["transcription"],
                    bg="white",
                    wraplength=460,
                    justify="left",
                    font=("Segoe UI", 9, "italic"),
                    fg="#444",
                ).pack(anchor="w", padx=24)

        # Flagged categories — regex + NLP merged for display.
        try:
            cats = json.loads(cats_json) if cats_json else {}
        except (TypeError, ValueError):
            cats = {}
        if isinstance(cats, list):
            cats = {str(c): [] for c in cats}
        elif not isinstance(cats, dict):
            cats = {}
        try:
            nlp_cats = json.loads(extra.get("nlp_categories_json") or "null") or {}
        except (TypeError, ValueError):
            nlp_cats = {}
        if cats or nlp_cats:
            tk.Label(
                host, text="Flagged categories:", bg="white", font=("Segoe UI", 9, "bold")
            ).pack(anchor="w", **pad)
            for cat, snippets in cats.items():
                line = f"• {cat}"
                if cat in nlp_cats:
                    line += f"   (NLP {nlp_cats[cat]:.2f})"
                tk.Label(host, text=line, bg="white", font=("Segoe UI", 9), fg="#b00020").pack(
                    anchor="w", padx=24
                )
                if not isinstance(snippets, (list, tuple)):
                    snippets = []
                for snip in snippets[:3]:
                    tk.Label(
                        host,
                        text=f"   “{snip}”",
                        bg="white",
                        font=("Segoe UI", 8),
                        fg="#555",
                        wraplength=460,
                        justify="left",
                    ).pack(anchor="w", padx=24)
            for cat, score in nlp_cats.items():
                if cat in cats:
                    continue
                tk.Label(
                    host,
                    text=f"• {cat}   (NLP {score:.2f})",
                    bg="white",
                    font=("Segoe UI", 9),
                    fg="#d9480f",
                ).pack(anchor="w", padx=24)
        else:
            tk.Label(
                host, text="No automated flags.", bg="white", fg="#2e7d32", font=("Segoe UI", 9)
            ).pack(anchor="w", **pad)

        # Original content
        tk.Label(host, text="Content:", bg="white", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", **pad
        )
        content_box = scrolledtext.ScrolledText(
            host, wrap="word", height=6, font=("Segoe UI", 9), bg="#fafafa"
        )
        content_box.insert("1.0", content)
        content_box.config(state="disabled")
        content_box.pack(fill="x", padx=12, pady=4)

        # Review note + status buttons
        tk.Label(host, text="Review note:", bg="white", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", **pad
        )
        note_box = tk.Text(host, height=3, font=("Segoe UI", 9))
        if note:
            note_box.insert("1.0", note)
        note_box.pack(fill="x", padx=12)

        actions = tk.Frame(host, bg="white")
        actions.pack(fill="x", padx=12, pady=10)

        def set_status(new_status):
            update_submission_status(
                sid,
                new_status,
                self.user["full_name"],
                note_box.get("1.0", "end").strip(),
            )
            audit_log(
                actor=self.user.get("username", "?"),
                actor_role=self.user.get("role"),
                action="status_change",
                case_id=sid,
                details=f"-> {new_status}",
            )
            notify_reporter_on_status_change(sid, new_status, actor=self.user.get("username", "?"))
            logger.info(
                "Safeguarding submission %s status->%s by %s",
                sid,
                new_status,
                self.user.get("username"),
            )
            messagebox.showinfo("Updated", f"Submission #{sid} marked as '{new_status}'.")
            self._refresh_staff_list()
            self._render_empty_detail()

        ttk.Button(
            actions, text="Mark In progress", command=lambda: set_status("In progress")
        ).pack(side="left", padx=2)
        ttk.Button(actions, text="Close case…", command=lambda: self._open_close_dialog(sid)).pack(
            side="left", padx=2
        )
        ttk.Button(
            actions, text="Escalate (DSL)", command=lambda: self._escalate_to_dsl(sid, note_box)
        ).pack(side="left", padx=2)

        # Feature 26 / 27 / 30 — extra tooling row.
        more = tk.Frame(host, bg="white")
        more.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(
            more, text="Apply support template…", command=lambda: self._open_template_dialog(sid)
        ).pack(side="left", padx=2)
        ttk.Button(
            more, text="Schedule review…", command=lambda: self._open_review_dialog(sid)
        ).pack(side="left", padx=2)
        ttk.Button(more, text="Merge…", command=lambda: self._open_merge_dialog(sid)).pack(
            side="left", padx=2
        )
        ttk.Button(more, text="Split…", command=lambda: self._open_split_dialog(sid)).pack(
            side="left", padx=2
        )

        # Feature 28 — show closure context if already closed.
        if extra.get("outcome_code"):
            tk.Label(
                host,
                text=f"Outcome: {extra['outcome_code']}  —  "
                f"{(extra.get('closure_reason') or '')[:120]}",
                bg="white",
                fg="#1f3a5f",
                font=("Segoe UI", 9, "italic"),
            ).pack(anchor="w", padx=12, pady=(4, 0))

    def _render_notes_tab(self, host, sid):
        tk.Label(
            host,
            text="Confidential case notes (append-only)",
            bg="white",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 6))
        lst = scrolledtext.ScrolledText(
            host, wrap="word", height=12, font=("Segoe UI", 9), bg="#fafafa"
        )
        for author, note, ts in list_case_notes(sid):
            lst.insert("end", f"[{ts.replace('T', ' ')[:19]}] {author}\n{note}\n\n")
        lst.config(state="disabled")
        lst.pack(fill="both", expand=True, padx=12)

        row = tk.Frame(host, bg="white")
        row.pack(fill="x", padx=12, pady=8)
        entry = tk.Text(row, height=3, font=("Segoe UI", 9))
        entry.pack(side="left", fill="x", expand=True)

        def _add():
            txt = entry.get("1.0", "end").strip()
            if not txt:
                return
            add_case_note(sid, self.user.get("username") or "?", txt)
            entry.delete("1.0", "end")
            # Re-render the tab
            for w in host.winfo_children():
                w.destroy()
            self._render_notes_tab(host, sid)

        ttk.Button(row, text="Append", command=_add).pack(side="right", padx=4)

    def _render_actions_tab(self, host, sid):
        tk.Label(host, text="Action plan", bg="white", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=12, pady=(10, 6)
        )
        cols = ("id", "title", "owner", "due", "status")
        tree = ttk.Treeview(host, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (40, 200, 100, 100, 80)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="x", padx=12)
        for item in list_action_items(sid):
            iid, title, owner, due, status, _completed = item
            tree.insert(
                "", "end", iid=str(iid), values=(iid, title, owner or "", due or "", status)
            )

        form = tk.Frame(host, bg="white")
        form.pack(fill="x", padx=12, pady=8)
        tk.Label(form, text="Title:", bg="white").grid(row=0, column=0, sticky="w")
        t_e = ttk.Entry(form, width=32)
        t_e.grid(row=0, column=1, padx=4)
        tk.Label(form, text="Owner:", bg="white").grid(row=0, column=2, sticky="w")
        o_e = ttk.Entry(form, width=14)
        o_e.grid(row=0, column=3, padx=4)
        tk.Label(form, text="Due (YYYY-MM-DD):", bg="white").grid(
            row=1, column=0, sticky="w", pady=4
        )
        d_e = ttk.Entry(form, width=14)
        d_e.grid(row=1, column=1, sticky="w", padx=4)

        def _add():
            title = t_e.get().strip()
            if not title:
                return
            add_action_item(sid, title, o_e.get().strip(), d_e.get().strip())
            for w in host.winfo_children():
                w.destroy()
            self._render_actions_tab(host, sid)

        def _complete():
            sel = tree.selection()
            if not sel:
                return
            complete_action_item(int(sel[0]))
            for w in host.winfo_children():
                w.destroy()
            self._render_actions_tab(host, sid)

        ttk.Button(form, text="Add", command=_add).grid(row=1, column=3, padx=4)
        ttk.Button(form, text="Mark complete", command=_complete).grid(row=1, column=4, padx=4)

    def _render_referrals_tab(self, host, sid):
        tk.Label(
            host,
            text="External referrals (Police, LA, Social Care…)",
            bg="white",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 6))
        cols = ("agency", "contact", "ref", "sent", "status")
        tree = ttk.Treeview(host, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (140, 130, 90, 130, 70)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="x", padx=12)
        for ref in list_referrals(sid):
            _iid, agency, contact, refno, sent_at, status, _note = ref
            tree.insert(
                "",
                "end",
                values=(agency, contact or "", refno or "", sent_at.replace("T", " ")[:16], status),
            )

        form = tk.Frame(host, bg="white")
        form.pack(fill="x", padx=12, pady=8)
        tk.Label(form, text="Agency:", bg="white").grid(row=0, column=0, sticky="w")
        a_e = ttk.Combobox(
            form,
            width=18,
            values=[
                "Police",
                "Local Authority",
                "Children's Social Care",
                "Adult Social Care",
                "NHS",
                "Charity / NGO",
                "Other",
            ],
        )
        a_e.grid(row=0, column=1, padx=4)
        tk.Label(form, text="Contact:", bg="white").grid(row=0, column=2, sticky="w")
        c_e = ttk.Entry(form, width=16)
        c_e.grid(row=0, column=3, padx=4)
        tk.Label(form, text="Ref #:", bg="white").grid(row=1, column=0, sticky="w", pady=4)
        r_e = ttk.Entry(form, width=14)
        r_e.grid(row=1, column=1, sticky="w", padx=4)
        tk.Label(form, text="Note:", bg="white").grid(row=1, column=2, sticky="w", pady=4)
        n_e = ttk.Entry(form, width=20)
        n_e.grid(row=1, column=3, padx=4)

        def _add():
            agency = a_e.get().strip()
            if not agency:
                return
            add_referral(sid, agency, c_e.get().strip(), r_e.get().strip(), n_e.get().strip())
            for w in host.winfo_children():
                w.destroy()
            self._render_referrals_tab(host, sid)

        ttk.Button(form, text="Log referral", command=_add).grid(row=1, column=4, padx=6)

    def _render_integrations_tab(self, host, sid, extra):
        pad = dict(padx=12, pady=4)
        tk.Label(
            host,
            text="Cross-system links & external notifications",
            bg="white",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 6))

        # Mandatory-reporting status + acknowledge
        if extra.get("mandatory_reporting"):
            mrow = tk.Frame(host, bg="#fff3e0", bd=1, relief="solid")
            mrow.pack(fill="x", padx=12, pady=4)
            tk.Label(
                mrow,
                text=f"Mandatory reporting: {extra.get('mandatory_status') or 'Pending'}"
                + (
                    f"  (reported {extra.get('mandatory_reported_at', '')[:19]})"
                    if extra.get("mandatory_reported_at")
                    else ""
                ),
                bg="#fff3e0",
                fg="#5b0011",
                font=("Segoe UI", 9, "bold"),
                padx=8,
                pady=4,
            ).pack(side="left")
            if (extra.get("mandatory_status") or "Pending") == "Pending":
                ttk.Button(
                    mrow,
                    text="Acknowledge / mark reported…",
                    command=lambda: self._ack_mandatory(sid),
                ).pack(side="right", padx=6)

        # Whistleblowing reviewer assignment notice
        if extra.get("whistleblowing"):
            tk.Label(
                host,
                text=f"Whistleblowing — independent reviewer: "
                f"{extra.get('wb_independent_reviewer') or '(unassigned)'}",
                bg="white",
                fg="#4527a0",
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w", **pad)

        # Live link summary
        def _link_line(label, value, button_label=None, button_cmd=None):
            row = tk.Frame(host, bg="white")
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(
                row,
                text=label + ":",
                bg="white",
                width=24,
                anchor="w",
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left")
            tk.Label(row, text=value or "—", bg="white", font=("Segoe UI", 9)).pack(side="left")
            if button_label:
                ttk.Button(row, text=button_label, command=button_cmd).pack(side="right")

        _link_line(
            "Wellbeing appointment",
            extra.get("linked_wellbeing_appt"),
            "Book…",
            lambda: self._book_wellbeing(sid),
        )
        _link_line(
            "Conduct case",
            extra.get("linked_conduct_case"),
            "Link…",
            lambda: self._link_conduct(sid),
        )
        _link_line(
            "Halls incident",
            extra.get("linked_halls_incident"),
            "Link…",
            lambda: self._link_halls(sid),
        )
        _link_line(
            "Health Centre referral",
            (extra.get("health_referral_sent_at") or "—")[:19],
            "Refer (consent)…",
            lambda: self._health_referral(sid),
        )
        _link_line(
            "Tutor notified",
            (extra.get("tutor_notified_at") or "—")[:19],
            "Notify tutor…",
            lambda: self._notify_tutor(sid),
        )
        if extra.get("tutor_notification_redacted"):
            tk.Label(
                host,
                text="Last sent to tutor (redacted):",
                bg="white",
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w", **pad)
            tk.Label(
                host,
                text=extra["tutor_notification_redacted"][:400],
                bg="white",
                wraplength=460,
                justify="left",
                fg="#555",
                font=("Segoe UI", 9, "italic"),
            ).pack(anchor="w", padx=24)

    def _render_linked_tab(self, host, sid, extra):
        tk.Label(
            host, text="Linked cases — same subject", bg="white", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=12, pady=(10, 6))
        subj = extra.get("linked_subject_id")
        if not subj:
            tk.Label(
                host,
                text="No subject id (anonymous case) — cannot link.",
                bg="white",
                fg="#666",
                font=("Segoe UI", 9, "italic"),
            ).pack(anchor="w", padx=12, pady=8)
            return
        cols = ("id", "submitted", "severity", "status", "lifecycle")
        tree = ttk.Treeview(host, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (50, 140, 90, 90, 90)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=12)
        related = find_linked_cases(subj, exclude_id=sid)
        for lid, lts, lsev, lstatus, llifecycle in related:
            tree.insert(
                "",
                "end",
                values=(lid, lts.replace("T", " ")[:16], lsev, lstatus, llifecycle or "Open"),
            )

        n, escalate = cumulative_concern(subj)
        warn = (
            f"⚠ {n} concerns in the last {_CUMULATIVE_WINDOW_DAYS} days"
            if escalate
            else f"{n} concerns in the last {_CUMULATIVE_WINDOW_DAYS} days"
        )
        tk.Label(
            host,
            text=warn,
            bg="white",
            fg="#b00020" if escalate else "#1f3a5f",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=12, pady=(8, 0))

    def _render_audit_tab(self, host, sid, extra):
        tk.Label(host, text="Assignment history", bg="white", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=12, pady=(10, 6)
        )
        cols = ("assignee", "by", "at", "note")
        tree = ttk.Treeview(host, columns=cols, show="headings", height=6)
        for c, w in zip(cols, (110, 110, 140, 200)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="x", padx=12)
        for assignee, by, at, note in list_assignments(sid):
            tree.insert("", "end", values=(assignee, by, at.replace("T", " ")[:16], note or ""))

        # Reassignment form
        form = tk.Frame(host, bg="white")
        form.pack(fill="x", padx=12, pady=8)
        tk.Label(form, text="Reassign to (username):", bg="white").grid(row=0, column=0, sticky="w")
        u_e = ttk.Entry(form, width=18)
        u_e.grid(row=0, column=1, padx=4)
        tk.Label(form, text="Note:", bg="white").grid(row=0, column=2, sticky="w")
        n_e = ttk.Entry(form, width=24)
        n_e.grid(row=0, column=3, padx=4)

        def _reassign():
            who = u_e.get().strip()
            if not who:
                return
            assign_case(
                sid, who, assigned_by=self.user.get("username") or "?", note=n_e.get().strip()
            )
            for w in host.winfo_children():
                w.destroy()
            self._render_audit_tab(host, sid, extra)

        ttk.Button(form, text="Reassign", command=_reassign).grid(row=0, column=4, padx=6)
