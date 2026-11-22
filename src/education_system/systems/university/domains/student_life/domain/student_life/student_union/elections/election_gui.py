"""Compatibility façade for the split implementation."""

from . import election_gui_shared as _shared
from .election_gui_shared import *  # noqa: F401,F403

from .election_gui_parts import bootstrap_auth_from_env as _part_1
_bootstrap_auth_from_env = _part_1._bootstrap_auth_from_env
_shared._bootstrap_auth_from_env = _bootstrap_auth_from_env
_shared.__all__.append("_bootstrap_auth_from_env") if "_bootstrap_auth_from_env" not in _shared.__all__ else None

from .election_gui_parts import database as _part_2
Database = _part_2.Database
_shared.Database = Database
_shared.__all__.append("Database") if "Database" not in _shared.__all__ else None

from .election_gui_parts import setup_styles as _part_3
setup_styles = _part_3.setup_styles
_shared.setup_styles = setup_styles
_shared.__all__.append("setup_styles") if "setup_styles" not in _shared.__all__ else None

from .election_gui_parts import full_name as _part_4
_full_name = _part_4._full_name
_shared._full_name = _full_name
_shared.__all__.append("_full_name") if "_full_name" not in _shared.__all__ else None

from .election_gui_parts import is_admin_user as _part_5
_is_admin_user = _part_5._is_admin_user
_shared._is_admin_user = _is_admin_user
_shared.__all__.append("_is_admin_user") if "_is_admin_user" not in _shared.__all__ else None

from .election_gui_parts import student_contact as _part_6
_student_contact = _part_6._student_contact
_shared._student_contact = _student_contact
_shared.__all__.append("_student_contact") if "_student_contact" not in _shared.__all__ else None

from .election_gui_parts import send_candidate_email as _part_7
_send_candidate_email = _part_7._send_candidate_email
_shared._send_candidate_email = _send_candidate_email
_shared.__all__.append("_send_candidate_email") if "_send_candidate_email" not in _shared.__all__ else None

from .election_gui_parts import bulk_email_active_students as _part_8
_bulk_email_active_students = _part_8._bulk_email_active_students
_shared._bulk_email_active_students = _bulk_email_active_students
_shared.__all__.append("_bulk_email_active_students") if "_bulk_email_active_students" not in _shared.__all__ else None

from .election_gui_parts import voterdashboard as _part_9
VoterDashboard = _part_9.VoterDashboard
_shared.VoterDashboard = VoterDashboard
_shared.__all__.append("VoterDashboard") if "VoterDashboard" not in _shared.__all__ else None

from .election_gui_parts import candidateswindow as _part_10
CandidatesWindow = _part_10.CandidatesWindow
_shared.CandidatesWindow = CandidatesWindow
_shared.__all__.append("CandidatesWindow") if "CandidatesWindow" not in _shared.__all__ else None

from .election_gui_parts import nominatedialog as _part_11
NominateDialog = _part_11.NominateDialog
_shared.NominateDialog = NominateDialog
_shared.__all__.append("NominateDialog") if "NominateDialog" not in _shared.__all__ else None

from .election_gui_parts import admindashboard_init as _part_12_1
from .election_gui_parts import admindashboard_build_campaigns_tab as _part_12_2
class AdminDashboard(_part_12_1.AdminDashboard, _part_12_2.AdminDashboard):
    pass
_shared.AdminDashboard = AdminDashboard
_shared.__all__.append("AdminDashboard") if "AdminDashboard" not in _shared.__all__ else None

from .election_gui_parts import candidatedialog as _part_13
CandidateDialog = _part_13.CandidateDialog
_shared.CandidateDialog = CandidateDialog
_shared.__all__.append("CandidateDialog") if "CandidateDialog" not in _shared.__all__ else None

from .election_gui_parts import app as _part_14
App = _part_14.App
_shared.App = App
_shared.__all__.append("App") if "App" not in _shared.__all__ else None

from .election_gui_parts import open_elections_hub as _part_15
open_elections_hub = _part_15.open_elections_hub
_shared.open_elections_hub = open_elections_hub
_shared.__all__.append("open_elections_hub") if "open_elections_hub" not in _shared.__all__ else None

from .election_gui_parts import open_in_toplevel as _part_16
open_in_toplevel = _part_16.open_in_toplevel
_shared.open_in_toplevel = open_in_toplevel
_shared.__all__.append("open_in_toplevel") if "open_in_toplevel" not in _shared.__all__ else None

_bootstrap_auth_from_env()

_exports = {name: globals()[name] for name in ['AdminDashboard', 'App', 'CandidateDialog', 'CandidatesWindow', 'Database', 'NominateDialog', 'VoterDashboard', '_bootstrap_auth_from_env', '_bulk_email_active_students', '_full_name', '_is_admin_user', '_send_candidate_email', '_student_contact', 'open_elections_hub', 'open_in_toplevel', 'setup_styles']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12_1, _part_12_2, _part_13, _part_14, _part_15, _part_16]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12_1, _part_12_2, _part_13, _part_14, _part_15, _part_16]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['AdminDashboard', 'App', 'CandidateDialog', 'CandidatesWindow', 'Database', 'NominateDialog', 'VoterDashboard', '_bootstrap_auth_from_env', '_bulk_email_active_students', '_full_name', '_is_admin_user', '_send_candidate_email', '_student_contact', 'open_elections_hub', 'open_in_toplevel', 'setup_styles']

if __name__ == "__main__":
    App().run()
