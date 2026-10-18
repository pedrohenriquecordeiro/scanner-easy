from pathlib import Path

from digitalizadora.configuration import ApplicationConfiguration

TEST_HOST = "127.0.0.1"
TEST_PORT = 8765


def build_application_configuration(
    tmp_path: Path, scanner_address_override: str | None
) -> ApplicationConfiguration:
    return ApplicationConfiguration(
        host=TEST_HOST,
        port=TEST_PORT,
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        default_output_folder=tmp_path / "scans",
        scanner_address_override=scanner_address_override,
    )
