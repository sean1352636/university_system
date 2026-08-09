class EventManagementError(RuntimeError):
    pass

class EventCapacityError(EventManagementError):
    pass

class RegistrationError(EventManagementError):
    pass

class EventPermissionError(EventManagementError):
    pass
