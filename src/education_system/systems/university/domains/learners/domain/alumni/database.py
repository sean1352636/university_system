"""Alumni database setup.

The alumni tables are created by Alembic migrations (the baseline and
``e6a8c0d2f4b7``); nothing here creates tables at run time any more.
:func:`init_alumni_db` only applies the alumni-office additions to the open
database, and :func:`init_default_enhanced_data` adds the standard e-mail
templates and engagement badges (configuration, not records). It no longer
invents a fundraising campaign.
"""

from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection, sqlite3


def init_alumni_db():
    """Make sure the alumni-office columns and tables exist (idempotent)."""
    from education_system.systems.university.infrastructure.database.schemas import (
        alumni_office_schema,
    )
    try:
        conn = get_connection()
        try:
            alumni_office_schema.apply_to_connection(conn)
            init_default_enhanced_data(conn.cursor())
            conn.commit()
        finally:
            conn.close()
        return True
    except sqlite3.Error as e:
        print(f"An error occurred while preparing the alumni database: {e}")
        return False


def init_default_enhanced_data(cursor):
    """Standard e-mail templates and engagement badges (inserted once)."""
    templates = [
        ('Welcome Email', 'Welcome to our Alumni Network! We are excited to have you join our '
         'community.', 'welcome'),
        ('Event Invitation', 'You are invited to our upcoming alumni event. Please find details '
         'below.', 'event'),
        ('Newsletter Template', 'Alumni Newsletter - Stay connected with your alma mater and '
         'fellow alumni.', 'newsletter'),
        ('Job Posting', 'New job opportunity available through our alumni network.', 'job'),
        ('Donation Thank You', 'Thank you for your generous donation to our institution.',
         'donation'),
    ]
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for name, content, template_type in templates:
        if not cursor.execute("SELECT 1 FROM email_templates WHERE template_name = ? AND "
                              "template_type = ?", (name, template_type)).fetchone():
            cursor.execute("INSERT INTO email_templates (template_name, template_content, "
                           "template_type, created_date, created_by) VALUES (?, ?, ?, ?, "
                           "'system')", (name, content, template_type, now))
    badges = [
        ('New Member', 'Welcome to the alumni community!', 0, 'badge_new.png', 'engagement'),
        ('Active Networker', 'Made 10 networking connections', 100, 'badge_network.png',
         'networking'),
        ('Generous Donor', 'Made your first donation', 50, 'badge_donor.png', 'giving'),
        ('Event Enthusiast', 'Attended 5 events', 150, 'badge_events.png', 'events'),
        ('Mentor', 'Became a mentor to fellow alumni', 200, 'badge_mentor.png', 'mentoring'),
        ('Ambassador', 'Joined the ambassador program', 300, 'badge_ambassador.png',
         'leadership'),
    ]
    for name, desc, points, icon, category in badges:     # the table has no unique key
        if not cursor.execute("SELECT 1 FROM achievement_badges WHERE badge_name = ?",
                              (name,)).fetchone():
            cursor.execute("INSERT INTO achievement_badges (badge_name, badge_description, "
                           "points_required, badge_icon, category) VALUES (?, ?, ?, ?, ?)",
                           (name, desc, points, icon, category))
