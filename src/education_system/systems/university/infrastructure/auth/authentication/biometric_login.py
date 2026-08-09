from ..facade import UserAuth

def authenticate_biometric(auth: UserAuth, biometric_data):
    return auth.login_via_biometric(biometric_data)
