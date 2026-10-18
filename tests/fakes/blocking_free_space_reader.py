import threading
from pathlib import Path

# Only a broken test ever reaches it: the held reading then gives up instead of hanging the suite.
RELEASE_TIMEOUT_SECONDS = 2.0


class BlockingFreeSpaceReader:
    """Stands in for read_free_space_in_bytes and holds the first reading until release().

    Injected in the StorageGuardService of the DocumentFinalizer: checking the free space is the first
    thing a finalization does with the lock held (6.6.3, step 3), so a test can make requests while the
    lock is busy. entered is set when the first reading starts; later readings answer at once.
    """

    def __init__(self, free_space_in_bytes: int) -> None:
        self._free_space_in_bytes = free_space_in_bytes
        self._released = threading.Event()
        self.entered = threading.Event()

    def release(self) -> None:
        self._released.set()

    def __call__(self, folder: Path) -> int:
        if not self.entered.is_set():
            self.entered.set()
            self._released.wait(RELEASE_TIMEOUT_SECONDS)
        return self._free_space_in_bytes
