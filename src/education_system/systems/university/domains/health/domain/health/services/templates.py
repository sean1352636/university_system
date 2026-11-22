from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

import csv
import json
import logging
import os

from education_system.systems.university.domains.health.infrastructure.health.storage import get_connection, sqlite3
from education_system.systems.university.domains.health.domain.health.services.audit import log_audit_event
from education_system.systems.university.domains.health.domain.health.services.security import truthy
from education_system.systems.university.domains.health.domain.health.services.health_db_backup import ensure_templates_schema
from education_system.systems.university.infrastructure.i18n import get_text

def _normalize_template_dict(d: dict) -> dict:
    """
    Accepts flexible keys and returns a normalized template record.
    Required: name, body
    Optional: category, created_by, is_shared, version
    """
    name = (d.get("name") or d.get("title") or "").strip()
    if not name:
        raise ValueError("Template missing 'name'")

    body = d.get("body") or d.get("content") or d.get("template") or ""
    if not isinstance(body, str):
        body = json.dumps(body, ensure_ascii=False)
    if not body.strip():
        raise ValueError(f"Template '{name}' missing 'body'")

    category = d.get("category") or d.get("tag") or d.get("group")
    created_by = d.get("created_by") or d.get("author") or d.get("owner")
    version = d.get("version") or 1
    is_shared = d["is_shared"] if "is_shared" in d else d.get("shared")

    return {
        "name": name,
        "body": body,
        "category": category,
        "created_by": created_by,
        "version": int(version) if str(version).isdigit() else 1,
        "is_shared": 1 if truthy(is_shared) else 0,
    }

