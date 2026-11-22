"""Background Checker CLI — the text twin of the Background Checker window.

Same tables (``bgcheck_*`` in student_records.db), same risk score, same
audit log and the same three tiers the window maps roles onto: viewers
read, officers (staff, HR, instructors) record and run checks, admins also
delete. Students, parents and alumni are refused outright: the register
holds criminal-record and disciplinary flags about named people.
"""

from __future__ import annotations

import uuid
from typing import Any

from education_system.systems.university.domains.staff.domain.staff_hr.background_checks.university_bg_checker import (
    AuditLogger,
    Database,
    _bgcheck_role,
    calculate_risk_score,
    now_iso,
)

STATUSES = ("pending", "in-progress", "cleared", "flagged", "inactive")
PERSON_ROLES = ("student", "staff", "faculty")
_REFUSED = ("student", "parent", "alumni", "guest", "")

_auth: Any = None


def set_auth(auth_object: Any) -> None:
    global _auth
    _auth = auth_object


def _user() -> dict:
    user = getattr(_auth, "current_user", None) if _auth else None
    return user if isinstance(user, dict) else {}


def _pause() -> None:
    input("\nPress Enter to continue...")


def _print_cases(rows) -> None:
    if not rows:
        print("  No cases.")
        return
    print(f"  {'Case':<14}{'Person':<12}{'Name':<26}{'Role':<9}{'Status':<13}{'Risk':>5}")
    for r in rows:
        print(f"  {r['case_id']:<14}{r['person_id']:<12}{(r['full_name'] or '')[:25]:<26}"
              f"{r['role']:<9}{r['status']:<13}{r['risk_score'] or 0:>5}")


