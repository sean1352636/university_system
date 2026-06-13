"""Package split from the original gui.py.

EqualityDiversityGUI is reassembled from per-responsibility mixins so the
class identity and signatures stay identical. The two entry-point functions
and the constants/helpers/dialogs sub-modules are re-exported for any
caller that referenced them on the original module.
"""
from __future__ import annotations

from .mixins.lifecycle  import _LifecycleMixin
from .mixins.dashboard  import _DashboardMixin
from .mixins.records    import _RecordsMixin
from .mixins.add_record import _Add_recordMixin
from .mixins.incidents  import _IncidentsMixin
from .mixins.reports    import _ReportsMixin
from .mixins.my_data    import _My_dataMixin
from .mixins.admin      import _AdminMixin


class EqualityDiversityGUI(
    _LifecycleMixin,
    _DashboardMixin,
    _RecordsMixin,
    _Add_recordMixin,
    _IncidentsMixin,
    _ReportsMixin,
    _My_dataMixin,
    _AdminMixin,
):
    """Main GUI for the Equality & Diversity system.

    All methods inherited from per-responsibility mixins in the mixins/
    subpackage. The constructor and lifecycle live in _LifecycleMixin.
    """
    pass


# Re-exports for code that imported helpers / dialogs / constants
# directly from the original gui.py.
from ._constants import (  # noqa: E402,F401
    PERSON_TYPES, DEPARTMENTS, AGE_GROUPS, GENDERS, ETHNICITIES,
    DISABILITY_STATUS, RELIGIONS, SEXUAL_ORIENTATIONS,
    INCIDENT_CATEGORIES, INCIDENT_STATUS, SEVERITIES, SLA_DAYS,
    FIELD_OPTIONS, THEMES, PAGE_SIZE,
)
from ._helpers   import _t, _prompt_string, _render_bar_table, _embed_chart  # noqa: E402,F401
from ._dialogs   import RecordEditor, MergeDialog, IncidentDetail, ScheduleEditor  # noqa: E402,F401
from .entrypoints import open_equality_diversity_gui, submit_anonymous_record  # noqa: E402

__all__ = [
    "EqualityDiversityGUI",
    "open_equality_diversity_gui",
    "submit_anonymous_record",
]
