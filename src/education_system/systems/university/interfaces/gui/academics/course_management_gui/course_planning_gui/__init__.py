"""Package split from the original course_planning_gui.py.

CoursePlanningGUI is reassembled from per-responsibility mixins so the
public class identity and call signatures stay identical to the original.
"""

from .mixins.lifecycle       import _LifecycleMixin
from .mixins.dashboard       import _DashboardMixin
from .mixins.planner         import _PlannerMixin
from .mixins.prerequisites   import _PrerequisitesMixin
from .mixins.recommendations import _RecommendationsMixin
from .mixins.conflicts       import _ConflictsMixin
from .mixins.export          import _ExportMixin
from .mixins.tools           import _ToolsMixin


class CoursePlanningGUI(
    _LifecycleMixin,
    _DashboardMixin,
    _PlannerMixin,
    _PrerequisitesMixin,
    _RecommendationsMixin,
    _ConflictsMixin,
    _ExportMixin,
    _ToolsMixin,
):
    """Main GUI for Course Planning Assistant.

    All methods inherited from per-responsibility mixins; see the mixins/
    subpackage. The constructor and entry points live in _LifecycleMixin.
    """
    pass


from .launcher import launch_course_planning_gui  # noqa: E402  (depends on CoursePlanningGUI)

__all__ = ["CoursePlanningGUI", "launch_course_planning_gui"]
