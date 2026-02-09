from .base import ParentPortalGUI

# Import all modules to attach their methods to ParentPortalGUI
from . import dashboard
from . import children
from . import menus
from . import grades
from . import attendance
from . import assignments
from . import medical
from . import transport
from . import messages
from . import meetings
from . import financial
from . import meal
from . import fundraising
from . import library
from . import activities
from . import goals
from . import calendar_docs
from . import account
from . import admin
from . import dialogs
from . import misc

__all__ = ['ParentPortalGUI']