class _Session:
    def __init__(self, username: str, tier: str):
        self.db = Database()
        self.audit = AuditLogger(self.db)
        self.username = username
        self.tier = tier

    def require(self, *tiers: str) -> bool:
        if self.tier in tiers:
            return True
        print(f"\n  Requires the {' or '.join(tiers)} tier; you are {self.tier}.")
        return False

    def case(self, case_id: str):
        row = self.db.fetchone("SELECT * FROM bgcheck_persons WHERE case_id = ?", (case_id,))
        if not row:
            print(f"\n  No case {case_id}.")
        return row

    # -- reading ---------------------------------------------------------
    def list_cases(self) -> None:
        status = input("  Status filter (Enter = all): ").strip()
        text = input("  Name / person id contains (Enter = any): ").strip()
        sql, params = "SELECT * FROM bgcheck_persons WHERE 1=1", []
        if status in STATUSES:
            sql += " AND status = ?"
            params.append(status)
        if text:
            sql += " AND (full_name LIKE ? OR person_id LIKE ?)"
            params += [f"%{text}%", f"%{text}%"]
        _print_cases(self.db.fetchall(sql + " ORDER BY updated_at DESC", tuple(params)))
        self.db.execute("INSERT INTO bgcheck_search_history (username, query, timestamp) "
                        "VALUES (?, ?, ?)", (self.username, f"status:{status} q:{text}", now_iso()))

    def view_case(self) -> None:
        row = self.case(input("  Case id: ").strip())
        if not row:
            return
        for key in ("case_id", "person_id", "full_name", "role", "email", "phone", "department",
                    "status", "risk_score", "criminal_flag", "disciplinary_history",
                    "employment_history", "references_text", "documents", "notes", "updated_at"):
            print(f"  {key.replace('_', ' ').title():<22}: {row[key] if row[key] is not None else '—'}")
        self.audit.log(self.username, "VIEW", row["case_id"])

    def audit_log(self) -> None:
        for r in self.db.fetchall("SELECT * FROM bgcheck_audit_log ORDER BY id DESC LIMIT 30"):
            print(f"  {r['timestamp'][:19]}  {r['username'] or '':<14}{r['action']:<14}"
                  f"{r['target'] or ''}  {r['details'] or ''}")

    # -- writing ---------------------------------------------------------
    def add_case(self) -> None:
        if not self.require("admin", "officer"):
            return
        person_id = input("  Person id (student/staff number): ").strip()
        name = input("  Full name: ").strip()
        role = input(f"  Role ({'/'.join(PERSON_ROLES)}): ").strip().lower()
        if not person_id or not name or role not in PERSON_ROLES:
            print("\n  Person id, name and a valid role are required.")
            return
        case_id = f"BG-{uuid.uuid4().hex[:8].upper()}"
        now = now_iso()
        self.db.execute(
            "INSERT INTO bgcheck_persons (case_id, person_id, full_name, role, email, department, "
            "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
            (case_id, person_id, name, role, input("  Email: ").strip() or None,
             input("  Department: ").strip() or None, now, now))
        self.audit.log(self.username, "ADD", case_id, name)
        print(f"\n  Case {case_id} opened.")

    def set_status(self) -> None:
        if not self.require("admin", "officer"):
            return
        row = self.case(input("  Case id: ").strip())
        status = input(f"  New status ({'/'.join(STATUSES)}): ").strip()
        if not row or status not in STATUSES:
            return
        self.db.execute("UPDATE bgcheck_persons SET status = ?, updated_at = ? WHERE case_id = ?",
                        (status, now_iso(), row["case_id"]))
        self.audit.log(self.username, "STATUS", row["case_id"], status)
        print("\n  Status updated.")

    def add_note(self) -> None:
        if not self.require("admin", "officer"):
            return
        row = self.case(input("  Case id: ").strip())
        note = input("  Note: ").strip() if row else ""
        if not note:
            return
        new = f"{row['notes'] or ''}\n[{now_iso()} by {self.username}] {note}".strip()
        self.db.execute("UPDATE bgcheck_persons SET notes = ?, updated_at = ? WHERE case_id = ?",
                        (new, now_iso(), row["case_id"]))
        self.audit.log(self.username, "ADD_NOTE", row["case_id"], note[:80])
        print("\n  Note added.")

    def run_check(self) -> None:
        if not self.require("admin", "officer"):
            return
        row = self.case(input("  Case id: ").strip())
        if not row:
            return
        watch = [r["name"] for r in self.db.fetchall("SELECT name FROM bgcheck_watchlist")]
        risk = calculate_risk_score(dict(row), watch)
        status = "flagged" if risk >= 50 else "cleared"
        self.db.execute("UPDATE bgcheck_persons SET risk_score = ?, status = ?, updated_at = ? "
                        "WHERE case_id = ?", (risk, status, now_iso(), row["case_id"]))
        self.audit.log(self.username, "RUN_CHECK", row["case_id"], f"risk={risk} status={status}")
        print(f"\n  Risk score {risk} — {status}.")

    def watchlist(self) -> None:
        for r in self.db.fetchall("SELECT id, name, reason FROM bgcheck_watchlist ORDER BY name"):
            print(f"  {r['id']:>4}  {r['name']}  ({r['reason'] or ''})")
        if self.tier not in ("admin", "officer"):
            return
        action = input("\n  A = add, R = remove, Enter = back: ").strip().lower()
        if action == "a":
            name = input("  Name: ").strip()
            if name:
                self.db.execute("INSERT INTO bgcheck_watchlist (name, reason, added_at) "
                                "VALUES (?, ?, ?)", (name, input("  Reason: ").strip(), now_iso()))
                self.audit.log(self.username, "WATCHLIST_ADD", name)
        elif action == "r":
            wid = input("  Id to remove: ").strip()
            if wid.isdigit():
                self.db.execute("DELETE FROM bgcheck_watchlist WHERE id = ?", (int(wid),))
                self.audit.log(self.username, "WATCHLIST_DEL", wid)

    def delete_case(self) -> None:
        if not self.require("admin"):
            return
        row = self.case(input("  Case id: ").strip())
        if row and input(f"  Delete {row['case_id']} ({row['full_name']})? y/N: ").lower() == "y":
            self.db.execute("DELETE FROM bgcheck_persons WHERE case_id = ?", (row["case_id"],))
            self.audit.log(self.username, "DELETE", row["case_id"])
            print("\n  Case deleted.")


MENU = (
    ("1", "List / search cases", "list_cases"),
    ("2", "View a case", "view_case"),
    ("3", "Open a case", "add_case"),
    ("4", "Change a case's status", "set_status"),
    ("5", "Add a note", "add_note"),
    ("6", "Run risk check", "run_check"),
    ("7", "Watchlist", "watchlist"),
    ("8", "Audit log", "audit_log"),
    ("9", "Delete a case (admin)", "delete_case"),
)


def display_background_checks_menu(auth: Any = None) -> None:
    if auth is not None:
        set_auth(auth)
    user = _user()
    role = str(user.get("role") or "").lower()
    if not user or role in _REFUSED:
        print("\n  The Background Checker is for staff. Your account cannot open it.")
        _pause()
        return
    session = _Session(str(user.get("username") or user.get("id") or "unknown"), _bgcheck_role(role))
    session.audit.log(session.username, "LOGIN", "", f"role={session.tier} via=cli")
    actions = {key: getattr(session, method) for key, _label, method in MENU}
    try:
        while True:
            print("\n" + "=" * 60)
            print(f"  BACKGROUND CHECKER  ({session.username}, {session.tier})")
            print("=" * 60)
            for key, label, _method in MENU:
                print(f"  {key}. {label}")
            print("  0. Back")
            choice = input("\n  Choice: ").strip()
            if choice not in actions:
                return
            try:
                actions[choice]()
            except RuntimeError as exc:
                print(f"\n  Database error: {exc}")
            _pause()
    finally:
        session.db.close()
