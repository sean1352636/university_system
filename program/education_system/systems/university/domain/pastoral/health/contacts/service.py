from .models import EmergencyContact

def validate_contact(contact: EmergencyContact) -> None:
    if not contact.name.strip() or not contact.phone.strip():
        raise ValueError("contact name and phone are required")
