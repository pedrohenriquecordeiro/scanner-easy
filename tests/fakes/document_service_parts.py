import functools
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.document_draft import DocumentDraft
from digitalizadora.domain.document_draft_reconciliation import MANIFEST_FILE_NAME
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.document_manifest_codec import decode_manifest
from digitalizadora.repositories.file_system_document_draft_repository import (
    CURRENT_DRAFT_FOLDER_NAME,
    FileSystemDocumentDraftRepository,
)
from digitalizadora.repositories.file_system_scan_output_repository import FileSystemScanOutputRepository
from digitalizadora.services.document_draft_service import DocumentDraftCollaborators, DocumentDraftService
from digitalizadora.services.document_draft_store import DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.document_finalizer import DocumentFinalizer
from digitalizadora.services.document_page_capture import DocumentPageCapture
from digitalizadora.services.document_page_crop_detector import DocumentPageCropDetector
from digitalizadora.services.document_page_view_service import DocumentPageViewService
from digitalizadora.services.document_pdf_assembler import DocumentPdfAssembler
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.page_framing_renderer import PageFramingRenderer
from digitalizadora.services.page_image_view_service import PageImageViewService
from digitalizadora.services.pdf_assembly_service import PageImageSource, PdfAssemblyService, PdfDocumentMetadata
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.scan_service import ScanService
from digitalizadora.services.storage_guard_service import StorageGuardService
from digitalizadora.services.thumbnail_service import ThumbnailService
from tests.fakes.document_drafts import DRAFT_CREATED_AT
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.observing_scanner_gateway import ObservingScriptedScannerGateway
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.recording_scan_destinations import RecordingScanOutputService
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.scripted_scanner_gateway import FixedGatewayProvider, build_sample_capabilities
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers

DRAFT_SESSION = "5c0f9a2e7b1d4c38"
PLENTY_OF_FREE_SPACE_IN_BYTES = 1024**4
DRAFTS_FOLDER_NAME = "drafts"
OUTPUT_FOLDER_NAME = "output"
SCRIPTED_PAGE_COUNT = 4
SAMPLE_SCANNED_PAGE = ScannedImage(content=build_sample_jpeg(), media_type="image/jpeg")
SAMPLE_SCANNED_PAGES = (SAMPLE_SCANNED_PAGE,) * SCRIPTED_PAGE_COUNT


class InstantFileWriter(AtomicFileWriter):
    """AtomicFileWriter without the drive flush, for the draft files of the document service tests.

    Every F_FULLFSYNC takes a few milliseconds, and a test that adds two pages and finalizes would get
    near 100 ms. The atomic writes themselves are covered by the repository tests (Tasks 7 and 17).
    """

    def write_new_file_from(self, destination: Path, write_content: Callable[[BinaryIO], None]) -> int:
        with destination.open("xb") as stream:
            write_content(stream)
            return stream.tell()

    def replace_file(self, destination: Path, content: bytes) -> None:
        destination.write_bytes(content)


class ObservedDraftRepository:
    """The real draft repository, recording the threads that save the manifest.

    finished_mark_failure makes the save of a manifest with the M6 mark fail; deletion_failure makes
    delete_draft fail. Every other method goes straight to the real repository.
    """

    def __init__(self, draft_repository: FileSystemDocumentDraftRepository) -> None:
        self._draft_repository = draft_repository
        self.finished_mark_failure: Exception | None = None
        self.deletion_failure: Exception | None = None
        self.manifest_thread_identifiers: list[int] = []

    def __getattr__(self, name: str) -> object:
        return getattr(self._draft_repository, name)

    def save_manifest(self, draft: DocumentDraft) -> None:
        self.manifest_thread_identifiers.append(threading.get_ident())
        if draft.finished_document is not None and self.finished_mark_failure is not None:
            raise self.finished_mark_failure
        self._draft_repository.save_manifest(draft)

    def delete_draft(self) -> None:
        if self.deletion_failure is not None:
            raise self.deletion_failure
        self._draft_repository.delete_draft()


class ObservingPdfAssemblyService(PdfAssemblyService):
    """The real streamed assembly, recording the manifest on disk and the thread at the moment it runs."""

    def __init__(self, manifest_path: Path) -> None:
        self._manifest_path = manifest_path
        self.manifests_during_assembly: list[DocumentDraft] = []
        self.assembly_thread_identifiers: list[int] = []

    def write_pdf_from_sources(
        self, page_sources: Sequence[PageImageSource], metadata: PdfDocumentMetadata, output_stream: BinaryIO
    ) -> None:
        self.manifests_during_assembly.append(decode_manifest(self._manifest_path.read_bytes()))
        self.assembly_thread_identifiers.append(threading.get_ident())
        super().write_pdf_from_sources(page_sources, metadata, output_stream)


