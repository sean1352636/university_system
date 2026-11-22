"""Graduation office tabs: conferrals (with print jobs and certificate
verification) and holds (eligibility check, graduation holds, the name on
the certificate, graduation roles).

Every action goes through ``university/application/graduation/``, which
checks permissions itself; ``common.call`` runs each in one transaction and
shows a refusal as a dialog.

``ctx`` is the hosting window: ``who`` (graduation ``Officer``), ``root``,
``auth`` and ``refresh_all()``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.graduation import access as ga
from education_system.systems.university.application.graduation import conferral as gc
from education_system.systems.university.application.graduation import eligibility as ge
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.common import (  # noqa: E501
    Detail,
    Field,
    ask,
    call,
    confirm,
    fill,
    info,
    make_tree,
    nice,
    selected,
)

CONFERRAL_STATUSES = ("", "conferred", "suspended", "revoked", "superseded")


def _bar(parent):
    bar = ttk.Frame(parent, padding=(0, 4))
    bar.pack(side="bottom", fill="x")          # before anything that expands
    return bar


def _button(bar, text, command):
    ttk.Button(bar, text=text, command=command).pack(side="left", padx=3, pady=2)


# ═══ conferrals ═════════════════════════════════════════════════════════


class ConferralsTab(ttk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.current = None
        inner = ttk.Notebook(self)
        inner.pack(fill="both", expand=True, padx=4, pady=4)
        self._build_list(inner)
        self._build_jobs(inner)
        self._build_verify(inner)

    # ── conferrals list ──
    def _build_list(self, nb):
        page = ttk.Frame(nb)
        nb.add(page, text="  Conferrals  ")
        top = ttk.Frame(page, padding=(4, 4))
        top.pack(side="top", fill="x")
        ttk.Label(top, text="Search").pack(side="left")
        self.search = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search, width=22)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda _e: self.refresh())
        ttk.Label(top, text="Status").pack(side="left", padx=(8, 0))
        self.status = tk.StringVar()
        box = ttk.Combobox(top, textvariable=self.status, values=CONFERRAL_STATUSES, width=12,
                           state="readonly")
        box.pack(side="left", padx=4)
        box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        _button(top, "Refresh", self.refresh)
        _button(top, "Confer in absentia…", self.confer_in_absentia)
        panes = ttk.PanedWindow(page, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=4, pady=4)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        self.tree = make_tree(left, [("student_id", "Student", 90), ("name", "Name", 170),
                                     ("award", "Award", 200), ("mode", "Mode", 90),
                                     ("date", "Conferred", 90), ("status", "Status", 90)])
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show())
        self.actions = _bar(right)
        self.detail = Detail(right)
        self.detail.pack(fill="both", expand=True)
        self.detail.clear("Select a conferral.")

    def refresh(self):
        rows = call(self, gc.listing, self.ctx.who, search=self.search.get().strip() or None,
                    status=self.status.get() or None) or []
        fill(self.tree, rows, lambda r: r["conferral_id"],
             lambda r: (r["student_id"], r["certificate_name"], r["award_name"],
                        nice(r["mode"]), r["conferral_date"], r["status"]))
        if self.current and self.tree.exists(str(self.current)):
            self.tree.selection_set(str(self.current))
        else:
            self.current = None
            self.detail.clear("Select a conferral.")
            self._set_actions(None)
        self.refresh_jobs()

    def _show(self):
        cid = selected(self.tree)
        if cid is None:
            return
        rec = call(self, gc.record, self.ctx.who, int(cid))
        if rec is None:
            return
        self.current = int(cid)
        jobs = [f"#{j['job_id']} {j['kind']} {j['certificate_number']} – {j['status']} "
                f"({j['delivery']}{', fee £%.2f' % j['fee'] if j['fee'] else ''})"
                for j in rec["print_jobs"]]
        history = [f"{h['at']}  {h['actor'] or ''}  {h['action']}" for h in rec["history"]]
        self.detail.show(f"{rec['certificate_name']} — {rec['award_name']}", [
            ("Award", [("Student", rec["student_id"]), ("Classification", rec["classification"]),
                       ("Academic year", rec["academic_year"]),
                       ("Conferred", rec["conferral_date"]), ("Mode", nice(rec["mode"])),
                       ("Ceremony", rec["ceremony_id"]), ("Status", rec["status"]),
                       ("Status note", rec["status_reason"])]),
            ("Certificate", [("Number", rec["certificate_number"]),
                             ("Verification code", rec["verification_code"]),
                             ("Transcript snapshot", rec["freeze_id"]),
                             ("Replaces conferral", rec["replaces_conferral_id"])]),
            ("Print jobs", jobs), ("History", history)])
        self._set_actions(rec)

    def _set_actions(self, rec):
        for child in self.actions.winfo_children():
            child.destroy()
        if not rec:
            return
        if rec["status"] == "suspended":
            _button(self.actions, "Review after board", self.review)
        if rec["status"] in ("conferred", "suspended"):
            _button(self.actions, "Revoke…", self.revoke)
        if rec["status"] == "conferred":
            _button(self.actions, "Replacement certificate…", self.replace)

    # ── actions ──
    def confer_in_absentia(self):
        values = ask(self, "Confer in absentia", [
            Field("student_id", "Student ID", required=True),
            Field("conferral_date", "Conferral date", "date", hint="blank = today"),
            Field("delivery", "Certificate", "combo", choices=["post", "collect"],
                  required=True),
            Field("address", "Postal address", "multiline")],
            values={"delivery": "post"})
        if not values:
            return
        result = call(self, gc.confer, self.ctx.who, values["student_id"], mode="in_absentia",
                      conferral_date=values["conferral_date"] or None,
                      delivery=values["delivery"], address=values["address"] or None,
                      write=True)
        if result is None:
            return
        gc.after_commit(result)
        info(self, f"Conferred.\nCertificate {result['certificate_number']}\n"
                   f"Verification code {result['verification_code']}")
        self.current = result["conferral_id"]
        self.ctx.refresh_all()

    def review(self):
        result = call(self, gc.review_suspended, self.ctx.who, self.current, write=True)
        if result is None:
            return
        if result.get("reinstated"):
            info(self, "The award stands unchanged: the conferral is reinstated.")
        else:
            gc.after_commit(result)
            info(self, f"The award changed, so it was reissued.\nNew certificate "
                       f"{result['certificate_number']}")
            self.current = result["conferral_id"]
        self.ctx.refresh_all()

    def revoke(self):
        reason = common.ask_text(self, "Revoke award", "Reason (sent to the graduate)")
        if not reason or not confirm(self, "Revoke this award? Its certificate and digital "
                                           "credential stop verifying."):
            return
        if call(self, gc.revoke, self.ctx.who, self.current, reason, write=True) is not None:
            self.ctx.refresh_all()

    def replace(self):
        values = ask(self, "Replacement certificate", [
            Field("reason", "Reason", "multiline", required=True),
            Field("delivery", "Delivery", "combo", choices=["post", "collect"], required=True),
            Field("address", "Postal address", "multiline"),
            Field("waive_fee", f"Waive the £{gc.REPLACEMENT_FEE:.2f} fee", "check")],
            values={"delivery": "post"})
        if not values:
            return
        result = call(self, gc.replace_certificate, self.ctx.who, self.current,
                      values["reason"], delivery=values["delivery"],
                      address=values["address"] or None, waive_fee=values["waive_fee"],
                      write=True)
        if result is None:
            return
        gc.charge_replacement_fee(result, self.ctx.who.username)
        info(self, f"New certificate {result['certificate_number']}"
                   + (f"; £{result['fee']:.2f} charged" if result["fee"] else "; fee waived"))
        self.ctx.refresh_all()

    # ── print jobs ──
    def _build_jobs(self, nb):
        page = ttk.Frame(nb)
        nb.add(page, text="  Print jobs  ")
        top = ttk.Frame(page, padding=4)
        top.pack(side="top", fill="x")
        ttk.Label(top, text="Status").pack(side="left")
        self.job_status = tk.StringVar()
        box = ttk.Combobox(top, textvariable=self.job_status, values=("", *gc.JOB_STATUSES),
                           width=12, state="readonly")
        box.pack(side="left", padx=4)
        box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_jobs())
        _button(top, "Refresh", self.refresh_jobs)
        self.job_bar = _bar(page)
        self.jobs = make_tree(page, [("job", "Job", 50), ("kind", "Kind", 90),
                                     ("student", "Student", 90), ("name", "Name", 170),
                                     ("cert", "Certificate", 150), ("delivery", "Delivery", 80),
                                     ("fee", "Fee", 60), ("status", "Status", 90),
                                     ("created", "Created", 140)])
        self.jobs.bind("<<TreeviewSelect>>", lambda _e: self._job_actions())
        self._job_rows = {}

    def refresh_jobs(self):
        rows = call(self, gc.print_jobs, self.job_status.get() or None) or []
        self._job_rows = {str(r["job_id"]): r for r in rows}
        fill(self.jobs, rows, lambda r: r["job_id"],
             lambda r: (r["job_id"], r["kind"], r["student_id"], r.get("certificate_name"),
                        r["certificate_number"], r["delivery"],
                        f"£{r['fee']:.2f}" if r["fee"] else "", r["status"], r["created_at"]))
        self._job_actions()

    def _job_actions(self):
        for child in self.job_bar.winfo_children():
            child.destroy()
        jid = selected(self.jobs)
        job = self._job_rows.get(jid) if jid else None
        if not job:
            ttk.Label(self.job_bar, text="Select a job to move it on.").pack(side="left")
            return
        ttk.Label(self.job_bar, text=f"Job {jid} ({job['status']}) → ").pack(side="left")
        for status in sorted(gc._JOB_NEXT.get(job["status"], ())):
            _button(self.job_bar, status.capitalize(),
                    lambda s=status, j=job: self._move_job(j, s))

    def _move_job(self, job, status):
        note = ""
        if status in ("failed", "cancelled"):
            note = common.ask_text(self, "Print job", "Why?", multiline=False)
            if note is None:
                return
        if call(self, gc.set_job_status, self.ctx.who, job["job_id"], status, note,
                write=True) is not None:
            self.refresh_jobs()

    # ── verification ──
    def _build_verify(self, nb):
        page = ttk.Frame(nb, padding=10)
        nb.add(page, text="  Verify a certificate  ")
        row = ttk.Frame(page)
        row.pack(side="top", fill="x")
        ttk.Label(row, text="Certificate number or verification code").pack(side="left")
        self.ref = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.ref, width=36)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self.verify())
        _button(row, "Check", self.verify)
        ttk.Label(page, text="This shows exactly what an employer sees.",
                  foreground="#555555").pack(side="top", anchor="w", pady=(4, 6))
        self.verify_detail = Detail(page)
        self.verify_detail.pack(fill="both", expand=True)

    def verify(self):
        result = call(self, gc.verify, self.ref.get().strip())
        if result is None:
            return
        pairs = [("Result", result["message"], "" if result["valid"] else "bad")]
        if "name" in result:
            pairs += [("Name", result["name"]), ("Award", result["award"]),
                      ("Classification", result["classification"]),
                      ("Conferred", result["conferral_date"]),
                      ("In absentia", "yes" if result["in_absentia"] else "no")]
        self.verify_detail.show("Valid" if result["valid"] else "Not valid", [("", pairs)])


def build_conferrals_tab(notebook, ctx, text="  Conferrals  "):
    tab = ConferralsTab(notebook, ctx)
    notebook.add(tab, text=text)
    tab.refresh()
    return tab


# ═══ holds, eligibility, names, roles ═══════════════════════════════════


class HoldsTab(ttk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        inner = ttk.Notebook(self)
        inner.pack(fill="both", expand=True, padx=4, pady=4)
        self._build_check(inner)
        self._build_holds(inner)
        self._build_roles(inner)

    # ── eligibility check + certificate name ──
    def _build_check(self, nb):
        page = ttk.Frame(nb, padding=8)
        nb.add(page, text="  Eligibility  ")
        row = ttk.Frame(page)
        row.pack(side="top", fill="x")
        ttk.Label(row, text="Student ID").pack(side="left")
        self.sid = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.sid, width=16)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self.check())
        _button(row, "Check", self.check)
        _button(row, "Place hold…", lambda: self.place_hold(self.sid.get().strip()))
        _button(row, "Set certificate name…", self.set_name)
        self.check_detail = Detail(page)
        self.check_detail.pack(fill="both", expand=True, pady=(6, 0))
        self.check_detail.clear("Enter a student ID and press Check.")

    def check(self):
        sid = self.sid.get().strip()
        if not sid:
            return
        r = call(self, ge.check, sid)
        if r is None:
            return
        award = r["award"] or {}
        conf = r["conferral"] or {}
        self.check_detail.show(
            f"{r['student_name']} ({sid}) — " + ("eligible" if r["eligible"] else "not eligible"),
            [("Award", [("Award", award.get("award_name") or "none released"),
                        ("Classification", award.get("classification")),
                        ("Ratified", award.get("ratified_at"))]),
             ("Blocking", [(str(n), b, "bad") for n, b in enumerate(r["blockers"], 1)] or
              ["Nothing blocks graduation."]),
             ("Warnings (not blocking)", [(str(n), w, "warn")
                                          for n, w in enumerate(r["warnings"], 1)] or ["None."]),
             ("Credits (advisory)", [("Recorded", f"{r['credits_earned']:.0f}"),
                                     ("Programme rule", f"{r['credits_required']} — "
                                                        f"{r['credits_source']}")]),
             ("Certificate name", [("Name", r["certificate_name"]),
                                   ("Confirmed", "yes" if r["name_confirmed"] else "no")]),
             ("Conferral", [("Status", conf.get("status") or "not conferred"),
                            ("Certificate", conf.get("certificate_number"))])])

    def set_name(self):
        sid = self.sid.get().strip()
        values = ask(self, "Name on the certificate", [
            Field("student_id", "Student ID", required=True),
            Field("name", "Certificate name", required=True),
            Field("evidence", "Evidence seen", required=True,
                  hint="e.g. deed poll, passport")], values={"student_id": sid})
        if values and call(self, ge.set_name, self.ctx.who, values["student_id"],
                           values["name"], values["evidence"], write=True) is not None:
            self.sid.set(values["student_id"])
            self.check()

    # ── holds ──
    def _build_holds(self, nb):
        page = ttk.Frame(nb, padding=4)
        nb.add(page, text="  Holds  ")
        bar = _bar(page)
        _button(bar, "Refresh", self.refresh)
        _button(bar, "Place hold…", lambda: self.place_hold(""))
        _button(bar, "Release selected…", self.release)
        self.holds = make_tree(page, [("student", "Student", 90), ("kind", "Kind", 90),
                                      ("reason", "Reason", 380), ("by", "Placed by", 110),
                                      ("at", "Placed", 140)])

    def refresh(self):
        rows = call(self, ge.all_open_holds) or []
        fill(self.holds, rows, lambda r: r["hold_id"],
             lambda r: (r["student_id"], r["kind"], r["reason"], r["placed_by"],
                        r["placed_at"]))
        self.refresh_roles()

    def place_hold(self, sid):
        values = ask(self, "Place a graduation hold", [
            Field("student_id", "Student ID", required=True),
            Field("kind", "Kind", "combo", choices=list(ge.HOLD_KINDS), required=True),
            Field("reason", "Reason", "multiline", required=True)],
            values={"student_id": sid, "kind": "appeal"})
        if values and call(self, ge.place_hold, self.ctx.who, values["student_id"],
                           values["kind"], values["reason"], write=True) is not None:
            self.ctx.refresh_all()

    def release(self):
        hid = selected(self.holds)
        if hid is None:
            info(self, "Select a hold first.")
            return
        note = common.ask_text(self, "Release hold", "Why is it released?")
        if note and call(self, ge.release_hold, self.ctx.who, int(hid), note,
                         write=True) is not None:
            self.ctx.refresh_all()

    # ── roles ──
    def _build_roles(self, nb):
        page = ttk.Frame(nb, padding=4)
        nb.add(page, text="  Graduation roles  ")
        ttk.Label(page, text="Admins and registrars run graduation. Graduation office staff "
                             "can do everything; ceremony staff can only check graduands in.",
                  foreground="#555555", wraplength=900).pack(side="top", anchor="w")
        bar = _bar(page)
        _button(bar, "Give a role…", self.grant)
        _button(bar, "Remove selected role", self.revoke)
        self.roles = make_tree(page, [("username", "Username", 140),
                                      ("name", "Name", 200), ("role", "Role", 150),
                                      ("by", "Granted by", 120), ("at", "Granted", 150)])

    def refresh_roles(self):
        rows = call(self, ga.roles, quiet=True) or []
        names = call(self, lambda conn: {r["username"]: ga.person_name(conn, r["username"])
                                         for r in rows}, quiet=True) or {}
        fill(self.roles, rows, lambda r: f"{r['username']}|{r['role']}",
             lambda r: (r["username"], names.get(r["username"]), ga.ROLES.get(r["role"]),
                        r["granted_by"], r["granted_at"]))

    def grant(self):
        values = ask(self, "Give a graduation role", [
            Field("username", "Member of staff", "staff", common.staff_choices(self),
                  required=True),
            Field("role", "Role", "combo", list(ga.ROLES.items()), required=True)])
        if values and call(self, ga.grant_role, self.ctx.who, values["username"],
                           values["role"], write=True) is not None:
            self.refresh_roles()

    def revoke(self):
        key = selected(self.roles)
        if key is None:
            info(self, "Select a role first.")
            return
        username, role = key.split("|", 1)
        if confirm(self, f"Remove {ga.ROLES.get(role, role)} from {username}?") and call(
                self, ga.revoke_role, self.ctx.who, username, role, write=True) is not None:
            self.refresh_roles()


def build_holds_tab(notebook, ctx, text="  Holds & Eligibility  "):
    tab = HoldsTab(notebook, ctx)
    notebook.add(tab, text=text)
    tab.refresh()
    return tab
