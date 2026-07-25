"""Public entry points extracted from gui.py."""
from __future__ import annotations

import secrets
from datetime import datetime
from tkinter import messagebox

from education_system.systems.university.domain.pastoral.equality_diversity import integrations
from education_system.systems.university.domain.pastoral.equality_diversity.schema import get_connection, migrate

from . import EqualityDiversityGUI  # re-exported by __init__.py

def open_equality_diversity_gui(parent, auth_manager) -> EqualityDiversityGUI:
    """Open the E&D GUI using the already-authenticated session."""
    migrate()
    if not getattr(auth_manager, "current_user", None):
        messagebox.showerror(
            "Equality & Diversity",
            "You must be logged in to access the Equality & Diversity system.")
        raise PermissionError("open_equality_diversity_gui requires an authenticated user")
    return EqualityDiversityGUI(parent, auth_manager)




def submit_anonymous_record(token: str, fields: dict) -> bool:
    """feature 46 — anonymous self-identification via pre-issued token.

    This helper has **no** auth dependency; call from a web form or a public
    kiosk. Returns True on success.
    """
    migrate()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT used_at FROM ed_anonymous_tokens WHERE token=?", (token,)
        ).fetchone()
        if not row or row[0] is not None:
            return False
        ref = f"anon-{secrets.token_hex(4)}"
        conn.execute(
            "INSERT INTO ed_people (ref_code, person_type, gender, ethnicity, "
            "disability, religion, sexual_orientation, age_group, nationality, "
            "date_added) VALUES (?, 'Student', ?, ?, ?, ?, ?, ?, ?, ?)",
            (ref,
             fields.get("gender"), fields.get("ethnicity"),
             fields.get("disability"), fields.get("religion"),
             fields.get("sexual_orientation"), fields.get("age_group"),
             fields.get("nationality"),
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.execute(
            "UPDATE ed_anonymous_tokens SET used_at=? WHERE token=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), token))
        conn.commit()
    finally:
        conn.close()
    integrations.audit("anonymous", "self_id_submit", "person", ref)
    return True
