# Backward-compatibility shim — redirects to finance.core.students
import sys as _sys
from education_system.university_system.modules.domain.finance.core import students as _real
_sys.modules[__name__] = _real
