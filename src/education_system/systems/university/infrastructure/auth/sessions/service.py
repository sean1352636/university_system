from ..facade import UserAuth

class SessionService:
    def __init__(self, auth: UserAuth):
        self.auth = auth
    def validate(self) -> bool:
        return self.auth.check_session()
    def terminate(self):
        return self.auth.logout()
