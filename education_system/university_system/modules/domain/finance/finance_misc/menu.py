# Backward-compatibility shim — redirects to finance.core.menu
import sys as _sys
from education_system.university_system.modules.domain.finance.core import menu as _real
_sys.modules[__name__] = _real
