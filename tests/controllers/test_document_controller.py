import logging
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.document_body import build_document_body
from digitalizadora.controllers.document_controller import (
    DOCUMENT_ERROR_STATUSES,
    THUMBNAIL_CACHE_HEADERS,
    DocumentController,
)
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import (
    DamagedDocumentPageError,
    DigitalizadoraError,
    DocumentAssemblyFailedError,
    DocumentBusyError,
    DocumentTooLargeError,
    DraftStorageUnavailableError,
    EmptyDocumentError,
    InsufficientDraftStorageError,
    InsufficientStorageError,
    InvalidDocumentNameError,
    InvalidPageOrderError,
    NoOpenDocumentError,
    OutputFolderUnavailableError,
    PageNotFoundError,
    ScanAlreadyRunningError,
    ScannerUnreachableError,
)
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from tests.controllers.controller_test_support import StubFolderPreparer, build_test_client
from tests.fakes.document_drafts import page_identifier_at
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.stub_document_draft_service import StubDocumentDraftService, build_stub_snapshot

CATALOG = ErrorMessageCatalog()
ADJUSTMENT = ImageAdjustment(rotation=PageRotation.HALF_TURN, auto_crop=True)
SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.PDF,
    scan_settings=ScanPreset.PHOTO.settings,
    adjustment=ADJUSTMENT,
)
SECOND_PAGE_IDENTIFIER = page_identifier_at(2)
REVERSED_PAGE_ORDER = [page_identifier_at(2), page_identifier_at(1)]


@dataclass(frozen=True)
class EditRequest:
    method: str
    path: str
    body: object = None


@dataclass(frozen=True)
class ExpectedFailure:
    error: DigitalizadoraError
    status: HTTPStatus


EDIT_REQUESTS = [
    EditRequest("DELETE", "/api/document/pages/last"),
    EditRequest("DELETE", f"/api/document/pages/{SECOND_PAGE_IDENTIFIER}"),
    EditRequest("PUT", "/api/document/page-order", {"page_identifiers": REVERSED_PAGE_ORDER}),
    EditRequest("PUT", "/api/document/name", {"name": "Contrato"}),
    EditRequest("POST", "/api/document/finalize"),
    EditRequest("DELETE", "/api/document"),
]
DRAFT_STORAGE_FAILURES = [
    ExpectedFailure(DraftStorageUnavailableError("disk unreadable"), HTTPStatus.SERVICE_UNAVAILABLE),
    ExpectedFailure(InsufficientDraftStorageError("disk full"), HTTPStatus.INSUFFICIENT_STORAGE),
]
FINALIZE_FAILURES = [
    ExpectedFailure(ScanAlreadyRunningError("scan running"), HTTPStatus.CONFLICT),
    ExpectedFailure(NoOpenDocumentError("no draft"), HTTPStatus.NOT_FOUND),
    ExpectedFailure(EmptyDocumentError("no pages"), HTTPStatus.UNPROCESSABLE_ENTITY),
    ExpectedFailure(OutputFolderUnavailableError("external disk gone"), HTTPStatus.SERVICE_UNAVAILABLE),
    ExpectedFailure(InsufficientStorageError("output disk full"), HTTPStatus.INSUFFICIENT_STORAGE),
    ExpectedFailure(DraftStorageUnavailableError("page unreadable"), HTTPStatus.SERVICE_UNAVAILABLE),
    ExpectedFailure(DocumentAssemblyFailedError("not an image"), HTTPStatus.INTERNAL_SERVER_ERROR),
    ExpectedFailure(DocumentTooLargeError("out of memory"), HTTPStatus.INTERNAL_SERVER_ERROR),
]


def describe_edit_request(edit_request: EditRequest) -> str:
    return f"{edit_request.method} {edit_request.path}"


def describe_expected_failure(expected_failure: ExpectedFailure) -> str:
    return expected_failure.error.code


def build_error_answer(error: DigitalizadoraError, status: HTTPStatus) -> tuple[HTTPStatus, dict[str, str]]:
    return status, {"code": error.code, "message": CATALOG.message_for(error.code)}


