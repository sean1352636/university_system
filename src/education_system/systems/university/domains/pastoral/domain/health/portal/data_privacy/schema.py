"""Schema bootstrap for the health portal's integration and security tables.

Every function here is idempotent: it creates tables if missing, adds
compatibility/alias columns for older schemas, and backfills them.
"""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.pastoral.infrastructure.health.storage import sqlite3
from education_system.systems.university.domains.pastoral.domain.health.services import get_connection

def ensure_integration_schema():
    """
    Ensure integrations tables exist + expose expected columns.
    Safe to call repeatedly.
    """
    conn = get_connection()
    try:
        c = conn.cursor()

        # 1) Base tables (created if missing)
        c.execute("""
            CREATE TABLE IF NOT EXISTS integration_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT,          -- e.g., 'insurance','lab','hl7','fhir'
                system   TEXT,          -- optional: vendor/system name
                event_type TEXT,
                status TEXT,            -- success, error, pending
                message TEXT,
                correlation_id TEXT,
                http_status INTEGER,
                duration_ms INTEGER,
                endpoint TEXT,
                payload TEXT,
                response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS insurance_integration_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT,
                patient_id TEXT,
                event_type TEXT,        -- submitted/approved/denied/cancelled
                status TEXT,
                external_id TEXT,
                correlation_id TEXT,
                payload TEXT,
                response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS lab_integration_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                patient_id TEXT,
                test_code TEXT,
                event_type TEXT,        -- order_sent/result_received/ack/error
                status TEXT,
                external_id TEXT,
                correlation_id TEXT,
                payload TEXT,
                response TEXT,
                result_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                queue_name TEXT,        -- optional: 'default','labs','claims'
                entity_type TEXT,       -- e.g., 'student','claim','lab_order'
                entity_id TEXT,
                operation TEXT,         -- upsert/delete/sync
                payload TEXT,
                priority INTEGER DEFAULT 5,
                attempts INTEGER DEFAULT 0,
                next_attempt_at TEXT,
                last_error TEXT,
                status TEXT,            -- pending/locked/failed/done
                locked_by TEXT,
                locked_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            )
        """)

        # 2) Add compatibility/alias columns if older schemas exist
        def cols(table):
            from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
            validate_identifier(table, "table")
            c.execute("PRAGMA table_info([" + table + "])")
            return {r[1] for r in c.fetchall()}

        # integration_logs: accept 'service' and 'timestamp' aliases
        lg = cols("integration_logs")
        if "provider" not in lg and "service" in lg:
            c.execute("ALTER TABLE integration_logs ADD COLUMN provider TEXT")
            c.execute("UPDATE integration_logs SET provider = service WHERE provider IS NULL")
        if "created_at" not in lg and "timestamp" in lg:
            c.execute("ALTER TABLE integration_logs ADD COLUMN created_at TEXT")
            c.execute("UPDATE integration_logs SET created_at = timestamp WHERE created_at IS NULL")

        # insurance_integration_events: common extras
        ins = cols("insurance_integration_events")
        if "event_time" in ins and "created_at" not in ins:
            c.execute("ALTER TABLE insurance_integration_events ADD COLUMN created_at TEXT")
            c.execute("UPDATE insurance_integration_events SET created_at = event_time WHERE created_at IS NULL")
        if "updated_at" not in ins:
            c.execute("ALTER TABLE insurance_integration_events ADD COLUMN updated_at TEXT")

        # lab_integration_events: common extras
        lab = cols("lab_integration_events")
        if "event_time" in lab and "created_at" not in lab:
            c.execute("ALTER TABLE lab_integration_events ADD COLUMN created_at TEXT")
            c.execute("UPDATE lab_integration_events SET created_at = event_time WHERE created_at IS NULL")
        if "updated_at" not in lab:
            c.execute("ALTER TABLE lab_integration_events ADD COLUMN updated_at TEXT")

        # sync_queue: make sure status/priority/attempts exist
        sq = cols("sync_queue")
        if "status" not in sq:
            c.execute("ALTER TABLE sync_queue ADD COLUMN status TEXT")
            c.execute("UPDATE sync_queue SET status = COALESCE(status,'pending')")
        if "priority" not in sq:
            c.execute("ALTER TABLE sync_queue ADD COLUMN priority INTEGER DEFAULT 5")
        if "attempts" not in sq:
            c.execute("ALTER TABLE sync_queue ADD COLUMN attempts INTEGER DEFAULT 0")

        # 3) Indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_il_provider      ON integration_logs(provider)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_il_event_type    ON integration_logs(event_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_il_created       ON integration_logs(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_il_correlation   ON integration_logs(correlation_id)")

        c.execute("CREATE INDEX IF NOT EXISTS idx_ins_claim        ON insurance_integration_events(claim_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ins_status       ON insurance_integration_events(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ins_created      ON insurance_integration_events(created_at)")

        c.execute("CREATE INDEX IF NOT EXISTS idx_lab_order        ON lab_integration_events(order_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_lab_status       ON lab_integration_events(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_lab_created      ON lab_integration_events(created_at)")

        c.execute("CREATE INDEX IF NOT EXISTS idx_sq_status        ON sync_queue(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sq_next_attempt  ON sync_queue(next_attempt_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sq_priority      ON sync_queue(priority)")

        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


