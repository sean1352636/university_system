from ..facade import UserAuth

class UserPersistence:
    def __init__(self, auth: UserAuth):
        self.auth = auth
