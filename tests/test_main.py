import logging
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from digitalizadora.__main__ import configure_logging, ensure_port_is_available, run_application

LOOPBACK_HOST = "127.0.0.1"


class RecordingUvicornRun:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, application: object, **options: object) -> None:
        self.calls.append(options)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK_HOST, 0))
        return probe.getsockname()[1]


@pytest.fixture(autouse=True)
def restore_root_logger() -> Iterator[None]:
    root_logger = logging.getLogger()
    http_client_logger = logging.getLogger("httpx")
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    original_http_client_level = http_client_logger.level
    yield
    for handler in list(root_logger.handlers):
        if handler not in original_handlers:
            root_logger.removeHandler(handler)
            handler.close()
    root_logger.setLevel(original_level)
    http_client_logger.setLevel(original_http_client_level)


def test_free_port_is_available() -> None:
    ensure_port_is_available(LOOPBACK_HOST, find_free_port())


def test_port_in_use_is_rejected() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((LOOPBACK_HOST, 0))
        listener.listen()
        with pytest.raises(OSError):
            ensure_port_is_available(LOOPBACK_HOST, listener.getsockname()[1])


def test_configure_logging_writes_to_the_log_directory(tmp_path: Path) -> None:
    configure_logging(tmp_path / "logs")
    logging.getLogger("digitalizadora.test").info("log line for the test")
    for handler in logging.getLogger().handlers:
        handler.flush()
    log_text = (tmp_path / "logs" / "digitalizadora.log").read_text(encoding="utf-8")
    assert "log line for the test" in log_text


def test_configure_logging_hides_one_line_per_scanner_request(tmp_path: Path) -> None:
    configure_logging(tmp_path / "logs")
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)


def test_invalid_port_is_explained_and_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_application({"DIGITALIZADORA_PORT": "abc"}, tmp_path)
    assert (exit_code, "Configuração inválida" in capsys.readouterr().out) == (1, True)


def test_relative_output_folder_is_explained_and_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_application({"DIGITALIZADORA_OUTPUT_FOLDER": "Scans"}, tmp_path)
    assert (exit_code, "DIGITALIZADORA_OUTPUT_FOLDER" in capsys.readouterr().out) == (1, True)


def test_port_in_use_is_explained_in_portuguese_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((LOOPBACK_HOST, 0))
        listener.listen()
        port = listener.getsockname()[1]
        exit_code = run_application({"DIGITALIZADORA_PORT": str(port)}, tmp_path)
    assert (exit_code, f"A porta {port} já está em uso" in capsys.readouterr().out) == (1, True)


def test_run_application_serves_on_the_configured_loopback_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = RecordingUvicornRun()
    monkeypatch.setattr(uvicorn, "run", recorder)
    port = find_free_port()
    exit_code = run_application({"DIGITALIZADORA_PORT": str(port)}, tmp_path)
    expected_options = {
        "host": LOOPBACK_HOST,
        "port": port,
        "log_level": "info",
        "log_config": None,
        "access_log": False,
    }
    assert (exit_code, recorder.calls) == (0, [expected_options])


def test_run_application_tells_how_to_open_the_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(uvicorn, "run", RecordingUvicornRun())
    port = find_free_port()
    run_application({"DIGITALIZADORA_PORT": str(port)}, tmp_path)
    output = capsys.readouterr().out
    assert (f"http://{LOOPBACK_HOST}:{port}" in output, "Terminal aberta" in output) == (True, True)
