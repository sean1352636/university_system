from datetime import datetime
from .events import AuditEvent

def create_event(principal_id=None, **payload):
    return AuditEvent('authentication.recovery', datetime.now(), principal_id, payload)
