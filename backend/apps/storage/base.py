from dataclasses import dataclass
from typing import BinaryIO, Protocol, Sequence


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    sha256: str


class StorageProvider(Protocol):
    def put_stream(
        self, key: str, stream: BinaryIO, *, expected_size: int
    ) -> StoredObject: ...

    def compose(
        self,
        source_keys: Sequence[str],
        destination_key: str,
        *,
        expected_size: int,
        expected_sha256: str,
    ) -> StoredObject: ...

    def open(self, key: str, mode: str = "rb") -> BinaryIO: ...
    def exists(self, key: str) -> bool: ...
    def size(self, key: str) -> int: ...
    def delete(self, key: str) -> bool: ...
    def move(self, source_key: str, destination_key: str) -> None: ...

