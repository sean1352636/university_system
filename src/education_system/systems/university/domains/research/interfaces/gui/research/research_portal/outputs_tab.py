"""Research outputs: the record, its authors in order and its REF
open-access status. Rules are in ``university/application/research/outputs``."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.research import outputs as ro
from education_system.systems.university.application.research import projects as rp
from education_system.systems.university.application.research import ref as rr
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.common import (  # noqa: E501
    Field,
    nice,
)

OA_EXPLAINED = {
    "compliant": "Deposited within three months of acceptance (or gold open access).",
    "exception": "An open-access exception is recorded.",
    "not in scope": "Only journal articles and conference papers with an ISSN are in scope.",
    "no acceptance date": "Record the acceptance date so the deposit deadline can be checked.",
    "not deposited": "Not deposited and the three-month deadline has passed.",
    "late deposit": "Deposited more than three months after acceptance.",
}


class OutputsTab(common.RecordTab):
    columns = [("title", "Title", 260), ("type", "Type", 110), ("date", "Published", 85),
               ("uoa", "UoA", 65), ("oa", "Open access", 130)]

    def __init__(self, parent, portal):
        self.mine = tk.BooleanVar(value=False)
        self.oa_only = tk.BooleanVar(value=False)
        super().__init__(parent, portal)

    def new_actions(self):
        return [("New output", self.on_new)]

    def extra_toolbar(self, bar):
        ttk.Checkbutton(bar, text="Mine only", variable=self.mine,
                        command=self.refresh).pack(side="left", padx=6)
        ttk.Checkbutton(bar, text="Open-access problems", variable=self.oa_only,
                        command=self.refresh).pack(side="left", padx=6)

    def load(self, conn, search, status):
        rows = ro.oa_problems(conn, self.who) if self.oa_only.get() else \
            ro.listing(conn, self.who, search=search, mine=self.mine.get())
        if self.oa_only.get():
            mine = {r["publication_id"] for r in ro.listing(conn, self.who, mine=True)} \
                if self.mine.get() else None
            needle = (search or "").lower()
            rows = [r for r in rows if (mine is None or r["publication_id"] in mine)
                    and (not needle or needle in r["title"].lower())]
        return rows

    def row_id(self, row):
        return row["publication_id"]

    def values(self, row):
        return (row["title"], row.get("publication_type"), row.get("publication_date") or "",
                row.get("uoa") or "", row["oa_status"])

    def fetch(self, conn, record_id):
        return ro.record(conn, self.who, int(record_id))

    def render(self, o):
        authors = [f"{a['position']}. {a['name']}" + (f" [{a['username']}]" if a["username"]
                                                       else "") for a in o["authors_list"]]
        status = o["oa_status"]
        tag = "" if ro.oa_ok(o) else "bad"
        explain = OA_EXPLAINED.get(status, "Deposit it before the deadline.")
        self.detail.show(o["title"], [
            ("Authors", authors),
            ("Output", [("Type", o.get("publication_type")), ("Venue", o.get("venue")
                                                              or o.get("journal_name")),
                        ("DOI", o.get("doi")), ("ISSN", o.get("issn")), ("URL", o.get("url")),
                        ("Project", o.get("project_id")), ("Unit of assessment", o.get("uoa")),
                        ("Peer reviewed", "yes" if o.get("is_peer_reviewed") else "no"),
                        ("Agreed REF rating", o.get("quality_rating")),
                        ("Selected for REF", "yes" if o.get("ref_submitted") else "no")]),
            ("Dates", [("Accepted", o.get("acceptance_date")),
                       ("Published", o.get("publication_date")),
                       ("Deposited", o.get("deposit_date"))]),
            ("Open access", [("Status", status, tag), ("", explain),
                             ("Route", o.get("oa_route")), ("Exception", o.get("oa_exception")),
                             ("Repository", o.get("repository_url"))]),
            ("Abstract", o.get("abstract") or "—"),
            ("History", [f"{h['at']}  {h['actor'] or ''}  {nice(h['action'])}"
                         for h in o["history"]]),
        ])

    def actions(self, o):
        acts = []
        if o["can_edit"]:
            acts.append(("Edit", self.on_edit))
        if self.who.is_office:
            acts.append(("Remove", self.on_remove))
        return acts

    def _fields(self):
        projects = common.call(self, rp.choices, self.who, quiet=True) or []
        return [Field("title", "Title", required=True),
                Field("publication_type", "Type", "combo", list(ro.TYPES), required=True),
                Field("authors", "Authors", "multiline", required=True,
                      hint="one per line; staff as Name [username]"),
                Field("venue", "Journal / venue"), Field("doi", "DOI"),
                Field("issn", "ISSN"), Field("url", "URL"),
                Field("acceptance_date", "Accepted", "date"),
                Field("publication_date", "Published", "date"),
                Field("deposit_date", "Deposited in repository", "date"),
                Field("repository_url", "Repository link"),
                Field("oa_route", "Open-access route", "combo", ["", *ro.OA_ROUTES]),
                Field("oa_exception", "Open-access exception", "combo",
                      ["", *ro.OA_EXCEPTIONS]),
                Field("uoa", "Unit of assessment", "combo", ["", *rr.UOAS]),
                Field("project_id", "Project", "combo", [("", "(none)"), *projects]),
                Field("is_peer_reviewed", "Peer reviewed", "check"),
                Field("abstract", "Abstract", "multiline")]

    def on_new(self):
        me = f"{common.call(self, _name, self.who.username, quiet=True) or ''} " \
             f"[{self.who.username}]"
        data = common.ask(self, "New output", self._fields(),
                          {"authors": me.strip(), "publication_type": "Journal article"},
                          columns=2)
        if data:
            authors = data.pop("authors")
            pid = common.call(self, ro.create, self.who, _blank(data), _lines(authors),
                              write=True)
            if pid is not None:
                self.open_record(pid)
                self.portal.changed()

    def on_edit(self):
        o = self.record
        values = dict(o, authors="\n".join(
            a["name"] + (f" [{a['username']}]" if a["username"] else "")
            for a in o["authors_list"]))
        data = common.ask(self, "Edit output", self._fields(), values, columns=2)
        if data:
            authors = data.pop("authors")
            self.write(ro.update, self.who, o["publication_id"], _blank(data, keep=True),
                       _lines(authors))

    def on_remove(self):
        reason = common.ask_text(self, "Remove output", "Reason (kept in the audit log)")
        if reason:
            self.write(ro.remove, self.who, self.record["publication_id"], reason)
            self.current_id = None
            self.refresh()


def _name(conn, username):
    from education_system.systems.university.application.research import access as ra
    return ra.person_name(conn, username)


def _lines(text):
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def _blank(data, keep=False):
    out = {}
    for key, value in data.items():
        if value in ("", None):
            if keep:
                out[key] = None
            continue
        out[key] = value
    return out
