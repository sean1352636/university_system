"""ShiftsMixin — auto-split from bakery_shop.py."""
from education_system.post_18.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class ShiftsMixin:
    def list_active_shifts(self):
        return self._query("""SELECT id, staff, role, clock_in
                              FROM bakery_staff_shifts
                              WHERE status='open'
                              ORDER BY clock_in""")

    def list_recent_shifts(self, limit=50):
        return self._query("""SELECT id, staff, role, clock_in, clock_out,
                                     status, notes
                              FROM bakery_staff_shifts
                              ORDER BY id DESC LIMIT ?""", (int(limit),))

    def clock_in(self, *, role=None, notes=""):
        if not self.current_user:
            return None
        try:
            existing = self._query("""SELECT id FROM bakery_staff_shifts
                                      WHERE staff=? AND status='open' LIMIT 1""",
                                    (self.current_user,))
            if existing:
                return existing[0][0]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                cur = conn.execute("""INSERT INTO bakery_staff_shifts
                              (staff, role, clock_in, notes, status)
                              VALUES (?, ?, ?, ?, 'open')""",
                              (self.current_user, role or self.user_type,
                               now, notes))
                sid = cur.lastrowid
                conn.commit()
            finally:
                conn.close()
            logger.info("Shift clock-in id=%s staff=%s role=%s",
                        sid, self.current_user, role)
            return sid
        except Exception:
            logger.exception("clock_in failed")
            return None

    def clock_out(self):
        if not self.current_user:
            return False
        try:
            existing = self._query("""SELECT id FROM bakery_staff_shifts
                                      WHERE staff=? AND status='open' LIMIT 1""",
                                    (self.current_user,))
            if not existing:
                return False
            sid = existing[0][0]
            self._exec("""UPDATE bakery_staff_shifts
                          SET clock_out=?, status='closed' WHERE id=?""",
                       (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sid))
            logger.info("Shift clock-out id=%s staff=%s", sid, self.current_user)
            return True
        except Exception:
            logger.exception("clock_out failed")
            return False

    def attribution_staff(self):
        """Who currently has an open shift? Returns the first one as the
        attributed staff member for new sales."""
        active = self.list_active_shifts()
        return active[0][1] if active else None

