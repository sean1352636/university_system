from .main_gui import ModuleSchedulingGUI, main, launch_gui, launch_cli, create_desktop_shortcut, setup_application, launch_module_scheduling_gui, run_gui_with_database

# Import all tab modules to attach methods to ModuleSchedulingGUI
from . import dashboard_tab
from . import schedules_tab
from . import rooms_tab
from . import instructors_tab
from . import timetables_tab
from . import analytics_tab
from . import conflicts_tab
from . import management_tab
from . import settings_tab
from . import modules_tab
from . import scheduling_engine
from . import notifications
from . import exports
from . import dialogs
from . import backup
from . import misc
