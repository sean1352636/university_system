"""Extracted function implementation."""

from .. import degree_audit_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def launch_degree_audit_gui(root, auth):
    """Launch the Degree Audit & Academic Advising GUI"""
    try:
        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror(_("common.error"),
                               _("degree_audit.messages.must_be_logged_in"))
            return

        DegreeAuditGUI(root, auth)

    except Exception as e:
        messagebox.showerror(_("common.error"),
                           _("degree_audit.messages.failed_launch").format(error=e))
