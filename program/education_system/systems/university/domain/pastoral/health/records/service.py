from .models import HealthRecord

def has_clinical_information(record: HealthRecord) -> bool:
    return any((record.allergies, record.medications, record.conditions))
