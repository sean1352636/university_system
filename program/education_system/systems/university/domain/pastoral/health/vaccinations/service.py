from datetime import date
from .models import Vaccination

def is_due(vaccination: Vaccination, *, today: date | None = None) -> bool:
    return vaccination.next_due_date is not None and vaccination.next_due_date <= (today or date.today())
