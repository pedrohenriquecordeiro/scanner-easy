import pytest

from digitalizadora.domain.output.output_format import OutputFormat


@pytest.mark.parametrize(
    ("output_format", "expected_extension"),
    [(OutputFormat.PDF, "pdf"), (OutputFormat.JPEG, "jpg")],
)
def test_file_extension_matches_format(
    output_format: OutputFormat, expected_extension: str
) -> None:
    assert output_format.file_extension == expected_extension


def test_format_is_created_from_its_stored_text() -> None:
    assert OutputFormat("jpg") is OutputFormat.JPEG
