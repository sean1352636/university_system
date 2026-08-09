"""Compatibility façade for the split implementation."""

from . import admin_support_schemas_shared as _shared
from .admin_support_schemas_shared import *  # noqa: F401,F403

from .admin_support_schemas_parts import init_course_evaluation_system_db as _part_1
init_course_evaluation_system_db = _part_1.init_course_evaluation_system_db
_shared.init_course_evaluation_system_db = init_course_evaluation_system_db
_shared.__all__.append("init_course_evaluation_system_db") if "init_course_evaluation_system_db" not in _shared.__all__ else None

from .admin_support_schemas_parts import init_auth_tables as _part_2
init_auth_tables = _part_2.init_auth_tables
_shared.init_auth_tables = init_auth_tables
_shared.__all__.append("init_auth_tables") if "init_auth_tables" not in _shared.__all__ else None

from .admin_support_schemas_parts import init_audit_tables as _part_3
init_audit_tables = _part_3.init_audit_tables
_shared.init_audit_tables = init_audit_tables
_shared.__all__.append("init_audit_tables") if "init_audit_tables" not in _shared.__all__ else None

from .admin_support_schemas_parts import init_documents_tables as _part_4
init_documents_tables = _part_4.init_documents_tables
_shared.init_documents_tables = init_documents_tables
_shared.__all__.append("init_documents_tables") if "init_documents_tables" not in _shared.__all__ else None

from .admin_support_schemas_parts import init_support_tables as _part_5
init_support_tables = _part_5.init_support_tables
_shared.init_support_tables = init_support_tables
_shared.__all__.append("init_support_tables") if "init_support_tables" not in _shared.__all__ else None

from .admin_support_schemas_parts import init_parent_tables as _part_6
init_parent_tables = _part_6.init_parent_tables
_shared.init_parent_tables = init_parent_tables
_shared.__all__.append("init_parent_tables") if "init_parent_tables" not in _shared.__all__ else None

from .admin_support_schemas_parts import init_library_tables as _part_7
init_library_tables = _part_7.init_library_tables
_shared.init_library_tables = init_library_tables
_shared.__all__.append("init_library_tables") if "init_library_tables" not in _shared.__all__ else None

from .admin_support_schemas_parts import init_commerce_tables as _part_8
init_commerce_tables = _part_8.init_commerce_tables
_shared.init_commerce_tables = init_commerce_tables
_shared.__all__.append("init_commerce_tables") if "init_commerce_tables" not in _shared.__all__ else None

from .admin_support_schemas_parts import init_other_tables as _part_9
init_other_tables = _part_9.init_other_tables
_shared.init_other_tables = init_other_tables
_shared.__all__.append("init_other_tables") if "init_other_tables" not in _shared.__all__ else None

from .admin_support_schemas_parts import init_certificate_tables as _part_10
init_certificate_tables = _part_10.init_certificate_tables
_shared.init_certificate_tables = init_certificate_tables
_shared.__all__.append("init_certificate_tables") if "init_certificate_tables" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['init_audit_tables', 'init_auth_tables', 'init_certificate_tables', 'init_commerce_tables', 'init_course_evaluation_system_db', 'init_documents_tables', 'init_library_tables', 'init_other_tables', 'init_parent_tables', 'init_support_tables']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['init_audit_tables', 'init_auth_tables', 'init_certificate_tables', 'init_commerce_tables', 'init_course_evaluation_system_db', 'init_documents_tables', 'init_library_tables', 'init_other_tables', 'init_parent_tables', 'init_support_tables']
