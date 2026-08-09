from ..facade import UserAuth

class FederationService:
    def __init__(self, auth: UserAuth):
        self.auth = auth
    def configure(self, *args, **kwargs):
        return self.auth.configure_sso_provider(*args, **kwargs)
