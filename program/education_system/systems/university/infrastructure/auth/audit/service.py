from dataclasses import asdict
from .immutable_store import ImmutableAuditStore

class SecurityAuditService:
    def __init__(self, store: ImmutableAuditStore):
        self.store = store
    def record(self, event):
        return self.store.append(asdict(event))
