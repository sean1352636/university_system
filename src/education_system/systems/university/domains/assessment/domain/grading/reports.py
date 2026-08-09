"""Compatibility façade for the split implementation."""

from . import reports_shared as _shared
from .reports_shared import *  # noqa: F401,F403

from .reports_parts import get_grading_imports as _part_1
_get_grading_imports = _part_1._get_grading_imports
_shared._get_grading_imports = _get_grading_imports
_shared.__all__.append("_get_grading_imports") if "_get_grading_imports" not in _shared.__all__ else None

from .reports_parts import generate_statistical_report as _part_2
generate_statistical_report = _part_2.generate_statistical_report
_shared.generate_statistical_report = generate_statistical_report
_shared.__all__.append("generate_statistical_report") if "generate_statistical_report" not in _shared.__all__ else None

from .reports_parts import generate_module_stats_report as _part_3
generate_module_stats_report = _part_3.generate_module_stats_report
_shared.generate_module_stats_report = generate_module_stats_report
_shared.__all__.append("generate_module_stats_report") if "generate_module_stats_report" not in _shared.__all__ else None

from .reports_parts import generate_all_modules_stats_report as _part_4
generate_all_modules_stats_report = _part_4.generate_all_modules_stats_report
_shared.generate_all_modules_stats_report = generate_all_modules_stats_report
_shared.__all__.append("generate_all_modules_stats_report") if "generate_all_modules_stats_report" not in _shared.__all__ else None

from .reports_parts import generate_course_stats_report as _part_5
generate_course_stats_report = _part_5.generate_course_stats_report
_shared.generate_course_stats_report = generate_course_stats_report
_shared.__all__.append("generate_course_stats_report") if "generate_course_stats_report" not in _shared.__all__ else None

from .reports_parts import generate_all_courses_stats_report as _part_6
generate_all_courses_stats_report = _part_6.generate_all_courses_stats_report
_shared.generate_all_courses_stats_report = generate_all_courses_stats_report
_shared.__all__.append("generate_all_courses_stats_report") if "generate_all_courses_stats_report" not in _shared.__all__ else None

from .reports_parts import generate_comprehensive_stats_report as _part_7
generate_comprehensive_stats_report = _part_7.generate_comprehensive_stats_report
_shared.generate_comprehensive_stats_report = generate_comprehensive_stats_report
_shared.__all__.append("generate_comprehensive_stats_report") if "generate_comprehensive_stats_report" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['_get_grading_imports', 'generate_all_courses_stats_report', 'generate_all_modules_stats_report', 'generate_comprehensive_stats_report', 'generate_course_stats_report', 'generate_module_stats_report', 'generate_statistical_report']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['_get_grading_imports', 'generate_all_courses_stats_report', 'generate_all_modules_stats_report', 'generate_comprehensive_stats_report', 'generate_course_stats_report', 'generate_module_stats_report', 'generate_statistical_report']
