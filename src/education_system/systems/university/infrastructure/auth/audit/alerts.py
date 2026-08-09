from ..facade import SECURITY_ALERTS_AVAILABLE

class SecurityAlertAdapter:
    @property
    def available(self) -> bool:
        return SECURITY_ALERTS_AVAILABLE
