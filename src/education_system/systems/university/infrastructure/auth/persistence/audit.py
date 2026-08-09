from ..facade import UserAuth

class AuditPersistence:
    def __init__(self, auth: UserAuth):
        self.auth = auth
