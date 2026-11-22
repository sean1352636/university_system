from .repositories import HealthRepository

class AuditRepository(HealthRepository):
    def recent(self, limit: int = 100):
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
