from .models import Appointment
from .policies import appointment_is_in_future

def validate_appointment(appointment: Appointment) -> None:
    if not appointment.appointment_type.strip():
        raise ValueError("appointment_type is required")
    if not appointment_is_in_future(appointment.scheduled_at):
        raise ValueError("appointment must be scheduled in the future")