@dataclass(frozen=True)
class DocumentServiceParts:
    """A DocumentDraftService wired as the composition root will wire it, with the pieces a test looks at."""

    document_draft_service: DocumentDraftService
    collaborators: DocumentDraftCollaborators
    scan_service: ScanService
    gateway: ObservingScriptedScannerGateway
    draft_repository: ObservedDraftRepository
    pdf_assembly_service: ObservingPdfAssemblyService
    clock: FixedClock
    drafts_folder: Path
    output_folder: Path

    @property
    def draft_folder(self) -> Path:
        return self.drafts_folder / CURRENT_DRAFT_FOLDER_NAME

    def read_manifest_on_disk(self) -> DocumentDraft:
        return decode_manifest((self.draft_folder / MANIFEST_FILE_NAME).read_bytes())


def _build_scan_service(
    clock: FixedClock, scanned_pages: Sequence[ScannedImage]
) -> tuple[ScanService, ObservingScriptedScannerGateway]:
    progress_tracker = ScanProgressTracker(clock)
    gateway = ObservingScriptedScannerGateway(build_sample_capabilities(), list(scanned_pages), progress_tracker)
    scan_service = ScanService(
        FixedGatewayProvider(gateway), RecordingScanOutputService(progress_tracker), progress_tracker
    )
    return scan_service, gateway


def _build_finalizer(
    output_folder: Path, pdf_assembly_service: PdfAssemblyService, free_space_reader: Callable[[Path], int]
) -> DocumentFinalizer:
    settings_repository = InMemoryApplicationSettingsRepository(
        ApplicationSettings(output_folder, OutputFormat.PDF, ScanPreset.DOCUMENT.settings)
    )
    scan_output_repository = FileSystemScanOutputRepository(
        settings_repository, ScanFileNamingPolicy(), AtomicFileWriter()
    )
    return DocumentFinalizer(
        DocumentPdfAssembler(PageFramingRenderer(), pdf_assembly_service),
        scan_output_repository,
        StorageGuardService(free_space_reader),
    )


def build_document_service_parts(
    root_folder: Path,
    finalizer_free_space_reader: Callable[[Path], int],
    scanned_pages: Sequence[ScannedImage] = SAMPLE_SCANNED_PAGES,
) -> DocumentServiceParts:
    """Real store, repository, page capture, scan service and finalizer under root_folder.

    The printer is an ObservingScriptedScannerGateway with the scanned pages; the draft disk always has
    plenty of space, and finalizer_free_space_reader answers for the output folder.
    """
    clock = FixedClock(DRAFT_CREATED_AT)
    drafts_folder = root_folder / DRAFTS_FOLDER_NAME
    output_folder = root_folder / OUTPUT_FOLDER_NAME
    draft_repository = ObservedDraftRepository(
        FileSystemDocumentDraftRepository(drafts_folder, InstantFileWriter(), clock)
    )
    draft_store = DocumentDraftStore(
        draft_repository,
        StorageGuardService(RecordingFreeSpaceReader(PLENTY_OF_FREE_SPACE_IN_BYTES)),
        DraftIdentitySource(DRAFT_SESSION, SequentialPageIdentifiers()),
    )
    scan_service, gateway = _build_scan_service(clock, scanned_pages)
    crop_detection_service = PageCropDetectionService()
    page_capture = DocumentPageCapture(
        ScanEncoder(JpegResolutionService(), PdfAssemblyService(), ThumbnailService()),
        draft_store,
        crop_detection_service,
    )
    pdf_assembly_service = ObservingPdfAssemblyService(
        drafts_folder / CURRENT_DRAFT_FOLDER_NAME / MANIFEST_FILE_NAME
    )
    collaborators = DocumentDraftCollaborators(
        draft_store=draft_store,
        page_scanner=functools.partial(scan_service.scan_document_page, page_capture=page_capture),
        finalizer=_build_finalizer(output_folder, pdf_assembly_service, finalizer_free_space_reader),
        page_cropper=DocumentPageCropDetector(draft_store, crop_detection_service),
        page_views=DocumentPageViewService(draft_store, PageImageViewService()),
    )
    return DocumentServiceParts(
        document_draft_service=DocumentDraftService(scan_service, collaborators, clock),
        collaborators=collaborators,
        scan_service=scan_service,
        gateway=gateway,
        draft_repository=draft_repository,
        pdf_assembly_service=pdf_assembly_service,
        clock=clock,
        drafts_folder=drafts_folder,
        output_folder=output_folder,
    )
