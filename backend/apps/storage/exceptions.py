class StorageError(Exception):
    pass


class InvalidStorageKey(StorageError):
    pass


class StorageValidationError(StorageError):
    pass

