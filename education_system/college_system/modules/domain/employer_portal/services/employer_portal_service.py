"""Apprenticeship employer portal service."""
from education_system.college_system.core.exceptions import EmployerPortalError
from education_system.college_system.infrastructure.database.db import connect
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EmployerPortalService:
    """Manage employer accounts, learner links, reviews and sign-offs."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ------------------------------------------------------------------
    # Employer Accounts
    # ------------------------------------------------------------------

    def register_employer(self, company_name, contact_name, contact_email,
                          contact_phone, sector, company_size="small",
                          levy_payer=0):
        """Register a new employer."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO employer_accounts
                   (company_name, contact_name, contact_email, contact_phone,
                    sector, company_size, levy_payer, is_active,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))""",
                (company_name, contact_name, contact_email, contact_phone,
                 sector, company_size, levy_payer),
            )
            conn.commit()
            logger.info("Registered employer '%s' (id=%s)", company_name, cur.lastrowid)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to register employer: %s", exc)
            raise EmployerPortalError(f"Failed to register employer: {exc}") from exc
        finally:
            conn.close()

    def list_employers(self, active_only=True):
        """List all employer accounts."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM employer_accounts"
            if active_only:
                sql += " WHERE is_active = 1"
            sql += " ORDER BY company_name"
            rows = conn.execute(sql).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list employers: %s", exc)
            raise EmployerPortalError(f"Failed to list employers: {exc}") from exc
        finally:
            conn.close()

    def update_employer(self, employer_id, **updates):
        """Update employer account details."""
        conn = self._conn()
        try:
            allowed = {"company_name", "contact_name", "contact_email",
                        "contact_phone", "address", "sector", "company_size",
                        "levy_payer", "is_active", "portal_access_enabled", "notes"}
            fields = {k: v for k, v in updates.items() if k in allowed}
            if not fields:
                return
            sets = ", ".join(f"{k} = ?" for k in fields)
            vals = list(fields.values()) + [employer_id]
            conn.execute(
                f"UPDATE employer_accounts SET {sets}, updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update employer: %s", exc)
            raise EmployerPortalError(f"Failed to update employer: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Learner Links
    # ------------------------------------------------------------------

    def link_learner(self, employer_id, student_id, apprenticeship_standard,
                     start_date, expected_end_date, mentor_name=None,
                     mentor_email=None):
        """Link a learner to an employer."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO employer_learner_links
                   (employer_id, student_id, apprenticeship_standard,
                    start_date, expected_end_date, mentor_name, mentor_email,
                    status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'active',
                           datetime('now'), datetime('now'))""",
                (employer_id, student_id, apprenticeship_standard,
                 start_date, expected_end_date, mentor_name, mentor_email),
            )
            conn.commit()
            logger.info("Linked learner %s to employer %s", student_id, employer_id)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to link learner: %s", exc)
            raise EmployerPortalError(f"Failed to link learner: {exc}") from exc
        finally:
            conn.close()

    def list_learner_links(self, employer_id=None, student_id=None, status=None):
        """List learner-employer links."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM employer_learner_links WHERE 1=1"
            params = []
            if employer_id is not None:
                sql += " AND employer_id = ?"
                params.append(employer_id)
            if student_id is not None:
                sql += " AND student_id = ?"
                params.append(student_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY start_date DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list learner links: %s", exc)
            raise EmployerPortalError(f"Failed to list learner links: {exc}") from exc
        finally:
            conn.close()

    def update_learner_link(self, link_id, **updates):
        """Update a learner link."""
        conn = self._conn()
        try:
            allowed = {"apprenticeship_standard", "expected_end_date",
                        "actual_end_date", "mentor_name", "mentor_email",
                        "training_plan", "status"}
            fields = {k: v for k, v in updates.items() if k in allowed}
            if not fields:
                return
            sets = ", ".join(f"{k} = ?" for k in fields)
            vals = list(fields.values()) + [link_id]
            conn.execute(
                f"UPDATE employer_learner_links SET {sets}, updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update learner link: %s", exc)
            raise EmployerPortalError(f"Failed to update learner link: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Progress Reviews
    # ------------------------------------------------------------------

    def schedule_review(self, learner_link_id, review_date, review_type="monthly"):
        """Schedule a progress review."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO progress_reviews
                   (learner_link_id, review_date, review_type, status,
                    created_at, updated_at)
                   VALUES (?, ?, ?, 'scheduled', datetime('now'), datetime('now'))""",
                (learner_link_id, review_date, review_type),
            )
            conn.commit()
            logger.info("Scheduled %s review for link %s on %s",
                        review_type, learner_link_id, review_date)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to schedule review: %s", exc)
            raise EmployerPortalError(f"Failed to schedule review: {exc}") from exc
        finally:
            conn.close()

    def list_reviews(self, learner_link_id=None, status=None):
        """List progress reviews."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM progress_reviews WHERE 1=1"
            params = []
            if learner_link_id is not None:
                sql += " AND learner_link_id = ?"
                params.append(learner_link_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY review_date DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list reviews: %s", exc)
            raise EmployerPortalError(f"Failed to list reviews: {exc}") from exc
        finally:
            conn.close()

    def complete_review(self, review_id, on_track, ksbm_progress, off_the_job_hours,
                        employer_feedback, learner_feedback=None, assessor_feedback=None,
                        actions=None, next_review_date=None):
        """Complete a progress review."""
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE progress_reviews
                   SET on_track = ?, ksbm_progress = ?, off_the_job_hours = ?,
                       employer_feedback = ?, learner_feedback = ?,
                       assessor_feedback = ?, actions = ?,
                       next_review_date = ?, status = 'completed',
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (on_track, ksbm_progress, off_the_job_hours,
                 employer_feedback, learner_feedback, assessor_feedback,
                 actions, next_review_date, review_id),
            )
            conn.commit()
            logger.info("Completed review %s", review_id)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to complete review: %s", exc)
            raise EmployerPortalError(f"Failed to complete review: {exc}") from exc
        finally:
            conn.close()

    def sign_off_review(self, review_id, signer_type, signer_name, comments=None):
        """Sign off a progress review."""
        conn = self._conn()
        try:
            # Record the sign-off
            conn.execute(
                """INSERT INTO employer_sign_offs
                   (review_id, signer_type, signer_name, signed_at, comments, created_at)
                   VALUES (?, ?, ?, datetime('now'), ?, datetime('now'))""",
                (review_id, signer_type, signer_name, comments),
            )
            # Update the review's signed flag
            col_map = {
                "employer": "employer_signed",
                "learner": "learner_signed",
                "assessor": "assessor_signed",
            }
            col = col_map.get(signer_type)
            if col:
                conn.execute(
                    f"UPDATE progress_reviews SET {col} = 1, updated_at = datetime('now') WHERE id = ?",
                    (review_id,),
                )
            conn.commit()
            logger.info("Review %s signed off by %s (%s)", review_id, signer_name, signer_type)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to sign off review: %s", exc)
            raise EmployerPortalError(f"Failed to sign off review: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Dashboard & Analytics
    # ------------------------------------------------------------------

    def get_learner_progress(self, student_id):
        """Get learner progress summary with reviews and OTJ hours."""
        conn = self._conn()
        try:
            link = conn.execute(
                "SELECT * FROM employer_learner_links WHERE student_id = ? AND status = 'active'",
                (student_id,),
            ).fetchone()
            if not link:
                return {"student_id": student_id, "status": "no_active_link"}

            link = dict(link)
            reviews = conn.execute(
                """SELECT * FROM progress_reviews
                   WHERE learner_link_id = ?
                   ORDER BY review_date DESC""",
                (link["id"],),
            ).fetchall()

            total_otj = sum(r["off_the_job_hours"] or 0 for r in reviews)
            otj_target = reviews[0]["off_the_job_target"] if reviews and reviews[0]["off_the_job_target"] else 0

            # Calculate completion percentage based on dates
            start = link.get("start_date", "")
            end = link.get("expected_end_date", "")
            completion_pct = 0
            if start and end:
                try:
                    s = datetime.strptime(start, "%Y-%m-%d")
                    e = datetime.strptime(end, "%Y-%m-%d")
                    now = datetime.now()
                    total_days = (e - s).days
                    elapsed = (now - s).days
                    if total_days > 0:
                        completion_pct = min(round(elapsed * 100.0 / total_days, 1), 100)
                except ValueError:
                    pass

            return {
                "student_id": student_id,
                "link": link,
                "reviews": [dict(r) for r in reviews],
                "total_otj_hours": total_otj,
                "otj_target": otj_target,
                "completion_pct": completion_pct,
                "num_reviews": len(reviews),
            }
        except Exception as exc:
            logger.error("Failed to get learner progress: %s", exc)
            raise EmployerPortalError(f"Failed to get learner progress: {exc}") from exc
        finally:
            conn.close()

    def get_employer_dashboard(self, employer_id):
        """Get employer dashboard with learner summaries."""
        conn = self._conn()
        try:
            links = conn.execute(
                "SELECT * FROM employer_learner_links WHERE employer_id = ?",
                (employer_id,),
            ).fetchall()

            summaries = []
            for link in links:
                link = dict(link)
                reviews = conn.execute(
                    """SELECT COUNT(*) AS total,
                              COUNT(CASE WHEN status = 'completed' THEN 1 END) AS completed,
                              COUNT(CASE WHEN on_track = 1 THEN 1 END) AS on_track,
                              COALESCE(SUM(off_the_job_hours), 0) AS total_otj
                       FROM progress_reviews WHERE learner_link_id = ?""",
                    (link["id"],),
                ).fetchone()
                link["review_summary"] = dict(reviews) if reviews else {}
                summaries.append(link)

            return {
                "employer_id": employer_id,
                "total_learners": len(links),
                "active_learners": sum(1 for l in links if l.get("status") == "active"),
                "learner_summaries": summaries,
            }
        except Exception as exc:
            logger.error("Failed to get employer dashboard: %s", exc)
            raise EmployerPortalError(f"Failed to get employer dashboard: {exc}") from exc
        finally:
            conn.close()

    def get_off_the_job_summary(self, learner_link_id):
        """Get OTJ hours summary for a learner."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COALESCE(SUM(off_the_job_hours), 0) AS total_hours,
                          MAX(off_the_job_target) AS target_hours
                   FROM progress_reviews WHERE learner_link_id = ?""",
                (learner_link_id,),
            ).fetchone()
            total = row["total_hours"] if row else 0
            target = row["target_hours"] if row and row["target_hours"] else 0
            pct = round(total * 100.0 / target, 1) if target > 0 else 0
            return {
                "total_hours": total,
                "target_hours": target,
                "percentage_complete": pct,
            }
        except Exception as exc:
            logger.error("Failed to get OTJ summary: %s", exc)
            raise EmployerPortalError(f"Failed to get OTJ summary: {exc}") from exc
        finally:
            conn.close()

    def get_overdue_reviews(self):
        """Get reviews that are past their scheduled date and not completed."""
        conn = self._conn()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            rows = conn.execute(
                """SELECT pr.*, ell.student_id, ell.employer_id,
                          ell.apprenticeship_standard
                   FROM progress_reviews pr
                   JOIN employer_learner_links ell ON ell.id = pr.learner_link_id
                   WHERE pr.status = 'scheduled' AND pr.review_date < ?
                   ORDER BY pr.review_date ASC""",
                (today,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to get overdue reviews: %s", exc)
            raise EmployerPortalError(f"Failed to get overdue reviews: {exc}") from exc
        finally:
            conn.close()

    def get_epa_readiness(self, learner_link_id):
        """Check EPA (End Point Assessment) readiness for a learner."""
        conn = self._conn()
        try:
            link = conn.execute(
                "SELECT * FROM employer_learner_links WHERE id = ?",
                (learner_link_id,),
            ).fetchone()
            if not link:
                raise EmployerPortalError(f"Learner link {learner_link_id} not found")

            # Check reviews
            reviews = conn.execute(
                """SELECT COUNT(*) AS total,
                          COUNT(CASE WHEN status = 'completed' THEN 1 END) AS completed,
                          COUNT(CASE WHEN on_track = 0 THEN 1 END) AS off_track,
                          COALESCE(SUM(off_the_job_hours), 0) AS total_otj,
                          MAX(off_the_job_target) AS otj_target
                   FROM progress_reviews WHERE learner_link_id = ?""",
                (learner_link_id,),
            ).fetchone()

            # Check sign-offs
            sign_offs = conn.execute(
                """SELECT COUNT(DISTINCT eso.signer_type) AS signed_types
                   FROM employer_sign_offs eso
                   JOIN progress_reviews pr ON pr.id = eso.review_id
                   WHERE pr.learner_link_id = ?
                   AND pr.review_type = 'gateway'""",
                (learner_link_id,),
            ).fetchone()

            otj_target = reviews["otj_target"] or 0
            otj_met = reviews["total_otj"] >= otj_target if otj_target > 0 else False
            gateway_signed = (sign_offs["signed_types"] or 0) >= 3 if sign_offs else False

            return {
                "learner_link_id": learner_link_id,
                "total_reviews": reviews["total"],
                "completed_reviews": reviews["completed"],
                "otj_hours": reviews["total_otj"],
                "otj_target": otj_target,
                "otj_met": otj_met,
                "gateway_signed": gateway_signed,
                "ready_for_epa": otj_met and gateway_signed and reviews["off_track"] == 0,
            }
        except EmployerPortalError:
            raise
        except Exception as exc:
            logger.error("Failed to get EPA readiness: %s", exc)
            raise EmployerPortalError(f"Failed to get EPA readiness: {exc}") from exc
        finally:
            conn.close()
