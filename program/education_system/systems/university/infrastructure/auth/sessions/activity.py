from ..facade import UserAuth

def update_last_activity(auth: UserAuth):
    return auth.update_activity()
