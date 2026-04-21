class PtSnapCoreError(Exception):
    pass


class FocusNotConfiguredError(PtSnapCoreError):
    pass


class FocusFileInvalidError(PtSnapCoreError):
    pass


class DatabaseMissingError(PtSnapCoreError):
    pass


class DatabaseSchemaError(PtSnapCoreError):
    pass


class InvalidDeviceError(PtSnapCoreError):
    pass


class InvalidCategoryError(PtSnapCoreError):
    pass


class TemplateNotFoundError(PtSnapCoreError):
    pass


class TemplateRenderError(PtSnapCoreError):
    pass


class QueryExecutionError(PtSnapCoreError):
    pass
