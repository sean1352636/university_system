import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import logging

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.email.template_utils import render_template

from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

from education_system.university_system.modules.domain.student_affairs.services.internship_management import (
    setup_internship_permissions,
    init_internship_db,
    set_auth,
    view_available_internships,
    view_internship_details,
    apply_for_internship,
    view_applications,
    review_application,
    create_internship,
    edit_internship,
    delete_internship,
    generate_internship_report,
    display_internship_menu
)

logger = logging.getLogger(__name__)
