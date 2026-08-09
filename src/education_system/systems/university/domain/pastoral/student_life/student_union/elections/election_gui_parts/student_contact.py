"""Extracted function implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _student_contact(db, student_id):
    """Resolve a student's inbox-routable email + display name.

    Prefers ``users.email`` (joined by ``students.student_id =
    users.student_id``) over ``students.email_address`` because the
    central ``send_email_db_only`` flow creates the inbox ``messages``
    row only when ``users.email`` matches the recipient address. If
    we sent to ``students.email_address`` and the two columns differ,
    the message lands in ``stored_emails`` but never reaches the
    in-app inbox.

    Falls back to ``students.email_address`` when no users row exists,
    so demo / unsynced students still get a stored copy.
    Returns ``(email_or_None, display_name)``.
    """
    if not student_id:
        return None, ""
    try:
        conn = db.connect()
        row = conn.execute(
            "SELECT u.email, s.email_address, "
            "       s.first_name, s.last_name "
            "FROM students s "
            "LEFT JOIN users u ON u.student_id = s.student_id "
            "WHERE s.student_id = ?",
            (student_id,)).fetchone()
        conn.close()
    except sqlite3.Error:
        return None, str(student_id)
    if not row:
        return None, str(student_id)
    user_email, student_email, first, last = row
    email = user_email or student_email or None
    name = _full_name(first, last, fallback=str(student_id))
    return email, name
