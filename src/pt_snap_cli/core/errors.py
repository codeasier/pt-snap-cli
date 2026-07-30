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
    """Raised when the built-in snapshot import backend is unavailable.

    The backend is part of pt-snap-cli, so this indicates a packaging or
    installation problem rather than a missing optional tool.
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

    Covers the snapshot adaptor returning False, raising an exception,
    or producing no .db artifact where one was expected.
    """

    pass


class ImportMetadataError(PtSnapCoreError):
    """Raised when import metadata cannot be read, written, or validated."""

    pass


class SourceChangedError(ImportExecutionError):
    """Raised when the source snapshot changes while an import is running."""

    pass
