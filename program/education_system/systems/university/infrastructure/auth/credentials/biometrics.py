from ..facade import UserAuth

def enroll(auth: UserAuth, user_id, biometric_data):
    return auth.enroll_biometric(user_id, biometric_data)

def revoke(auth: UserAuth, user_id, enrollment_id):
    return auth.revoke_biometric_enrollment(user_id, enrollment_id)
