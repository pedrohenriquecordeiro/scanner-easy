from dataclasses import dataclass


@dataclass(frozen=True)
class ScannedImage:
    content: bytes
    media_type: str
