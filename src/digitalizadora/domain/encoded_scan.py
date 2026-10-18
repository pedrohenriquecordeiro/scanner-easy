from dataclasses import dataclass
from datetime import datetime

from digitalizadora.domain.output_format import OutputFormat


@dataclass(frozen=True)
class EncodedScan:
    content: bytes
    output_format: OutputFormat
    created_at: datetime
