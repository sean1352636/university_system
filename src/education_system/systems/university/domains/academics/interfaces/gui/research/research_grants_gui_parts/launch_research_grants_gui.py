"""Extracted function implementation."""

from .. import research_grants_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def launch_research_grants_gui(root, auth):
    """Launch the Research & Grants Management GUI"""
    try:
        ResearchGrantsGUI(root, auth)
    except Exception as e:
        messagebox.showerror(_("common.error"), _("research_grants.errors.launch_failed").format(error=e))
        print(f"❌ Research & Grants GUI error: {e}")
