from ..facade import UserAuth

class CredentialService:
    def __init__(self, auth: UserAuth):
        self.auth = auth
    def change_password(self, *args, **kwargs):
        return self.auth.change_password(*args, **kwargs)
