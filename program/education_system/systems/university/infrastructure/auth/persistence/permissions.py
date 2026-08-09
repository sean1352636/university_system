from ..facade import UserAuth

class PermissionPersistence:
    def __init__(self, auth: UserAuth):
        self.auth = auth
