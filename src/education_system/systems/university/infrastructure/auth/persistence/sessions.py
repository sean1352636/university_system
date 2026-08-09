from ..facade import UserAuth

class SessionPersistence:
    def __init__(self, auth: UserAuth):
        self.auth = auth
