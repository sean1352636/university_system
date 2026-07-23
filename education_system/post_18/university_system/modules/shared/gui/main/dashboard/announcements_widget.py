"""Reusable, role-aware announcements panel for dashboards and portals.

Announcements created via the Email / Communications GUI (Communications →
Announcements tab → *Create Announcement*) are written to the ``announcements``
table.  This widget surfaces the active ones on any dashboard or role portal,
filtered to the audiences relevant to the logged-in user, so a new announcement
shows up everywhere that user can see — the main dashboard as well as the
student, instructor, staff, alumni and parent portals.

Both the query and the audience mapping intentionally mirror
``_AnnouncementsMixin.get_announcements`` (infrastructure/email/admin/
announcements.py) so the panel and the Communications GUI agree on what each
role is allowed to see.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
import logging

from education_system.post_18.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

# Which announcement audiences each role should see. Unknown or graduated roles
# (e.g. alumni, parent) only see announcements targeted at everyone ('all').
_ROLE_AUDIENCES = {
    'student': ['all', 'students'],
    'instructor': ['all', 'instructors'],
    'staff': ['all', 'staff'],
    # Admins post announcements, so let them preview every audience.
    'admin': ['all', 'staff', 'students', 'instructors'],
    'alumni': ['all'],
    'parent': ['all'],
}

_URGENT_COLOUR = '#b00020'
_NORMAL_COLOUR = '#003366'


def fetch_announcements(role, limit=5):
    """Return up to ``limit`` active announcements visible to ``role``.

    An announcement is *active* when ``is_active = 1`` and the current time
    falls within its ``start_date`` / ``end_date`` window.  Urgent items sort
    first, then most-recent.  Never raises — returns ``[]`` on any error.
    """
    audiences = _ROLE_AUDIENCES.get((role or '').lower(), ['all'])
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    placeholders = ','.join('?' for _ in audiences)
    query = f"""
        SELECT title, content, is_urgent, created_at
        FROM announcements
        WHERE is_active = 1
          AND start_date <= ?
          AND (end_date IS NULL OR end_date >= ?)
          AND target_audience IN ({placeholders})
        ORDER BY is_urgent DESC, created_at DESC
        LIMIT ?
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(query, (now, now, *audiences, limit)).fetchall()
        return [
            {
                'title': r['title'],
                'content': r['content'],
                'is_urgent': bool(r['is_urgent']),
                'created_at': r['created_at'],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"Could not load announcements: {e}")
        return []


def create_announcements_panel(parent, auth, limit=5, **pack_kwargs):
    """Build and pack an Announcements panel into ``parent``.

    Reads the current user's role from ``auth`` and shows the active
    announcements targeted at that audience.  Always returns the frame; on any
    error it degrades to an empty "No active announcements." panel rather than
    raising, so a dashboard is never broken by the announcements strip.

    Extra ``pack_kwargs`` are forwarded to the frame's ``pack`` call so callers
    can tune padding to match their layout.
    """
    frame = ttk.LabelFrame(parent, text="📢 Announcements", padding=10)
    pack_opts = {'fill': tk.X, 'padx': 15, 'pady': (10, 5)}
    pack_opts.update(pack_kwargs)
    frame.pack(**pack_opts)

    role = ''
    try:
        if auth and getattr(auth, 'current_user', None):
            role = auth.current_user.get('role', '') or ''
    except Exception:
        role = ''

    announcements = fetch_announcements(role, limit=limit)

    if not announcements:
        ttk.Label(frame, text="No active announcements.",
                  foreground="#777").pack(anchor='w')
        return frame

    for a in announcements:
        colour = _URGENT_COLOUR if a['is_urgent'] else _NORMAL_COLOUR
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, anchor='w', pady=2)

        bullet = "⚠ " if a['is_urgent'] else "● "  # ⚠ / ●
        tk.Label(row, text=f"{bullet}{a['title']}", foreground=colour,
                 font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

        # Show the first line of the body as a one-line summary.
        body_lines = (a['content'] or '').strip().splitlines()
        summary = body_lines[0].strip() if body_lines else ''
        if len(summary) > 100:
            summary = summary[:97] + '...'
        if summary:
            ttk.Label(row, text=f" — {summary}").pack(side=tk.LEFT)

    return frame
