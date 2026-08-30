import os
import uuid
import abc
from typing import BinaryIO, Dict
import gridfs
from backend.app.core.config import settings
from backend.app.core.database import get_db, InMemoryMongoDb


class BaseStorageAdapter(abc.ABC):
    @abc.abstractmethod
    def save_file(self, file_obj: BinaryIO, original_filename: str) -> tuple[str, str, int]:
        pass

    @abc.abstractmethod
    def get_file_bytes(self, storage_key: str) -> bytes:
        pass

    @abc.abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        pass


class InMemoryStorageAdapter(BaseStorageAdapter):
    """In-memory file store for testing without any database setup."""
    def __init__(self):
        self._store: Dict[str, bytes] = {}

    def save_file(self, file_obj: BinaryIO, original_filename: str) -> tuple[str, str, int]:
        ext = os.path.splitext(original_filename)[1].lower()
        storage_key = f"{uuid.uuid4().hex}{ext}"
        file_obj.seek(0)
        file_bytes = file_obj.read()
        self._store[storage_key] = file_bytes
        return storage_key, storage_key, len(file_bytes)

    def get_file_bytes(self, storage_key: str) -> bytes:
        if storage_key in self._store:
            return self._store[storage_key]
        return b""

    def delete_file(self, storage_key: str) -> bool:
        if storage_key in self._store:
            del self._store[storage_key]
            return True
        return False


class MongoGridFSStorageAdapter(BaseStorageAdapter):
    def __init__(self):
        self.db = get_db()
        self.fs = gridfs.GridFS(self.db)

    def save_file(self, file_obj: BinaryIO, original_filename: str) -> tuple[str, str, int]:
        ext = os.path.splitext(original_filename)[1].lower()
        storage_key = f"{uuid.uuid4().hex}{ext}"
        file_obj.seek(0)
        file_bytes = file_obj.read()
        file_id = self.fs.put(
            file_bytes,
            filename=storage_key,
            original_name=original_filename,
            content_type=ext,
        )
        return storage_key, str(file_id), len(file_bytes)

    def get_file_bytes(self, storage_key: str) -> bytes:
        grid_out = self.fs.find_one({"filename": storage_key})
        if not grid_out:
            raise FileNotFoundError(f"File not found in GridFS: {storage_key}")
        return grid_out.read()

    def delete_file(self, storage_key: str) -> bool:
        grid_out = self.fs.find_one({"filename": storage_key})
        if grid_out:
            self.fs.delete(grid_out._id)
            return True
        return False


_in_memory_storage = InMemoryStorageAdapter()


def get_storage_adapter() -> BaseStorageAdapter:
    db = get_db()
    if isinstance(db, InMemoryMongoDb):
        return _in_memory_storage
    try:
        return MongoGridFSStorageAdapter()
    except Exception:
        return _in_memory_storage
