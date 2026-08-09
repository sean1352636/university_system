from ..facade import UserAuth

class AuthenticationService:
    def __init__(self, auth: UserAuth):
        self.auth = auth
    def login(self, username: str, password: str):
        return self.auth.login(username, password)
    def logout(self):
        return self.auth.logout()