def ensure_security_schema():
    """
    Ensure security tables exist and expose the columns your UI expects.
    Idempotent; adds compatibility/alias columns and backfills them.
    """
    conn = get_connection()
    try:
        c = conn.cursor()

        # ----- Core security tables -----
        c.execute("""
            CREATE TABLE IF NOT EXISTS data_privacy_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_key TEXT UNIQUE NOT NULL,
                value TEXT,
                description TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS encryption_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT UNIQUE NOT NULL,
                public_key TEXT,
                private_key_encrypted TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                rotated_at TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        # ----- RBAC (minimal shape; names added below if missing) -----
        c.execute("CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        c.execute("CREATE TABLE IF NOT EXISTS permissions (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                PRIMARY KEY (role_id, permission_id)
            )
        """)

        # Utility: list columns
        def cols_of(table: str) -> set[str]:
            from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
            validate_identifier(table, "table")
            c.execute("PRAGMA table_info([" + table + "])")
            return {row[1] for row in c.fetchall()}

        # ----- Ensure friendly columns on roles/permissions -----
        rcols = cols_of("roles")
        if not {"name", "role_name", "title", "label", "code"} & rcols:
            c.execute("ALTER TABLE roles ADD COLUMN name TEXT")

        pcols = cols_of("permissions")
        if not {"name", "permission_name", "permission", "code", "label"} & pcols:
            c.execute("ALTER TABLE permissions ADD COLUMN name TEXT")

        # ----- Compatibility columns for data_privacy_settings -----
        spcols = cols_of("data_privacy_settings")
        if "policy_name" not in spcols:
            c.execute("ALTER TABLE data_privacy_settings ADD COLUMN policy_name TEXT")
            c.execute("UPDATE data_privacy_settings SET policy_name = policy_key WHERE policy_name IS NULL")
        if "status" not in spcols:
            c.execute("ALTER TABLE data_privacy_settings ADD COLUMN status TEXT")
            c.execute("""
                UPDATE data_privacy_settings
                   SET status = CASE
                                 WHEN LOWER(COALESCE(value, '')) IN ('1','true','on','enabled','enable') THEN 'enabled'
                                 WHEN LOWER(COALESCE(value, '')) IN ('0','false','off','disabled','disable') THEN 'disabled'
                                 ELSE value
                               END
                 WHERE status IS NULL
            """)
        if "last_updated" not in spcols:
            c.execute("ALTER TABLE data_privacy_settings ADD COLUMN last_updated TEXT")
            c.execute("UPDATE data_privacy_settings SET last_updated = updated_at WHERE last_updated IS NULL")

        # ----- Compatibility columns for encryption_keys -----
        ekcols = cols_of("encryption_keys")
        if "algorithm" not in ekcols:
            c.execute("ALTER TABLE encryption_keys ADD COLUMN algorithm TEXT")
            c.execute("UPDATE encryption_keys SET algorithm = COALESCE(algorithm, 'unknown')")
        if "status" not in ekcols:
            c.execute("ALTER TABLE encryption_keys ADD COLUMN status TEXT")
            c.execute("""
                UPDATE encryption_keys
                   SET status = CASE COALESCE(is_active, 0)
                                  WHEN 1 THEN 'active'
                                  ELSE 'inactive'
                                END
                 WHERE status IS NULL
            """)

        # ===================== Incident Management =====================
        # Base tables
        c.execute("""
            CREATE TABLE IF NOT EXISTS security_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT UNIQUE,            -- human-friendly ref (e.g., INC-2025-0001)
                summary TEXT,
                description TEXT,
                severity TEXT,                      -- low/medium/high/critical
                status TEXT,                        -- open/contained/eradicated/monitoring/closed
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reported_by TEXT,
                assigned_to TEXT,
                category TEXT,                      -- phishing, malware, policy_violation, etc.
                source TEXT,                        -- system/user/external
                affected_user TEXT,
                containment TEXT,
                eradication TEXT,
                recovery TEXT,
                resolved_at TEXT,
                root_cause TEXT,
                tags TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS security_incident_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_pk INTEGER NOT NULL,       -- FK to security_incidents.id
                event_time TEXT DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT,                    -- note, containment, escalation, closure, etc.
                details TEXT,
                actor TEXT
            )
        """)
        # Lightweight indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_inc_status    ON security_incidents(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_inc_severity  ON security_incidents(severity)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_inc_detected  ON security_incidents(detected_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_inc_incident  ON security_incidents(incident_id)")

        # Add common alias/compat columns + backfill where applicable
        icols = cols_of("security_incidents")

        # title <-> summary
        if "title" not in icols:
            c.execute("ALTER TABLE security_incidents ADD COLUMN title TEXT")
            c.execute("UPDATE security_incidents SET title = COALESCE(title, summary)")
            icols.add("title")
        if "summary" not in icols:
            c.execute("ALTER TABLE security_incidents ADD COLUMN summary TEXT")
            c.execute("UPDATE security_incidents SET summary = COALESCE(summary, title)")
            icols.add("summary")

        # opened_at / closed_at aliases
        if "opened_at" not in icols:
            c.execute("ALTER TABLE security_incidents ADD COLUMN opened_at TEXT")
            c.execute("UPDATE security_incidents SET opened_at = detected_at WHERE opened_at IS NULL")
            icols.add("opened_at")
        if "closed_at" not in icols:
            c.execute("ALTER TABLE security_incidents ADD COLUMN closed_at TEXT")
            c.execute("UPDATE security_incidents SET closed_at = resolved_at WHERE closed_at IS NULL")
            icols.add("closed_at")

        # priority alias for severity
        if "priority" not in icols:
            c.execute("ALTER TABLE security_incidents ADD COLUMN priority TEXT")
            c.execute("""
                UPDATE security_incidents
                   SET priority = CASE LOWER(COALESCE(severity, ''))
                                    WHEN 'critical' THEN 'p0'
                                    WHEN 'high'     THEN 'p1'
                                    WHEN 'medium'   THEN 'p2'
                                    WHEN 'low'      THEN 'p3'
                                    ELSE NULL
                                  END
                 WHERE priority IS NULL
            """)
            icols.add("priority")

        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


def _first_existing_column(conn: sqlite3.Connection, table: str, candidates: list[str]) -> str | None:
    from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
    validate_identifier(table, "table")
    cur = conn.cursor()
    cur.execute("PRAGMA table_info([" + table + "])")
    cols = {row[1] for row in cur.fetchall()}
    for col in candidates:
        if col in cols:
            return col
    return None
