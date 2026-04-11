"""Student Council service layer."""

from education_system.college_system.core.exceptions import StudentCouncilError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class StudentCouncilService:
    """Service for managing student council members, meetings, and proposals."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        conn = connect(self._db_path)
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        return conn

    # ── Members CRUD ──

    def list_members(self, status: str | None = None, role: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT cm.*, s.first_name, s.last_name
                     FROM council_members cm
                     LEFT JOIN students s ON cm.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if status:
                sql += " AND cm.status = ?"
                params.append(status)
            if role:
                sql += " AND cm.role = ?"
                params.append(role)
            sql += " ORDER BY cm.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_member(self, member_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT cm.*, s.first_name, s.last_name
                   FROM council_members cm
                   LEFT JOIN students s ON cm.student_id = s.id
                   WHERE cm.id = ?""",
                (member_id,),
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_member(self, student_id: int, role: str = "representative",
                      year_group: str | None = None, department: str | None = None,
                      elected_date: str | None = None, term_end_date: str | None = None,
                      **kwargs) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO council_members
                   (student_id, role, year_group, department, elected_date, term_end_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, role, year_group, department, elected_date, term_end_date),
            )
            conn.commit()
            logger.info("Council member created: student=%d role=%s", student_id, role)
            row = conn.execute(
                """SELECT cm.*, s.first_name, s.last_name
                   FROM council_members cm
                   LEFT JOIN students s ON cm.student_id = s.id
                   WHERE cm.id = last_insert_rowid()""",
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to create member: {e}") from e
        finally:
            conn.close()

    def update_member(self, member_id: int, **kwargs) -> dict:
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_pieces: list[str] = []
        params: list = []
        for col in ("role", "year_group", "department", "elected_date",
                    "term_end_date", "status"):
            val = kwargs.get(col)
            if val is not None:
                set_pieces.append(f"{col} = ?")
                params.append(val)
        if not set_pieces:
            raise StudentCouncilError("No valid fields to update.")
        params.append(member_id)
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM council_members WHERE id = ?", (member_id,)).fetchone()
            if not existing:
                raise StudentCouncilError("Member not found.")
            set_parts = ", ".join(set_pieces)
            conn.execute(f"UPDATE council_members SET {set_parts} WHERE id = ?",  # nosec B608
                         params)
            conn.commit()
            logger.info("Council member updated: id=%d", member_id)
            return self.get_member(member_id)
        except StudentCouncilError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to update member: {e}") from e
        finally:
            conn.close()

    def delete_member(self, member_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM council_members WHERE id = ?", (member_id,)).fetchone()
            if not existing:
                raise StudentCouncilError("Member not found.")
            conn.execute("DELETE FROM council_members WHERE id = ?", (member_id,))
            conn.commit()
            logger.info("Council member deleted: id=%d", member_id)
            return True
        except StudentCouncilError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to delete member: {e}") from e
        finally:
            conn.close()

    def end_term(self, member_id: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM council_members WHERE id = ?", (member_id,)).fetchone()
            if not existing:
                raise StudentCouncilError("Member not found.")
            conn.execute(
                """UPDATE council_members
                   SET status = 'term_ended', term_end_date = date('now')
                   WHERE id = ?""",
                (member_id,),
            )
            conn.commit()
            logger.info("Council member term ended: id=%d", member_id)
            return self.get_member(member_id)
        except StudentCouncilError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to end term: {e}") from e
        finally:
            conn.close()

    # ── Meetings CRUD ──

    def list_meetings(self, status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT m.*, cm.role as chair_role,
                            s.first_name as chair_first_name, s.last_name as chair_last_name
                     FROM council_meetings m
                     LEFT JOIN council_members cm ON m.chair_id = cm.id
                     LEFT JOIN students s ON cm.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if status:
                sql += " AND m.status = ?"
                params.append(status)
            sql += " ORDER BY m.meeting_date DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_meeting(self, meeting_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT m.*, cm.role as chair_role,
                          s.first_name as chair_first_name, s.last_name as chair_last_name
                   FROM council_meetings m
                   LEFT JOIN council_members cm ON m.chair_id = cm.id
                   LEFT JOIN students s ON cm.student_id = s.id
                   WHERE m.id = ?""",
                (meeting_id,),
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_meeting(self, meeting_date: str, chair_id: int | None = None,
                       agenda: str | None = None, **kwargs) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO council_meetings (meeting_date, chair_id, agenda)
                   VALUES (?, ?, ?)""",
                (meeting_date, chair_id, agenda),
            )
            conn.commit()
            meeting_id = conn.execute("SELECT last_insert_rowid()").fetchone()["last_insert_rowid()"]
            logger.info("Council meeting created: date=%s id=%d", meeting_date, meeting_id)
            return self.get_meeting(meeting_id)
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to create meeting: {e}") from e
        finally:
            conn.close()

    def update_meeting(self, meeting_id: int, **kwargs) -> dict:
        allowed = {"meeting_date", "chair_id", "agenda", "minutes", "attendees", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise StudentCouncilError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM council_meetings WHERE id = ?", (meeting_id,)).fetchone()
            if not existing:
                raise StudentCouncilError("Meeting not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE council_meetings SET {set_parts} WHERE id = ?",  # nosec B608
                         (*updates.values(), meeting_id))
            conn.commit()
            logger.info("Council meeting updated: id=%d", meeting_id)
            return self.get_meeting(meeting_id)
        except StudentCouncilError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to update meeting: {e}") from e
        finally:
            conn.close()

    def delete_meeting(self, meeting_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM council_meetings WHERE id = ?", (meeting_id,)).fetchone()
            if not existing:
                raise StudentCouncilError("Meeting not found.")
            conn.execute("DELETE FROM council_meetings WHERE id = ?", (meeting_id,))
            conn.commit()
            logger.info("Council meeting deleted: id=%d", meeting_id)
            return True
        except StudentCouncilError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to delete meeting: {e}") from e
        finally:
            conn.close()

    def complete_meeting(self, meeting_id: int, minutes: str, attendees: str) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM council_meetings WHERE id = ?", (meeting_id,)).fetchone()
            if not existing:
                raise StudentCouncilError("Meeting not found.")
            conn.execute(
                """UPDATE council_meetings
                   SET status = 'completed', minutes = ?, attendees = ?
                   WHERE id = ?""",
                (minutes, attendees, meeting_id),
            )
            conn.commit()
            logger.info("Council meeting completed: id=%d", meeting_id)
            return self.get_meeting(meeting_id)
        except StudentCouncilError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to complete meeting: {e}") from e
        finally:
            conn.close()

    # ── Proposals CRUD ──

    def list_proposals(self, category: str | None = None,
                       implementation_status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT p.*, cm.role as proposer_role,
                            s.first_name as proposer_first_name, s.last_name as proposer_last_name
                     FROM council_proposals p
                     LEFT JOIN council_members cm ON p.proposed_by = cm.id
                     LEFT JOIN students s ON cm.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if category:
                sql += " AND p.category = ?"
                params.append(category)
            if implementation_status:
                sql += " AND p.implementation_status = ?"
                params.append(implementation_status)
            sql += " ORDER BY p.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_proposal(self, proposal_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT p.*, cm.role as proposer_role,
                          s.first_name as proposer_first_name, s.last_name as proposer_last_name
                   FROM council_proposals p
                   LEFT JOIN council_members cm ON p.proposed_by = cm.id
                   LEFT JOIN students s ON cm.student_id = s.id
                   WHERE p.id = ?""",
                (proposal_id,),
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_proposal(self, title: str, proposed_by: int | None = None,
                        meeting_id: int | None = None, description: str | None = None,
                        category: str = "general", **kwargs) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO council_proposals
                   (title, proposed_by, meeting_id, description, category)
                   VALUES (?, ?, ?, ?, ?)""",
                (title, proposed_by, meeting_id, description, category),
            )
            conn.commit()
            proposal_id = conn.execute("SELECT last_insert_rowid()").fetchone()["last_insert_rowid()"]
            logger.info("Council proposal created: title=%s id=%d", title, proposal_id)
            return self.get_proposal(proposal_id)
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to create proposal: {e}") from e
        finally:
            conn.close()

    def update_proposal(self, proposal_id: int, **kwargs) -> dict:
        allowed = {"title", "proposed_by", "meeting_id", "description", "category",
                    "vote_for", "vote_against", "vote_abstain", "outcome",
                    "management_response", "implementation_status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise StudentCouncilError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM council_proposals WHERE id = ?", (proposal_id,)).fetchone()
            if not existing:
                raise StudentCouncilError("Proposal not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE council_proposals SET {set_parts} WHERE id = ?",  # nosec B608
                         (*updates.values(), proposal_id))
            conn.commit()
            logger.info("Council proposal updated: id=%d", proposal_id)
            return self.get_proposal(proposal_id)
        except StudentCouncilError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to update proposal: {e}") from e
        finally:
            conn.close()

    def delete_proposal(self, proposal_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM council_proposals WHERE id = ?", (proposal_id,)).fetchone()
            if not existing:
                raise StudentCouncilError("Proposal not found.")
            conn.execute("DELETE FROM council_proposals WHERE id = ?", (proposal_id,))
            conn.commit()
            logger.info("Council proposal deleted: id=%d", proposal_id)
            return True
        except StudentCouncilError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to delete proposal: {e}") from e
        finally:
            conn.close()

    def record_votes(self, proposal_id: int, vote_for: int, vote_against: int,
                     vote_abstain: int, outcome: str) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM council_proposals WHERE id = ?", (proposal_id,)).fetchone()
            if not existing:
                raise StudentCouncilError("Proposal not found.")
            conn.execute(
                """UPDATE council_proposals
                   SET vote_for = ?, vote_against = ?, vote_abstain = ?, outcome = ?
                   WHERE id = ?""",
                (vote_for, vote_against, vote_abstain, outcome, proposal_id),
            )
            conn.commit()
            logger.info("Votes recorded for proposal: id=%d outcome=%s", proposal_id, outcome)
            return self.get_proposal(proposal_id)
        except StudentCouncilError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to record votes: {e}") from e
        finally:
            conn.close()

    def respond_to_proposal(self, proposal_id: int, management_response: str,
                            implementation_status: str) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM council_proposals WHERE id = ?", (proposal_id,)).fetchone()
            if not existing:
                raise StudentCouncilError("Proposal not found.")
            conn.execute(
                """UPDATE council_proposals
                   SET management_response = ?, implementation_status = ?
                   WHERE id = ?""",
                (management_response, implementation_status, proposal_id),
            )
            conn.commit()
            logger.info("Management response for proposal: id=%d status=%s", proposal_id, implementation_status)
            return self.get_proposal(proposal_id)
        except StudentCouncilError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentCouncilError(f"Failed to respond to proposal: {e}") from e
        finally:
            conn.close()

    # ── Statistics ──

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            # Members
            total_members = conn.execute("SELECT COUNT(*) as c FROM council_members").fetchone()["c"]
            active_members = conn.execute(
                "SELECT COUNT(*) as c FROM council_members WHERE status = 'active'"
            ).fetchone()["c"]
            role_rows = conn.execute(
                "SELECT role, COUNT(*) as c FROM council_members WHERE status = 'active' GROUP BY role"
            ).fetchall()
            by_role = {r["role"]: r["c"] for r in role_rows}

            # Meetings
            total_meetings = conn.execute("SELECT COUNT(*) as c FROM council_meetings").fetchone()["c"]
            completed_meetings = conn.execute(
                "SELECT COUNT(*) as c FROM council_meetings WHERE status = 'completed'"
            ).fetchone()["c"]

            # Proposals
            total_proposals = conn.execute("SELECT COUNT(*) as c FROM council_proposals").fetchone()["c"]
            cat_rows = conn.execute(
                "SELECT category, COUNT(*) as c FROM council_proposals GROUP BY category"
            ).fetchall()
            by_category = {r["category"]: r["c"] for r in cat_rows}
            status_rows = conn.execute(
                "SELECT implementation_status, COUNT(*) as c FROM council_proposals GROUP BY implementation_status"
            ).fetchall()
            by_implementation_status = {r["implementation_status"]: r["c"] for r in status_rows}
            proposals_implemented = conn.execute(
                "SELECT COUNT(*) as c FROM council_proposals WHERE implementation_status = 'implemented'"
            ).fetchone()["c"]

            return {
                "total_members": total_members,
                "active_members": active_members,
                "by_role": by_role,
                "total_meetings": total_meetings,
                "completed_meetings": completed_meetings,
                "total_proposals": total_proposals,
                "by_category": by_category,
                "by_implementation_status": by_implementation_status,
                "proposals_implemented": proposals_implemented,
            }
        finally:
            conn.close()
