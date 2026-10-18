from enum import Enum


class OutputFormat(str, Enum):
    PDF = "pdf"
    JPEG = "jpg"

    @property
    def file_extension(self) -> str:
        return self.value
