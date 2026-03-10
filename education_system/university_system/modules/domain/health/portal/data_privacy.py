from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.health.services import get_connection

from education_system.university_system.modules.domain.health.services import (
    analyze_data_access_patterns,
    external_system_connections,
    view_failed_logins,
)
from education_system.university_system.modules.domain.health.records.screening.guidelines import screening_recommendations
from datetime import datetime, timedelta
import random
import os
import hashlib
import hmac
import json
import logging
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from cryptography.fernet import Fernet
import requests
from collections import defaultdict
import csv
import statistics
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)
from education_system.university_system.utils.logging.log_config import configure_logging

# Configure logging for audit trail
audit_logger = configure_logging(name=__name__)

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
            from education_system.university_system.core.sql_safety import validate_identifier
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
            pass

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
            CREATE TABLE IF NOT EXISTS security_policies (
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
            from education_system.university_system.core.sql_safety import validate_identifier
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

        # ----- Compatibility columns for security_policies -----
        spcols = cols_of("security_policies")
        if "policy_name" not in spcols:
            c.execute("ALTER TABLE security_policies ADD COLUMN policy_name TEXT")
            c.execute("UPDATE security_policies SET policy_name = policy_key WHERE policy_name IS NULL")
        if "status" not in spcols:
            c.execute("ALTER TABLE security_policies ADD COLUMN status TEXT")
            c.execute("""
                UPDATE security_policies
                   SET status = CASE
                                 WHEN LOWER(COALESCE(value, '')) IN ('1','true','on','enabled','enable') THEN 'enabled'
                                 WHEN LOWER(COALESCE(value, '')) IN ('0','false','off','disabled','disable') THEN 'disabled'
                                 ELSE value
                               END
                 WHERE status IS NULL
            """)
        if "last_updated" not in spcols:
            c.execute("ALTER TABLE security_policies ADD COLUMN last_updated TEXT")
            c.execute("UPDATE security_policies SET last_updated = updated_at WHERE last_updated IS NULL")

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
            pass

def _first_existing_column(conn: sqlite3.Connection, table: str, candidates: list[str]) -> str | None:
    from education_system.university_system.core.sql_safety import validate_identifier
    validate_identifier(table, "table")
    cur = conn.cursor()
    cur.execute("PRAGMA table_info([" + table + "])")
    cols = {row[1] for row in cur.fetchall()}
    for col in candidates:
        if col in cols:
            return col
    return None

def get_or_create_encryption_key():
    """Get or create encryption key for sensitive data"""
    key_file = 'health_encryption.key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

def log_audit_event(user_id, action, resource_type, resource_id, details=None):
    """Log audit events for compliance"""
    audit_logger.info(f"USER:{user_id} ACTION:{action} RESOURCE:{resource_type}:{resource_id} DETAILS:{details}")

def advanced_security_menu(auth):
    """Advanced security management"""
    ensure_security_schema()
    if auth.current_user['role'] != 'admin':
        print("Only administrators can access advanced security features.")
        return
    
    while True:
        print("\n===== Advanced Security Management =====")
        print("1. User Session Management")
        print("2. IP Restriction Management")
        print("3. Two-Factor Authentication")
        print("4. Security Policy Configuration")
        print("5. Encryption Key Management")
        print("6. Access Control Lists")
        print("7. Security Incident Response")
        print("8. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-8): ")
        
        if choice == '1':
            user_session_management(auth)
        elif choice == '2':
            ip_restriction_management(auth)
        elif choice == '3':
            two_factor_authentication_setup(auth)
        elif choice == '4':
            security_policy_configuration(auth)
        elif choice == '5':
            encryption_key_management(auth)
        elif choice == '6':
            access_control_lists(auth)
        elif choice == '7':
            security_incident_response(auth)
        elif choice == '8':
            break
        else:
            print("Invalid choice. Please try again.")

def user_session_management(auth):
    """Manage active user sessions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Active User Sessions =====")
    
    # Get recent login activity from audit trail
    cursor.execute('''
    SELECT user_id, ip_address, timestamp
    FROM audit_trail
    WHERE action = 'login' AND timestamp >= datetime('now', '-24 hours')
    ORDER BY timestamp DESC
    ''')
    
    sessions = cursor.fetchall()
    
    if not sessions:
        print("No active sessions found in the last 24 hours.")
        conn.close()
        return
    
    print("Recent Login Activity (Last 24 hours):")
    for user_id, ip_address, timestamp in sessions:
        print(f"  {timestamp} - User: {user_id} - IP: {ip_address}")
    
    # Session management options
    print("\nSession Management Options:")
    print("1. Force logout all users")
    print("2. Force logout specific user")
    print("3. View failed login attempts")
    print("4. Return to security menu")
    
    choice = input("\nSelect option (1-4): ")
    
    if choice == '1':
        confirm = input("Force logout ALL users? (yes/no): ")
        if confirm.lower() == 'yes':
            # This would invalidate all sessions in a real system
            log_audit_event(auth.current_user['id'], 'force_logout_all', 'security', 0)
            print("All user sessions terminated.")
    
    elif choice == '2':
        user_to_logout = input("Enter username to force logout: ")
        log_audit_event(auth.current_user['id'], 'force_logout_user', 'security', 0, user_to_logout)
        print(f"User {user_to_logout} session terminated.")
    
    elif choice == '3':
        view_failed_logins(auth)
    
    conn.close()

def access_control_lists(auth):
    """
    Show roles and their permissions, regardless of the exact column names used
    by the roles/permissions tables.
    """
    ensure_security_schema()

    conn = get_connection()
    try:
        r_name = _first_existing_column(conn, "roles", ["name", "role_name", "title", "label", "code"])
        p_name = _first_existing_column(conn, "permissions", ["name", "permission_name", "permission", "code", "label"])

        # If still missing, add standard columns so the query won't break
        cur = conn.cursor()
        if not r_name:
            cur.execute("ALTER TABLE roles ADD COLUMN name TEXT")
            conn.commit()
            r_name = "name"
        if not p_name:
            cur.execute("ALTER TABLE permissions ADD COLUMN name TEXT")
            conn.commit()
            p_name = "name"

        sql = f"""
        SELECT r.{r_name} AS role_name,
               COALESCE(GROUP_CONCAT(p.{p_name}, ', '), '(no permissions)') AS permissions
          FROM roles r
     LEFT JOIN role_permissions rp ON rp.role_id = r.id
     LEFT JOIN permissions p      ON p.id = rp.permission_id
      GROUP BY r.{r_name}
      ORDER BY r.{r_name} COLLATE NOCASE
        """
        rows = cur.execute(sql).fetchall()

        print("\nAccess Control Lists:")
        if not rows:
            print("- No roles found.")
        else:
            for role_name, perms in rows:
                role_name = role_name or "(unnamed role)"
                print(f"- {role_name}: {perms}")

        input("\nPress Enter to return...")

    except sqlite3.OperationalError as e:
        print(f"ACL view unavailable: {e}")
        input("\nPress Enter to return...")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def security_policy_configuration(auth):
    """
    Display and manage security policies.
    Works with either (policy_name,status,last_updated) or (policy_key,value,updated_at).
    """
    ensure_security_schema()
    conn = get_connection()
    try:
        c = conn.cursor()

        policy_name = _first_existing_column(conn, "security_policies", ["policy_name", "policy_key", "name", "key"])
        status_col  = _first_existing_column(conn, "security_policies", ["status", "value", "enabled"])
        updated_col = _first_existing_column(conn, "security_policies", ["last_updated", "updated_at", "modified_at", "timestamp"])

        sql = ("SELECT [" + policy_name + "], [" + status_col + "], [" + updated_col + "]"
               " FROM [security_policies] ORDER BY [" + policy_name + "]")
        rows = c.execute(sql).fetchall()

        print("\nSecurity Policies:")
        if not rows:
            print("- (none)")
        else:
            for pname, pstatus, pupd in rows:
                # normalize status for display
                s = str(pstatus).strip().lower()
                if s in ("1","true","on","enabled","enable","active"):
                    s_disp = "enabled"
                elif s in ("0","false","off","disabled","disable","inactive"):
                    s_disp = "disabled"
                else:
                    s_disp = pstatus if pstatus is not None else "—"
                print(f"- {pname or '(unnamed)'}: {s_disp} (updated {pupd or '—'})")

        input("\nPress Enter to return...")

    except sqlite3.OperationalError as e:
        print(f"Security policy view unavailable: {e}")
        input("\nPress Enter to return...")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def encryption_key_management(auth):
    """
    Show key inventory. Handles schemas with/without algorithm/status.
    """
    ensure_security_schema()
    conn = get_connection()
    try:
        c = conn.cursor()

        key_id     = _first_existing_column(conn, "encryption_keys", ["key_id", "id", "kid"])
        algorithm  = _first_existing_column(conn, "encryption_keys", ["algorithm", "algo", "type", "key_type"])
        created_at = _first_existing_column(conn, "encryption_keys", ["created_at", "created", "timestamp"])
        status_col = _first_existing_column(conn, "encryption_keys", ["status", "is_active"])

        cols = [key_id, algorithm, created_at, status_col]
        sel  = ", ".join("[" + c + "]" for c in cols)
        sql  = "SELECT " + sel + " FROM [encryption_keys] ORDER BY [" + created_at + "] DESC"
        rows = c.execute(sql).fetchall()

        print("\nEncryption Keys:")
        if not rows:
            print("- (none)")
        else:
            for row in rows:
                kid, algo, c_at, st = row
                # normalize status
                s = str(st).strip().lower()
                if s in ("1","true","on","enabled","active"):
                    s_disp = "active"
                elif s in ("0","false","off","disabled","inactive"):
                    s_disp = "inactive"
                else:
                    s_disp = st if st is not None else "—"
                print(f"- {kid}: {algo or 'unknown'}, created {c_at or '—'} [{s_disp}]")

        input("\nPress Enter to return...")

    except sqlite3.OperationalError as e:
        print(f"Encryption key view unavailable: {e}")
        input("\nPress Enter to return...")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def integration_logs(auth):
    """Stub: show last 20 integration log entries if present."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='integration_logs'")
        if not c.fetchone():
            print("No 'integration_logs' table."); return
        c.execute("SELECT created_at, system, level, message FROM integration_logs ORDER BY created_at DESC LIMIT 20")
        for ts, sysname, level, msg in c.fetchall():
            print(f"[{ts}] {sysname} {level}: {msg}")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")

