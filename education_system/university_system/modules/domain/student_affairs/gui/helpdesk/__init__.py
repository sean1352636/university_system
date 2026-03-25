# Package initializer
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base import HelpdeskGUI

# Import all modules to attach their methods to HelpdeskGUI
# These modules define functions and attach them using HelpdeskGUI.method = function
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import dashboard
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import tickets_my
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import tickets_all
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import ticket_create
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import ticket_view
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import ticket_actions
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import knowledge_base
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import search
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import analytics_reports
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import admin
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import user_management
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import departments_orgs
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import sla_workflows
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import export_import

# Re-export standalone functions
from education_system.university_system.modules.domain.student_affairs.gui.helpdesk.export_import import run_gui_helpdesk, display_helpdesk_menu_gui
