from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Patient:
    patient_number: str
    user_id: str
    email: str = ""

@dataclass(frozen=True)
class Appointment:
    reference: str
    patient_number: str
    status: str

@dataclass(frozen=True)
class Treatment:
    reference: str
    patient_number: str
    treatment_type: str

@dataclass(frozen=True)
class Payment:
    reference: str
    amount: float
    method: str
