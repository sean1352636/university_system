from ..facade import UserAuth

class RecoveryService:
    def __init__(self, auth: UserAuth):
        self.auth = auth
    def reset_password(self, *args, **kwargs):
        return self.auth.reset_password(*args, **kwargs)
    def unlock_account(self, *args, **kwargs):
        return self.auth.unlock_account(*args, **kwargs)
