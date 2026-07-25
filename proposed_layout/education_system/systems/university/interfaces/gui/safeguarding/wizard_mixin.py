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

from education_system.systems.university.domain.safeguarding.api import (
    RISK_PATTERNS,
    SEVERITY_ORDER,
    SUPPORT_RESOURCES,
    VULNERABILITY_FLAGS,
    _CUMULATIVE_WINDOW_DAYS,
    _LANG_NAMES,
    _SECURE_DIR,
    add_case_note,
    analyse_text,
    canonical_subject_id,
    clear_draft,
    cumulative_concern,
    encrypt_and_store,
    fetch_user_submissions,
    find_duplicate,
    is_self_harm_case,
    issue_contact_token,
    load_draft,
    lookup_by_contact_token,
    maybe_transcribe,
    nlp_classify,
    save_draft,
    save_submission,
    tr,
)


class WizardMixin:
    def show_student_dashboard(self):
        self._clear()
        self.unbind("<Return>")
        self._build_topbar(f"Welcome, {self.user['full_name']}")

        # Per-user state held on the instance
        self.lang = self.user.get("language") or "en"
        self.wizard_step = 0
        self.wizard_state = {
            "consent_disclosure": False,
            "consent_contact": False,
            "anonymous": False,
            "on_behalf_of": False,
            "subject_relation": "",
            "triage": {"q1": "", "q2": "", "q3": "", "q4": ""},
            "content": "",
            "attachments": [],  # list of dicts: {"orig": str, "stored": str|None}
            "audio_orig": "",
            "audio_stored": "",
            "transcription": "",
            "vulnerability_flags": [],
            "case_location": "",
            "case_department": "",
            "whistleblowing": False,
            "wb_independent_reviewer": "",
        }
        existing_draft = load_draft(self.user.get("username") or "")
        if existing_draft:
            try:
                self.wizard_state.update(existing_draft.get("state") or {})
                self.lang = existing_draft.get("lang") or self.lang
                messagebox.showinfo("Draft", tr("draft_restored", self.lang))
            except Exception:
                pass

        # Layout: wizard on left, history + support on right
        body = tk.Frame(self.container, bg="#f4f6fa")
        body.pack(fill="both", expand=True, padx=20, pady=10)

        left = tk.Frame(body, bg="#f4f6fa")
        right = tk.Frame(body, bg="#f4f6fa", width=300)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="y", padx=(15, 0))

        self.wizard_host = tk.Frame(left, bg="#f4f6fa")
        self.wizard_host.pack(fill="both", expand=True)
        self._render_wizard()

        # Right column: anonymous check + history + support
        anon_btn = ttk.Button(
            right, text=tr("check_anon", self.lang), command=self._open_anon_check
        )
        anon_btn.pack(anchor="w", pady=(0, 8))

        ttk.Label(right, text="Your recent submissions", style="Sub.TLabel").pack(anchor="w")
        self.history_list = tk.Listbox(right, width=40, height=10, font=("Segoe UI", 9))
        self.history_list.pack(fill="x", pady=(2, 15))
        self._refresh_student_history()

        support = tk.Frame(right, bg="#eaf4ec", bd=1, relief="solid")
        support.pack(fill="x")
        tk.Label(support, text="Need help now?", bg="#eaf4ec", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=10, pady=(8, 4)
        )
        tk.Label(
            support,
            text=SUPPORT_RESOURCES,
            bg="#eaf4ec",
            justify="left",
            font=("Segoe UI", 9),
            wraplength=280,
        ).pack(anchor="w", padx=10, pady=(0, 10))

    def _render_wizard(self):
        for w in self.wizard_host.winfo_children():
            w.destroy()

        # Step pills
        steps = [
            tr("step_consent", self.lang),
            tr("step_triage", self.lang),
            tr("step_details", self.lang),
            tr("step_review", self.lang),
        ]
        pill = tk.Frame(self.wizard_host, bg="#f4f6fa")
        pill.pack(fill="x", pady=(0, 8))
        for i, name in enumerate(steps):
            active = i == self.wizard_step
            tk.Label(
                pill,
                text=f"  {i + 1}. {name}  ",
                bg="#1f3a5f" if active else "#d0d6e0",
                fg="white" if active else "#333",
                font=("Segoe UI", 9, "bold" if active else "normal"),
                padx=6,
                pady=4,
            ).pack(side="left", padx=2)

        body = tk.Frame(self.wizard_host, bg="white", bd=1, relief="solid")
        body.pack(fill="both", expand=True)
        renderer = (self._step_consent, self._step_triage, self._step_details, self._step_review)[
            self.wizard_step
        ]
        renderer(body)

        # Nav row
        nav = tk.Frame(self.wizard_host, bg="#f4f6fa")
        nav.pack(fill="x", pady=8)
        if self.wizard_step > 0:
            ttk.Button(nav, text=tr("back", self.lang), command=self._wizard_back).pack(side="left")
        if self.wizard_step < 3:
            ttk.Button(nav, text=tr("next", self.lang), command=self._wizard_next).pack(
                side="right"
            )
        else:
            ttk.Button(nav, text=tr("submit", self.lang), command=self._wizard_submit).pack(
                side="right"
            )

    def _wizard_back(self):
        self._collect_current_step()
        self.wizard_step = max(0, self.wizard_step - 1)
        self._render_wizard()

    def _wizard_next(self):
        if not self._collect_current_step(validate=True):
            return
        self._persist_draft()
        self.wizard_step = min(3, self.wizard_step + 1)
        self._render_wizard()

    def _persist_draft(self):
        save_draft(self.user.get("username") or "", {"lang": self.lang, "state": self.wizard_state})

    def _step_consent(self, host):
        pad = dict(padx=14, pady=4)
        tk.Label(
            host, text=tr("consent_heading", self.lang), bg="white", font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(
            host,
            text=tr("consent_body", self.lang),
            bg="white",
            wraplength=520,
            justify="left",
            font=("Segoe UI", 9),
        ).pack(anchor="w", **pad)

        # Language selector
        lang_row = tk.Frame(host, bg="white")
        lang_row.pack(fill="x", **pad)
        tk.Label(lang_row, text=tr("language", self.lang) + ":", bg="white").pack(side="left")
        self._lang_var = tk.StringVar(value=self.lang)
        codes = list(_LANG_NAMES.keys())
        names = [_LANG_NAMES[c] for c in codes]
        combo = ttk.Combobox(lang_row, values=names, state="readonly", width=18)
        combo.current(codes.index(self.lang) if self.lang in codes else 0)
        combo.pack(side="left", padx=6)

        def on_lang(_e):
            new = codes[combo.current()]
            if new != self.lang:
                self.lang = new
                self._collect_current_step()
                self._render_wizard()

        combo.bind("<<ComboboxSelected>>", on_lang)

        # Consent checkboxes
        self._cv_disclose = tk.BooleanVar(value=self.wizard_state["consent_disclosure"])
        self._cv_contact = tk.BooleanVar(value=self.wizard_state["consent_contact"])
        self._cv_anon = tk.BooleanVar(value=self.wizard_state["anonymous"])
        self._cv_obo = tk.BooleanVar(value=self.wizard_state["on_behalf_of"])

        tk.Checkbutton(
            host,
            text=tr("consent_disclose", self.lang),
            variable=self._cv_disclose,
            bg="white",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", **pad)
        tk.Checkbutton(
            host,
            text=tr("consent_contact", self.lang),
            variable=self._cv_contact,
            bg="white",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", **pad)
        tk.Checkbutton(
            host, text=tr("anonymous", self.lang), variable=self._cv_anon, bg="white"
        ).pack(anchor="w", **pad)
        tk.Checkbutton(
            host,
            text=tr("on_behalf", self.lang),
            variable=self._cv_obo,
            bg="white",
            command=self._toggle_obo_field,
        ).pack(anchor="w", **pad)

        self._obo_row = tk.Frame(host, bg="white")
        self._obo_row.pack(fill="x", **pad)
        self._toggle_obo_field()

        # Feature 17 — vulnerability flags
        tk.Label(
            host, text="Vulnerability factors (optional):", bg="white", font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", **pad)
        self._vuln_vars = {}
        existing = set(self.wizard_state.get("vulnerability_flags") or [])
        vuln_row = tk.Frame(host, bg="white")
        vuln_row.pack(anchor="w", padx=20)
        for i, flag in enumerate(VULNERABILITY_FLAGS):
            var = tk.BooleanVar(value=(flag in existing))
            self._vuln_vars[flag] = var
            tk.Checkbutton(vuln_row, text=flag, variable=var, bg="white").grid(
                row=i // 2, column=i % 2, sticky="w", padx=4
            )

        # Feature 19 — location & department for the incident
        loc_row = tk.Frame(host, bg="white")
        loc_row.pack(fill="x", **pad)
        tk.Label(loc_row, text="Location:", bg="white", width=12, anchor="w").pack(side="left")
        self._loc_entry = ttk.Entry(loc_row, width=22)
        self._loc_entry.insert(0, self.wizard_state.get("case_location") or "")
        self._loc_entry.pack(side="left", padx=4)
        tk.Label(loc_row, text="  Department:", bg="white").pack(side="left")
        self._dept_entry = ttk.Entry(loc_row, width=22)
        self._dept_entry.insert(0, self.wizard_state.get("case_department") or "")
        self._dept_entry.pack(side="left", padx=4)

        # Feature 42 — Whistleblowing channel
        self._cv_wb = tk.BooleanVar(value=self.wizard_state["whistleblowing"])
        tk.Checkbutton(
            host,
            text="This is a whistleblowing disclosure (handled by independent reviewers only)",
            variable=self._cv_wb,
            bg="white",
            command=self._toggle_wb_field,
            wraplength=520,
            justify="left",
        ).pack(anchor="w", **pad)
        self._wb_row = tk.Frame(host, bg="white")
        self._wb_row.pack(fill="x", **pad)
        self._toggle_wb_field()

    def _toggle_wb_field(self):
        for w in self._wb_row.winfo_children():
            w.destroy()
        if self._cv_wb.get():
            tk.Label(
                self._wb_row, text="Preferred independent reviewer (optional username):", bg="white"
            ).pack(side="left")
            self._wb_entry = ttk.Entry(self._wb_row, width=22)
            self._wb_entry.insert(0, self.wizard_state.get("wb_independent_reviewer") or "")
            self._wb_entry.pack(side="left", padx=6)

    def _toggle_obo_field(self):
        for w in self._obo_row.winfo_children():
            w.destroy()
        if self._cv_obo.get():
            tk.Label(self._obo_row, text=tr("subject_relation", self.lang) + ":", bg="white").pack(
                side="left"
            )
            self._obo_entry = ttk.Entry(self._obo_row, width=30)
            self._obo_entry.insert(0, self.wizard_state.get("subject_relation") or "")
            self._obo_entry.pack(side="left", padx=6)

    def _step_triage(self, host):
        pad = dict(padx=14, pady=(6, 2))
        tk.Label(
            host, text=tr("step_triage", self.lang), bg="white", font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=14, pady=(14, 4))

        self._tr_q1 = self._labelled_entry(
            host, tr("triage_q1", self.lang), self.wizard_state["triage"].get("q1", "")
        )
        self._tr_q2 = self._labelled_entry(
            host, tr("triage_q2", self.lang), self.wizard_state["triage"].get("q2", "")
        )

        # q3 — immediate danger (radio)
        tk.Label(
            host, text=tr("triage_q3", self.lang), bg="white", font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", **pad)
        self._tr_q3 = tk.StringVar(value=self.wizard_state["triage"].get("q3", "no"))
        row = tk.Frame(host, bg="white")
        row.pack(anchor="w", padx=20)
        for code, label in (
            ("yes", tr("yes", self.lang)),
            ("no", tr("no", self.lang)),
            ("unsure", tr("unsure", self.lang)),
        ):
            tk.Radiobutton(row, text=label, value=code, variable=self._tr_q3, bg="white").pack(
                side="left", padx=4
            )

        # q4 — told anyone
        tk.Label(
            host, text=tr("triage_q4", self.lang), bg="white", font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", **pad)
        self._tr_q4 = tk.StringVar(value=self.wizard_state["triage"].get("q4", "no"))
        row2 = tk.Frame(host, bg="white")
        row2.pack(anchor="w", padx=20, pady=(0, 10))
        for code, label in (("yes", tr("yes", self.lang)), ("no", tr("no", self.lang))):
            tk.Radiobutton(row2, text=label, value=code, variable=self._tr_q4, bg="white").pack(
                side="left", padx=4
            )

    def _labelled_entry(self, host, label, initial):
        tk.Label(host, text=label, bg="white", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", padx=14, pady=(6, 2)
        )
        e = ttk.Entry(host, width=70)
        e.insert(0, initial or "")
        e.pack(anchor="w", padx=14)
        return e

    def _step_details(self, host):
        tk.Label(
            host, text=tr("step_details", self.lang), bg="white", font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=14, pady=(14, 4))

        self.txt_input = scrolledtext.ScrolledText(
            host,
            wrap="word",
            font=("Segoe UI", 11),
            relief="flat",
            padx=10,
            pady=10,
            height=10,
        )
        if self.wizard_state.get("content"):
            self.txt_input.insert("1.0", self.wizard_state["content"])
        self.txt_input.pack(fill="both", expand=True, padx=14, pady=4)
        # Auto-save on each key release
        self.txt_input.bind("<KeyRelease>", lambda _e: self._autosave_content())

        # Attachments
        tk.Label(
            host, text=tr("attachments", self.lang) + ":", bg="white", font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=14, pady=(8, 2))
        self._att_list = tk.Listbox(host, height=4, font=("Segoe UI", 9))
        for a in self.wizard_state.get("attachments", []):
            self._att_list.insert("end", os.path.basename(a.get("orig") or "(file)"))
        self._att_list.pack(fill="x", padx=14)

        row = tk.Frame(host, bg="white")
        row.pack(anchor="w", padx=14, pady=4)
        ttk.Button(row, text=tr("add_file", self.lang), command=self._add_attachment).pack(
            side="left"
        )
        ttk.Button(row, text=tr("add_audio", self.lang), command=self._add_audio).pack(
            side="left", padx=6
        )
        ttk.Button(row, text=tr("remove", self.lang), command=self._remove_attachment).pack(
            side="left"
        )
        if self.wizard_state.get("audio_orig"):
            tk.Label(
                row,
                text="🎙 " + os.path.basename(self.wizard_state["audio_orig"]),
                bg="white",
                fg="#1f3a5f",
            ).pack(side="left", padx=8)

    def _autosave_content(self):
        try:
            self.wizard_state["content"] = self.txt_input.get("1.0", "end").strip()
            self._persist_draft()
        except tk.TclError:
            pass

    def _add_attachment(self):
        path = filedialog.askopenfilename(
            title=tr("add_file", self.lang),
            filetypes=[("All files", "*.*")],
        )
        if not path:
            return
        stored = encrypt_and_store(path)
        self.wizard_state["attachments"].append({"orig": path, "stored": stored})
        self._att_list.insert("end", os.path.basename(path))
        self._persist_draft()

    def _remove_attachment(self):
        sel = list(self._att_list.curselection())
        for idx in reversed(sel):
            try:
                entry = self.wizard_state["attachments"].pop(idx)
                if entry.get("stored"):
                    p = os.path.join(_SECURE_DIR, entry["stored"])
                    if os.path.exists(p):
                        os.remove(p)
            except (IndexError, OSError):
                pass
            self._att_list.delete(idx)
        self._persist_draft()

    def _add_audio(self):
        path = filedialog.askopenfilename(
            title=tr("add_audio", self.lang),
            filetypes=[("Audio", "*.wav *.mp3 *.m4a *.ogg *.flac"), ("All files", "*.*")],
        )
        if not path:
            return
        stored = encrypt_and_store(path)
        transcription = maybe_transcribe(path) or ""
        self.wizard_state["audio_orig"] = path
        self.wizard_state["audio_stored"] = stored or ""
        self.wizard_state["transcription"] = transcription
        self._persist_draft()
        if transcription:
            messagebox.showinfo(
                "Audio attached",
                f"Auto-transcribed:\n\n{transcription[:400]}",
            )
        else:
            messagebox.showinfo(
                "Audio attached",
                "Audio note saved. Automatic transcription is not available; "
                "a reviewer will listen to the note.",
            )
        # Re-render to show the audio chip
        self._render_wizard()

    def _step_review(self, host):
        tk.Label(
            host, text=tr("step_review", self.lang), bg="white", font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=14, pady=(14, 4))
        s = self.wizard_state

        def line(label, value):
            row = tk.Frame(host, bg="white")
            row.pack(fill="x", padx=14, pady=2)
            tk.Label(
                row,
                text=label + ":",
                bg="white",
                font=("Segoe UI", 9, "bold"),
                width=24,
                anchor="w",
            ).pack(side="left")
            tk.Label(
                row,
                text=str(value),
                bg="white",
                wraplength=400,
                justify="left",
                font=("Segoe UI", 9),
            ).pack(side="left")

        line("Language", _LANG_NAMES.get(self.lang, self.lang))
        line("Anonymous", "Yes" if s["anonymous"] else "No")
        line("On behalf of another", "Yes" if s["on_behalf_of"] else "No")
        if s["on_behalf_of"]:
            line("Relation", s.get("subject_relation") or "(unspecified)")
        line("Immediate danger", s["triage"].get("q3", "no"))
        line("Summary", (s["triage"].get("q1") or "")[:120])
        line("Attachments", len(s.get("attachments") or []))
        if s.get("audio_orig"):
            line("Audio note", os.path.basename(s["audio_orig"]))
        line("Message length", f"{len(s.get('content') or '')} chars")

    def _collect_current_step(self, validate: bool = False) -> bool:
        try:
            if self.wizard_step == 0:
                self.wizard_state["consent_disclosure"] = bool(self._cv_disclose.get())
                self.wizard_state["consent_contact"] = bool(self._cv_contact.get())
                self.wizard_state["anonymous"] = bool(self._cv_anon.get())
                self.wizard_state["on_behalf_of"] = bool(self._cv_obo.get())
                if self._cv_obo.get() and hasattr(self, "_obo_entry"):
                    self.wizard_state["subject_relation"] = self._obo_entry.get().strip()
                if hasattr(self, "_vuln_vars"):
                    self.wizard_state["vulnerability_flags"] = [
                        flag for flag, var in self._vuln_vars.items() if var.get()
                    ]
                if hasattr(self, "_loc_entry"):
                    self.wizard_state["case_location"] = self._loc_entry.get().strip()
                if hasattr(self, "_dept_entry"):
                    self.wizard_state["case_department"] = self._dept_entry.get().strip()
                if hasattr(self, "_cv_wb"):
                    self.wizard_state["whistleblowing"] = bool(self._cv_wb.get())
                if hasattr(self, "_wb_entry") and self._cv_wb.get():
                    self.wizard_state["wb_independent_reviewer"] = self._wb_entry.get().strip()
                if validate and not self._cv_disclose.get():
                    messagebox.showwarning("Consent required", tr("consent_disclose", self.lang))
                    return False
            elif self.wizard_step == 1:
                self.wizard_state["triage"] = {
                    "q1": self._tr_q1.get().strip(),
                    "q2": self._tr_q2.get().strip(),
                    "q3": self._tr_q3.get(),
                    "q4": self._tr_q4.get(),
                }
                if validate and not self.wizard_state["triage"]["q1"]:
                    messagebox.showwarning("Required", tr("triage_q1", self.lang))
                    return False
            elif self.wizard_step == 2:
                self.wizard_state["content"] = self.txt_input.get("1.0", "end").strip()
                if validate and not self.wizard_state["content"]:
                    messagebox.showwarning("Required", tr("step_details", self.lang))
                    return False
        except (tk.TclError, AttributeError):
            pass
        return True

    def _wizard_submit(self):
        if not self._collect_current_step(validate=True):
            return
        s = self.wizard_state
        text = s.get("content") or ""
        if not text:
            messagebox.showwarning("Empty", tr("step_details", self.lang))
            self.wizard_step = 2
            self._render_wizard()
            return

        # Duplicate detection
        username = self.user.get("username") or ""
        dup_id = find_duplicate(username, text)
        if dup_id and not messagebox.askyesno(
            "Possible duplicate", tr("duplicate_warn", self.lang, sid=dup_id)
        ):
            return

        matches, overall = analyse_text(text)
        # Also analyse the audio transcription if present
        if s.get("transcription"):
            tr_matches, tr_overall = analyse_text(s["transcription"])
            for cat, info in tr_matches.items():
                matches.setdefault(cat, info)
            if SEVERITY_ORDER.get(tr_overall, 0) > SEVERITY_ORDER.get(overall, 0):
                overall = tr_overall

        # Feature 12 — NLP categorisation alongside the regex matches.
        nlp_scores, nlp_overall_conf = nlp_classify(
            (text or "") + " " + (s.get("transcription") or "")
        )
        # If NLP flags a CRITICAL-tier category not already in regex matches,
        # incorporate it so it's surfaced to staff.
        for cat in nlp_scores:
            if cat not in matches:
                matches[cat] = {
                    "severity": RISK_PATTERNS.get(cat, {}).get("severity", "MEDIUM"),
                    "snippets": [f"(NLP score {nlp_scores[cat]:.2f})"],
                }
                cat_sev = matches[cat]["severity"]
                if SEVERITY_ORDER.get(cat_sev, 0) > SEVERITY_ORDER.get(overall, 0):
                    overall = cat_sev

        categories = {cat: info["snippets"] for cat, info in matches.items()}

        # Anonymous flow: issue contact token
        raw_token, token_hash = (None, None)
        if s["anonymous"]:
            raw_token, token_hash = issue_contact_token()

        # The DB row's "username" reflects who the case is *about*.
        # For anonymous submissions we strip identity; for on-behalf-of we
        # record reporter_username separately.
        store_user = dict(self.user)
        reporter_username = None
        if s["anonymous"]:
            store_user = {
                "username": "(anonymous)",
                "full_name": "(anonymous)",
                "role": self.user.get("role"),
            }
        elif s["on_behalf_of"]:
            reporter_username = self.user.get("username")

        attachments_meta = [
            {"orig_name": os.path.basename(a.get("orig") or ""), "stored": a.get("stored")}
            for a in (s.get("attachments") or [])
        ]

        sid = save_submission(
            store_user,
            text,
            overall,
            categories,
            anonymous=s["anonymous"],
            contact_token_hash=token_hash,
            on_behalf_of=s["on_behalf_of"],
            reporter_username=reporter_username,
            subject_relation=s.get("subject_relation"),
            triage=s.get("triage"),
            attachments=attachments_meta,
            audio_path=s.get("audio_stored") or None,
            transcription=s.get("transcription") or None,
            language=self.lang,
            consent_disclosure=s["consent_disclosure"],
            consent_contact=s["consent_contact"],
            duplicate_of=dup_id,
            vulnerability_flags=s.get("vulnerability_flags"),
            case_location=s.get("case_location"),
            case_department=s.get("case_department"),
            nlp_score=nlp_overall_conf,
            nlp_categories=nlp_scores,
            whistleblowing=s.get("whistleblowing", False),
            wb_independent_reviewer=s.get("wb_independent_reviewer") or None,
        )
        logger.info(
            "Safeguarding submission saved id=%s severity=%s anon=%s obo=%s dup_of=%s nlp=%.2f",
            sid,
            overall,
            s["anonymous"],
            s["on_behalf_of"],
            dup_id,
            nlp_overall_conf,
        )

        # Feature 18 — cumulative-concern check fires a back-end note so
        # the staff dashboard can highlight the pattern.
        if not s["anonymous"]:
            subj_id = canonical_subject_id(self.user, anonymous=False)
            count, escalate = cumulative_concern(subj_id)
            if escalate:
                add_case_note(
                    sid,
                    "system",
                    f"[cumulative] {count} concerns logged about this subject "
                    f"in the last {_CUMULATIVE_WINDOW_DAYS} days — review pattern.",
                )

        clear_draft(self.user.get("username") or "")

        if raw_token:
            messagebox.showwarning(
                tr("anon_token_heading", self.lang),
                tr("anon_token_body", self.lang, token=raw_token),
            )

        # Feature 13 — self-harm pathway
        if is_self_harm_case(matches, nlp_scores):
            messagebox.showwarning(
                "Immediate support",
                "Please know help is available right now.\n\n" + SUPPORT_RESOURCES,
            )
        elif overall == "CRITICAL":
            messagebox.showwarning(
                "We're here for you",
                "Thank you for reaching out. A member of the safeguarding "
                "team has been alerted.\n\n" + SUPPORT_RESOURCES,
            )
        elif overall in ("HIGH", "MEDIUM"):
            messagebox.showinfo(
                "Submitted", "Your submission has been flagged for review.\n\n" + SUPPORT_RESOURCES
            )
        else:
            messagebox.showinfo("Submitted", f"Thank you. Submission #{sid} received.")

        # Reset wizard
        self.show_student_dashboard()

    def _refresh_student_history(self):
        self.history_list.delete(0, "end")
        for sid, ts, sev, status in fetch_user_submissions(self.user.get("username") or ""):
            date = ts.split("T")[0]
            self.history_list.insert("end", f"#{sid}  {date}   {sev:<8}  {status}")

    def _open_anon_check(self):
        win = tk.Toplevel(self._host)
        win.title(tr("check_anon", self.lang))
        win.configure(bg="#f4f6fa")
        tk.Label(win, text=tr("check_anon_prompt", self.lang), bg="#f4f6fa").pack(
            padx=14, pady=(14, 4)
        )
        entry = ttk.Entry(win, width=36)
        entry.pack(padx=14, pady=4)
        out = tk.Label(win, text="", bg="#f4f6fa", justify="left", font=("Segoe UI", 9))
        out.pack(padx=14, pady=8)

        def do_lookup():
            row = lookup_by_contact_token(entry.get())
            if not row:
                out.config(text=tr("check_anon_not_found", self.lang), fg="#b00020")
                return
            sid, ts, sev, status, note = row
            msg = tr(
                "check_anon_result",
                self.lang,
                sid=sid,
                ts=ts.replace("T", " ")[:19],
                sev=sev,
                status=status,
            )
            if note:
                msg += f"\n\nReviewer note:\n{note}"
            out.config(text=msg, fg="#1f3a5f")

        ttk.Button(win, text="Check", command=do_lookup).pack(pady=(0, 12))
