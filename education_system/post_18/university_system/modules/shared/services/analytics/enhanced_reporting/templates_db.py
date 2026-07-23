"""Template CRUD operations for enhanced reporting."""

import json
from datetime import datetime

from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting.config import logger
from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting.models import ReportTemplate


def save_template(template):
    """Save a report template to database with versioning"""
    from education_system.post_18.university_system.infrastructure.database.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    # Check if template with this name already exists
    cursor.execute("""
        SELECT template_id, template_content FROM email_templates
        WHERE template_name = ?
    """, (template.name,))
    existing = cursor.fetchone()

    template_dict = template.to_dict()
    template_json = json.dumps(template_dict)

    if existing:
        # Update existing template
        old_content = json.loads(existing[1]) if existing[1] else {}
        old_version = old_content.get("version", "1.0")
        major, minor = old_version.split(".")
        template.version = f"{major}.{int(minor) + 1}"
        template_dict = template.to_dict()
        template_json = json.dumps(template_dict)

        cursor.execute("""
            UPDATE email_templates
            SET template_content = ?, template_type = ?, created_date = ?
            WHERE template_id = ?
        """, (template_json, template_dict.get('sections', [{}])[0].get('type', 'custom') if template_dict.get('sections') else 'custom',
              datetime.now().isoformat(), existing[0]))
        logger.info(f"Template {template.name} updated to version {template.version}")
    else:
        # Insert new template
        cursor.execute("""
            INSERT INTO email_templates (template_name, template_content, template_type, created_date, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (template.name, template_json,
              template_dict.get('sections', [{}])[0].get('type', 'custom') if template_dict.get('sections') else 'custom',
              datetime.now().isoformat(), 'system'))
        logger.info(f"Template {template.name} created")

    conn.commit()
    conn.close()

    return template


def load_templates():
    """Load all report templates from database"""
    from education_system.post_18.university_system.infrastructure.database.db import get_connection

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT template_name, template_content FROM email_templates
            WHERE template_type = 'report_template'
            AND template_content IS NOT NULL AND template_content != ''
        """)
        rows = cursor.fetchall()
        conn.close()

        templates = []
        for row in rows:
            try:
                template_data = json.loads(row[1])
                # Ensure it has the expected structure
                if isinstance(template_data, dict) and 'name' in template_data:
                    templates.append(template_data)
                else:
                    # Try to create a basic template structure from the data
                    templates.append({
                        'name': row[0],
                        'description': 'Legacy template',
                        'sections': [],
                        'version': '1.0'
                    })
            except (json.JSONDecodeError, TypeError):
                # Skip invalid JSON entries
                continue

        return templates
    except Exception as e:
        logger.error(f"Error loading templates from database: {e}")
        return []


def save_template_dict(template_data):
    """Save a template dictionary directly to database (for simple templates)"""
    from education_system.post_18.university_system.infrastructure.database.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    # Check if template with this name already exists
    cursor.execute("""
        SELECT template_id FROM email_templates
        WHERE template_name = ? AND template_type = 'report_template'
    """, (template_data['name'],))
    existing = cursor.fetchone()

    template_json = json.dumps(template_data)

    if existing:
        # Update existing template
        cursor.execute("""
            UPDATE email_templates
            SET template_content = ?, created_date = ?
            WHERE template_id = ?
        """, (template_json, datetime.now().isoformat(), existing[0]))
        logger.info(f"Template {template_data['name']} updated")
    else:
        # Insert new template
        cursor.execute("""
            INSERT INTO email_templates (template_name, template_content, template_type, created_date, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (template_data['name'], template_json, 'report_template',
              datetime.now().isoformat(), 'system'))
        logger.info(f"Template {template_data['name']} created")

    conn.commit()
    conn.close()

    return template_data


def delete_template_from_db(template_name):
    """Delete a template from the database"""
    from education_system.post_18.university_system.infrastructure.database.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM email_templates
        WHERE template_name = ? AND template_type = 'report_template'
    """, (template_name,))

    conn.commit()
    deleted_count = cursor.rowcount
    conn.close()

    logger.info(f"Deleted {deleted_count} template(s) named {template_name}")
    return deleted_count > 0


def get_template(name):
    """Get a specific template by name"""
    templates = load_templates()
    for template_data in templates:
        if template_data["name"] == name:
            return ReportTemplate.from_dict(template_data)
    return None
