"""Compatibility façade for the split implementation."""

from . import university_research_shared as _shared
from .university_research_shared import *  # noqa: F401,F403

from .university_research_parts import get_current_user as _part_1
_get_current_user = _part_1._get_current_user
_shared._get_current_user = _get_current_user
_shared.__all__.append("_get_current_user") if "_get_current_user" not in _shared.__all__ else None

from .university_research_parts import user_display_name as _part_2
_user_display_name = _part_2._user_display_name
_shared._user_display_name = _user_display_name
_shared.__all__.append("_user_display_name") if "_user_display_name" not in _shared.__all__ else None

from .university_research_parts import remove_legacy_db as _part_3
_remove_legacy_db = _part_3._remove_legacy_db
_shared._remove_legacy_db = _remove_legacy_db
_shared.__all__.append("_remove_legacy_db") if "_remove_legacy_db" not in _shared.__all__ else None

from .university_research_parts import charts as _part_3b
BarChart = _part_3b.BarChart
_shared.BarChart = BarChart
StatCard = _part_3b.StatCard
_shared.StatCard = StatCard
money = _part_3b.money
_shared.money = money
for _n in ('BarChart', 'StatCard', 'money'):
    if _n not in _shared.__all__:
        _shared.__all__.append(_n)

from .university_research_parts import people as _part_3c
for _n in ('fetch_people', 'people_index', 'person_name', 'person_choices',
           'person_key', 'split_key'):
    globals()[_n] = getattr(_part_3c, _n)
    setattr(_shared, _n, globals()[_n])
    if _n not in _shared.__all__:
        _shared.__all__.append(_n)

from .university_research_parts import database as _part_4
Database = _part_4.Database
_shared.Database = Database
_shared.__all__.append("Database") if "Database" not in _shared.__all__ else None

from .university_research_parts import configure_styles as _part_5
configure_styles = _part_5.configure_styles
_shared.configure_styles = configure_styles
_shared.__all__.append("configure_styles") if "configure_styles" not in _shared.__all__ else None

from .university_research_parts import status_colour as _part_6
status_colour = _part_6.status_colour
_shared.status_colour = status_colour
_shared.__all__.append("status_colour") if "status_colour" not in _shared.__all__ else None

from .university_research_parts import fmt_date as _part_7
fmt_date = _part_7.fmt_date
_shared.fmt_date = fmt_date
_shared.__all__.append("fmt_date") if "fmt_date" not in _shared.__all__ else None

from .university_research_parts import parse_date as _part_8
parse_date = _part_8.parse_date
_shared.parse_date = parse_date
_shared.__all__.append("parse_date") if "parse_date" not in _shared.__all__ else None

from .university_research_parts import fieldspec as _part_9
FieldSpec = _part_9.FieldSpec
_shared.FieldSpec = FieldSpec
_shared.__all__.append("FieldSpec") if "FieldSpec" not in _shared.__all__ else None

from .university_research_parts import recorddialog as _part_10
RecordDialog = _part_10.RecordDialog
_shared.RecordDialog = RecordDialog
_shared.__all__.append("RecordDialog") if "RecordDialog" not in _shared.__all__ else None

from .university_research_parts import moduletab as _part_11
ModuleTab = _part_11.ModuleTab
_shared.ModuleTab = ModuleTab
_shared.__all__.append("ModuleTab") if "ModuleTab" not in _shared.__all__ else None

from .university_research_parts import dashboardtab as _part_12
DashboardTab = _part_12.DashboardTab
_shared.DashboardTab = DashboardTab
_shared.__all__.append("DashboardTab") if "DashboardTab" not in _shared.__all__ else None

from .university_research_parts import tablemodule as _part_13
TableModule = _part_13.TableModule
_shared.TableModule = TableModule
_shared.__all__.append("TableModule") if "TableModule" not in _shared.__all__ else None

from .university_research_parts import ethicstab as _part_14
EthicsTab = _part_14.EthicsTab
_shared.EthicsTab = EthicsTab
_shared.__all__.append("EthicsTab") if "EthicsTab" not in _shared.__all__ else None

from .university_research_parts import outputstab as _part_15
OutputsTab = _part_15.OutputsTab
_shared.OutputsTab = OutputsTab
_shared.__all__.append("OutputsTab") if "OutputsTab" not in _shared.__all__ else None

from .university_research_parts import iptab as _part_16
IPTab = _part_16.IPTab
_shared.IPTab = IPTab
_shared.__all__.append("IPTab") if "IPTab" not in _shared.__all__ else None

from .university_research_parts import thesistab as _part_17
ThesisTab = _part_17.ThesisTab
_shared.ThesisTab = ThesisTab
_shared.__all__.append("ThesisTab") if "ThesisTab" not in _shared.__all__ else None

from .university_research_parts import peopletab as _part_18
PeopleTab = _part_18.PeopleTab
_shared.PeopleTab = PeopleTab
_shared.__all__.append("PeopleTab") if "PeopleTab" not in _shared.__all__ else None

from .university_research_parts import searchtab as _part_18b
SearchTab = _part_18b.SearchTab
_shared.SearchTab = SearchTab
_shared.__all__.append('SearchTab') if 'SearchTab' not in _shared.__all__ else None

from .university_research_parts import reportstab as _part_18c
ReportsTab = _part_18c.ReportsTab
_shared.ReportsTab = ReportsTab
_shared.__all__.append('ReportsTab') if 'ReportsTab' not in _shared.__all__ else None

from .university_research_parts import universityapp as _part_19
UniversityApp = _part_19.UniversityApp
_shared.UniversityApp = UniversityApp
_shared.__all__.append("UniversityApp") if "UniversityApp" not in _shared.__all__ else None

from .university_research_parts import main as _part_20
main = _part_20.main
_shared.main = main
_shared.__all__.append("main") if "main" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['BarChart', 'DashboardTab', 'fetch_people', 'people_index', 'person_name', 'person_choices', 'Database', 'EthicsTab', 'FieldSpec', 'IPTab', 'ModuleTab', 'OutputsTab', 'PeopleTab', 'RecordDialog', 'TableModule', 'ReportsTab', 'SearchTab', 'StatCard', 'ThesisTab', 'UniversityApp', '_get_current_user', '_remove_legacy_db', '_user_display_name', 'configure_styles', 'fmt_date', 'main', 'money', 'parse_date', 'status_colour']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_18b, _part_18c, _part_19, _part_20, _part_3b, _part_3c]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_18b, _part_18c, _part_19, _part_20, _part_3b, _part_3c]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['BarChart', 'DashboardTab', 'fetch_people', 'people_index', 'person_name', 'person_choices', 'Database', 'EthicsTab', 'FieldSpec', 'IPTab', 'ModuleTab', 'OutputsTab', 'PeopleTab', 'RecordDialog', 'TableModule', 'ReportsTab', 'SearchTab', 'StatCard', 'ThesisTab', 'UniversityApp', '_get_current_user', '_remove_legacy_db', '_user_display_name', 'configure_styles', 'fmt_date', 'main', 'money', 'parse_date', 'status_colour']

if __name__ == "__main__":
    main()
