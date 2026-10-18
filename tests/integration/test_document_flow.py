import asyncio
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import pikepdf
import pytest
from fastapi.testclient import TestClient

from digitalizadora.application_factory import create_application
from digitalizadora.composition_root import DRAFTS_FOLDER_NAME, ContainerOverrides, build_container
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.domain.document_draft_reconciliation import MANIFEST_FILE_NAME, page_file_name
from digitalizadora.domain.errors import DraftFolderInUseError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.infrastructure.escl.escl_scanner_gateway import EsclGatewayTiming
from digitalizadora.repositories.file_system_document_draft_repository import CURRENT_DRAFT_FOLDER_NAME
from digitalizadora.simulator.fake_escl_scanner_app import FakeScannerBehavior, create_fake_escl_scanner_app
from tests.fakes.configuration_builder import TEST_PORT, build_application_configuration
from tests.fakes.document_drafts import (
    DRAFT_CREATED_AT,
    build_document_draft,
    page_identifier_at,
    seed_draft_folder,
    write_draft_folder,
)
from tests.fakes.sample_images import build_sample_jpeg

BASE_ADDRESS = f"http://127.0.0.1:{TEST_PORT}"
SCANNER_ADDRESS = "http://scanner.test/eSCL"
STATE_CHANGING_HEADERS = {"X-Requested-With": "digitalizadora"}
ABUNDANT_FREE_SPACE_BYTES = 100 * 1024**3
MAXIMUM_STATE_POLLS = 500
STATE_POLL_INTERVAL_SECONDS = 0.01
# 72 dpi makes one point of the PDF page equal one pixel of the JPEG.
POINTS_PER_INCH = 72
SEEDED_PAGE_WIDTHS = [40, 64, 88]
ORPHAN_PAGE_POSITION = 9
EXISTING_PDF_CONTENT = b"%PDF-1.4 already saved"


async def yield_without_waiting(seconds: float) -> None:
    await asyncio.sleep(0)


def read_abundant_free_space(folder: Path) -> int:
    return ABUNDANT_FREE_SPACE_BYTES


def build_overrides() -> ContainerOverrides:
    return ContainerOverrides(
        scanner_transport=httpx.ASGITransport(app=create_fake_escl_scanner_app(FakeScannerBehavior())),
        gateway_timing=EsclGatewayTiming(sleep=yield_without_waiting),
        free_space_reader=read_abundant_free_space,
    )


def build_client(configuration: ApplicationConfiguration) -> TestClient:
    container = build_container(configuration, build_overrides())
    application = create_application(container.controllers, container.web_configuration)
    return TestClient(application, base_url=BASE_ADDRESS)


def drafts_folder_of(configuration: ApplicationConfiguration) -> Path:
    return configuration.data_directory / DRAFTS_FOLDER_NAME


def has_document_pages(expected_count: int) -> Callable[[dict], bool]:
    return lambda state: state["scan_phase"] == "idle" and state["document"]["page_count"] == expected_count


def wait_for_state(client: TestClient, condition: Callable[[dict], bool]) -> dict:
    state: dict = {}
    for _ in range(MAXIMUM_STATE_POLLS):
        state = client.get("/api/state").json()
        if condition(state):
            return state
        time.sleep(STATE_POLL_INTERVAL_SECONDS)
    raise AssertionError(f"The expected state never arrived; last state: {state}")


def save_economy_settings(client: TestClient, output_folder: Path) -> None:
    settings = {"output_folder": str(output_folder), "output_format": "pdf", "scan_preset": "document_economy"}
    response = client.put("/api/settings", json=settings, headers=STATE_CHANGING_HEADERS)
    assert response.status_code == 200


@pytest.fixture
def configuration(tmp_path: Path) -> ApplicationConfiguration:
    return build_application_configuration(tmp_path, SCANNER_ADDRESS)


def test_page_scanned_by_the_fake_printer_appears_in_the_document(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration) as client:
        save_economy_settings(client, configuration.default_output_folder)
        client.post("/api/document/pages", headers=STATE_CHANGING_HEADERS)
        wait_for_state(client, has_document_pages(1))
        document = client.get("/api/document").json()["document"]
    assert (document["page_count"], document["pages"][0]["dots_per_inch"]) == (1, 200)


def test_finalizing_a_seeded_draft_writes_its_pages_in_order(configuration: ApplicationConfiguration) -> None:
    page_contents = [build_sample_jpeg(width, 48, POINTS_PER_INCH) for width in SEEDED_PAGE_WIDTHS]
    seed_draft_folder(drafts_folder_of(configuration), page_contents)
    with build_client(configuration) as client:
        finalization = client.post("/api/document/finalize", headers=STATE_CHANGING_HEADERS).json()
    with pikepdf.open(Path(finalization["output_folder"]) / finalization["file_name"]) as document:
        page_widths = [round(float(page.mediabox[2])) for page in document.pages]
    assert page_widths == SEEDED_PAGE_WIDTHS


def test_startup_resumes_a_seeded_draft_with_a_recovery_report(configuration: ApplicationConfiguration) -> None:
    seed_draft_folder(drafts_folder_of(configuration), [build_sample_jpeg(), build_sample_jpeg()])
    with build_client(configuration) as client:
        body = client.get("/api/document").json()
    assert (body["document"]["page_count"], body["recovery"]["outcome"]) == (2, "resumed")


def test_startup_deletes_a_page_left_outside_the_manifest(configuration: ApplicationConfiguration) -> None:
    drafts_folder = drafts_folder_of(configuration)
    seed_draft_folder(drafts_folder, [build_sample_jpeg()])
    orphan_page = drafts_folder / CURRENT_DRAFT_FOLDER_NAME / page_file_name(page_identifier_at(ORPHAN_PAGE_POSITION))
    orphan_page.write_bytes(build_sample_jpeg())
    with build_client(configuration):
        pass
    assert not orphan_page.exists()


def test_startup_deletes_a_draft_whose_pdf_was_already_saved(configuration: ApplicationConfiguration) -> None:
    saved_pdf = configuration.default_output_folder / "Contrato.pdf"
    saved_pdf.parent.mkdir(parents=True)
    saved_pdf.write_bytes(EXISTING_PDF_CONTENT)
    finished_document = ScanResult(saved_pdf, OutputFormat.PDF, DRAFT_CREATED_AT, len(EXISTING_PDF_CONTENT))
    drafts_folder = drafts_folder_of(configuration)
    write_draft_folder(drafts_folder, build_document_draft(2).marked_finished(finished_document))
    with build_client(configuration) as client:
        document = client.get("/api/document").json()["document"]
    manifest = drafts_folder / CURRENT_DRAFT_FOLDER_NAME / MANIFEST_FILE_NAME
    assert (document, manifest.exists()) == (None, False)


def test_second_container_on_the_same_data_directory_is_refused(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration), pytest.raises(DraftFolderInUseError):
        build_container(configuration, build_overrides())
