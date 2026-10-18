import re
from datetime import datetime

from digitalizadora.domain.output_format import OutputFormat

DATE_FORMAT = "%Y-%m-%d"
SEQUENCE_NUMBER_MINIMUM_DIGITS = 5
FIRST_SEQUENCE_NUMBER = 1
FILE_EXTENSIONS_PATTERN = "|".join(
    re.escape(output_format.file_extension) for output_format in OutputFormat
)


class ScanFileNamingPolicy:
    def build_file_name(
        self, scanned_at: datetime, sequence_number: int, output_format: OutputFormat
    ) -> str:
        date_text = scanned_at.strftime(DATE_FORMAT)
        padded_sequence = f"{sequence_number:0{SEQUENCE_NUMBER_MINIMUM_DIGITS}d}"
        return f"{date_text}_{padded_sequence}.{output_format.file_extension}"

    def extract_sequence_number(self, file_name: str, scanned_at: datetime) -> int | None:
        date_text = re.escape(scanned_at.strftime(DATE_FORMAT))
        pattern = (
            rf"{date_text}_([0-9]{{{SEQUENCE_NUMBER_MINIMUM_DIGITS},}})"
            rf"\.(?:{FILE_EXTENSIONS_PATTERN})"
        )
        match = re.fullmatch(pattern, file_name)
        if match is None:
            return None
        sequence_number = int(match.group(1))
        if sequence_number < FIRST_SEQUENCE_NUMBER:
            return None
        return sequence_number
