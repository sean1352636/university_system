from ..facade import UserAuth

class RecoveryPersistence:
    def __init__(self, auth: UserAuth):
        self.auth = auth
