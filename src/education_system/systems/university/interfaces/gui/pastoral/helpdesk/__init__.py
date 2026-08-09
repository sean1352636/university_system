# Package initializer
from education_system.systems.university.interfaces.gui.pastoral.helpdesk.base import HelpdeskGUI

# Import all modules to attach their methods to HelpdeskGUI
# These modules define functions and attach them using HelpdeskGUI.method = function
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import dashboard
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import tickets_my
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import tickets_all
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import ticket_create
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import ticket_view
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import ticket_actions
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import knowledge_base
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import search
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import analytics_reports
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import admin
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import user_management
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import departments_orgs
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import sla_workflows
from education_system.systems.university.interfaces.gui.pastoral.helpdesk import export_import

# Re-export standalone functions
from education_system.systems.university.interfaces.gui.pastoral.helpdesk.export_import import run_gui_helpdesk, display_helpdesk_menu_gui
