# Backward-compatibility shim — redirects to finance.core.aid
import sys as _sys
from education_system.university_system.modules.domain.finance.core import aid as _real
_sys.modules[__name__] = _real
