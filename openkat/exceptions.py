class OpenKATError(Exception):
    pass


class ClearanceLevelTooLowException(Exception):
    pass


class AcknowledgedClearanceLevelTooLowException(ClearanceLevelTooLowException):
    pass


class TrustedClearanceLevelTooLowException(ClearanceLevelTooLowException):
    pass
