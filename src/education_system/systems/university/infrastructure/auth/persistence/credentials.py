from ..facade import UserAuth

class CredentialPersistence:
    def __init__(self, auth: UserAuth):
        self.auth = auth
