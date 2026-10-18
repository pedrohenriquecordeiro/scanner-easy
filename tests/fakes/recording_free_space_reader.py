from pathlib import Path


class RecordingFreeSpaceReader:
    """Stands in for read_free_space_in_bytes: answers a fixed amount, or raises the configured failure."""

    def __init__(self, free_space_in_bytes: int) -> None:
        self._free_space_in_bytes = free_space_in_bytes
        self.failure: Exception | None = None
        self.requested_folders: list[Path] = []

    def __call__(self, folder: Path) -> int:
        self.requested_folders.append(folder)
        if self.failure is not None:
            raise self.failure
        return self._free_space_in_bytes
