class RecoveryError(RuntimeError):
    pass

class InvalidRecoveryToken(RecoveryError):
    pass
