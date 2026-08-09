from .exceptions import EventCapacityError, RegistrationError

def ensure_capacity(*, capacity: int | None, registered: int) -> None:
    if capacity is not None and capacity > 0 and registered >= capacity:
        raise EventCapacityError("event is at capacity")

def ensure_not_registered(already_registered: bool) -> None:
    if already_registered:
        raise RegistrationError("student is already registered")
