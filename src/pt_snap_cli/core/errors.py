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


class ImportToolMissingError(PtSnapCoreError):
    """Raised when the vendored snapshot import backend is unavailable.

    In the vendored model, this no longer means "the user forgot to install
    memsnapdump" — the dump2db backend is built in. It means the vendored
    backend could not be imported or initialized, which is a packaging
    or installation problem.
    """

    pass


class SnapshotFileInvalidError(PtSnapCoreError):
    """Raised when a candidate snapshot pickle file cannot be used as input.

    Triggers include: path does not exist, path is not a regular file,
    suffix is not .pkl or .pickle, file cannot be unpickled, or the
    unpickled top-level object is not a dict.
    """

    pass


class ImportExecutionError(PtSnapCoreError):
    """Raised when the import backend itself fails to produce a database.

    Covers upstream dump2db returning False, raising an exception,
    or producing no .db artifact where one was expected.
    """

    pass
