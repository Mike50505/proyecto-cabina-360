import hashlib
import os
import uuid
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Sequence

from .base import StoredObject
from .exceptions import InvalidStorageKey, StorageValidationError


class LocalStorageProvider:
    chunk_size = 1024 * 1024

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        pure_key = PurePosixPath(key)
        if pure_key.is_absolute() or not pure_key.parts or ".." in pure_key.parts:
            raise InvalidStorageKey("La clave de almacenamiento no es válida.")
        path = (self.root / Path(*pure_key.parts)).resolve()
        if path != self.root and self.root not in path.parents:
            raise InvalidStorageKey("La clave escapa de la raíz de almacenamiento.")
        return path

    def put_stream(
        self, key: str, stream: BinaryIO, *, expected_size: int
    ) -> StoredObject:
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.writing")
        digest = hashlib.sha256()
        written = 0
        try:
            with temporary.open("xb") as output:
                while True:
                    block = stream.read(self.chunk_size)
                    if not block:
                        break
                    written += len(block)
                    if written > expected_size:
                        raise StorageValidationError("El stream excede el tamaño esperado.")
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            if written != expected_size:
                raise StorageValidationError("El stream no coincide con el tamaño esperado.")
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return StoredObject(key=key, size=written, sha256=digest.hexdigest())

    def compose(
        self,
        source_keys: Sequence[str],
        destination_key: str,
        *,
        expected_size: int,
        expected_sha256: str,
    ) -> StoredObject:
        destination = self._path(destination_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.writing")
        digest = hashlib.sha256()
        written = 0
        try:
            with temporary.open("xb") as output:
                for source_key in source_keys:
                    with self.open(source_key) as source:
                        while block := source.read(self.chunk_size):
                            written += len(block)
                            if written > expected_size:
                                raise StorageValidationError(
                                    "Las partes exceden el tamaño esperado."
                                )
                            digest.update(block)
                            output.write(block)
                output.flush()
                os.fsync(output.fileno())
            actual_sha256 = digest.hexdigest()
            if written != expected_size:
                raise StorageValidationError("Faltan bytes para completar el objeto.")
            if actual_sha256 != expected_sha256.lower():
                raise StorageValidationError("El checksum final no coincide.")
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return StoredObject(
            key=destination_key, size=written, sha256=digest.hexdigest()
        )

    def open(self, key: str, mode: str = "rb") -> BinaryIO:
        return self._path(key).open(mode)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def size(self, key: str) -> int:
        return self._path(key).stat().st_size

    def delete(self, key: str) -> bool:
        path = self._path(key)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    def move(self, source_key: str, destination_key: str) -> None:
        source = self._path(source_key)
        destination = self._path(destination_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)

