from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.printer_controller import PrinterController
from digitalizadora.domain.scanner_route import ScannerRoute
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.services.printer_connection_service import PrinterConnectionState
from tests.controllers.controller_test_support import (
    StubPrinterConnectionService,
    build_test_client,
)

CATALOG = ErrorMessageCatalog()
CONNECTED_STATE = PrinterConnectionState(
    connected=True,
    display_name="HP DeskJet 2800 series [000001]",
    scanner_state=ScannerState.IDLE,
    error_code=None,
    route=ScannerRoute.USB,
)
CONNECTED_BODY = {
    "connected": True,
    "display_name": "HP DeskJet 2800 series [000001]",
    "scanner_state": "idle",
    "route": "usb",
    "error": None,
}
MANUAL_ADDRESS = "http://192.168.0.40:8080/eSCL"


def build_disconnected_state(error_code: str) -> PrinterConnectionState:
    return PrinterConnectionState(
        connected=False, display_name=None, scanner_state=None, error_code=error_code
    )


@pytest.fixture
def printer_service() -> StubPrinterConnectionService:
    return StubPrinterConnectionService(CONNECTED_STATE)


@pytest.fixture
def client(printer_service: StubPrinterConnectionService) -> TestClient:
    controller = PrinterController(printer_service, CATALOG)
    return build_test_client(controller.build_router())


def test_get_printer_describes_a_printer_connected_by_usb(client: TestClient) -> None:
    response = client.get("/api/printer")

    assert (response.status_code, response.json()) == (HTTPStatus.OK, CONNECTED_BODY)


def test_get_printer_reports_the_network_route(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    printer_service.connection_state = PrinterConnectionState(
        connected=True,
        display_name="HP DeskJet 2800 series [000001]",
        scanner_state=ScannerState.IDLE,
        error_code=None,
        route=ScannerRoute.NETWORK,
    )

    assert client.get("/api/printer").json()["route"] == "network"


@pytest.mark.parametrize("error_code", ["scanner_unreachable", "local_network_blocked"])
def test_get_printer_describes_a_missing_printer_with_the_catalog_message(
    client: TestClient, printer_service: StubPrinterConnectionService, error_code: str
) -> None:
    printer_service.connection_state = build_disconnected_state(error_code)

    body = client.get("/api/printer").json()

    assert body == {
        "connected": False,
        "display_name": None,
        "scanner_state": None,
        "route": None,
        "error": {"code": error_code, "message": CATALOG.message_for(error_code)},
    }


def test_get_printer_checks_the_connection_once(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    client.get("/api/printer")

    assert printer_service.calls == ["check_connection"]


def test_refresh_answers_with_the_connection_state(client: TestClient) -> None:
    response = client.post("/api/printer/refresh")

    assert (response.status_code, response.json()) == (HTTPStatus.OK, CONNECTED_BODY)


def test_refresh_searches_the_printer_again(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    client.post("/api/printer/refresh")

    assert printer_service.calls == ["refresh"]


def test_put_address_answers_with_the_connection_state(client: TestClient) -> None:
    response = client.put("/api/printer/address", json={"base_address": MANUAL_ADDRESS})

    assert (response.status_code, response.json()) == (HTTPStatus.OK, CONNECTED_BODY)


def test_put_address_stores_the_manual_address(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    client.put("/api/printer/address", json={"base_address": MANUAL_ADDRESS})

    assert printer_service.manual_addresses == [MANUAL_ADDRESS]


def test_put_address_checks_the_connection_after_storing_the_address(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    client.put("/api/printer/address", json={"base_address": MANUAL_ADDRESS})

    assert printer_service.calls == ["use_manual_address", "check_connection"]


def test_put_address_ignores_surrounding_whitespace(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    client.put("/api/printer/address", json={"base_address": f"  {MANUAL_ADDRESS}\n"})

    assert printer_service.manual_addresses == [MANUAL_ADDRESS]


@pytest.mark.parametrize(
    "invalid_address",
    ["", "   ", "192.168.0.40:8080/eSCL", "https://192.168.0.40/eSCL", "ftp://printer.local"],
)
def test_put_address_rejects_an_empty_or_non_http_address(
    client: TestClient, invalid_address: str
) -> None:
    response = client.put("/api/printer/address", json={"base_address": invalid_address})

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        {"code": "invalid_settings", "message": CATALOG.message_for("invalid_settings")},
    )


@pytest.mark.parametrize("invalid_address", ["", "ftp://printer.local"])
def test_a_rejected_address_never_reaches_the_service(
    client: TestClient, printer_service: StubPrinterConnectionService, invalid_address: str
) -> None:
    client.put("/api/printer/address", json={"base_address": invalid_address})

    assert printer_service.calls == []
