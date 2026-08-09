"""Compatibility façade for the split implementation."""

from . import first_aid_portal_shared as _shared
from .first_aid_portal_shared import *  # noqa: F401,F403

from .first_aid_portal_parts import get_current_user as _part_1
_get_current_user = _part_1._get_current_user
_shared._get_current_user = _get_current_user
_shared.__all__.append("_get_current_user") if "_get_current_user" not in _shared.__all__ else None

from .first_aid_portal_parts import user_display_name as _part_2
_user_display_name = _part_2._user_display_name
_shared._user_display_name = _user_display_name
_shared.__all__.append("_user_display_name") if "_user_display_name" not in _shared.__all__ else None

from .first_aid_portal_parts import is_valid_email as _part_3
_is_valid_email = _part_3._is_valid_email
_shared._is_valid_email = _is_valid_email
_shared.__all__.append("_is_valid_email") if "_is_valid_email" not in _shared.__all__ else None

from .first_aid_portal_parts import is_valid_phone as _part_4
_is_valid_phone = _part_4._is_valid_phone
_shared._is_valid_phone = _is_valid_phone
_shared.__all__.append("_is_valid_phone") if "_is_valid_phone" not in _shared.__all__ else None

from .first_aid_portal_parts import is_valid_id as _part_5
_is_valid_id = _part_5._is_valid_id
_shared._is_valid_id = _is_valid_id
_shared.__all__.append("_is_valid_id") if "_is_valid_id" not in _shared.__all__ else None

from .first_aid_portal_parts import remove_legacy_db as _part_6
_remove_legacy_db = _part_6._remove_legacy_db
_shared._remove_legacy_db = _remove_legacy_db
_shared.__all__.append("_remove_legacy_db") if "_remove_legacy_db" not in _shared.__all__ else None

from .first_aid_portal_parts import firstaidportal_init as _part_7_1
from .first_aid_portal_parts import firstaidportal_create_report_tab as _part_7_2
from .first_aid_portal_parts import firstaidportal_resource_register_course as _part_7_3
from .first_aid_portal_parts import firstaidportal_admin_emails as _part_7_4
from .first_aid_portal_parts import firstaidportal_load_first_aid_data as _part_7_5
class FirstAidPortal(_part_7_1.FirstAidPortal, _part_7_2.FirstAidPortal, _part_7_3.FirstAidPortal, _part_7_4.FirstAidPortal, _part_7_5.FirstAidPortal):
    pass
_shared.FirstAidPortal = FirstAidPortal
_shared.__all__.append("FirstAidPortal") if "FirstAidPortal" not in _shared.__all__ else None

from .first_aid_portal_parts import main as _part_8
main = _part_8.main
_shared.main = main
_shared.__all__.append("main") if "main" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['FirstAidPortal', '_get_current_user', '_is_valid_email', '_is_valid_id', '_is_valid_phone', '_remove_legacy_db', '_user_display_name', 'main']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7_1, _part_7_2, _part_7_3, _part_7_4, _part_7_5, _part_8]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7_1, _part_7_2, _part_7_3, _part_7_4, _part_7_5, _part_8]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['FirstAidPortal', '_get_current_user', '_is_valid_email', '_is_valid_id', '_is_valid_phone', '_remove_legacy_db', '_user_display_name', 'main']

if __name__ == "__main__":
    main()
