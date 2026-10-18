from pathlib import Path

import pytest

from digitalizadora.configuration import ApplicationConfiguration

HOME_DIRECTORY = Path("/Users/example")


def build_configuration(environment: dict[str, str]) -> ApplicationConfiguration:
    return ApplicationConfiguration.from_environment(environment, HOME_DIRECTORY)


def test_data_directory_defaults_to_application_support() -> None:
    expected_directory = HOME_DIRECTORY / "Library" / "Application Support" / "Digitalizadora"
    assert build_configuration({}).data_directory == expected_directory


def test_log_directory_defaults_to_library_logs() -> None:
    expected_directory = HOME_DIRECTORY / "Library" / "Logs" / "Digitalizadora"
    assert build_configuration({}).log_directory == expected_directory


def test_default_output_folder_is_inside_pictures() -> None:
    expected_folder = HOME_DIRECTORY / "Pictures" / "Digitalizadora"
    assert build_configuration({}).default_output_folder == expected_folder


def test_port_defaults_to_8765() -> None:
    assert build_configuration({}).port == 8765


def test_host_defaults_to_loopback() -> None:
    assert build_configuration({}).host == "127.0.0.1"


def test_host_cannot_be_changed_by_the_environment() -> None:
    assert build_configuration({"DIGITALIZADORA_HOST": "0.0.0.0"}).host == "127.0.0.1"


def test_scanner_address_override_is_absent_by_default() -> None:
    assert build_configuration({}).scanner_address_override is None


def test_output_folder_can_be_overridden() -> None:
    environment = {"DIGITALIZADORA_OUTPUT_FOLDER": "/Volumes/Disco/Scans"}
    assert build_configuration(environment).default_output_folder == Path("/Volumes/Disco/Scans")


def test_blank_output_folder_falls_back_to_default() -> None:
    expected_folder = HOME_DIRECTORY / "Pictures" / "Digitalizadora"
    assert build_configuration({"DIGITALIZADORA_OUTPUT_FOLDER": "  "}).default_output_folder == expected_folder


@pytest.mark.parametrize(
    "raw_folder, expected_folder",
    [
        ("~/Scans", HOME_DIRECTORY / "Scans"),
        ("~", HOME_DIRECTORY),
        (" ~/Scans/2026 ", HOME_DIRECTORY / "Scans" / "2026"),
    ],
)
def test_home_shortcut_in_output_folder_uses_the_given_home(raw_folder: str, expected_folder: Path) -> None:
    environment = {"DIGITALIZADORA_OUTPUT_FOLDER": raw_folder}
    assert build_configuration(environment).default_output_folder == expected_folder


@pytest.mark.parametrize("raw_folder", ["relative/dir", "Scans", "./Scans", "~someone/Scans"])
def test_relative_output_folder_raises_value_error(raw_folder: str) -> None:
    with pytest.raises(ValueError, match="DIGITALIZADORA_OUTPUT_FOLDER"):
        build_configuration({"DIGITALIZADORA_OUTPUT_FOLDER": raw_folder})


@pytest.mark.parametrize(
    "raw_port, expected_port",
    [("1", 1), ("8765", 8765), ("65535", 65535), (" 9000 ", 9000)],
)
def test_valid_port_is_accepted(raw_port: str, expected_port: int) -> None:
    assert build_configuration({"DIGITALIZADORA_PORT": raw_port}).port == expected_port


@pytest.mark.parametrize("raw_port", ["0", "65536", "-1", "abc", "80.5", "", "   "])
def test_invalid_port_raises_value_error(raw_port: str) -> None:
    with pytest.raises(ValueError, match="DIGITALIZADORA_PORT"):
        build_configuration({"DIGITALIZADORA_PORT": raw_port})


def test_scanner_address_override_is_stripped() -> None:
    environment = {"DIGITALIZADORA_SCANNER_ADDRESS": "  http://127.0.0.1:8080/eSCL \n"}
    assert build_configuration(environment).scanner_address_override == "http://127.0.0.1:8080/eSCL"


@pytest.mark.parametrize("raw_address", ["", "   ", "\t\n"])
def test_blank_scanner_address_becomes_none(raw_address: str) -> None:
    environment = {"DIGITALIZADORA_SCANNER_ADDRESS": raw_address}
    assert build_configuration(environment).scanner_address_override is None
