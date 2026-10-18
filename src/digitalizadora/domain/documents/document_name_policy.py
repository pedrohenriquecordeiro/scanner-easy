import re
import unicodedata

from digitalizadora.domain.errors import InvalidDocumentNameError

MAXIMUM_DOCUMENT_NAME_CHARACTERS = 120
MAXIMUM_DOCUMENT_NAME_BYTES = 200
FORBIDDEN_FILE_NAME_CHARACTERS = frozenset('/\\:*?"<>|')
FORBIDDEN_CHARACTER_REPLACEMENT = "-"
REMOVED_UNICODE_CATEGORIES = frozenset({"Cc", "Cf", "Cs"})
PDF_FILE_SUFFIX = ".pdf"
UNICODE_NORMAL_FORM = "NFC"
NAME_ENCODING = "utf-8"
SPACE = " "
REPEATED_SPACES_PATTERN = re.compile(" {2,}")
EDGE_CHARACTERS_TO_STRIP = ". "
FIRST_ATTEMPT_NUMBER = 1


def _clean_character(character: str) -> str:
    if character.isspace():
        return SPACE
    if character in FORBIDDEN_FILE_NAME_CHARACTERS:
        return FORBIDDEN_CHARACTER_REPLACEMENT
    if unicodedata.category(character) in REMOVED_UNICODE_CATEGORIES:
        return ""
    return character


def _without_pdf_suffix(name: str) -> str:
    if name.lower().endswith(PDF_FILE_SUFFIX):
        return name[: -len(PDF_FILE_SUFFIX)]
    return name


def clean_document_name(raw_name: str) -> str:
    """Turns what the user typed into a file name that APFS and exFAT accept; "" means the automatic name.

    A name that is too long is refused, never cut short silently.
    """
    normalized = unicodedata.normalize(UNICODE_NORMAL_FORM, raw_name)
    replaced = "".join(_clean_character(character) for character in normalized)
    collapsed = REPEATED_SPACES_PATTERN.sub(SPACE, replaced).strip(SPACE)
    cleaned = _without_pdf_suffix(collapsed).lstrip(EDGE_CHARACTERS_TO_STRIP).rstrip(EDGE_CHARACTERS_TO_STRIP)
    if not cleaned:
        if not raw_name.strip():
            return ""
        raise InvalidDocumentNameError(f"{raw_name!r} has no visible character left after cleaning")
    too_many_characters = len(cleaned) > MAXIMUM_DOCUMENT_NAME_CHARACTERS
    too_many_bytes = len(cleaned.encode(NAME_ENCODING)) > MAXIMUM_DOCUMENT_NAME_BYTES
    if too_many_characters or too_many_bytes:
        raise InvalidDocumentNameError(f"{cleaned!r} is longer than a document name may be")
    return cleaned


def build_document_file_name(document_name: str, attempt_number: int) -> str:
    """The first attempt is "<name>.pdf"; attempt n is "<name> (n).pdf". Receives an already clean name."""
    if attempt_number == FIRST_ATTEMPT_NUMBER:
        return f"{document_name}{PDF_FILE_SUFFIX}"
    return f"{document_name} ({attempt_number}){PDF_FILE_SUFFIX}"
