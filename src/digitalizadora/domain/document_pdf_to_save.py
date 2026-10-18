from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO


@dataclass(frozen=True)
class DocumentPdfToSave:
    """A PDF written straight into the output stream, so the pages are never joined in memory."""

    write_content: Callable[[BinaryIO], None]
    created_at: datetime
    document_name: str
