class SmartTextileError(ValueError):
    pass


class UnknownRegistryCode(SmartTextileError):
    pass


class SchemaValidationError(SmartTextileError):
    pass


class ReleaseReadinessError(SmartTextileError):
    def __init__(self, reason_codes: tuple[str, ...]):
        self.reason_codes = reason_codes
        super().__init__(", ".join(reason_codes))
