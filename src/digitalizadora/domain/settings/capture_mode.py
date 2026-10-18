from enum import Enum


class CaptureMode(str, Enum):
    SINGLE = "single"  # quick mode: one click, one file (PDF or JPG)
    DOCUMENT = "document"  # document mode: many pages, one PDF
