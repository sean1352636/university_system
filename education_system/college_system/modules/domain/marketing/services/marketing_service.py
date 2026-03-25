"""Marketing & Open Days service — events, registrations, campaigns."""

from education_system.college_system.core.exceptions import MarketingError
from education_system.college_system.infrastructure.database.db import connect

from education_system.college_system.core.sql_safety import escape_like
import logging

logger = logging.getLogger(__name__)


class MarketingService:
    """Service for managing open day events, registrations, and marketing campaigns."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Open Days ──

    def create_event(self, event_name: str, event_date: str,
                     event_type: str = "open_day", start_time: str | None = None,
                     end_time: str | None = None, capacity: int | None = None,
                     location: str | None = None, description: str | None = None,
                     target_audience: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO open_days
                   (event_name, event_date, event_type, start_time, end_time,
                    capacity, location, description, target_audience)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_name, event_date, event_type, start_time, end_time,
                 capacity, location, description, target_audience),
            )
            conn.commit()
            logger.info("Open day event created: %s on %s", event_name, event_date)
            row = conn.execute("SELECT * FROM open_days WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to create event: {e}") from e
        finally:
            conn.close()

    def list_events(self, status: str | None = None,
                    event_type: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM open_days WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if event_type:
                sql += " AND event_type = ?"
                params.append(event_type)
            sql += " ORDER BY event_date DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_event(self, event_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM open_days WHERE id = ?", (event_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_event(self, event_id: int, **updates) -> dict:
        allowed = {"event_name", "event_date", "event_type", "start_time", "end_time",
                    "capacity", "registrations", "attendees", "location", "description",
                    "target_audience", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise MarketingError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM open_days WHERE id = ?", (event_id,)).fetchone()
            if not existing:
                raise MarketingError("Event not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE open_days SET {set_parts} WHERE id = ?",
                         (*updates.values(), event_id))
            conn.commit()
            logger.info("Event updated: id=%d", event_id)
            row = conn.execute("SELECT * FROM open_days WHERE id = ?", (event_id,)).fetchone()
            return dict(row)
        except MarketingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to update event: {e}") from e
        finally:
            conn.close()

    def delete_event(self, event_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM open_days WHERE id = ?", (event_id,)).fetchone()
            if not existing:
                raise MarketingError("Event not found.")
            conn.execute("DELETE FROM open_day_registrations WHERE event_id = ?", (event_id,))
            conn.execute("DELETE FROM open_days WHERE id = ?", (event_id,))
            conn.commit()
            logger.info("Event deleted (cascade): id=%d", event_id)
            return True
        except MarketingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to delete event: {e}") from e
        finally:
            conn.close()

    # ── Open Day Registrations ──

    def create_registration(self, event_id: int, student_name: str,
                            email: str | None = None, phone: str | None = None,
                            school: str | None = None, year_group: str | None = None,
                            interests: str | None = None) -> dict:
        conn = self._conn()
        try:
            event = conn.execute("SELECT id FROM open_days WHERE id = ?", (event_id,)).fetchone()
            if not event:
                raise MarketingError("Event not found.")
            conn.execute(
                """INSERT INTO open_day_registrations
                   (event_id, student_name, email, phone, school, year_group, interests)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event_id, student_name, email, phone, school, year_group, interests),
            )
            conn.execute(
                "UPDATE open_days SET registrations = registrations + 1 WHERE id = ?",
                (event_id,),
            )
            conn.commit()
            logger.info("Registration created: event=%d name=%s", event_id, student_name)
            row = conn.execute(
                "SELECT * FROM open_day_registrations WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except MarketingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to create registration: {e}") from e
        finally:
            conn.close()

    def list_registrations(self, event_id: int | None = None,
                           search: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM open_day_registrations WHERE 1=1"
            params: list = []
            if event_id:
                sql += " AND event_id = ?"
                params.append(event_id)
            if search:
                sql += " AND (student_name LIKE ? OR email LIKE ? OR school LIKE ?)"
                escaped = escape_like(search)
                like = f"%{escaped}%"
                params.extend([like, like, like])
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_registration(self, reg_id: int, **updates) -> dict:
        allowed = {"student_name", "email", "phone", "school", "year_group",
                    "interests", "attended", "follow_up_sent", "applied"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise MarketingError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM open_day_registrations WHERE id = ?", (reg_id,)
            ).fetchone()
            if not existing:
                raise MarketingError("Registration not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE open_day_registrations SET {set_parts} WHERE id = ?",
                (*updates.values(), reg_id),
            )
            conn.commit()
            logger.info("Registration updated: id=%d", reg_id)
            row = conn.execute(
                "SELECT * FROM open_day_registrations WHERE id = ?", (reg_id,)
            ).fetchone()
            return dict(row)
        except MarketingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to update registration: {e}") from e
        finally:
            conn.close()

    def delete_registration(self, reg_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT event_id FROM open_day_registrations WHERE id = ?", (reg_id,)
            ).fetchone()
            if not existing:
                raise MarketingError("Registration not found.")
            event_id = existing["event_id"]
            conn.execute("DELETE FROM open_day_registrations WHERE id = ?", (reg_id,))
            conn.execute(
                "UPDATE open_days SET registrations = MAX(0, registrations - 1) WHERE id = ?",
                (event_id,),
            )
            conn.commit()
            logger.info("Registration deleted: id=%d", reg_id)
            return True
        except MarketingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to delete registration: {e}") from e
        finally:
            conn.close()

    def mark_attended(self, reg_id: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id, event_id, attended FROM open_day_registrations WHERE id = ?",
                (reg_id,),
            ).fetchone()
            if not existing:
                raise MarketingError("Registration not found.")
            if not existing["attended"]:
                conn.execute(
                    "UPDATE open_day_registrations SET attended = 1 WHERE id = ?",
                    (reg_id,),
                )
                conn.execute(
                    "UPDATE open_days SET attendees = attendees + 1 WHERE id = ?",
                    (existing["event_id"],),
                )
                conn.commit()
                logger.info("Registration marked attended: id=%d", reg_id)
            row = conn.execute(
                "SELECT * FROM open_day_registrations WHERE id = ?", (reg_id,)
            ).fetchone()
            return dict(row)
        except MarketingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to mark attended: {e}") from e
        finally:
            conn.close()

    def mark_follow_up(self, reg_id: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM open_day_registrations WHERE id = ?", (reg_id,)
            ).fetchone()
            if not existing:
                raise MarketingError("Registration not found.")
            conn.execute(
                "UPDATE open_day_registrations SET follow_up_sent = 1 WHERE id = ?",
                (reg_id,),
            )
            conn.commit()
            logger.info("Follow-up marked: id=%d", reg_id)
            row = conn.execute(
                "SELECT * FROM open_day_registrations WHERE id = ?", (reg_id,)
            ).fetchone()
            return dict(row)
        except MarketingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to mark follow-up: {e}") from e
        finally:
            conn.close()

    # ── Marketing Campaigns ──

    def create_campaign(self, campaign_name: str, campaign_type: str = "digital",
                        start_date: str | None = None, end_date: str | None = None,
                        budget: float = 0, target_audience: str | None = None,
                        channels: str | None = None, notes: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO marketing_campaigns
                   (campaign_name, campaign_type, start_date, end_date,
                    budget, target_audience, channels, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (campaign_name, campaign_type, start_date, end_date,
                 budget, target_audience, channels, notes),
            )
            conn.commit()
            logger.info("Campaign created: %s", campaign_name)
            row = conn.execute(
                "SELECT * FROM marketing_campaigns WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to create campaign: {e}") from e
        finally:
            conn.close()

    def list_campaigns(self, status: str | None = None,
                       campaign_type: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM marketing_campaigns WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if campaign_type:
                sql += " AND campaign_type = ?"
                params.append(campaign_type)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_campaign(self, campaign_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM marketing_campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_campaign(self, campaign_id: int, **updates) -> dict:
        allowed = {"campaign_name", "campaign_type", "start_date", "end_date",
                    "budget", "spend", "target_audience", "channels",
                    "impressions", "enquiries", "applications", "notes", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise MarketingError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM marketing_campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
            if not existing:
                raise MarketingError("Campaign not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE marketing_campaigns SET {set_parts} WHERE id = ?",
                (*updates.values(), campaign_id),
            )
            conn.commit()
            logger.info("Campaign updated: id=%d", campaign_id)
            row = conn.execute(
                "SELECT * FROM marketing_campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
            return dict(row)
        except MarketingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to update campaign: {e}") from e
        finally:
            conn.close()

    def delete_campaign(self, campaign_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM marketing_campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
            if not existing:
                raise MarketingError("Campaign not found.")
            conn.execute("DELETE FROM marketing_campaigns WHERE id = ?", (campaign_id,))
            conn.commit()
            logger.info("Campaign deleted: id=%d", campaign_id)
            return True
        except MarketingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarketingError(f"Failed to delete campaign: {e}") from e
        finally:
            conn.close()

    # ── Statistics ──

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            ev = conn.execute(
                "SELECT COUNT(*) as total FROM open_days"
            ).fetchone()
            reg = conn.execute(
                """SELECT COUNT(*) as total,
                          COALESCE(SUM(attended), 0) as attended,
                          COALESCE(SUM(follow_up_sent), 0) as followed_up,
                          COALESCE(SUM(applied), 0) as applied
                   FROM open_day_registrations"""
            ).fetchone()
            camp = conn.execute(
                """SELECT COUNT(*) as total,
                          COALESCE(SUM(budget), 0) as total_budget,
                          COALESCE(SUM(spend), 0) as total_spend,
                          COALESCE(SUM(impressions), 0) as total_impressions,
                          COALESCE(SUM(enquiries), 0) as total_enquiries,
                          COALESCE(SUM(applications), 0) as total_applications
                   FROM marketing_campaigns"""
            ).fetchone()

            total_reg = reg["total"] if reg["total"] else 0
            attendance_rate = (reg["attended"] / total_reg * 100) if total_reg > 0 else 0
            application_rate = (reg["applied"] / total_reg * 100) if total_reg > 0 else 0

            total_budget = camp["total_budget"] if camp["total_budget"] else 0
            total_spend = camp["total_spend"] if camp["total_spend"] else 0
            budget_utilisation = (total_spend / total_budget * 100) if total_budget > 0 else 0

            return {
                "total_events": ev["total"],
                "total_registrations": total_reg,
                "total_attended": reg["attended"],
                "attendance_rate": round(attendance_rate, 1),
                "total_followed_up": reg["followed_up"],
                "total_applied": reg["applied"],
                "application_rate": round(application_rate, 1),
                "total_campaigns": camp["total"],
                "total_budget": round(total_budget, 2),
                "total_spend": round(total_spend, 2),
                "budget_utilisation": round(budget_utilisation, 1),
                "total_impressions": camp["total_impressions"],
                "total_enquiries": camp["total_enquiries"],
                "total_applications": camp["total_applications"],
            }
        finally:
            conn.close()