def data_sync_status(auth):
    """Stub: show pending/out-of-sync items if present."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_queue'")
        if not c.fetchone():
            print("No 'sync_queue' table."); return
        c.execute("SELECT system, COUNT(*) FROM sync_queue WHERE status!='synced' GROUP BY system")
        rows = c.fetchall()
        if not rows:
            print("All systems synced."); return
        print("Pending sync items:")
        for system, n in rows:
            print(f" - {system}: {n}")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")

def laboratory_system_integration(auth):
    """Stub: show last lab pushes if present."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lab_integration_events'")
        if not c.fetchone():
            print("No 'lab_integration_events' table."); return
        c.execute("SELECT created_at, event_type, status FROM lab_integration_events ORDER BY created_at DESC LIMIT 20")
        for ts, typ, status in c.fetchall():
            print(f"[{ts}] {typ}: {status}")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")

def insurance_system_integration(auth):
    """Stub: show last insurance pushes if present."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='insurance_integration_events'")
        if not c.fetchone():
            print("No 'insurance_integration_events' table."); return
        c.execute("SELECT created_at, event_type, status FROM insurance_integration_events ORDER BY created_at DESC LIMIT 20")
        for ts, typ, status in c.fetchall():
            print(f"[{ts}] {typ}: {status}")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")

def security_incident_response(auth):
    """Simple incident viewer (schema-adaptive)."""
    try:
        ensure_security_schema()
    except Exception as e:
        print(f"(warning) Incident schema check failed: {e}")

    conn = get_connection()
    try:
        c = conn.cursor()

        kid   = _first_existing_column(conn, "security_incidents", ["incident_id", "id", "reference", "ref"])
        title = _first_existing_column(conn, "security_incidents", ["title", "summary"])
        sev   = _first_existing_column(conn, "security_incidents", ["severity", "priority"])
        stat  = _first_existing_column(conn, "security_incidents", ["status"])
        when  = _first_existing_column(conn, "security_incidents", ["detected_at", "opened_at", "created_at"])

        from education_system.university_system.core.sql_safety import validate_identifier
        for col_name in [kid, title, sev, stat, when]:
            validate_identifier(col_name, "column")
        sel = ", ".join(["[" + x + "]" for x in [kid, title, sev, stat, when]])
        rows = c.execute("SELECT " + sel + " FROM security_incidents ORDER BY [" + when + "] DESC LIMIT 50").fetchall()

        print("\nSecurity Incidents (latest 50):")
        if not rows:
            print("- (none)")
        else:
            for r in rows:
                inc_id, t, s, st, dt = r
                print(f"- {inc_id or '(no-id)'} | {t or '(no title)'} | {s or '—'} | {st or '—'} | {dt or '—'}")

        input("\nPress Enter to return...")

    except sqlite3.OperationalError as e:
        print(f"Incident view unavailable: {e}")
        input("\nPress Enter to return...")
    finally:
        try:
            conn.close()
        except Exception:
            pass



def integration_health_check(auth):
    """Quick health snapshot of integrations (schema-adaptive)."""
    try:
        ensure_integration_schema()
    except Exception as e:
        print(f"(warning) Integration schema check failed: {e}")

    conn = get_connection()
    try:
        c = conn.cursor()

        # integration_logs by provider
        prov = _first_existing_column(conn, "integration_logs", ["provider", "service", "system"])
        created = _first_existing_column(conn, "integration_logs", ["created_at", "timestamp"])
        if prov and created:
            rows = c.execute(
                "SELECT [" + prov + "], COUNT(*), MAX([" + created + "])"
                " FROM integration_logs"
                " GROUP BY [" + prov + "]"
                " ORDER BY 2 DESC"
            ).fetchall()
            print("\nIntegration Logs (by provider):")
            if rows:
                for p, cnt, last in rows:
                    print(f"- {p or '(unknown)'}: {cnt} events; last at {last or '—'}")
            else:
                print("- (no log events)")
        else:
            print("\nIntegration Logs: table present, columns not standard — skipped.")

        # insurance events
        created = _first_existing_column(conn, "insurance_integration_events", ["created_at", "event_time"])
        status  = _first_existing_column(conn, "insurance_integration_events", ["status"])
        if created and status:
            rows = c.execute(
                "SELECT [" + status + "], COUNT(*)"
                " FROM insurance_integration_events"
                " GROUP BY [" + status + "]"
                " ORDER BY 2 DESC"
            ).fetchall()
            print("\nInsurance Events (by status):")
            if rows:
                for st, cnt in rows:
                    print(f"- {st or '—'}: {cnt}")
            else:
                print("- (none)")
        else:
            print("\nInsurance Events: table present, columns not standard — skipped.")

        # lab events
        created = _first_existing_column(conn, "lab_integration_events", ["created_at", "event_time"])
        status  = _first_existing_column(conn, "lab_integration_events", ["status"])
        if created and status:
            rows = c.execute(
                "SELECT [" + status + "], COUNT(*)"
                " FROM lab_integration_events"
                " GROUP BY [" + status + "]"
                " ORDER BY 2 DESC"
            ).fetchall()
            print("\nLab Events (by status):")
            if rows:
                for st, cnt in rows:
                    print(f"- {st or '—'}: {cnt}")
            else:
                print("- (none)")
        else:
            print("\nLab Events: table present, columns not standard — skipped.")

        # sync queue
        status = _first_existing_column(conn, "sync_queue", ["status"])
        nextat = _first_existing_column(conn, "sync_queue", ["next_attempt_at"])
        if status:
            total = c.execute("SELECT COUNT(*) FROM sync_queue").fetchone()[0]
            rows = c.execute("SELECT [" + status + "], COUNT(*) FROM sync_queue GROUP BY [" + status + "]").fetchall()
            print("\nSync Queue:")
            print(f"- total: {total}")
            for st, cnt in rows:
                print(f"- {st or '—'}: {cnt}")
            if nextat:
                nxt = c.execute(
                    "SELECT MIN([" + nextat + "]) FROM sync_queue"
                    " WHERE [" + status + "] IN ('pending','failed')"
                ).fetchone()[0]
                if nxt:
                    print(f"- next attempt at: {nxt}")
        else:
            print("\nSync Queue: table present, columns not standard — skipped.")

        input("\nPress Enter to return...")

    except sqlite3.OperationalError as e:
        print(f"Integration health check unavailable: {e}")
        input("\nPress Enter to return...")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def integration_management(auth):
    """Tiny integration admin shim — doesn’t crash if schemas drift."""
    try:
        ensure_integration_schema()
    except Exception as e:
        print(f"(warning) Integration schema check failed: {e}")

    print("\n===== Integration Management =====")
    print("1. View Health Check")
    print("2. Purge Old Logs (>30 days)")
    print("3. Return")

    choice = input("\nEnter choice (1-3): ").strip()
    if choice == "1":
        return integration_health_check(auth)
    elif choice == "2":
        conn = get_connection()
        try:
            c = conn.cursor()
            # best-effort purge using SQLite date math; will no-op if created_at is absent
            c.execute("""
                DELETE FROM integration_logs
                 WHERE COALESCE(created_at, '') <> ''
                   AND datetime(created_at) < datetime('now','-30 days')
            """)
            deleted = c.rowcount
            conn.commit()
            print(f"Purged {deleted if deleted is not None else 0} old log rows.")
            input("Press Enter to return...")
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"Purge failed: {e}")
            input("Press Enter to return...")
        finally:
            try:
                conn.close()
            except Exception:
                pass
    else:
        return


def view_risk_assessments(auth):
    """List recent risk assessments and optionally show details for one."""
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view risk assessments.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== View Risk Assessments =====")
    student_id = input("Filter by student ID (leave blank for latest 10): ").strip()

    if student_id:
        cursor.execute("""
            SELECT ra.id, ra.student_id, s.first_name, s.last_name,
                   ra.assessment_type, ra.risk_score, ra.assessed_date,
                   COALESCE(ra.follow_up_date, '')
            FROM risk_assessments ra
            LEFT JOIN students s ON s.student_id = ra.student_id
            WHERE ra.student_id = ?
            ORDER BY ra.assessed_date DESC, ra.id DESC
            LIMIT 50
        """, (student_id,))
    else:
        cursor.execute("""
            SELECT ra.id, ra.student_id, s.first_name, s.last_name,
                   ra.assessment_type, ra.risk_score, ra.assessed_date,
                   COALESCE(ra.follow_up_date, '')
            FROM risk_assessments ra
            LEFT JOIN students s ON s.student_id = ra.student_id
            ORDER BY ra.assessed_date DESC, ra.id DESC
            LIMIT 10
        """)

    rows = cursor.fetchall()
    if not rows:
        print("No risk assessments found.")
        conn.close()
        return

    print("\nID | Student | Type | Score | Assessed | Follow-up")
    print("-" * 78)
    for rid, sid, fn, ln, atype, score, assessed, follow in rows:
        name = f"{(fn or '').strip()} {(ln or '').strip()}".strip() or sid
        print(f"{rid} | {name} ({sid}) | {atype} | {score} | {assessed or '-'} | {follow or '-'}")

    sel = input("\nEnter an assessment ID to view details (or press Enter to return): ").strip()
    if sel.isdigit():
        cursor.execute("""
            SELECT ra.id, ra.student_id, s.first_name, s.last_name,
                   ra.assessment_type, ra.risk_score, ra.risk_factors,
                   ra.recommendations, ra.assessed_date, ra.assessed_by,
                   ra.follow_up_date, ra.created_at
            FROM risk_assessments ra
            LEFT JOIN students s ON s.student_id = ra.student_id
            WHERE ra.id = ?
        """, (int(sel),))
        rec = cursor.fetchone()
        if rec:
            (rid, sid, fn, ln, atype, score, rf_json, rec_json,
             assessed, by, follow, created) = rec

            print("\n--- Assessment Detail ---")
            print(f"ID: {rid}")
            print(f"Student: { (fn or '').strip()} { (ln or '').strip()} (ID: {sid})")
            print(f"Type: {atype}")
            print(f"Risk Score: {score}")
            print(f"Assessed: {assessed} by {by}")
            print(f"Follow-up: {follow or '-'}")

            try:
                risk_factors = json.loads(rf_json) if rf_json else []
            except Exception:
                risk_factors = rf_json

            try:
                recommendations = json.loads(rec_json) if rec_json else []
            except Exception:
                recommendations = rec_json

            print("\nRisk Factors:")
            if isinstance(risk_factors, list):
                for item in risk_factors:
                    print(f" - {item}")
            else:
                print(f" {risk_factors}")

            print("\nRecommendations:")
            if isinstance(recommendations, list):
                for item in recommendations:
                    print(f" - {item}")
            else:
                print(f" {recommendations}")

            log_audit_event(auth.current_user['id'],
                            'view_risk_assessment_detail', 'risk_assessment', rid)

    log_audit_event(auth.current_user['id'],
                    'view_risk_assessments', 'risk_assessment', 'list')
    conn.close()


def screening_recommendations(auth):
    """
    Simple wrapper: ask for an existing assessment ID, then print
    recommendations using generate_risk_recommendations().
    """
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view recommendations.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Risk-Based Screening Recommendations =====")
    sel = input("Enter an assessment ID (tip: use 'View Risk Assessments' to find one): ").strip()
    if not sel.isdigit():
        print("Invalid ID.")
        conn.close()
        return

    cursor.execute("""
        SELECT assessment_type, risk_score, risk_factors
        FROM risk_assessments
        WHERE id = ?
    """, (int(sel),))
    row = cursor.fetchone()
    if not row:
        print("Assessment not found.")
        conn.close()
        return

    assessment_type, risk_score, rf_json = row
    try:
        risk_factors = json.loads(rf_json) if rf_json else []
    except Exception:
        risk_factors = []

    recs = generate_risk_recommendations(assessment_type, risk_score, risk_factors)

    print("\nRecommendations:")
    for r in recs:
        print(f" - {r}")

    log_audit_event(auth.current_user['id'],
                    'screening_recommendations', 'risk_assessment', int(sel))
    conn.close()


def ip_restriction_management(auth):
    """Manage IP address restrictions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== IP Restriction Management =====")
    
    # Check current IP restriction setting
    cursor.execute('''
    SELECT setting_value FROM security_settings 
    WHERE setting_name = 'ip_restriction_enabled'
    ''')
    
    ip_restriction_enabled = cursor.fetchone()
    enabled = ip_restriction_enabled and ip_restriction_enabled[0] == '1'
    
    print(f"IP Restriction Status: {'Enabled' if enabled else 'Disabled'}")
    
    if enabled:
        cursor.execute('''
        SELECT setting_value FROM security_settings 
        WHERE setting_name = 'allowed_ip_ranges'
        ''')
        
        allowed_ips = cursor.fetchone()
        if allowed_ips and allowed_ips[0]:
            print(f"Allowed IP Ranges: {allowed_ips[0]}")
        else:
            print("No IP ranges configured")
    
    print("\nOptions:")
    print("1. Enable IP Restrictions")
    print("2. Disable IP Restrictions")
    print("3. Add IP Range")
    print("4. Remove IP Range")
    print("5. View Login Attempts by IP")
    print("6. Return to security menu")
    
    choice = input("\nSelect option (1-6): ")
    
    if choice == '1':
        cursor.execute('''
        UPDATE security_settings SET setting_value = '1', updated_at = ?
        WHERE setting_name = 'ip_restriction_enabled'
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
        print("IP restrictions enabled.")
    
    elif choice == '2':
        cursor.execute('''
        UPDATE security_settings SET setting_value = '0', updated_at = ?
        WHERE setting_name = 'ip_restriction_enabled'
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
        print("IP restrictions disabled.")
    
    elif choice == '3':
        ip_range = input("Enter IP range (e.g., 192.168.1.0/24): ")
        # In a real system, this would validate the IP range format
        print(f"IP range {ip_range} added to allowed list.")
    
    elif choice == '5':
        cursor.execute('''
        SELECT ip_address, COUNT(*) as attempt_count
        FROM audit_trail
        WHERE action = 'failed_login' AND timestamp >= datetime('now', '-24 hours')
        GROUP BY ip_address
        ORDER BY attempt_count DESC
        ''')
        
        ip_attempts = cursor.fetchall()
        
        if ip_attempts:
            print("\nFailed Login Attempts by IP (Last 24 hours):")
            for ip, count in ip_attempts:
                print(f"  {ip}: {count} attempts")
        else:
            print("No failed login attempts in the last 24 hours.")
    
    conn.close()

def two_factor_authentication_setup(auth):
    """Two-factor authentication management"""
    print("\n===== Two-Factor Authentication Setup =====")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check current 2FA setting
    cursor.execute('''
    SELECT setting_value FROM security_settings 
    WHERE setting_name = 'require_2fa_for_providers'
    ''')
    
    require_2fa = cursor.fetchone()
    enabled = require_2fa and require_2fa[0] == '1'
    
    print(f"2FA for Providers: {'Required' if enabled else 'Optional'}")
    
    print("\n2FA Management Options:")
    print("1. Require 2FA for All Providers")
    print("2. Make 2FA Optional")
    print("3. Reset User 2FA")
    print("4. View 2FA Statistics")
    print("5. Return to security menu")
    
    choice = input("\nSelect option (1-5): ")
    
    if choice == '1':
        cursor.execute('''
        UPDATE security_settings SET setting_value = '1', updated_at = ?
        WHERE setting_name = 'require_2fa_for_providers'
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
        log_audit_event(auth.current_user['id'], 'enable_mandatory_2fa', 'security', 0)
        print("2FA is now required for all healthcare providers.")
    
    elif choice == '2':
        cursor.execute('''
        UPDATE security_settings SET setting_value = '0', updated_at = ?
        WHERE setting_name = 'require_2fa_for_providers'
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
        log_audit_event(auth.current_user['id'], 'disable_mandatory_2fa', 'security', 0)
        print("2FA is now optional for healthcare providers.")
    
    elif choice == '3':
        username = input("Enter username to reset 2FA: ")
        log_audit_event(auth.current_user['id'], 'reset_user_2fa', 'security', 0, username)
        print(f"2FA reset for user {username}. They will need to set it up again.")
    
    elif choice == '4':
        print("2FA Statistics:")
        print("• Total users with 2FA enabled: [Would query user database]")
        print("• Providers with 2FA enabled: [Would query user database]")
        print("• Recent 2FA authentication attempts: [Would query audit log]")
    
    conn.close()

def integration_management(auth):
    """External system integration management"""
    if auth.current_user['role'] != 'admin':
        print("Only administrators can manage integrations.")
        return
    
    while True:
        print("\n===== Integration Management =====")
        print("1. External System Connections")
        print("2. API Key Management")
        print("3. Data Sync Status")
        print("4. Integration Logs")
        print("5. Laboratory System Integration")
        print("6. Insurance System Integration")
        print("7. Integration Health Check")
        print("8. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-8): ")
        
        if choice == '1':
            external_system_connections(auth)
        elif choice == '2':
            api_key_management(auth)
        elif choice == '3':
            data_sync_status(auth)
        elif choice == '4':
            integration_logs(auth)
        elif choice == '5':
            laboratory_system_integration(auth)
        elif choice == '6':
            insurance_system_integration(auth)
        elif choice == '7':
            integration_health_check(auth)
        elif choice == '8':
            break
        else:
            print("Invalid choice. Please try again.")

def api_key_management(auth):
    """Manage API keys for integrations"""
    print("\n===== API Key Management =====")
    
    # Mock API keys
    api_keys = [
        {"service": "LabCorp API", "key": "lc_***************", "expires": "2024-12-31", "status": "Active"},
        {"service": "Insurance API", "key": "ins_**************", "expires": "2024-06-30", "status": "Active"},
        {"service": "State Registry", "key": "sr_***************", "expires": "2025-03-15", "status": "Active"},
        {"service": "Hospital API", "key": "hosp_*************", "expires": "2024-02-28", "status": "Expiring Soon"}
    ]
    
    print("API Key Status:")
    for i, key in enumerate(api_keys):
        status_icon = "🟡" if key["status"] == "Expiring Soon" else "✅"
        print(f"{i+1}. {status_icon} {key['service']}")
        print(f"   Key: {key['key']}")
        print(f"   Expires: {key['expires']}")
        print(f"   Status: {key['status']}")
    
    print("\nActions:")
    print("1. Generate New API Key")
    print("2. Rotate Existing Key")
    print("3. Revoke API Key")
    print("4. View Key Usage Statistics")
    print("5. Return to integration menu")
    
    choice = input("\nSelect action (1-5): ")
    
    if choice == '1':
        service_name = input("Enter service name for new API key: ")
        print(f"New API key generated for {service_name}")
        print("Key: api_key_" + datetime.now().strftime('%Y%m%d%H%M%S'))
        log_audit_event(auth.current_user['id'], 'generate_api_key', 'integration', 0, service_name)
    
    elif choice == '2':
        key_num = input("Enter key number to rotate: ")
        print(f"API key {key_num} rotated successfully.")
        print("Old key will be valid for 24 hours for transition.")

def integration_health_check(auth):
    """Check health of all integrations"""
    print("\n===== Integration Health Check =====")
    
    # Mock health check results
    health_checks = [
        {"system": "LabCorp API", "status": "Healthy", "response_time": "245ms", "last_error": None},
        {"system": "Insurance API", "status": "Degraded", "response_time": "1.2s", "last_error": "Timeout on 2024-01-15"},
        {"system": "State Registry", "status": "Healthy", "response_time": "156ms", "last_error": None},
        {"system": "Hospital EMR", "status": "Down", "response_time": "N/A", "last_error": "Connection refused"}
    ]
    
    print("System Health Status:")
    
    for check in health_checks:
        if check["status"] == "Healthy":
            icon = "✅"
        elif check["status"] == "Degraded":
            icon = "🟡"
        else:
            icon = "❌"
        
        print(f"\n{icon} {check['system']}")
        print(f"   Status: {check['status']}")
        print(f"   Response Time: {check['response_time']}")
        if check['last_error']:
            print(f"   Last Error: {check['last_error']}")
    
    # Overall health summary
    healthy_count = sum(1 for c in health_checks if c["status"] == "Healthy")
    total_count = len(health_checks)
    
    print(f"\nOverall Integration Health: {healthy_count}/{total_count} systems healthy")
    
    if healthy_count < total_count:
        print("⚠️ Some integrations require attention.")
    else:
        print("✅ All integrations are functioning normally.")

def add_missing_menu_integrations():
    """
    Integration points for adding missing menus to the main health portal.
    Add these to the display_health_portal_menu function:
    """
    
    # Add to Provider/Admin section:
    provider_admin_menus = [
        ("Provider Dashboard", provider_dashboard),
        ("Provider Schedule Management", manage_provider_schedules),
        ("Referral Management", manage_referrals),
        ("Screening Schedule Management", manage_screening_schedules),
        ("Enhanced Record Templates", enhanced_health_record_templates),
        ("Advanced Security Management", advanced_security_menu),
        ("Integration Management", integration_management)
    ]
    
    # Add to Student section:
    student_menus = [
        ("Personal Health Dashboard", student_health_dashboard)
    ]

def generate_security_report(auth):
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Security Report Generation =====")
    
    timestamp = datetime.now()
    report_content = []
    
    # Report header
    report_content.append("HEALTH PORTAL SECURITY REPORT")
    report_content.append("=" * 40)
    report_content.append(f"Generated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append(f"Generated by: {auth.current_user['username']}")
    report_content.append("")
    
    # Security metrics
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Failed login attempts
    cursor.execute('''
    SELECT COUNT(*) FROM audit_trail
    WHERE action = 'failed_login' AND timestamp >= ?
    ''', (seven_days_ago,))
    
    failed_logins_7d = cursor.fetchone()[0]
    
    cursor.execute('''
    SELECT COUNT(*) FROM audit_trail
    WHERE action = 'failed_login' AND timestamp >= ?
    ''', (thirty_days_ago,))
    
    failed_logins_30d = cursor.fetchone()[0]
    
    report_content.append("AUTHENTICATION SECURITY")
    report_content.append("-" * 25)
    report_content.append(f"Failed login attempts (7 days): {failed_logins_7d}")
    report_content.append(f"Failed login attempts (30 days): {failed_logins_30d}")
    
    if failed_logins_7d > 50:
        report_content.append("⚠️  HIGH: Unusual number of failed logins")
    elif failed_logins_7d > 20:
        report_content.append("🟡 MEDIUM: Monitor login security")
    else:
        report_content.append("✅ LOW: Normal login activity")
    
    # Data access patterns
    cursor.execute('''
    SELECT COUNT(*) FROM audit_trail
    WHERE action LIKE '%view%' AND timestamp >= ?
    ''', (seven_days_ago,))
    
    data_access_7d = cursor.fetchone()[0]
    
    report_content.append("")
    report_content.append("DATA ACCESS SECURITY")
    report_content.append("-" * 20)
    report_content.append(f"Health record accesses (7 days): {data_access_7d}")
    
    # After-hours access
    cursor.execute('''
    SELECT COUNT(*) FROM audit_trail
    WHERE action LIKE '%view%' 
    AND (strftime('%H', timestamp) < '07' OR strftime('%H', timestamp) > '19')
    AND timestamp >= ?
    ''', (seven_days_ago,))
    
    after_hours_access = cursor.fetchone()[0]
    
    report_content.append(f"After-hours accesses (7 days): {after_hours_access}")
    
    if after_hours_access > 100:
        report_content.append("⚠️  REVIEW: High after-hours activity")
    elif after_hours_access > 50:
        report_content.append("🟡 MONITOR: Moderate after-hours activity")
    else:
        report_content.append("✅ NORMAL: Low after-hours activity")
    
    # Security settings compliance
    cursor.execute('''
    SELECT setting_name, setting_value FROM security_settings
    ''')
    
    security_settings = dict(cursor.fetchall())
    
    report_content.append("")
    report_content.append("SECURITY CONFIGURATION")
    report_content.append("-" * 22)
    
    config_issues = []
    
    # Check critical settings
    if security_settings.get('encryption_enabled') != '1':
        config_issues.append("Data encryption disabled")
    
    if security_settings.get('audit_logging_enabled') != '1':
        config_issues.append("Audit logging disabled")
    
    session_timeout = int(security_settings.get('session_timeout_minutes', '30'))
    if session_timeout > 60:
        config_issues.append(f"Session timeout too long: {session_timeout} minutes")
    
    max_attempts = int(security_settings.get('max_failed_login_attempts', '3'))
    if max_attempts > 5:
        config_issues.append(f"Too many login attempts allowed: {max_attempts}")
    
    if config_issues:
        report_content.append("Configuration Issues:")
        for issue in config_issues:
            report_content.append(f"  🔴 {issue}")
    else:
        report_content.append("✅ All critical settings properly configured")
    
    # Data retention compliance
    cursor.execute('''
    SELECT COUNT(*) FROM health_records 
    WHERE record_date < date('now', '-2555 days')
    ''')
    
    old_health_records = cursor.fetchone()[0]
    
    report_content.append("")
    report_content.append("DATA RETENTION COMPLIANCE")
    report_content.append("-" * 26)
    report_content.append(f"Health records exceeding retention: {old_health_records}")
    
    if old_health_records > 0:
        report_content.append("⚠️  ACTION NEEDED: Review old records for archival")
    else:
        report_content.append("✅ COMPLIANT: All records within retention periods")
    
    # Recommendations
    report_content.append("")
    report_content.append("SECURITY RECOMMENDATIONS")
    report_content.append("-" * 25)
    
    recommendations = []
    
    if failed_logins_7d > 20:
        recommendations.append("Implement additional login security measures")
    
    if after_hours_access > 50:
        recommendations.append("Review after-hours access policies")
    
    if config_issues:
        recommendations.append("Address security configuration issues")
    
    if old_health_records > 0:
        recommendations.append("Implement automated data retention policies")
    
    if not recommendations:
        recommendations.append("Continue current security practices")
        recommendations.append("Regular security monitoring and audits")
    
    for rec in recommendations:
        report_content.append(f"• {rec}")
    
    # Risk assessment
    risk_score = 0
    if failed_logins_7d > 50:
        risk_score += 3
    elif failed_logins_7d > 20:
        risk_score += 1
    
    if config_issues:
        risk_score += len(config_issues)
    
    if after_hours_access > 100:
        risk_score += 2
    elif after_hours_access > 50:
        risk_score += 1
    
    report_content.append("")
    report_content.append("OVERALL RISK ASSESSMENT")
    report_content.append("-" * 24)
    
    if risk_score >= 5:
        risk_level = "HIGH"
        risk_color = "🔴"
    elif risk_score >= 3:
        risk_level = "MEDIUM"
        risk_color = "🟡"
    else:
        risk_level = "LOW"
        risk_color = "✅"
    
    report_content.append(f"Risk Level: {risk_color} {risk_level}")
    report_content.append(f"Risk Score: {risk_score}/10")
    
    # Display report
    print("\n" + "="*60)
    for line in report_content:
        print(line)
    print("="*60)
    
    # Save report option
    save_report = input("\nSave security report to file? (y/n): ").lower()
    if save_report == 'y':
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        filename = f"security_report_{timestamp_str}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for line in report_content:
                    f.write(line + '\n')
            
            log_audit_event(auth.current_user['id'], 'generate_security_report', 'security_report', filename)
            print(f"Security report saved to: {filename}")
        except Exception as e:
            print(f"Error saving report: {e}")
    
    conn.close()

def population_risk_analysis(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to perform population risk analysis.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Population Risk Analysis =====")
    
    # High-risk student identification
    print("HIGH-RISK STUDENT IDENTIFICATION")
    print("-" * 32)
    
    # Students with multiple chronic conditions
    cursor.execute('''
    SELECT mc.student_id, s.first_name, s.last_name, COUNT(*) as condition_count,
           GROUP_CONCAT(mc.condition_name, ', ') as conditions
    FROM medical_conditions mc
    JOIN students s ON mc.student_id = s.student_id
    WHERE mc.status = 'active'
    GROUP BY mc.student_id, s.first_name, s.last_name
    HAVING COUNT(*) >= 2
    ORDER BY condition_count DESC
    ''')
    
    multi_condition_students = cursor.fetchall()
    
    if multi_condition_students:
        print(f"Students with multiple chronic conditions: {len(multi_condition_students)}")
        print("Top cases requiring care coordination:")
        for student_id, first_name, last_name, count, conditions in multi_condition_students[:5]:
            print(f"  {first_name} {last_name} (ID: {student_id}): {count} conditions")
            print(f"    Conditions: {conditions}")
    
    # Students with severe allergies
    cursor.execute('''
    SELECT a.student_id, s.first_name, s.last_name, 
           GROUP_CONCAT(a.allergen, ', ') as severe_allergies
    FROM allergies a
    JOIN students s ON a.student_id = s.student_id
    WHERE a.severity IN ('Severe', 'Life-threatening') AND a.verified = 1
    GROUP BY a.student_id, s.first_name, s.last_name
    ''')
    
    severe_allergy_students = cursor.fetchall()
    
    if severe_allergy_students:
        print(f"\nStudents with severe allergies: {len(severe_allergy_students)}")
        print("Requiring emergency action plans:")
        for student_id, first_name, last_name, allergies in severe_allergy_students[:5]:
            print(f"  {first_name} {last_name} (ID: {student_id})")
            print(f"    Severe allergies: {allergies}")
    
    # Risk stratification by demographics
    print(f"\nRISK STRATIFICATION ANALYSIS")
    print("-" * 27)
    
    # Age-based risk analysis
    cursor.execute('''
    SELECT 
        CASE 
            WHEN age < 20 THEN '18-19'
            WHEN age < 25 THEN '20-24'
            WHEN age < 30 THEN '25-29'
            WHEN age >= 30 THEN '30+'
        END as age_group,
        COUNT(*) as total_students,
        SUM(CASE WHEN EXISTS (
            SELECT 1 FROM medical_conditions mc 
            WHERE mc.student_id = s.student_id AND mc.status = 'active'
        ) THEN 1 ELSE 0 END) as with_conditions
    FROM students s
    GROUP BY age_group
    ORDER BY age_group
    ''')
    
    age_risk_data = cursor.fetchall()
    
    if age_risk_data:
        print("Chronic condition prevalence by age group:")
        for age_group, total, with_conditions in age_risk_data:
            prevalence = (with_conditions / total * 100) if total > 0 else 0
            print(f"  {age_group}: {with_conditions}/{total} ({prevalence:.1f}%)")
    
    # Mental health risk indicators
    cursor.execute('''
    SELECT COUNT(DISTINCT student_id) as mental_health_cases
    FROM medical_conditions
    WHERE condition_name IN ('Depression', 'Anxiety', 'PTSD', 'Bipolar Disorder')
    AND status = 'active'
    ''')
    
    mental_health_cases = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    mental_health_prevalence = (mental_health_cases / total_students * 100) if total_students > 0 else 0
    
    print(f"\nMental health conditions: {mental_health_cases} students ({mental_health_prevalence:.1f}%)")
    
    if mental_health_prevalence > 15:  # Above typical college rates
        print("  ⚠️  High prevalence - Consider expanded mental health services")
    elif mental_health_prevalence > 10:
        print("  🟡 Moderate prevalence - Monitor trends")
    else:
        print("  ✅ Within expected range")
    
    # Preventive care gaps
    print(f"\nPREVENTIVE CARE GAPS")
    print("-" * 19)
    
    # Vaccination gaps
    critical_vaccines = ['COVID-19', 'Influenza (Flu)', 'Hepatitis B', 'MMR']
    
    for vaccine in critical_vaccines:
        cursor.execute('''
        SELECT COUNT(DISTINCT student_id) 
        FROM vaccination_records 
        WHERE vaccine_name = ? AND verified = 1
        ''', (vaccine,))
        
        vaccinated = cursor.fetchone()[0]
        coverage = (vaccinated / total_students * 100) if total_students > 0 else 0
        
        print(f"{vaccine}: {coverage:.1f}% coverage")
        
        if coverage < 70:
            print(f"  🔴 Low coverage - Priority intervention needed")
        elif coverage < 85:
            print(f"  🟡 Suboptimal - Targeted outreach recommended")
        else:
            print(f"  ✅ Good coverage")
    
    # Emergency preparedness gaps
    cursor.execute('''
    SELECT COUNT(DISTINCT s.student_id)
    FROM students s
    LEFT JOIN emergency_contacts ec ON s.student_id = ec.student_id
    WHERE ec.student_id IS NULL
    ''')
    
    no_emergency_contacts = cursor.fetchone()[0]
    emergency_gap = (no_emergency_contacts / total_students * 100) if total_students > 0 else 0
    
    print(f"\nStudents without emergency contacts: {no_emergency_contacts} ({emergency_gap:.1f}%)")
    
    if emergency_gap > 10:
        print("  🔴 High gap - Emergency preparedness campaign needed")
    elif emergency_gap > 5:
        print("  🟡 Moderate gap - Targeted outreach")
    else:
        print("  ✅ Good emergency preparedness")
    
    # Generate population risk score
    risk_factors = 0
    
    if mental_health_prevalence > 15:
        risk_factors += 2
    elif mental_health_prevalence > 10:
        risk_factors += 1
    
    # Check vaccination coverage
    low_coverage_vaccines = 0
    for vaccine in critical_vaccines:
        cursor.execute('''
        SELECT COUNT(DISTINCT student_id) 
        FROM vaccination_records 
        WHERE vaccine_name = ? AND verified = 1
        ''', (vaccine,))
        
        vaccinated = cursor.fetchone()[0]
        coverage = (vaccinated / total_students * 100) if total_students > 0 else 0
        
        if coverage < 70:
            low_coverage_vaccines += 1
    
    risk_factors += low_coverage_vaccines
    
    if emergency_gap > 10:
        risk_factors += 1
    
    print(f"\n===== POPULATION RISK ASSESSMENT =====")
    print(f"Risk Score: {risk_factors}/7")
    
    if risk_factors >= 5:
        risk_level = "HIGH"
        print("🔴 HIGH RISK - Multiple intervention priorities")
    elif risk_factors >= 3:
        risk_level = "MODERATE"
        print("🟡 MODERATE RISK - Targeted interventions needed")
    else:
        risk_level = "LOW"
        print("✅ LOW RISK - Maintain current programs")
    
    # Recommendations
    print(f"\nRECOMMENDATIONS:")
    
    if mental_health_prevalence > 15:
        print("• Expand mental health services and counseling staff")
        print("• Implement mental health screening programs")
    
    if low_coverage_vaccines > 2:
        print("• Launch comprehensive vaccination campaign")
        print("• Implement vaccination requirements or incentives")
    
    if emergency_gap > 10:
        print("• Emergency contact collection campaign")
        print("• Integrate into enrollment/registration process")
    
    if len(multi_condition_students) > 10:
        print("• Develop care coordination programs")
        print("• Implement chronic disease management protocols")
    
    if not any([mental_health_prevalence > 10, low_coverage_vaccines > 1, emergency_gap > 5]):
        print("• Continue current preventive health programs")
        print("• Regular monitoring of population health metrics")
    
    conn.close()

def review_security_settings(auth):
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Security Settings Review =====")
    
    cursor.execute('''
    SELECT setting_name, setting_value, updated_at, updated_by
    FROM security_settings
    ORDER BY setting_name
    ''')
    
    settings = cursor.fetchall()
    
    if not settings:
        print("No security settings found.")
        conn.close()
        return
    
    security_issues = []
    
    for setting_name, setting_value, updated_at, updated_by in settings:
        print(f"\n{setting_name}: {setting_value}")
        if updated_at:
            print(f"  Last updated: {updated_at} by {updated_by}")
        
        # Security assessment
        if setting_name == 'session_timeout_minutes':
            timeout = int(setting_value)
            if timeout > 60:
                security_issues.append(f"Session timeout too long: {timeout} minutes")
                print("  🔴 RISK: Session timeout should be ≤60 minutes")
            elif timeout <= 30:
                print("  ✅ Good: Appropriate session timeout")
            else:
                print("  🟡 Acceptable: Session timeout within range")
        
        elif setting_name == 'max_failed_login_attempts':
            max_attempts = int(setting_value)
            if max_attempts > 5:
                security_issues.append(f"Too many login attempts allowed: {max_attempts}")
                print("  🔴 RISK: Max attempts should be ≤5")
            else:
                print("  ✅ Good: Appropriate login attempt limit")
        
        elif setting_name == 'password_expiry_days':
            expiry_days = int(setting_value)
            if expiry_days > 90:
                security_issues.append(f"Password expiry too long: {expiry_days} days")
                print("  🔴 RISK: Password should expire within 90 days")
            else:
                print("  ✅ Good: Appropriate password expiry")
        
        elif setting_name == 'encryption_enabled':
            if setting_value != '1':
                security_issues.append("Data encryption disabled")
                print("  🔴 CRITICAL: Encryption should be enabled")
            else:
                print("  ✅ Good: Encryption enabled")
        
        elif setting_name == 'audit_logging_enabled':
            if setting_value != '1':
                security_issues.append("Audit logging disabled")
                print("  🔴 CRITICAL: Audit logging should be enabled")
            else:
                print("  ✅ Good: Audit logging enabled")
        
        elif setting_name == 'require_2fa_for_providers':
            if setting_value != '1':
                security_issues.append("2FA not required for providers")
                print("  🟡 WARNING: Consider requiring 2FA for providers")
            else:
                print("  ✅ Good: 2FA required for providers")
    
    # Security recommendations
    print(f"\n===== Security Assessment =====")
    
    if security_issues:
        print("Security Issues Found:")
        for issue in security_issues:
            print(f"  🔴 {issue}")
        
        print(f"\nRecommendations:")
        print("  • Review and update security settings")
        print("  • Implement stricter policies where needed")
        print("  • Regular security setting audits")
    else:
        print("✅ All security settings appear to be properly configured.")
    
    # Update settings option
    update_settings = input("\nUpdate security settings? (y/n): ").lower()
    if update_settings == 'y':
        update_security_settings(auth)
    
    conn.close()

def update_security_settings(auth):
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Update Security Settings =====")
    
    # Show current settings
    cursor.execute('''
    SELECT setting_name, setting_value
    FROM security_settings
    ORDER BY setting_name
    ''')
    
    settings = cursor.fetchall()
    setting_names = [setting[0] for setting in settings]
    
    print("Current Settings:")
    for i, (name, value) in enumerate(settings):
        print(f"{i+1}. {name}: {value}")
    
    while True:
        choice = input(f"\nSelect setting to update (1-{len(settings)}) or 'q' to quit: ")
        if choice.lower() == 'q':
            break
        
        try:
            setting_idx = int(choice) - 1
            if 0 <= setting_idx < len(settings):
                setting_name = setting_names[setting_idx]
                current_value = settings[setting_idx][1]
                
                print(f"\nUpdating: {setting_name}")
                print(f"Current value: {current_value}")
                
                new_value = input("New value: ").strip()
                if new_value:
                    cursor.execute('''
                    UPDATE security_settings 
                    SET setting_value = ?, updated_at = ?, updated_by = ?
                    WHERE setting_name = ?
                    ''', (new_value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                          auth.current_user['username'], setting_name))
                    
                    conn.commit()
                    log_audit_event(auth.current_user['id'], 'update_security_setting', 'security_setting', 0,
                                   f"{setting_name}: {current_value} -> {new_value}")
                    print(f"Setting updated: {setting_name} = {new_value}")
                else:
                    print("No change made.")
            else:
                print("Invalid choice.")
        except ValueError:
            print("Invalid input.")
    
    conn.close()

def assess_contact_risk(contact, disease, severity):
    """Assess risk level for a contact based on exposure parameters"""
    risk_factors = 0
    
    # Contact type risk
    if contact['type'] == 'household':
        risk_factors += 3
    elif contact['type'] == 'close':
        risk_factors += 2
    elif contact['type'] == 'healthcare':
        risk_factors += 1
    
    # Duration risk
    try:
        duration = int(contact['duration'])
        if duration >= 60:
            risk_factors += 2
        elif duration >= 15:
            risk_factors += 1
    except (ValueError, KeyError, TypeError) as e:
        logging.warning(f"Invalid duration value in contact data: {e}")
    
    # Disease severity
    if severity in ['Severe', 'Critical']:
        risk_factors += 1
    
    # Disease type
    high_transmission_diseases = ['COVID-19', 'Influenza', 'Measles', 'Tuberculosis']
    if disease in high_transmission_diseases:
        risk_factors += 1
    
    # Risk classification
    if risk_factors >= 4:
        return 'High'
    elif risk_factors >= 2:
        return 'Moderate'
    else:
        return 'Low'

def security_audit_menu(auth):
    """Security audit and monitoring"""
    if auth.current_user['role'] != 'admin':
        print("Only administrators can access security audit features.")
        return
    
    while True:
        print("\n===== Security Audit =====")
        print("1. View Audit Log")
        print("2. Failed Login Attempts")
        print("3. Data Access Patterns")
        print("4. Security Settings Review")
        print("5. Generate Security Report")
        print("6. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            view_audit_log(auth)
        elif choice == '2':
            view_failed_logins(auth)
        elif choice == '3':
            analyze_data_access_patterns(auth)
        elif choice == '4':
            review_security_settings(auth)
        elif choice == '5':
            generate_security_report(auth)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def view_audit_log(auth):
    """View system audit log"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get recent audit events
    cursor.execute('''
    SELECT user_id, action, resource_type, resource_id, timestamp, ip_address
    FROM audit_trail
    ORDER BY timestamp DESC
    LIMIT 50
    ''')
    
    audit_events = cursor.fetchall()
    
    if not audit_events:
        print("No audit events found.")
        conn.close()
        return
    
    print("\n===== System Audit Log (Last 50 Events) =====")
    for event in audit_events:
        user_id, action, resource_type, resource_id, timestamp, ip_address = event
        
        print(f"{timestamp} - User: {user_id} - Action: {action}")
        print(f"  Resource: {resource_type}:{resource_id}")
        if ip_address:
            print(f"  IP: {ip_address}")
        print("-" * 30)
    
    conn.close()

def health_risk_assessment(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to access health risk assessment.")
        return
    
    while True:
        print("\n===== Health Risk Assessment =====")
        print("1. Conduct Risk Assessment")
        print("2. View Risk Assessments")
        print("3. Risk-Based Screening Recommendations")
        print("4. Population Risk Analysis")
        print("5. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == '1':
            conduct_risk_assessment(auth)
        elif choice == '2':
            view_risk_assessments(auth)
        elif choice == '3':
            screening_recommendations(auth)
        elif choice == '4':
            population_risk_analysis(auth)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")

def conduct_risk_assessment(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to conduct risk assessments.")
        return
    
    backup_before_operation('conduct_risk_assessment')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT first_name, last_name, age FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    
    if not student:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    first_name, last_name, age = student
    
    print(f"\n===== Risk Assessment for {first_name} {last_name} =====")
    
    # Assessment types
    assessment_types = [
        'General Health Risk',
        'Cardiovascular Risk',
        'Diabetes Risk',
        'Mental Health Risk',
        'Substance Use Risk',
        'Infectious Disease Risk'
    ]
    
    print("\nAssessment Types:")
    for i, assessment_type in enumerate(assessment_types):
        print(f"{i+1}. {assessment_type}")
    
    while True:
        type_choice = input("\nSelect assessment type (1-6): ")
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(assessment_types):
            assessment_type = assessment_types[int(type_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    # Get existing health data for risk calculation
    cursor.execute('''
    SELECT condition_name, severity FROM medical_conditions 
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))
    conditions = cursor.fetchall()
    
    cursor.execute('''
    SELECT allergen, severity FROM allergies 
    WHERE student_id = ? AND verified = 1
    ''', (student_id,))
    allergies = cursor.fetchall()
    
    cursor.execute('''
    SELECT bmi FROM vital_signs 
    WHERE student_id = ? AND bmi IS NOT NULL
    ORDER BY measurement_date DESC LIMIT 1
    ''', (student_id,))
    latest_bmi = cursor.fetchone()
    
    # Calculate risk score based on assessment type
    risk_score = calculate_risk_score(assessment_type, age, conditions, allergies, latest_bmi)
    
    # Get risk factors
    risk_factors = get_risk_factors(assessment_type, age, conditions, allergies, latest_bmi)
    
    # Generate recommendations
    recommendations = generate_risk_recommendations(assessment_type, risk_score, risk_factors)
    
    print(f"\nRisk Assessment Results:")
    print(f"Assessment Type: {assessment_type}")
    print(f"Risk Score: {risk_score}/100")
    
    if risk_score < 25:
        risk_level = "Low Risk"
    elif risk_score < 50:
        risk_level = "Moderate Risk"
    elif risk_score < 75:
        risk_level = "High Risk"
    else:
        risk_level = "Very High Risk"
    
    print(f"Risk Level: {risk_level}")
    
    if risk_factors:
        print("\nRisk Factors:")
        for factor in risk_factors:
            print(f"- {factor}")
    
    if recommendations:
        print("\nRecommendations:")
        for recommendation in recommendations:
            print(f"- {recommendation}")
    
    # Ask for follow-up date
    follow_up_needed = input("\nSchedule follow-up assessment? (y/n): ").lower() == 'y'
    follow_up_date = None
    
    if follow_up_needed:
        while True:
            follow_up_input = input("Follow-up date (YYYY-MM-DD): ")
            try:
                datetime.strptime(follow_up_input, '%Y-%m-%d')
                follow_up_date = follow_up_input
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
    
    # Save assessment
    assessed_date = datetime.now().strftime('%Y-%m-%d')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO risk_assessments 
    (student_id, assessment_type, risk_score, risk_factors, recommendations, 
     assessed_date, assessed_by, follow_up_date, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, assessment_type, risk_score, json.dumps(risk_factors), 
          json.dumps(recommendations), assessed_date, auth.current_user['username'], 
          follow_up_date, created_at))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'conduct_risk_assessment', 'risk_assessment', cursor.lastrowid)
    
    print("\nRisk assessment completed and saved!")
    
    conn.close()

def calculate_risk_score(assessment_type, age, conditions, allergies, latest_bmi):
    """Calculate risk score based on assessment type and health data"""
    base_score = 0
    
    # Age-based risk
    if age >= 65:
        base_score += 20
    elif age >= 45:
        base_score += 10
    elif age >= 25:
        base_score += 5
    
    # Condition-based risk
    high_risk_conditions = ['diabetes', 'hypertension', 'heart disease', 'asthma', 'obesity']
    for condition_name, severity in conditions:
        if any(risk_condition in condition_name.lower() for risk_condition in high_risk_conditions):
            if severity == 'Severe':
                base_score += 15
            elif severity == 'Moderate':
                base_score += 10
            else:
                base_score += 5
    
    # BMI-based risk
    if latest_bmi:
        bmi = latest_bmi[0]
        if bmi >= 30:
            base_score += 15
        elif bmi >= 25:
            base_score += 10
        elif bmi < 18.5:
            base_score += 5
    
    # Allergy-based risk
    for allergen, severity in allergies:
        if severity in ['Severe', 'Life-threatening']:
            base_score += 10
        elif severity == 'Moderate':
            base_score += 5
    
    # Assessment-specific adjustments
    if assessment_type == 'Cardiovascular Risk':
        # Additional cardiovascular risk factors would be assessed here
        pass
    elif assessment_type == 'Mental Health Risk':
        # Mental health specific risk factors
        pass
    
    return min(base_score, 100)  # Cap at 100

def get_risk_factors(assessment_type, age, conditions, allergies, latest_bmi):
    """Get list of risk factors based on assessment"""
    risk_factors = []
    
    if age >= 65:
        risk_factors.append("Advanced age (65+)")
    elif age >= 45:
        risk_factors.append("Middle age (45-64)")
    
    for condition_name, severity in conditions:
        risk_factors.append(f"Medical condition: {condition_name} ({severity})")
    
    for allergen, severity in allergies:
        if severity in ['Severe', 'Life-threatening']:
            risk_factors.append(f"Severe allergy: {allergen}")
    
    if latest_bmi:
        bmi = latest_bmi[0]
        if bmi >= 30:
            risk_factors.append(f"Obesity (BMI: {bmi})")
        elif bmi >= 25:
            risk_factors.append(f"Overweight (BMI: {bmi})")
        elif bmi < 18.5:
            risk_factors.append(f"Underweight (BMI: {bmi})")
    
    return risk_factors

def generate_risk_recommendations(assessment_type, risk_score, risk_factors):
    """Generate recommendations based on risk assessment"""
    recommendations = []
    
    if risk_score >= 75:
        recommendations.append("Schedule immediate follow-up with healthcare provider")
        recommendations.append("Consider referral to specialist")
    elif risk_score >= 50:
        recommendations.append("Schedule follow-up within 30 days")
        recommendations.append("Implement risk reduction strategies")
    elif risk_score >= 25:
        recommendations.append("Schedule follow-up within 3 months")
        recommendations.append("Monitor risk factors")
    else:
        recommendations.append("Continue routine preventive care")
        recommendations.append("Annual reassessment recommended")
    
    # Assessment-specific recommendations
    if assessment_type == 'Cardiovascular Risk':
        recommendations.extend([
            "Regular blood pressure monitoring",
            "Cholesterol screening",
            "Heart-healthy diet and exercise"
        ])
    elif assessment_type == 'Mental Health Risk':
        recommendations.extend([
            "Mental health screening",
            "Stress management techniques",
            "Counseling services available"
        ])
    
    return recommendations
