# Package initializer
from .base import HelpdeskGUI

# Import all modules to attach their methods to HelpdeskGUI
# These modules define functions and attach them using HelpdeskGUI.method = function
from . import dashboard
from . import tickets_my
from . import tickets_all
from . import ticket_create
from . import ticket_view
from . import ticket_actions
from . import knowledge_base
from . import search
from . import analytics_reports
from . import admin
from . import user_management
from . import departments_orgs
from . import sla_workflows
from . import export_import

# Re-export standalone functions
from .export_import import run_gui_helpdesk, display_helpdesk_menu_gui
