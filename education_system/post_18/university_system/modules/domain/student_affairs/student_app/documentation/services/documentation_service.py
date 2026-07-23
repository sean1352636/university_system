"""Enrolment verification / status letter service.

Self-serve flow for students requesting "proof of study" letters:
council tax exemption, mortgage application, employer confirmation,
visa / UKVI Student Route, and generic status letters.

Each issued letter has:
- a human reference code (e.g. ELR-2026-000123) printed on the letter,
- a verification token (URL-safe, 32 hex chars) that a third party
  (council, bank, employer, UKVI caseworker) can use to confirm the
  letter is genuine via verify_letter(token).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from education_system.post_18.university_system.infrastructure.database.db import (
    get_connection,
    transaction,
)


LETTER_TYPES: Dict[str, str] = {
    "council_tax": "Council Tax Exemption Letter",
    "mortgage": "Mortgage / Lender Status Letter",
    "employer": "Employer Confirmation of Study",
    "visa": "Visa / UKVI Student Route Letter",
    "bank": "Bank Account Opening Letter",
    "general": "General Proof of Study",
}

DEFAULT_VALIDITY_DAYS = 90


class DocumentationService:
    """Persist letter requests, generate letter content, and verify issued letters."""

    def __init__(self) -> None:
        self._ensure_tables_exist()

    # ------------------------------------------------------------------ schema
    def _ensure_tables_exist(self) -> None:
        with transaction() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enrolment_letter_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    letter_type TEXT NOT NULL,
                    purpose TEXT,
                    recipient_name TEXT,
                    recipient_address TEXT,
                    delivery_method TEXT DEFAULT 'download',
                    status TEXT DEFAULT 'pending',
                    rejection_reason TEXT,
                    requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    decided_at TEXT,
                    decided_by TEXT,
                    letter_id INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enrolment_letters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    letter_type TEXT NOT NULL,
                    reference_code TEXT UNIQUE NOT NULL,
                    verification_token TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    issued_by TEXT,
                    valid_until TEXT,
                    revoked INTEGER DEFAULT 0,
                    revoked_reason TEXT,
                    FOREIGN KEY(request_id) REFERENCES enrolment_letter_requests(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_letter_requests_student "
                "ON enrolment_letter_requests(student_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_letter_requests_status "
                "ON enrolment_letter_requests(status)"
            )
            conn.commit()

    # ----------------------------------------------------------- request flow
    def submit_request(
        self,
        student_id: str,
        letter_type: str,
        purpose: Optional[str] = None,
        recipient_name: Optional[str] = None,
        recipient_address: Optional[str] = None,
        delivery_method: str = "download",
    ) -> int:
        if letter_type not in LETTER_TYPES:
            raise ValueError(f"Unknown letter type: {letter_type}")
        with transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO enrolment_letter_requests
                    (student_id, letter_type, purpose, recipient_name,
                     recipient_address, delivery_method)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    letter_type,
                    purpose,
                    recipient_name,
                    recipient_address,
                    delivery_method,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def list_requests(
        self,
        student_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict]:
        sql = "SELECT * FROM enrolment_letter_requests WHERE 1=1"
        args: List = []
        if student_id is not None:
            sql += " AND student_id = ?"
            args.append(student_id)
        if status is not None:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY requested_at DESC"
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]

    def get_request(self, request_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM enrolment_letter_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            return dict(row) if row else None

    # ----------------------------------------------------------- approval flow
    def approve_request(
        self,
        request_id: int,
        approver_username: str,
        validity_days: int = DEFAULT_VALIDITY_DAYS,
    ) -> Dict:
        """Approve a pending request and issue the letter.

        Returns the issued letter row as a dict.
        """
        request = self.get_request(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        if request["status"] != "pending":
            raise ValueError(
                f"Request {request_id} is not pending (status={request['status']})"
            )

        student = self._lookup_student(request["student_id"])
        reference_code = self._next_reference_code()
        verification_token = secrets.token_hex(16)
        valid_until = (datetime.now() + timedelta(days=validity_days)).date().isoformat()
        content = self._render_letter(
            request, student, reference_code, verification_token, valid_until
        )

        with transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO enrolment_letters
                    (request_id, student_id, letter_type, reference_code,
                     verification_token, content, issued_by, valid_until)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    request["student_id"],
                    request["letter_type"],
                    reference_code,
                    verification_token,
                    content,
                    approver_username,
                    valid_until,
                ),
            )
            letter_id = cursor.lastrowid
            conn.execute(
                """
                UPDATE enrolment_letter_requests
                   SET status = 'issued',
                       decided_at = ?,
                       decided_by = ?,
                       letter_id = ?
                 WHERE id = ?
                """,
                (datetime.now().isoformat(), approver_username, letter_id, request_id),
            )
            conn.commit()
            return self.get_letter(letter_id)  # type: ignore[return-value]

    def reject_request(
        self, request_id: int, approver_username: str, reason: str
    ) -> bool:
        with transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE enrolment_letter_requests
                   SET status = 'rejected',
                       decided_at = ?,
                       decided_by = ?,
                       rejection_reason = ?
                 WHERE id = ? AND status = 'pending'
                """,
                (datetime.now().isoformat(), approver_username, reason, request_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ----------------------------------------------------------- letter access
    def get_letter(self, letter_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM enrolment_letters WHERE id = ?", (letter_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_letters(self, student_id: str) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, reference_code, letter_type, issued_at, valid_until, "
                "revoked FROM enrolment_letters WHERE student_id = ? "
                "ORDER BY issued_at DESC",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def verify_letter(self, token_or_reference: str) -> Optional[Dict]:
        """Public verification entry point.

        Returns a redacted dict suitable for showing to a third-party
        verifier — never the full letter body."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM enrolment_letters "
                "WHERE verification_token = ? OR reference_code = ?",
                (token_or_reference.strip(), token_or_reference.strip().upper()),
            ).fetchone()
            if not row:
                return None
            letter = dict(row)
            valid = not letter["revoked"]
            if letter.get("valid_until"):
                try:
                    valid = valid and (
                        datetime.fromisoformat(letter["valid_until"]).date()
                        >= datetime.now().date()
                    )
                except ValueError:
                    pass
            return {
                "reference_code": letter["reference_code"],
                "letter_type": LETTER_TYPES.get(
                    letter["letter_type"], letter["letter_type"]
                ),
                "student_id": letter["student_id"],
                "issued_at": letter["issued_at"],
                "valid_until": letter["valid_until"],
                "revoked": bool(letter["revoked"]),
                "revoked_reason": letter.get("revoked_reason"),
                "is_valid": valid,
            }

    def revoke_letter(self, letter_id: int, reason: str) -> bool:
        with transaction() as conn:
            cursor = conn.execute(
                "UPDATE enrolment_letters SET revoked = 1, revoked_reason = ? "
                "WHERE id = ?",
                (reason, letter_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ---------------------------------------------------------------- helpers
    def _next_reference_code(self) -> str:
        year = datetime.now().year
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM enrolment_letters "
                "WHERE reference_code LIKE ?",
                (f"ELR-{year}-%",),
            ).fetchone()[0]
        return f"ELR-{year}-{count + 1:06d}"

    def _lookup_student(self, student_id: str) -> Dict:
        """Best-effort lookup of student record. Falls back to id-only stub."""
        stub = {
            "student_id": student_id,
            "full_name": student_id,
            "course": "",
            "year_of_study": "",
            "enrolment_status": "Enrolled",
            "start_date": "",
            "expected_end_date": "",
            "tuition_status": "",
            "address": "",
        }
        with get_connection() as conn:
            for sql in (
                "SELECT * FROM students WHERE student_id = ?",
                "SELECT * FROM students WHERE id = ?",
            ):
                try:
                    row = conn.execute(sql, (student_id,)).fetchone()
                except Exception:
                    row = None
                if row:
                    rec = dict(row)
                    stub["full_name"] = (
                        rec.get("full_name")
                        or " ".join(
                            x for x in (rec.get("first_name"), rec.get("last_name")) if x
                        ).strip()
                        or student_id
                    )
                    stub["course"] = rec.get("course") or rec.get("programme") or ""
                    stub["year_of_study"] = (
                        rec.get("year_of_study") or rec.get("year") or ""
                    )
                    stub["enrolment_status"] = (
                        rec.get("status") or rec.get("enrolment_status") or "Enrolled"
                    )
                    stub["start_date"] = (
                        rec.get("start_date") or rec.get("enrolment_date") or ""
                    )
                    stub["expected_end_date"] = (
                        rec.get("expected_end_date")
                        or rec.get("expected_completion")
                        or ""
                    )
                    stub["tuition_status"] = rec.get("tuition_status") or ""
                    stub["address"] = rec.get("address") or ""
                    break
        return stub

    def _render_letter(
        self,
        request: Dict,
        student: Dict,
        reference_code: str,
        verification_token: str,
        valid_until: str,
    ) -> str:
        letter_type = request["letter_type"]
        issued = datetime.now().strftime("%d %B %Y")
        recipient_block = ""
        if request.get("recipient_name"):
            recipient_block += request["recipient_name"] + "\n"
        if request.get("recipient_address"):
            recipient_block += request["recipient_address"] + "\n"
        recipient_block = recipient_block or "To Whom It May Concern\n"

        body = self._letter_body(letter_type, student, request)

        return (
            f"University Registry — Enrolment Verification\n"
            f"Reference: {reference_code}\n"
            f"Issued: {issued}\n"
            f"Valid until: {valid_until}\n"
            f"\n{recipient_block}\n"
            f"Dear Sir/Madam,\n\n"
            f"{body}\n\n"
            f"This letter can be verified at the University verification portal\n"
            f"using reference code {reference_code} or token {verification_token}.\n\n"
            f"Yours faithfully,\n"
            f"University Registry Office\n"
        )

    def _letter_body(self, letter_type: str, student: Dict, request: Dict) -> str:
        name = student.get("full_name") or student.get("student_id")
        sid = student.get("student_id")
        course = student.get("course") or "(course on file)"
        year = student.get("year_of_study") or ""
        status = student.get("enrolment_status") or "Enrolled"
        start = student.get("start_date") or ""
        end = student.get("expected_end_date") or ""

        common = (
            f"This is to confirm that {name} (student ID {sid}) is currently {status} "
            f"on the {course} programme"
            + (f", year {year}" if year else "")
            + ".\n"
            + (f"Programme start date: {start}.\n" if start else "")
            + (f"Expected completion: {end}.\n" if end else "")
        )

        if letter_type == "council_tax":
            return (
                common
                + "\nThe student is engaged in a full-time course of study at this "
                "University and is therefore disregarded for the purposes of "
                "Council Tax under Schedule 1 of the Local Government Finance Act 1992."
            )
        if letter_type == "mortgage":
            tuition = student.get("tuition_status") or "in good financial standing"
            return (
                common
                + f"\nFor the purposes of a mortgage / lender affordability check, "
                f"the student is {tuition} with the University. This letter does not "
                "constitute proof of income."
            )
        if letter_type == "employer":
            return (
                common
                + "\nThe student is permitted to undertake employment alongside "
                "their studies in line with University policy and any visa "
                "conditions that may apply."
            )
        if letter_type == "visa":
            return (
                common
                + "\nThe University is a licensed Student Sponsor under the UKVI "
                "Student Route. This letter confirms that the student remains "
                "actively enrolled and in compliance with their sponsorship "
                "conditions at the date of issue."
            )
        if letter_type == "bank":
            addr = student.get("address") or "(address on file at the University)"
            return (
                common
                + f"\nThe address held on the University's record for this student is:\n"
                f"{addr}\n\n"
                "This letter is provided to support a UK bank account opening."
            )
        return common + (
            f"\nPurpose of letter: {request.get('purpose') or 'general proof of study'}."
        )
