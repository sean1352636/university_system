"""Alumni records, self-service, directory, newsletters and roles screens.

Every screen works through ``university/application/alumni/``, which
checks permissions again; ``self.who`` is the signed-in
:class:`~education_system.systems.university.application.alumni.access.AlumniUser`.
Writes go through ``infrastructure.ui.record_screens.call`` (one transaction, refusals
shown as dialogs, returned e-mails sent after the commit).
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, ttk

from education_system.systems.university.infrastructure.ui import record_screens as common


def _rules(name):
    import importlib
    return importlib.import_module(f"education_system.systems.university.application.alumni.{name}")


def _title(parent, text, subtitle=""):
    ttk.Label(parent, text=text, font=("Arial", 16, "bold")).pack(anchor="w", padx=16,
                                                                  pady=(10, 2))
    if subtitle:
        ttk.Label(parent, text=subtitle, foreground="#555555", wraplength=900,
                  justify="left").pack(anchor="w", padx=16, pady=(0, 8))


def _bar(parent):
    """A button bar pinned to the bottom (packed before anything expands)."""
    bar = ttk.Frame(parent, padding=(16, 6))
    bar.pack(side="bottom", fill="x")
    return bar


def _btn(bar, text, command):
    ttk.Button(bar, text=text, command=command).pack(side="left", padx=3)


def _flags(row) -> str:
    flags = []
    if row.get("anonymised_at"):
        flags.append("erased")
    if row.get("deceased_at"):
        flags.append("deceased")
    if row.get("do_not_contact"):
        flags.append("do not contact")
    if row.get("email_bounced"):
        flags.append("bounced")
    return ", ".join(flags)


def _consent(row) -> str:
    value = row.get("marketing_consent")
    return "not asked" if value is None else ("yes" if value else "no")


class AlumniOfficeRecordsMixin:
    """Mixed into ``AlumniGUIApp``."""

    # ── helpers ──
    def _call(self, fn, *args, write=False, **kwargs):
        return common.call(self.root, fn, *args, write=write, **kwargs)

    def _fresh(self, title, subtitle=""):
        self.clear_content()
        self.update_status(title)
        _title(self.content_frame, title, subtitle)

    # ── office: alumni records ─────────────────────────────────────────
    def show_alumni_records(self):
        self._fresh("Alumni records", "Every graduate's record, consent and suppression flags.")
        records = _rules("records")
        top = ttk.Frame(self.content_frame, padding=(16, 0))
        top.pack(side="top", fill="x")
        search, flt = tk.StringVar(), tk.StringVar(value="")
        ttk.Label(top, text="Search").pack(side="left")
        entry = ttk.Entry(top, textvariable=search, width=24)
        entry.pack(side="left", padx=4)
        ttk.Label(top, text="Show").pack(side="left", padx=(8, 0))
        box = ttk.Combobox(top, textvariable=flt, width=14, state="readonly",
                           values=("", "consented", "not_asked", "suppressed", "deceased"))
        box.pack(side="left", padx=4)
        bar = _bar(self.content_frame)
        panes = ttk.PanedWindow(self.content_frame, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=16, pady=4)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        tree = common.make_tree(left, [("alumni_id", "Alumni id", 90), ("name", "Name", 160),
                                       ("year", "Year", 50), ("consent", "Consent", 70),
                                       ("flags", "Flags", 140)])
        detail = common.Detail(right)
        detail.pack(fill="both", expand=True)
        state = {"rows": {}}

        def refresh():
            keep = common.selected(tree)
            rows = self._call(records.listing, self.who, search.get().strip() or None,
                              flt.get() or None) or []
            state["rows"] = {r["alumni_id"]: r for r in rows}
            common.fill(tree, rows, lambda r: r["alumni_id"], lambda r: (
                r["alumni_id"], " ".join(p for p in (r.get("first_name"), r.get("last_name"))
                                         if p), r.get("graduation_year"), _consent(r),
                _flags(r)))
            if keep and keep in state["rows"]:
                tree.selection_set(keep)        # stay on the record just changed
                tree.see(keep)
            else:
                detail.clear(f"{len(rows)} alumni. Select one.")

        def show(_e=None):
            aid = common.selected(tree)
            if not aid:
                return
            rec = self._call(records.profile, self.who, aid)
            if rec is None:
                return
            steps = [f"{'✓' if s['done'] else '…'} {s['step'].replace('_', ' ')}"
                     + (f" ({s['at']})" if s["at"] else "") for s in rec.get("transition", [])]
            detail.show(rec["name"], [
                ("Record", [("Alumni id", rec["alumni_id"]), ("Graduated", rec.get(
                    "graduation_year")), ("Degree", rec.get("degree_earned")),
                    ("E-mail", rec.get("email_address")), ("Phone", rec.get("phone")),
                    ("Employer", rec.get("current_employer")), ("Job", rec.get("job_title"))]),
                ("Contact", [("Newsletter consent", _consent(rec)),
                             ("Consent source", rec.get("consent_source")),
                             ("Do not contact", "yes" if rec.get("do_not_contact") else "no"),
                             ("Deceased", rec.get("deceased_at")),
                             ("Erased", rec.get("anonymised_at")),
                             ("Graduate Outcomes survey due", rec.get(
                                 "graduate_outcomes_due"))]),
                ("Listed in directory", "yes" if rec["directory"].get("searchable") else "no"),
                ("Transition", steps or ["not started"]),
                ("History", [f"{h['at']}  {h['actor']}  {h['action']}"
                             for h in rec.get("history", [])])])

        def current():
            aid = common.selected(tree)
            if not aid:
                common.info(self.root, "Select an alumnus first.")
            return aid

        def write(fn, *args, done=None):
            if self._call(fn, *args, write=True) is not None:
                refresh()
                if done:
                    common.info(self.root, done)

        def register():
            got = common.ask(self.root, "Register an alumnus", [
                common.Field("student_id", "Student id (blank for someone with no record)"),
                common.Field("alumni_id", "Alumni id (only without a student id)"),
                common.Field("first_name", "First name"), common.Field("last_name", "Last name"),
                common.Field("email_address", "E-mail"),
                common.Field("graduation_year", "Graduation year"),
                common.Field("degree_earned", "Degree")])
            if got:
                sid = got.pop("student_id") or None
                data = {k: v for k, v in got.items() if v}
                write(records.register, self.who, sid, data, done="Alumnus registered.")

        def edit():
            aid = current()
            rec = aid and state["rows"].get(aid)
            if not rec:
                return
            got = common.ask(self.root, f"Edit {aid}", [common.Field(k, k.replace("_", " ")
                                                                     .capitalize())
                                                        for k in records.SELF_FIELDS],
                             values=rec, columns=2)
            if got:
                write(records.update_profile, self.who, aid, got)

        def consent():
            aid = current()
            if not aid:
                return
            got = common.ask(self.root, "Record newsletter consent", [
                common.Field("consent", "Consents to newsletters", "check"),
                common.Field("source", "How it was given (e.g. phone call 16/10)",
                             required=True)])
            if got:
                write(records.set_consent, self.who, aid, got["consent"], got["source"])

        def dnc():
            aid = current()
            if not aid:
                return
            got = common.ask(self.root, "Do not contact", [
                common.Field("flag", "Do not contact", "check",),
                common.Field("reason", "Reason", required=True)],
                values={"flag": True})
            if got:
                write(records.set_do_not_contact, self.who, aid, got["flag"], got["reason"])

        def deceased():
            aid = current()
            if not aid:
                return
            got = common.ask(self.root, "Record a death", [
                common.Field("date", "Date of death", "date", required=True),
                common.Field("source", "Source (e.g. letter from family)", required=True)])
            if got and common.confirm(self.root, "This stops all contact, removes them from the "
                                                 "directory, ends mentoring and cancels "
                                                 "pledges. Continue?"):
                write(records.record_deceased, self.who, aid, got["date"], got["source"])

        def export():
            aid = current()
            if aid:
                self._export(aid)

        def erase():
            aid = current()
            if not aid:
                return
            reason = common.ask_text(self.root, "Erase alumni record", "Reason (e.g. erasure "
                                                                       "request 12)")
            if reason and common.confirm(self.root, "Anonymise this record? Gift amounts stay "
                                                    "for the accounts; Gift Aid declarations "
                                                    "stay for six years after the last claim."):
                result = self._call(records.erase, self.who, aid, reason, write=True)
                if result:
                    refresh()
                    kept = result.get("gift_aid_kept_until")
                    common.info(self.root, "Record erased." + (
                        f" Gift Aid declaration kept until {kept} (HMRC)." if kept else ""))

        def bounced():
            aid = current()
            if aid and common.confirm(self.root, "Mark this e-mail address as bouncing?"):
                write(_rules("comms").mark_bounced, self.who, aid)

        entry.bind("<Return>", lambda _e: refresh())
        box.bind("<<ComboboxSelected>>", lambda _e: refresh())
        tree.bind("<<TreeviewSelect>>", show)
        ttk.Button(top, text="Refresh", command=refresh).pack(side="left", padx=4)
        ttk.Button(top, text="Register…", command=register).pack(side="left", padx=4)
        ttk.Button(top, text="Data requests", command=self.show_data_requests).pack(
            side="left", padx=4)
        ttk.Button(top, text="Complete transition…", command=self._complete_transition).pack(
            side="left", padx=4)
        for text, cmd in (("Edit profile", edit), ("Record consent", consent),
                          ("Do not contact…", dnc), ("Record death…", deceased),
                          ("Export data…", export), ("Erase…", erase),
                          ("E-mail bounced", bounced)):
            _btn(bar, text, cmd)
        refresh()

    def _export(self, alumni_id):
        data = self._call(_rules("records").export, self.who, alumni_id, write=True)
        if data is None:
            return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                            initialfile=f"alumni-{alumni_id}.json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, default=str)
            common.info(self.root, f"Saved to {path}")

    def _complete_transition(self):
        sid = common.ask_text(self.root, "Complete the alumni transition",
                              "Student id of a graduate conferred before the transition "
                              "existed", multiline=False)
        if not sid:
            return
        from education_system.systems.university.domains.learners.application.alumni_transition import (  # noqa: E501
            transition_to_alumni,
        )
        try:
            missing = transition_to_alumni(sid.strip())   # opens its own transaction
        except (ValueError, PermissionError) as exc:
            common.info(self.root, str(exc))
            return
        common.info(self.root, f"Transition recorded ({missing} step(s) were missing).")

    def show_data_requests(self):
        self._fresh("Data requests", "Open export and erasure requests from alumni.")
        records = _rules("records")
        bar = _bar(self.content_frame)
        tree = common.make_tree(self.content_frame, [
            ("id", "Request", 70), ("alumni", "Alumni id", 100), ("kind", "Kind", 80),
            ("by", "Asked by", 120), ("at", "Asked at", 150), ("note", "Note", 300)])
        rows = self._call(records.data_requests, self.who) or []
        common.fill(tree, rows, lambda r: r["request_id"], lambda r: (
            r["request_id"], r["alumni_id"], r["kind"], r["requested_by"], r["requested_at"],
            r.get("note")))
        _btn(bar, "Back to records", self.show_alumni_records)

    # ── alumnus self-service ───────────────────────────────────────────
    def _need_alumnus(self) -> bool:
        if getattr(self, "who", None) is None or not self.who.alumni_id:
            self._fresh("Alumni only", "These pages are for graduates with an alumni record.")
            return False
        return True

    def show_my_profile(self):
        if not self._need_alumnus():
            return
        records = _rules("records")
        rec = self._call(records.profile, self.who, self.who.alumni_id)
        if rec is None:
            return
        self._fresh("My profile", "What we hold about you. Other alumni only see what you "
                                  "choose under Privacy & directory listing.")
        bar = _bar(self.content_frame)
        form = ttk.Frame(self.content_frame, padding=16)
        form.pack(fill="both", expand=True)
        vars_ = {}
        for n, key in enumerate(records.SELF_FIELDS):
            r, c = divmod(n, 2)
            ttk.Label(form, text=key.replace("_", " ").capitalize()).grid(
                row=r, column=c * 2, sticky="w", padx=(0, 6), pady=3)
            vars_[key] = tk.StringVar(value=rec.get(key) or "")
            ttk.Entry(form, textvariable=vars_[key], width=38).grid(row=r, column=c * 2 + 1,
                                                                   sticky="ew", pady=3)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        def save():
            if self._call(records.update_profile, self.who, self.who.alumni_id,
                          {k: v.get() for k, v in vars_.items()}, write=True) is not None:
                common.info(self.root, "Profile saved.")
        _btn(bar, "Save", save)

    def show_privacy(self):
        if not self._need_alumnus():
            return
        records = _rules("records")
        settings = self._call(records.directory_settings, self.who.alumni_id) or {}
        self._fresh("Privacy & directory listing",
                    "You are not listed in the alumni directory until you choose to be. Your "
                    "date of birth and home address are never shown.")
        bar = _bar(self.content_frame)
        box = ttk.LabelFrame(self.content_frame, text="What other alumni can see", padding=16)
        box.pack(fill="x", padx=16, pady=8)
        labels = {"searchable": "List me in the alumni directory",
                  "show_contact_info": "Show my e-mail, phone and LinkedIn",
                  "show_employment": "Show my employer, job and industry",
                  "show_education": "Show my degree",
                  "networking_available": "I'm open to networking requests",
                  "mentor_available": "I'm open to mentoring"}
        vars_ = {}
        for key in records.DIRECTORY_SETTINGS:
            vars_[key] = tk.BooleanVar(value=bool(settings.get(key)))
            ttk.Checkbutton(box, text=labels[key], variable=vars_[key]).pack(anchor="w", pady=3)
        if not settings.get("saved"):
            ttk.Label(box, text="You haven't chosen yet, so you are not listed.",
                      foreground="#b0620a").pack(anchor="w", pady=(8, 0))

        def save():
            if self._call(records.save_directory_settings, self.who, self.who.alumni_id,
                          {k: v.get() for k, v in vars_.items()}, write=True) is not None:
                common.info(self.root, "Your directory settings are saved.")
        _btn(bar, "Save", save)

    def show_keep_in_touch(self):
        if not self._need_alumnus():
            return
        records = _rules("records")
        rec = self._call(records.profile, self.who, self.who.alumni_id)
        if rec is None:
            return
        self._fresh("Keep in touch", "Choose whether we may send you alumni newsletters. You "
                                     "can change this at any time, or use the unsubscribe link "
                                     "in any newsletter.")
        bar = _bar(self.content_frame)
        ttk.Label(self.content_frame, text=f"Newsletters: {_consent(rec)}",
                  font=("Arial", 12)).pack(anchor="w", padx=16, pady=8)

        def choose(value):
            if self._call(records.set_consent, self.who, self.who.alumni_id, value,
                          write=True) is not None:
                self.show_keep_in_touch()
        _btn(bar, "Yes, send me newsletters", lambda: choose(True))
        _btn(bar, "No newsletters", lambda: choose(False))

    def show_my_data(self):
        if not self._need_alumnus():
            return
        self._fresh("My data", "Download everything we hold about you, or ask us to erase "
                               "your alumni record. Gift records needed for the accounts and "
                               "Gift Aid (six years) are kept in anonymised form.")
        bar = _bar(self.content_frame)

        def erase():
            note = common.ask_text(self.root, "Ask for erasure", "Anything we should know? "
                                                                 "(optional)", required=False)
            if note is not None and self._call(_rules("records").request_erasure,
                                               self.who, self.who.alumni_id, note,
                                               write=True) is not None:
                common.info(self.root, "Your request has gone to the alumni office.")
        _btn(bar, "Download my data…", lambda: self._export(self.who.alumni_id))
        _btn(bar, "Ask for my record to be erased…", erase)

    # ── directory ──────────────────────────────────────────────────────
    def show_directory(self):
        self._fresh("Alumni directory", "Only alumni who chose to be listed appear, showing "
                                        "only what they chose to show. Skills are searched "
                                        "only where an alumnus shows their employment, and a "
                                        "town only where they show their contact details.")
        records = _rules("records")
        top = ttk.Frame(self.content_frame, padding=(16, 0))
        top.pack(side="top", fill="x")
        fields = {}
        for key, label, width in (("name", "Name", 16), ("year", "Year", 6),
                                  ("industry", "Industry", 12), ("skills", "Skills", 16),
                                  ("location", "Town or country", 14)):
            ttk.Label(top, text=label).pack(side="left")
            fields[key] = tk.StringVar()
            ttk.Entry(top, textvariable=fields[key], width=width).pack(side="left", padx=(2, 8))
        tree = common.make_tree(self.content_frame, [
            ("name", "Name", 160), ("year", "Year", 50), ("degree", "Degree", 140),
            ("employer", "Employer", 140), ("job", "Job", 120), ("skills", "Skills", 150),
            ("where", "Location", 120), ("email", "E-mail", 160), ("phone", "Phone", 100),
            ("linkedin", "LinkedIn", 140)])

        def search():
            year = fields["year"].get().strip()
            if year and not year.isdigit():
                common.info(self.root, "Year must be a number")
                return
            rows = self._call(records.search_directory, self.who,
                              fields["name"].get().strip() or None, int(year) if year else None,
                              fields["industry"].get().strip() or None, None,
                              skills=fields["skills"].get().strip() or None,
                              location=fields["location"].get().strip() or None) or []
            common.fill(tree, rows, lambda r: r["alumni_id"], lambda r: (
                r["name"], r.get("graduation_year"), r.get("degree_earned"),
                r.get("current_employer"), r.get("job_title"), r.get("skills"),
                ", ".join(p for p in (r.get("city"), r.get("country")) if p),
                r.get("email_address"), r.get("phone"), r.get("linkedin_url")))
            self.update_status(f"{len(rows)} listed alumni found")
        ttk.Button(top, text="Search", command=search).pack(side="left")
        search()

    # Older screens call these names.
    def show_alumni_directory(self):
        self.show_directory()

    def show_directory_settings(self):
        self.show_privacy()

    # ── office: newsletters ────────────────────────────────────────────
    def show_newsletters(self):
        self._fresh("Newsletters", "Sent only to alumni who said yes and are not suppressed; "
                                   "each e-mail has its own unsubscribe link.")
        comms = _rules("comms")
        bar = _bar(self.content_frame)
        panes = ttk.PanedWindow(self.content_frame, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=16, pady=4)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        tree = common.make_tree(left, [("id", "#", 40), ("title", "Title", 200),
                                       ("status", "Status", 70), ("sent", "Sent", 50),
                                       ("supp", "Suppressed", 80)])
        detail = common.Detail(right)
        detail.pack(fill="both", expand=True)
        state = {"rows": {}}

        def refresh():
            rows = self._call(comms.newsletters) or []
            state["rows"] = {str(r["newsletter_id"]): r for r in rows}
            common.fill(tree, rows, lambda r: r["newsletter_id"], lambda r: (
                r["newsletter_id"], r.get("title"), r.get("status"), r.get("sent_count"),
                r.get("suppressed_count")))

        def show(_e=None):
            nid = common.selected(tree)
            row = state["rows"].get(str(nid)) if nid else None
            if not row:
                return
            audience = json.loads(row.get("audience_json") or "{}")
            outcomes = self._call(comms.deliveries, int(nid)) or []
            detail.show(row.get("title") or "", [
                ("", [("Status", row.get("status")), ("Sent", row.get("sent_at")),
                      ("Sent by", row.get("sent_by")),
                      ("Audience", ", ".join(f"{k}={v}" for k, v in audience.items())
                       or "all consenting alumni")]),
                ("Content", row.get("content") or ""),
                ("Deliveries", [f"{d['alumni_id']}: {d['outcome']}" for d in outcomes])])

        audience_fields = [common.Field("year_from", "Graduated from year"),
                           common.Field("year_to", "Graduated to year"),
                           common.Field("degree_contains", "Degree contains"),
                           common.Field("country", "Country"),
                           common.Field("chapter_id", "Chapter id"),
                           common.Field("donors_only", "Donors only", "check")]

        def preview_text(audience):
            p = self._call(comms.preview, self.who, audience)
            if p is None:
                return None
            lines = [f"Matching alumni: {p['matching']}", f"Will be sent: {p['will_send']}"]
            lines += [f"Not sent – {k}: {v}" for k, v in p["suppressed"].items()]
            return "\n".join(lines)

        def new():
            got = common.ask(self.root, "New newsletter", [
                common.Field("title", "Title", required=True),
                common.Field("content", "Content", "multiline", required=True),
                *audience_fields])
            if not got:
                return
            audience = {f.key: got[f.key] for f in audience_fields if got.get(f.key)}
            text = preview_text(audience)
            if text is None:
                return
            if common.confirm(self.root, f"{text}\n\nSave this newsletter as a draft?"):
                if self._call(comms.create, self.who, got["title"], got["content"], audience,
                              write=True) is not None:
                    refresh()

        def send():
            nid = common.selected(tree)
            row = state["rows"].get(str(nid)) if nid else None
            if not row:
                common.info(self.root, "Select a draft newsletter.")
                return
            text = preview_text(json.loads(row.get("audience_json") or "{}"))
            if text is None or not common.confirm(self.root, f"{text}\n\nSend now?"):
                return
            result = self._call(comms.send, self.who, int(nid), write=True)
            if result:
                refresh()
                common.info(self.root, f"Sent to {result['sent']}; {result['suppressed']} not "
                                       "sent (no consent or suppressed).")
        tree.bind("<<TreeviewSelect>>", show)
        _btn(bar, "New newsletter…", new)
        _btn(bar, "Send…", send)
        _btn(bar, "Refresh", refresh)
        refresh()

    # Older menu name.
    def show_create_newsletter(self):
        self.show_newsletters()

    # ── office: roles and audit ────────────────────────────────────────
    def show_roles_audit(self):
        self._fresh("Roles & audit", "Who runs which part of the alumni system, and every "
                                     "change made.")
        access = _rules("access")
        bar = _bar(self.content_frame)
        ttk.Label(self.content_frame, text="Roles", font=("Arial", 11, "bold")).pack(
            anchor="w", padx=16)
        roles_tree = common.make_tree(self.content_frame, [
            ("user", "Username", 140), ("role", "Role", 180), ("by", "Granted by", 120),
            ("at", "Granted at", 160)], height=6)
        ttk.Label(self.content_frame, text="Audit log", font=("Arial", 11, "bold")).pack(
            anchor="w", padx=16, pady=(8, 0))
        audit_tree = common.make_tree(self.content_frame, [
            ("at", "When", 150), ("actor", "Who", 110), ("entity", "What", 110),
            ("id", "Id", 100), ("action", "Action", 140), ("detail", "Detail", 300)], height=10)

        def refresh():
            rows = self._call(access.roles) or []
            common.fill(roles_tree, rows, lambda r: f"{r['username']}|{r['role']}", lambda r: (
                r["username"], access.ROLES.get(r["role"], r["role"]), r.get("granted_by"),
                r.get("granted_at")))
            log = self._call(access.recent_audit, self.who) or []
            common.fill(audit_tree, log, lambda r: r["audit_id"], lambda r: (
                r["at"], r.get("actor"), r["entity"], r["entity_id"], r["action"],
                (r.get("detail") or "")[:200]))

        def grant():
            got = common.ask(self.root, "Give a role", [
                common.Field("username", "Member of staff", "staff",
                             common.staff_choices(self.root), required=True),
                common.Field("role", "Role", "combo", list(access.ROLES.items()),
                             required=True)])
            if got and self._call(access.grant_role, self.who, got["username"], got["role"],
                                  write=True) is not None:
                refresh()

        def revoke():
            key = common.selected(roles_tree)
            if not key:
                common.info(self.root, "Select a role to remove.")
                return
            username, role = key.split("|", 1)
            if common.confirm(self.root, f"Remove {role} from {username}?") and self._call(
                    access.revoke_role, self.who, username, role, write=True) is not None:
                refresh()
        _btn(bar, "Give a role…", grant)
        _btn(bar, "Remove selected role", revoke)
        _btn(bar, "Refresh", refresh)
        refresh()
