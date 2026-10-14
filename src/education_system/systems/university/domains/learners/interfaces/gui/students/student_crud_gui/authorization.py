"""Authorization guards for student CRUD GUI callbacks."""

from tkinter import messagebox

from education_system.systems.university.infrastructure.i18n import get_text as _t


def require_student_permission(owner, permission: str, action: str) -> bool:
    """Fail closed unless the current GUI user still has *permission*.

    This guard belongs inside each public CRUD entry point and is called again
    by mutation callbacks.  Button visibility is presentation, not security,
    and a dialog may remain open after a user's permissions change.
    """
    auth = getattr(owner, "auth", None)
    current_user = getattr(auth, "current_user", None) if auth else None
    allowed = False
    if current_user:
        checker = getattr(auth, "check_permission", None)
        if not callable(checker):
            checker = getattr(auth, "has_permission", None)
        if callable(checker):
            try:
                allowed = bool(checker(permission))
            except Exception:
                allowed = False

    if not allowed:
        messagebox.showerror(
            _t("common.access_denied", default="Access denied"),
            f"You don't have permission to {action} student records.",
            parent=getattr(owner, "root", None),
        )
    return allowed