def build_expected_answer(expected_failure: ExpectedFailure) -> tuple[HTTPStatus, dict[str, str]]:
    return build_error_answer(expected_failure.error, expected_failure.status)


@pytest.fixture
def document_service() -> StubDocumentDraftService:
    return StubDocumentDraftService(build_stub_snapshot(2))


@pytest.fixture
def client(document_service: StubDocumentDraftService) -> TestClient:
    settings_service = ApplicationSettingsService(
        InMemoryApplicationSettingsRepository(SETTINGS), StubFolderPreparer()
    )
    controller = DocumentController(document_service, settings_service, CATALOG)
    return build_test_client(controller.build_router())


def test_get_document_answers_the_body_of_the_current_snapshot(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    response = client.get("/api/document")

    assert (response.status_code, response.json()) == (
        HTTPStatus.OK,
        build_document_body(document_service.draft_snapshot),
    )


def test_get_document_without_a_draft_answers_a_null_document(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    document_service.draft_snapshot = build_stub_snapshot(0)

    assert client.get("/api/document").json()["document"] is None


def test_post_pages_answers_202_accepted(client: TestClient) -> None:
    response = client.post("/api/document/pages")

    assert (response.status_code, response.json()) == (HTTPStatus.ACCEPTED, {"accepted": True})


def test_post_pages_adds_a_page_with_the_saved_quality_and_adjustment(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    client.post("/api/document/pages")

    assert document_service.received_arguments["add_page"] == (ScanPreset.PHOTO.settings, ADJUSTMENT)


@pytest.mark.parametrize(
    "refusal", [ScanAlreadyRunningError("scan running"), DocumentBusyError("finalizing")], ids=lambda error: error.code
)
def test_post_pages_answers_409_when_a_page_cannot_start(
    client: TestClient, document_service: StubDocumentDraftService, refusal: DigitalizadoraError
) -> None:
    document_service.add_page_refusal = refusal

    response = client.post("/api/document/pages")

    assert (response.status_code, response.json()) == build_error_answer(refusal, HTTPStatus.CONFLICT)


def test_refused_post_pages_does_not_add_a_page(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    document_service.add_page_refusal = DocumentBusyError("finalizing")

    client.post("/api/document/pages")

    assert document_service.calls == ["ensure_can_add_page"]


def test_a_page_failure_in_the_background_does_not_change_the_answer(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    document_service.failure = ScannerUnreachableError("printer offline")

    assert client.post("/api/document/pages").status_code == HTTPStatus.ACCEPTED


def test_a_page_failure_in_the_background_is_logged_with_its_code(
    client: TestClient, document_service: StubDocumentDraftService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    document_service.failure = DocumentBusyError("another change started first")

    client.post("/api/document/pages")

    assert "document_busy" in caplog.text


def test_an_unexpected_page_failure_in_the_background_is_logged(
    client: TestClient, document_service: StubDocumentDraftService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR)
    document_service.failure = RuntimeError("boom")

    client.post("/api/document/pages")

    assert "boom" in caplog.text


@pytest.mark.parametrize("edit_request", EDIT_REQUESTS, ids=describe_edit_request)
def test_every_edit_answers_409_during_a_scan(
    client: TestClient, document_service: StubDocumentDraftService, edit_request: EditRequest
) -> None:
    refusal = ScanAlreadyRunningError("scan running")
    document_service.failure = refusal

    response = client.request(edit_request.method, edit_request.path, json=edit_request.body)

    assert (response.status_code, response.json()) == build_error_answer(refusal, HTTPStatus.CONFLICT)


def test_discard_last_page_answers_the_body_after_the_edit(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    document_service.snapshot_after_edit = build_stub_snapshot(1)

    response = client.delete("/api/document/pages/last")

    assert (response.status_code, response.json()) == (HTTPStatus.OK, build_document_body(build_stub_snapshot(1)))


def test_pages_last_is_not_taken_for_a_page_identifier(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    client.delete("/api/document/pages/last")

    assert document_service.calls == ["discard_last_page"]


def test_discarding_the_only_page_answers_a_null_document(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    document_service.snapshot_after_edit = build_stub_snapshot(0)

    assert client.delete("/api/document/pages/last").json()["document"] is None


def test_discard_last_page_without_a_draft_answers_404(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    refusal = NoOpenDocumentError("no draft")
    document_service.failure = refusal

    response = client.delete("/api/document/pages/last")

    assert (response.status_code, response.json()) == build_error_answer(refusal, HTTPStatus.NOT_FOUND)


def test_delete_page_passes_the_identifier_of_the_path(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    client.delete(f"/api/document/pages/{SECOND_PAGE_IDENTIFIER}")

    assert document_service.received_arguments["delete_page"] == SECOND_PAGE_IDENTIFIER


def test_delete_page_answers_the_body_after_the_edit(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    document_service.snapshot_after_edit = build_stub_snapshot(1)

    response = client.delete(f"/api/document/pages/{SECOND_PAGE_IDENTIFIER}")

    assert (response.status_code, response.json()) == (HTTPStatus.OK, build_document_body(build_stub_snapshot(1)))


def test_delete_of_an_unknown_page_answers_404(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    refusal = PageNotFoundError("not in the draft")
    document_service.failure = refusal

    response = client.delete("/api/document/pages/not-a-page")

    assert (response.status_code, response.json()) == build_error_answer(refusal, HTTPStatus.NOT_FOUND)


@pytest.mark.parametrize("expected_failure", DRAFT_STORAGE_FAILURES, ids=describe_expected_failure)
def test_delete_page_answers_the_draft_disk_errors(
    client: TestClient, document_service: StubDocumentDraftService, expected_failure: ExpectedFailure
) -> None:
    document_service.failure = expected_failure.error

    response = client.delete(f"/api/document/pages/{SECOND_PAGE_IDENTIFIER}")

    assert (response.status_code, response.json()) == build_expected_answer(expected_failure)


def test_reorder_passes_the_whole_order(client: TestClient, document_service: StubDocumentDraftService) -> None:
    client.put("/api/document/page-order", json={"page_identifiers": REVERSED_PAGE_ORDER})

    assert document_service.received_arguments["reorder"] == REVERSED_PAGE_ORDER


def test_reorder_answers_the_body_after_the_edit(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    document_service.snapshot_after_edit = build_stub_snapshot(3)

    response = client.put("/api/document/page-order", json={"page_identifiers": []})

    assert (response.status_code, response.json()) == (HTTPStatus.OK, build_document_body(build_stub_snapshot(3)))


def test_reorder_with_a_stale_order_answers_422(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    refusal = InvalidPageOrderError("not a permutation")
    document_service.failure = refusal

    response = client.put("/api/document/page-order", json={"page_identifiers": [page_identifier_at(1)]})

    assert (response.status_code, response.json()) == build_error_answer(refusal, HTTPStatus.UNPROCESSABLE_ENTITY)


def test_rename_passes_the_typed_name(client: TestClient, document_service: StubDocumentDraftService) -> None:
    client.put("/api/document/name", json={"name": "  Recibo: março  "})

    assert document_service.received_arguments["rename"] == "  Recibo: março  "


def test_rename_answers_the_body_after_the_edit(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    document_service.snapshot_after_edit = build_stub_snapshot(3)

    response = client.put("/api/document/name", json={"name": "Contrato"})

    assert (response.status_code, response.json()) == (HTTPStatus.OK, build_document_body(build_stub_snapshot(3)))


def test_rename_with_an_invalid_name_answers_422(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    refusal = InvalidDocumentNameError("only dots")
    document_service.failure = refusal

    response = client.put("/api/document/name", json={"name": "..."})

    assert (response.status_code, response.json()) == build_error_answer(refusal, HTTPStatus.UNPROCESSABLE_ENTITY)


def test_finalize_answers_the_saved_pdf(client: TestClient) -> None:
    response = client.post("/api/document/finalize")

    assert (response.status_code, response.json()) == (
        HTTPStatus.OK,
        {
            "file_name": "Contrato do apartamento.pdf",
            "output_folder": "/Volumes/External/scans",
            "page_count": 2,
            "size_in_bytes": 1612246,
        },
    )


@pytest.mark.parametrize("expected_failure", FINALIZE_FAILURES, ids=describe_expected_failure)
def test_finalize_answers_each_failure_with_its_status(
    client: TestClient, document_service: StubDocumentDraftService, expected_failure: ExpectedFailure
) -> None:
    document_service.failure = expected_failure.error

    response = client.post("/api/document/finalize")

    assert (response.status_code, response.json()) == build_expected_answer(expected_failure)


def test_finalize_with_a_damaged_page_names_the_page(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    document_service.failure = DamagedDocumentPageError(SECOND_PAGE_IDENTIFIER, 2)

    response = client.post("/api/document/finalize")

    assert (response.status_code, response.json()) == (
        HTTPStatus.CONFLICT,
        {
            "code": "damaged_document_page",
            "message": CATALOG.message_for("damaged_document_page"),
            "page_identifier": SECOND_PAGE_IDENTIFIER,
        },
    )


def test_cancel_answers_the_body_without_a_draft(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    document_service.snapshot_after_edit = build_stub_snapshot(0)

    response = client.delete("/api/document")

    assert (response.status_code, response.json()) == (HTTPStatus.OK, build_document_body(build_stub_snapshot(0)))


def test_cancel_that_cannot_delete_the_manifest_answers_503(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    failure = DraftStorageUnavailableError("manifest kept")
    document_service.failure = failure

    response = client.delete("/api/document")

    assert (response.status_code, response.json()) == build_error_answer(failure, HTTPStatus.SERVICE_UNAVAILABLE)


def test_any_other_domain_error_answers_500_with_its_own_code(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    failure = ScannerUnreachableError("not expected here")
    document_service.failure = failure

    response = client.delete("/api/document")

    assert (response.status_code, response.json()) == build_error_answer(failure, HTTPStatus.INTERNAL_SERVER_ERROR)


def test_thumbnail_is_served_as_jpeg(client: TestClient, document_service: StubDocumentDraftService) -> None:
    thumbnail_jpeg = build_sample_jpeg()
    document_service.thumbnails[SECOND_PAGE_IDENTIFIER] = thumbnail_jpeg

    response = client.get(f"/api/document/pages/{SECOND_PAGE_IDENTIFIER}/thumbnail")

    assert (response.status_code, response.headers["content-type"], response.content) == (
        HTTPStatus.OK,
        "image/jpeg",
        thumbnail_jpeg,
    )


def test_thumbnail_may_be_cached_forever(client: TestClient, document_service: StubDocumentDraftService) -> None:
    document_service.thumbnails[SECOND_PAGE_IDENTIFIER] = build_sample_jpeg()

    response = client.get(f"/api/document/pages/{SECOND_PAGE_IDENTIFIER}/thumbnail")

    assert response.headers["cache-control"] == THUMBNAIL_CACHE_HEADERS["Cache-Control"]


def test_missing_thumbnail_answers_404_without_a_body(client: TestClient) -> None:
    response = client.get(f"/api/document/pages/{SECOND_PAGE_IDENTIFIER}/thumbnail")

    assert (response.status_code, response.content) == (HTTPStatus.NOT_FOUND, b"")


def test_error_statuses_cover_the_documented_codes() -> None:
    assert {code: int(status) for code, status in DOCUMENT_ERROR_STATUSES.items()} == {
        "scan_already_running": 409,
        "document_busy": 409,
        "damaged_document_page": 409,
        "no_open_document": 404,
        "page_not_found": 404,
        "invalid_page_order": 422,
        "invalid_document_name": 422,
        "empty_document": 422,
        "output_folder_unavailable": 503,
        "draft_storage_unavailable": 503,
        "insufficient_storage": 507,
        "insufficient_draft_storage": 507,
    }
