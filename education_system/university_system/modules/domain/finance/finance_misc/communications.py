# Backward-compatibility shim — redirects to finance.core.communications
import sys as _sys
from education_system.university_system.modules.domain.finance.core import communications as _real
_sys.modules[__name__] = _real
