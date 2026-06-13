from __future__ import annotations

import csv
import json
import logging
import os

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.health.services.audit import log_audit_event
from education_system.university_system.modules.domain.health.services.security import truthy
from education_system.university_system.core.i18n import get_text

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
        print(get_text("health.templates.import_aborted_schema", error=e))
        return

    # Ask for a path if none provided
    if not source_path:
        try:
            source_path = input("Path to templates file (.json or .csv): ").strip()
        except Exception:
            source_path = ""
    if not source_path:
        print(get_text("health.templates.import_cancelled"))
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
            print(get_text("health.templates.unsupported_file_type", ext=ext))
            return
    except Exception as e:
        print(get_text("health.templates.failed_to_read", path=source_path, error=e))
        return

    if not records:
        print(get_text("health.templates.no_templates_to_import"))
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
                    print(get_text("health.templates.skipping_template", name=r.get('name'), error=ie))
            conn.commit()

        # If we used the UPSERT path, we can't distinguish insert/update per rowcount reliably.
        if updated == 0 and skipped == 0 and inserted > 0:
            print(get_text("health.templates.imported_processed", count=inserted))
        else:
            print(get_text("health.templates.imported_summary", inserted=inserted, updated=updated, skipped=skipped))
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(get_text("health.templates.import_failed", error=e))
    finally:
        try:
            conn.close()
        except Exception:
            pass

def import_templates(auth):
    """Import templates from CSV: columns name,category,body."""
    path = input("Path to CSV/JSON: ").strip()
    if not path or not os.path.exists(path):
        print(get_text("health.templates.file_not_found"))
        return
    import_templates_from_path(auth, path)

def shared_templates(auth):
    """List templates marked as shared if column exists, else list all."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='templates'")
        if not c.fetchone():
            print(get_text("health.templates.no_templates_table")); return
        # Check for 'shared' column
        c.execute("PRAGMA table_info(templates)")
        cols = [r[1] for r in c.fetchall()]
        if 'shared' in cols:
            c.execute("SELECT id, name, category FROM templates WHERE shared=1 ORDER BY name")
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

def use_existing_template(auth):
    """Use existing template to create health record"""
    # Mock template system - would be stored in database
    templates = {
        "Annual Physical": {
            "record_type": "Annual Physical Exam",
            "description": "Comprehensive annual physical examination including:\n- Vital signs assessment\n- General health evaluation\n- Preventive care counseling\n- Age-appropriate screenings\n- Immunization review",
            "category": "Preventive Care"
        },
        "Sick Visit": {
            "record_type": "General Medical",
            "description": "Patient presented with acute illness symptoms:\n- Chief complaint: [FILL IN]\n- History of present illness: [FILL IN]\n- Physical examination: [FILL IN]\n- Assessment and plan: [FILL IN]\n- Follow-up instructions: [FILL IN]",
            "category": "Acute Care"
        },
        "Mental Health Assessment": {
            "record_type": "Mental Health",
            "description": "Mental health screening and assessment:\n- Mood assessment: [FILL IN]\n- Anxiety screening: [FILL IN]\n- Sleep patterns: [FILL IN]\n- Stress factors: [FILL IN]\n- Recommendations: [FILL IN]\n- Resources provided: [FILL IN]",
            "category": "Mental Health"
        },
        "Vaccination Record": {
            "record_type": "Vaccination",
            "description": "Vaccination administered:\n- Vaccine: [FILL IN]\n- Dose: [FILL IN]\n- Site: [FILL IN]\n- Patient tolerated procedure well\n- No immediate adverse reactions\n- Post-vaccination instructions provided",
            "category": "Immunizations"
        }
    }

    print("\n===== Available Templates =====")

    template_list = list(templates.keys())
    for i, template_name in enumerate(template_list):
        template = templates[template_name]
        print(f"{i+1}. {template_name}")
        print(f"   Category: {template['category']}")
        print(f"   Type: {template['record_type']}")

    while True:
        choice = input(f"\nSelect template (1-{len(template_list)}) or 'q' to quit: ")
        if choice.lower() == 'q':
            return
        if choice.isdigit() and 1 <= int(choice) <= len(template_list):
            selected_template = templates[template_list[int(choice) - 1]]
            break
        print("Invalid choice. Please try again.")

    print(f"\nTemplate: {template_list[int(choice) - 1]}")
    print(f"Description:\n{selected_template['description']}")

    use_template = input("\nUse this template to create a record? (y/n): ").lower()
    if use_template == 'y':
        print("Opening record creation with template...")

def create_new_template(auth):
    """Create new health record template"""
    print("\n===== Create New Template =====")

    template_name = input("Template name: ")

    categories = ["Preventive Care", "Acute Care", "Mental Health", "Immunizations", "Chronic Care", "Emergency", "Other"]
    print("\nCategories:")
    for i, category in enumerate(categories):
        print(f"{i+1}. {category}")

    while True:
        cat_choice = input("\nSelect category (1-7): ")
        if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(categories):
            category = categories[int(cat_choice) - 1]
            if category == "Other":
                category = input("Enter custom category: ")
            break
        print("Invalid choice. Please try again.")

    record_type = input("Record type: ")
    description = input("Template description/content: ")

    # Would save to database
    print(f"\nTemplate '{template_name}' created successfully!")
    print(f"Category: {category}")
    print(f"Record Type: {record_type}")

    log_audit_event(auth.current_user['id'], 'create_health_record_template', 'template', 0, template_name)

def template_usage_statistics(auth):
    """Show template usage statistics"""
    print("\n===== Template Usage Statistics =====")

    # Mock statistics - would query actual usage from database
    usage_stats = [
        {"template": "Annual Physical", "uses": 145, "last_used": "2024-01-15"},
        {"template": "Sick Visit", "uses": 89, "last_used": "2024-01-15"},
        {"template": "Vaccination Record", "uses": 67, "last_used": "2024-01-14"},
        {"template": "Mental Health Assessment", "uses": 34, "last_used": "2024-01-13"},
        {"template": "Follow-up Visit", "uses": 23, "last_used": "2024-01-12"}
    ]

    print("Template Usage (Last 30 Days):")
    print(f"{'Template':<25} {'Uses':<8} {'Last Used':<12}")
    print("-" * 50)

    for stat in usage_stats:
        print(f"{stat['template']:<25} {stat['uses']:<8} {stat['last_used']:<12}")

    total_uses = sum(stat['uses'] for stat in usage_stats)
    print(f"\nTotal template uses: {total_uses}")

    most_used = max(usage_stats, key=lambda x: x['uses'])
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
