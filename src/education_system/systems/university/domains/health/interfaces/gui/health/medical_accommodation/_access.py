# _access.py
# Who may see, change and approve medical accommodations.
#
# Accommodations describe a student's condition, so they follow the health
# portal's rules (now kept in domain/disability/access, shared with the
# Disability & Accessibility portal):
#   * the health team and accommodation staff (view/manage/approve
#     accommodation permissions) see every student;
#   * a student sees only their own (by student number, never users.id);
#   * anyone else sees nothing.
# Adding, changing, removing, importing, exporting and reports need the
# health team or manage_accommodations; approving or rejecting needs a
# health administrator, an administrator, or approve/manage_accommodations.

import functools
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox

from education_system.systems.university.domains.student_support.domain.disability import access as _rules

# One set of rules for the whole Disability & Accessibility portal
# (domain/disability/access); these names are kept for existing callers.
TITLE = "Medical Accommodations"
STAFF_PERMISSIONS = _rules.STAFF_PERMISSIONS
APPROVER_ROLES = _rules.APPROVER_ROLES


def scope(auth):
    """``None`` = every student; a student number = only that one.
    Raises ``PermissionError`` for anyone else."""
    return _rules.scope(auth)


def may_manage(auth):
    return _rules.may_manage(auth)


def may_approve(auth):
    return _rules.may_decide(auth)


_CHECKS = {
    'manage': (may_manage, "Only the health team or accommodation managers can do this."),
    'approve': (may_approve, "Only a health administrator or an accommodation approver can "
                             "approve or reject accommodations."),
}


def gated(level, quiet=False):
    """Refuse the wrapped GUI action unless the signed-in user passes
    ``level`` ('manage' or 'approve'); ``quiet`` skips the message (for
    actions run while the window is being built)."""
    check, message = _CHECKS[level]

    def wrap(func):
        @functools.wraps(func)
        def inner(self, *args, **kwargs):
            if not check(getattr(self, 'auth', None)):
                if not quiet:
                    messagebox.showerror(TITLE, message)
                return None
            return func(self, *args, **kwargs)
        return inner
    return wrap


# GUI actions and the level each needs (applied in main_gui).
GATED_METHODS = {
    'add_accommodation_dialog': 'manage',
    'update_accommodation_dialog': 'manage',
    'remove_accommodation_dialog': 'manage',
    'import_csv': 'manage',
    'import_json': 'manage',
    'export_data': 'manage',
    'show_dashboard': 'manage',
    'generate_statistics': 'manage',
    'view_students_by_accommodation_type': 'manage',
    'check_expiry': 'manage',
    'bulk_operations_dialog': 'manage',
    'upload_document_dialog': 'manage',
    'save_template_dialog': 'manage',
    'apply_template_dialog': 'manage',
    'edit_template_dialog': 'manage',
    'delete_template_dialog': 'manage',
    'import_medical_templates': 'manage',
    'migrate_database_schema': 'manage',
    'approve_selected': 'approve',
    'reject_selected': 'approve',
    'approve_accommodation_dialog': 'approve',
    'process_approval': 'approve',
}
QUIET_METHODS = {'refresh_dashboard': 'manage'}


def apply(cls):
    """Wrap ``cls``'s gated actions in place."""
    for name, level in GATED_METHODS.items():
        if hasattr(cls, name):
            setattr(cls, name, gated(level)(getattr(cls, name)))
    for name, level in QUIET_METHODS.items():
        if hasattr(cls, name):
            setattr(cls, name, gated(level, quiet=True)(getattr(cls, name)))
    return cls


def row_visible(auth, student_id):
    try:
        allowed = scope(auth)
    except PermissionError:
        return False
    return allowed is None or str(student_id) == allowed
