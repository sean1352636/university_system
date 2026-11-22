"""People: the researcher directory, profiles, and (for the office) who
holds which research role."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.research import access as ra
from education_system.systems.university.application.research import projects as rp
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.common import (  # noqa: E501
    Field,
)


class PeopleTab(ttk.Frame):
    def __init__(self, parent, portal):
        super().__init__(parent)
        self.portal = portal
        self.who = portal.who
        self.manager = self.who.is_admin or self.who.is_office
        self.current = None
        book = ttk.Notebook(self)
        book.pack(fill="both", expand=True, padx=4, pady=4)
        book.add(self._directory(book), text="  Directory  ")
        if self.manager:
            book.add(self._roles(book), text="  Research roles  ")

    # ── directory ──
    def _directory(self, book):
        frame = ttk.Frame(book)
        top = ttk.Frame(frame, padding=(4, 4))
        top.pack(side="top", fill="x")
        ttk.Label(top, text="Search").pack(side="left")
        self.query = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.query, width=26)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(top, text="My profile", command=lambda: self._show(self.who.username)).pack(
            side="left", padx=4)
        panes = ttk.PanedWindow(frame, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=4)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        self.tree = common.make_tree(left, [("name", "Name", 170), ("department", "Department",
                                                                     130),
                                            ("uoa", "UoA", 60), ("orcid", "ORCID", 140)])
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._selected())
        bar = ttk.Frame(right, padding=(0, 4))
        bar.pack(side="bottom", fill="x")
        self.edit_button = ttk.Button(bar, text="Edit profile", command=self._edit)
        self.edit_button.pack(side="left", padx=3)
        self.detail = common.Detail(right)
        self.detail.pack(fill="both", expand=True)
        self.detail.clear("Select someone on the left.")
        return frame

    def refresh(self):
        rows = common.call(self, rp.directory, self.query.get().strip() or None) or []
        common.fill(self.tree, rows, lambda r: r["username"], lambda r: (
            r["name"] or r["username"], r.get("department"), r.get("uoa"), r.get("orcid_id")))
        if self.manager:
            self._refresh_roles()

    def _selected(self):
        username = common.selected(self.tree)
        if username:
            self._show(username)

    def _show(self, username):
        profile = common.call(self, rp.profile, username)
        if profile is None:
            return
        self.current = profile
        self.detail.show(f"{profile['name']} ({username})", [
            ("", [("Department", profile.get("department")),
                  ("REF unit of assessment", profile.get("uoa")),
                  ("REF FTE", profile.get("ref_fte")),
                  ("Outputs", profile.get("outputs")),
                  ("Projects", profile.get("projects"))]),
            ("Research interests", profile.get("research_interests") or "—"),
            ("Identifiers", [("ORCID", profile.get("orcid_id")),
                             ("Google Scholar", profile.get("google_scholar_id")),
                             ("Scopus", profile.get("scopus_id")),
                             ("ResearchGate", profile.get("researchgate_url"))]),
        ])
        can = username == self.who.username or self.who.is_office
        self.edit_button.configure(state="normal" if can else "disabled")

    def _edit(self):
        if not self.current:
            self._show(self.who.username)
        if not self.current:
            return
        username = self.current["user_id"]
        data = common.ask(self, "Research profile", [
            Field("research_interests", "Research interests", "multiline"),
            Field("orcid_id", "ORCID iD", hint="0000-0000-0000-0000"),
            Field("google_scholar_id", "Google Scholar id"),
            Field("scopus_id", "Scopus author id"),
            Field("researchgate_url", "ResearchGate URL")], self.current)
        if data is None:
            return
        if common.call(self, rp.save_profile, self.who, username, data, write=True) is not None:
            self.refresh()
            self._show(username)

    # ── research roles ──
    def _roles(self, book):
        frame = ttk.Frame(book, padding=4)
        bar = ttk.Frame(frame, padding=(0, 4))
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Give a role", command=self._grant).pack(side="left", padx=3)
        ttk.Button(bar, text="Remove selected role", command=self._revoke).pack(side="left",
                                                                               padx=3)
        ttk.Label(frame, text="Heads of department need the department as scope; a REF lead's "
                              "scope is a UoA (e.g. UoA 11) or blank for all.",
                  foreground="#555555").pack(side="top", anchor="w")
        self.roles_tree = common.make_tree(frame, [("username", "Username", 140),
                                                   ("name", "Name", 180),
                                                   ("role", "Role", 170), ("scope", "Scope", 140),
                                                   ("granted", "Given by / on", 200)])
        self._role_rows = {}
        return frame

    def _refresh_roles(self):
        rows = common.call(self, _roles_named, quiet=True) or []
        self._role_rows = {str(n): r for n, r in enumerate(rows)}
        common.fill(self.roles_tree, list(self._role_rows.items()), lambda p: p[0], lambda p: (
            p[1]["username"], p[1]["name"], ra.ROLES.get(p[1]["role"], p[1]["role"]),
            p[1]["scope"], f"{p[1].get('granted_by') or ''} {p[1]['granted_at'][:10]}"))

    def _grant(self):
        data = common.ask(self, "Give a research role", [
            Field("username", "Member of staff", "staff", common.staff_choices(self),
                  required=True),
            Field("role", "Role", "combo", list(ra.ROLES.items()), required=True),
            Field("scope", "Scope", hint="department or UoA")])
        if data is None:
            return
        if common.call(self, ra.grant_role, self.who, data["username"], data["role"],
                       data["scope"], write=True) is not None:
            self._refresh_roles()

    def _revoke(self):
        row = self._role_rows.get(common.selected(self.roles_tree) or "")
        if not row:
            common.info(self, "Select a role first.")
            return
        if not common.confirm(self, f"Remove {ra.ROLES.get(row['role'], row['role'])} from "
                                    f"{row['username']}?"):
            return
        if common.call(self, ra.revoke_role, self.who, row["username"], row["role"],
                       row["scope"], write=True) is not None:
            self._refresh_roles()


def _roles_named(conn):
    rows = ra.roles(conn)
    for row in rows:
        row["name"] = ra.person_name(conn, row["username"])
    return rows
