"""FeedbackKitchenMixin — auto-split from bakery_shop.py."""
from education_system.post_18.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class FeedbackKitchenMixin:
    def submit_feedback(self, *, category, subject, message, rating=None,
                         order_id=None):
        if not message:
            return None
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ticket_id = None
            # Best-effort: route complaints to the existing helpdesk.
            if (category or "").lower() == "complaint":
                ticket_id = self._open_helpdesk_ticket(subject, message)
            conn = self._connect()
            try:
                cur = conn.execute("""INSERT INTO bakery_feedback
                                  (user, order_id, category, subject, message,
                                   rating, helpdesk_ticket_id, status,
                                   created_at, updated_at)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
                                  (self.current_user or "Guest", order_id,
                                   category, subject, message,
                                   int(rating) if rating else None,
                                   ticket_id, now, now))
                fid = cur.lastrowid
                conn.commit()
            finally:
                conn.close()
            logger.info("Feedback submitted id=%s user=%s category=%s "
                        "ticket=%s", fid, self.current_user, category,
                        ticket_id)
            return fid
        except Exception:
            logger.exception("submit_feedback failed")
            return None

    def _open_helpdesk_ticket(self, subject, body):
        """Best-effort: open a helpdesk ticket via the central helpdesk
        services. Returns the ticket ref or None."""
        try:
            from education_system.post_18.university_system.modules.domain.helpdesk import (
                tickets as helpdesk_tickets,
            )
            ref = helpdesk_tickets.create_ticket(
                title=f"[Bakery] {subject}",
                description=body,
                user=self.current_user or "Guest",
                category="bakery",
            )
            return str(ref) if ref else None
        except Exception:
            logger.debug("Helpdesk routing skipped (module unavailable)",
                         exc_info=True)
            return None

    def list_feedback(self, *, status=None):
        sql = """SELECT id, user, order_id, category, subject, message,
                        rating, helpdesk_ticket_id, status, response,
                        created_at FROM bakery_feedback"""
        params = ()
        if status:
            sql += " WHERE status=?"; params = (status,)
        sql += " ORDER BY id DESC"
        return self._query(sql, params)

    def respond_to_feedback(self, fid, response, *, mark_closed=True):
        try:
            self._exec("""UPDATE bakery_feedback
                          SET response=?, status=?, handled_by=?,
                              updated_at=?
                          WHERE id=?""",
                       (response, "closed" if mark_closed else "open",
                        self.current_user or "admin",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), fid))
            logger.info("Feedback id=%s responded-to by %s",
                        fid, self.current_user)
            return True
        except Exception:
            logger.exception("respond_to_feedback failed")
            return False

    def get_kitchen_stage(self, preorder_id):
        rows = self._query(
            "SELECT stage, updated_at FROM bakery_kitchen_status WHERE preorder_id=?",
            (preorder_id,))
        return rows[0][0] if rows else "queued"

    def set_kitchen_stage(self, preorder_id, stage, notes=""):
        valid = ("queued", "prepping", "ready")
        if stage not in valid:
            return False
        try:
            self._exec("""INSERT OR REPLACE INTO bakery_kitchen_status
                          (preorder_id, stage, updated_at, updated_by, notes)
                          VALUES (?, ?, ?, ?, ?)""",
                       (preorder_id, stage,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        self.current_user or "kitchen", notes))
            logger.info("Kitchen pre-order id=%s -> %s",
                        preorder_id, stage)
            return True
        except Exception:
            logger.exception("set_kitchen_stage failed")
            return False

