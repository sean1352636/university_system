"""Secondary school authentication - delegates to shared auth module.

Existing imports like ``from education_system.secondary_school.infrastructure.auth.core
import UserAuth`` continue to work unchanged.
"""

from education_system.shared.auth.core import UserAuth  # noqa: F401
from education_system.shared.auth.exceptions import AuthError  # noqa: F401
