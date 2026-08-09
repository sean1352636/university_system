from ..facade import ACTIVITY_LOGGER_AVAILABLE

class ActivityLoggerAdapter:
    @property
    def available(self) -> bool:
        return ACTIVITY_LOGGER_AVAILABLE