def import_templates_from_path(auth, source_path: str | None = None):
    """
    Import templates from a JSON or CSV file.
    JSON: list of objects or {"templates": [ ... ]}
    CSV:  columns: name, body, [category, created_by, is_shared, version]
    Upserts by unique 'name'.
    """
    # Ensure the schema exists
    try:
        ensure_templates_schema()
    except Exception as e:
        print(get_text("health.templates.import_aborted_schema", error=e, default="Import Aborted Schema: {error}"))
        return

    # Ask for a path if none provided
    if not source_path:
        try:
            source_path = input("Path to templates file (.json or .csv): ").strip()
        except Exception:
            source_path = ""
    if not source_path:
        print(get_text("health.templates.import_cancelled", default="Import cancelled."))
        return

    ext = os.path.splitext(source_path)[1].lower()
    records = []

    # Read file
    try:
        if ext == ".json":
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "templates" in data:
                data = data["templates"]
            if not isinstance(data, list):
                raise ValueError("JSON must be a list or {'templates': [...]}")

            for item in data:
                records.append(_normalize_template_dict(item))

        elif ext == ".csv":
            with open(source_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(_normalize_template_dict(row))
        else:
            print(get_text("health.templates.unsupported_file_type", ext=ext, default="Unsupported File Type: {ext}"))
            return
    except Exception as e:
        print(get_text("health.templates.failed_to_read", path=source_path, error=e, default="Failed To Read: {error} {path}"))
        return

    if not records:
        print(get_text("health.templates.no_templates_to_import", default="No Templates To Import."))
        return

    # Upsert into DB
    conn = get_connection()
    inserted = updated = skipped = 0
    try:
        c = conn.cursor()
        # Try native UPSERT (SQLite ≥ 3.24.0)
        try:
            for r in records:
                c.execute(
                    """
                    INSERT INTO templates(name, category, body, created_by, is_shared, version, updated_at)
                    VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
                    ON CONFLICT(name) DO UPDATE SET
                        category=excluded.category,
                        body=excluded.body,
                        created_by=COALESCE(excluded.created_by, templates.created_by),
                        is_shared=COALESCE(excluded.is_shared, templates.is_shared),
                        version=COALESCE(excluded.version, templates.version),
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        r["name"],
                        r.get("category"),
                        r["body"],
                        r.get("created_by"),
                        r.get("is_shared", 0),
                        r.get("version", 1),
                    ),
                )
                # rowcount==1 when inserted; ==2 isn't guaranteed here, so detect via changes() if needed
                inserted += 1  # optimistic; we'll correct below if needed
            conn.commit()
        except sqlite3.OperationalError:
            # Fallback path for older SQLite without UPSERT
            conn.rollback()
            for r in records:
                try:
                    c.execute(
                        "INSERT OR IGNORE INTO templates(name, category, body, created_by, is_shared, version, updated_at) "
                        "VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                        (
                            r["name"],
                            r.get("category"),
                            r["body"],
                            r.get("created_by"),
                            r.get("is_shared", 0),
                            r.get("version", 1),
                        ),
                    )
                    if c.rowcount == 1:
                        inserted += 1
                    else:
                        c.execute(
                            """
                            UPDATE templates
                               SET category=?,
                                   body=?,
                                   created_by=COALESCE(?, created_by),
                                   is_shared=COALESCE(?, is_shared),
                                   version=COALESCE(?, version),
                                   updated_at=CURRENT_TIMESTAMP
                             WHERE name=?
                            """,
                            (
                                r.get("category"),
                                r["body"],
                                r.get("created_by"),
                                r.get("is_shared", 0),
                                r.get("version", 1),
                                r["name"],
                            ),
                        )
                        updated += c.rowcount
                except Exception as ie:
                    skipped += 1
                    print(get_text("health.templates.skipping_template", name=r.get('name'), error=ie, default="Skipping Template: {error} {name}"))
            conn.commit()

        # If we used the UPSERT path, we can't distinguish insert/update per rowcount reliably.
        if updated == 0 and skipped == 0 and inserted > 0:
            print(get_text("health.templates.imported_processed", count=inserted, default="Imported Processed: {count}"))
        else:
            print(get_text("health.templates.imported_summary", inserted=inserted, updated=updated, skipped=skipped, default="Imported Summary: {inserted} {skipped} {updated}"))
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        print(get_text("health.templates.import_failed", error=e, default="Import Failed: {error}"))
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

def import_templates(auth):
    """Import templates from CSV: columns name,category,body."""
    path = input("Path to CSV/JSON: ").strip()
    if not path or not os.path.exists(path):
        print(get_text("health.templates.file_not_found", default="File not found."))
        return
    import_templates_from_path(auth, path)

def shared_templates(auth):
    """List templates marked as shared if column exists, else list all."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='templates'")
        if not c.fetchone():
            print(get_text("health.templates.no_templates_table", default="No Templates Table.")); return
        # Check for the shared flag
        c.execute("PRAGMA table_info(templates)")
        cols = [r[1] for r in c.fetchall()]
        if 'is_shared' in cols:
            c.execute("SELECT id, name, category FROM templates WHERE is_shared=1 ORDER BY name")
        else:
            c.execute("SELECT id, name, category FROM templates ORDER BY name")
        rows = c.fetchall()
        if not rows:
            print("No templates found."); return
        print("\nTemplates:")
        for tid, name, cat in rows:
            print(f" - [{tid}] {name or '(unnamed)'} ({cat or 'general'})")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")

# ── Record templates ───────────────────────────────────────────────────
# Built-in templates are offered alongside the ones saved in ``templates``
# (they are not written to the table). A saved template's body starts with
# a "Record type: ..." line; using one creates a real ``health_records``
# row and an audit entry, which is also what the usage statistics count.

TEMPLATE_CATEGORIES = ("Preventive Care", "Acute Care", "Mental Health", "Immunizations",
                       "Chronic Care", "Emergency", "Other")
USE_ACTION = "use_health_record_template"
_TYPE_PREFIX = "Record type:"

BUILT_IN_TEMPLATES = (
    {"name": "Annual Physical", "category": "Preventive Care", "record_type": "Annual Physical Exam",
     "body": "Comprehensive annual physical examination including:\n- Vital signs assessment\n"
             "- General health evaluation\n- Preventive care counseling\n"
             "- Age-appropriate screenings\n- Immunization review"},
    {"name": "Sick Visit", "category": "Acute Care", "record_type": "General Medical",
     "body": "Patient presented with acute illness symptoms:\n- Chief complaint: [FILL IN]\n"
             "- History of present illness: [FILL IN]\n- Physical examination: [FILL IN]\n"
             "- Assessment and plan: [FILL IN]\n- Follow-up instructions: [FILL IN]"},
    {"name": "Mental Health Assessment", "category": "Mental Health", "record_type": "Mental Health",
     "body": "Mental health screening and assessment:\n- Mood assessment: [FILL IN]\n"
             "- Anxiety screening: [FILL IN]\n- Sleep patterns: [FILL IN]\n"
             "- Stress factors: [FILL IN]\n- Recommendations: [FILL IN]\n"
             "- Resources provided: [FILL IN]"},
    {"name": "Vaccination Record", "category": "Immunizations", "record_type": "Vaccination",
     "body": "Vaccination administered:\n- Vaccine: [FILL IN]\n- Dose: [FILL IN]\n"
             "- Site: [FILL IN]\n- Patient tolerated procedure well\n"
             "- No immediate adverse reactions\n- Post-vaccination instructions provided"},
    {"name": "Injury Assessment", "category": "Emergency", "record_type": "Injury Treatment",
     "body": "Injury assessment and treatment provided:\n- Mechanism of injury: [FILL IN]\n"
             "- Examination: [FILL IN]\n- First aid / treatment: [FILL IN]\n"
             "- Follow-up: [FILL IN]"},
)


def _ensure_templates(conn) -> None:
    """The health schema on this connection when ``templates`` is missing."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'templates'"
                    ).fetchone() is None:
        from education_system.systems.university.domains.health.infrastructure.health import (
            health_schema,
        )
        health_schema.apply_to_connection(conn)


def _split_body(body):
    text = str(body or "")
    first, _, rest = text.partition("\n")
    if first.startswith(_TYPE_PREFIX):
        return first[len(_TYPE_PREFIX):].strip(), rest.lstrip("\n")
    return None, text


def list_record_templates(conn) -> list[dict]:
    """Built-in and saved templates: ``{id, name, category, record_type,
    body, source, created_by, is_shared, version}`` (``id`` None for
    built-ins)."""
    out = [dict(t, id=None, source="built-in", created_by=None, is_shared=1, version=1)
           for t in BUILT_IN_TEMPLATES]
    _ensure_templates(conn)
    saved = conn.execute("SELECT id, name, category, body, created_by, is_shared, version "
                         "FROM templates ORDER BY name").fetchall()
    names = {t["name"].lower() for t in out}
    for tid, name, category, body, created_by, shared, version in saved:
        record_type, text = _split_body(body)
        item = {"id": tid, "name": name, "category": category or "Other",
                "record_type": record_type or name, "body": text, "source": "saved",
                "created_by": created_by, "is_shared": shared, "version": version}
        if name.lower() in names:              # a saved copy replaces the built-in
            out = [t for t in out if t["name"].lower() != name.lower()]
        out.append(item)
    return sorted(out, key=lambda t: (t["category"] or "", t["name"]))


def save_record_template(conn, *, name, category, record_type, body, by, shared=True,
                         template_id=None) -> int:
    """Create (or, with ``template_id``, update) a saved template; audited.
    Returns its id."""
    name, body = str(name or "").strip(), str(body or "").strip()
    record_type = str(record_type or "").strip() or name
    if not name or not body:
        raise ValueError("A template name and content are required")
    _ensure_templates(conn)
    stored = f"{_TYPE_PREFIX} {record_type}\n\n{body}"
    from datetime import datetime
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if template_id:
        cur = conn.execute("UPDATE templates SET name = ?, category = ?, body = ?, is_shared = ?, "
                           "version = COALESCE(version, 1) + 1, updated_at = ? WHERE id = ?",
                           (name, category, stored, 1 if shared else 0, stamp, int(template_id)))
        if not cur.rowcount:
            raise LookupError(f"Template {template_id} not found")
        log_audit_event(by, "update_health_record_template", "template", template_id, name,
                        conn=conn)
        return int(template_id)
    try:
        cur = conn.execute("INSERT INTO templates (name, category, body, created_by, is_shared, "
                           "version, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
                           (name, category, stored, str(by), 1 if shared else 0, stamp))
    except sqlite3.IntegrityError:
        raise ValueError(f"A template called {name!r} already exists") from None
    log_audit_event(by, "create_health_record_template", "template", cur.lastrowid, name,
                    conn=conn)
    return cur.lastrowid


def create_record_from_template(conn, who, template: dict, *, student_id, description,
                                record_date=None, provider=None, confidential=False) -> int:
    """A ``health_records`` row from a template (clinicians only; a
    confidential description is sealed). Audited, which is what
    :func:`template_usage` counts. Returns the record id."""
    from datetime import datetime
    from education_system.systems.university.domains.health.application.health import (
        access, sealed_fields,
    )
    access.require_clinician(who, "create health records")
    student_id = str(student_id or "").strip()
    if conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                    (student_id,)).fetchone() is None:
        raise LookupError(f"Student {student_id} not found")
    description = str(description or "").strip()
    if not description:
        raise ValueError("The record description is empty")
    if "[FILL IN]" in description:
        raise ValueError("Fill in every [FILL IN] in the template first")
    day = str(record_date or "").strip() or datetime.now().strftime("%Y-%m-%d")
    datetime.strptime(day, "%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO health_records (student_id, record_type, record_date, provider, description, "
        "confidential, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (student_id, template["record_type"], day, provider or who.username,
         sealed_fields.seal_value("health_records", "description", description,
                                  confidential=1 if confidential else 0),
         1 if confidential else 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_audit_event(who.username, USE_ACTION, "template", template["name"],
                    {"record_id": cur.lastrowid, "student_id": student_id}, conn=conn)
    return cur.lastrowid


def template_usage(conn, days=30) -> list[dict]:
    """Records created from each template in the last ``days`` days (from
    the audit trail): ``[{template, uses, last_used}]``, most used first."""
    from datetime import datetime, timedelta
    since = (datetime.now() - timedelta(days=int(days))).strftime("%Y-%m-%d")
    try:
        rows = conn.execute("SELECT resource_id, COUNT(*), MAX(timestamp) FROM audit_trail "
                            "WHERE action = ? AND timestamp >= ? GROUP BY resource_id "
                            "ORDER BY COUNT(*) DESC", (USE_ACTION, since)).fetchall()
    except sqlite3.Error:
        return []
    return [{"template": r[0], "uses": r[1], "last_used": str(r[2] or "")[:10]} for r in rows]


def _pick(options, prompt):
    while True:
        choice = input(prompt).strip()
        if choice.lower() == 'q':
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("Invalid choice. Please try again.")


def use_existing_template(auth):
    """Create a health record from a template (built-in or saved)."""
    from education_system.systems.university.domains.health.application.health import access
    who = access.from_user(auth.current_user)
    conn = get_connection(row_factory=False)
    try:
        templates = list_record_templates(conn)
        print("\n===== Available Templates =====")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template['name']}  [{template['source']}]")
            print(f"   Category: {template['category']}")
            print(f"   Type: {template['record_type']}")
        selected = _pick(templates, f"\nSelect template (1-{len(templates)}) or 'q' to quit: ")
        if selected is None:
            return
        print(f"\nTemplate: {selected['name']}")
        print(f"Description:\n{selected['body']}")
        if input("\nUse this template to create a record? (y/n): ").lower() != 'y':
            return
        try:
            access.require_clinician(who, "create health records")
        except PermissionError as exc:
            print(exc)
            return
        student_id = input("Student ID: ").strip()
        description = selected['body']
        if "[FILL IN]" in description:
            print("Fill in each [FILL IN] (press Enter to leave a line as it is):")
            lines = []
            for line in description.split("\n"):
                if "[FILL IN]" in line:
                    answer = input(f"  {line.replace('[FILL IN]', '').strip()} ").strip()
                    line = line.replace("[FILL IN]", answer or "not recorded")
                lines.append(line)
            description = "\n".join(lines)
        record_date = input("Record date (YYYY-MM-DD) [today]: ").strip()
        provider = input(f"Provider [{who.username}]: ").strip()
        confidential = input("Confidential? (y/N): ").strip().lower() == 'y'
        try:
            record_id = create_record_from_template(
                conn, who, selected, student_id=student_id, description=description,
                record_date=record_date, provider=provider, confidential=confidential)
            conn.commit()
        except (PermissionError, ValueError, LookupError) as exc:
            conn.rollback()
            print(f"Not saved: {exc}")
            return
        print(f"\nHealth record #{record_id} created from '{selected['name']}'.")
    finally:
        conn.close()


def create_new_template(auth):
    """Create new health record template (saved in ``templates``)."""
    print("\n===== Create New Template =====")
    template_name = input("Template name: ").strip()
    print("\nCategories:")
    for i, category in enumerate(TEMPLATE_CATEGORIES, 1):
        print(f"{i}. {category}")
    category = _pick(TEMPLATE_CATEGORIES, f"\nSelect category (1-{len(TEMPLATE_CATEGORIES)}): ")
    if category is None:
        return
    if category == "Other":
        category = input("Enter custom category: ").strip() or "Other"
    record_type = input("Record type: ").strip()
    print("Template content (use [FILL IN] where the clinician completes it; "
          "finish with an empty line):")
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    conn = get_connection(row_factory=False)
    try:
        template_id = save_record_template(conn, name=template_name, category=category,
                                           record_type=record_type, body="\n".join(lines),
                                           by=auth.current_user['username'])
        conn.commit()
    except (ValueError, LookupError) as exc:
        conn.rollback()
        print(f"Not saved: {exc}")
        return
    finally:
        conn.close()
    print(f"\nTemplate '{template_name}' saved (#{template_id}).")
    print(f"Category: {category}")
    print(f"Record Type: {record_type or template_name}")


def template_usage_statistics(auth):
    """Show template usage statistics (records created from templates)."""
    print("\n===== Template Usage Statistics =====")
    conn = get_connection(row_factory=False)
    try:
        usage_stats = template_usage(conn)
    finally:
        conn.close()
    if not usage_stats:
        print("No health records have been created from a template in the last 30 days.")
        return
    print("Template Usage (Last 30 Days):")
    print(f"{'Template':<25} {'Uses':<8} {'Last Used':<12}")
    print("-" * 50)
    for stat in usage_stats:
        print(f"{stat['template']:<25} {stat['uses']:<8} {stat['last_used']:<12}")
    print(f"\nTotal template uses: {sum(stat['uses'] for stat in usage_stats)}")
    most_used = usage_stats[0]
    print(f"Most used template: {most_used['template']} ({most_used['uses']} uses)")

def edit_template(auth):
    """Edit an existing template's name/body if templates table exists."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='templates'")
        if not c.fetchone():
            print("No 'templates' table."); return
        tid = input("Template ID to edit: ").strip()
        if not tid.isdigit():
            print("Invalid ID."); return
        new_name = input("New name (leave blank to keep): ").strip()
        new_body = input("New body (leave blank to keep): ").strip()
        if new_name:
            c.execute("UPDATE templates SET name=? WHERE id=?", (new_name, int(tid)))
        if new_body:
            c.execute("UPDATE templates SET body=? WHERE id=?", (new_body, int(tid)))
        conn.commit()
        print("Template updated.")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")
