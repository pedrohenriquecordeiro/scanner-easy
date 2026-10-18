import functools
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from digitalizadora.application_factory import ApplicationControllers, WebInterfaceConfiguration
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.controllers.documents.document_controller import DocumentController
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.printer_controller import PrinterController
from digitalizadora.controllers.quick_scan.last_scan_controller import LastScanController
from digitalizadora.controllers.quick_scan.preview_controller import PreviewController
from digitalizadora.controllers.quick_scan.scan_controller import ScanController
from digitalizadora.controllers.settings_controller import SettingsController
from digitalizadora.controllers.state_controller import StateController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.documents.document_draft import generate_draft_session, generate_page_identifier
from digitalizadora.domain.errors import InsufficientStorageError, OutputFolderUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import ApplicationSettingsRepository, Clock, ScannerGateway
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.infrastructure.bonjour_scanner_discovery import BonjourScannerDiscovery, ServiceRecordSource
from digitalizadora.infrastructure.dns_service_discovery_record_source import DnsServiceDiscoveryRecordSource
from digitalizadora.infrastructure.escl.escl_scanner_gateway import EsclGatewayTiming, EsclScannerGateway
from digitalizadora.infrastructure.system_clock import SystemClock
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.documents.file_system_document_draft_repository import (
    FileSystemDocumentDraftRepository,
)
from digitalizadora.repositories.file_system_scan_output_repository import FileSystemScanOutputRepository
from digitalizadora.repositories.json_application_settings_repository import JsonApplicationSettingsRepository
from digitalizadora.repositories.json_scanner_endpoint_repository import JsonScannerEndpointRepository
from digitalizadora.repositories.output_folder_preparer import prepare_output_folder
from digitalizadora.repositories.quick_scan.file_system_quick_scan_slot_repository import (
    FileSystemQuickScanSlotRepository,
)
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from digitalizadora.services.application_state_service import ApplicationStateService
from digitalizadora.services.documents.document_draft_service import DocumentDraftCollaborators, DocumentDraftService
from digitalizadora.services.documents.document_draft_store import DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.documents.document_finalizer import DocumentFinalizer
from digitalizadora.services.documents.document_page_capture import DocumentPageCapture
from digitalizadora.services.documents.document_page_crop_detector import DocumentPageCropDetector
from digitalizadora.services.documents.document_page_view_service import DocumentPageViewService
from digitalizadora.services.documents.document_pdf_assembler import DocumentPdfAssembler
from digitalizadora.services.image_pixel_limit import raise_decompression_limit_to_scanner_size
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.page_framing_renderer import PageFramingRenderer
from digitalizadora.services.page_image_view_service import PageImageViewService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.printer_connection_service import PrinterConnectionService
from digitalizadora.services.quick_scan.last_scan_edit_service import LastScanEditParts, LastScanEditService
from digitalizadora.services.quick_scan.last_scan_view_service import LastScanViewService
from digitalizadora.services.quick_scan.quick_scan_output_renderer import QuickScanOutputRenderer
from digitalizadora.services.quick_scan.scan_output_service import ScanOutputParts, ScanOutputService
from digitalizadora.services.quick_scan.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.scan_service import ScanService
from digitalizadora.services.storage_guard_service import StorageGuardService, read_free_space_in_bytes
from digitalizadora.services.thumbnail_service import ThumbnailService

logger = logging.getLogger(__name__)

SETTINGS_FILE_NAME = "settings.json"
SCANNER_ENDPOINT_FILE_NAME = "scanner-endpoint.json"
DRAFTS_FOLDER_NAME = "drafts"
QUICK_SCAN_FOLDER_NAME = "quick-scan"
SCAN_IDENTIFIER_SIZE_IN_BYTES = 8
STATIC_DIRECTORY = Path(__file__).parent / "web" / "static"

SCANNER_DEFAULT_TIMEOUT_SECONDS = 30.0
SCANNER_CONNECT_TIMEOUT_SECONDS = 5.0
# Gate 0: this printer's NextDocument blocks until the page is ready (72 s at 600 dpi in colour); 180 s leaves margin.
# It is only the default of the HTTP client: the gateway sets the read timeout of NextDocument on every request,
# from the page area (EsclGatewayTiming.scan_timeout_for), so 1200 dpi is not cut at 180 s.
SCANNER_READ_TIMEOUT_SECONDS = 180.0
NO_IDLE_CONNECTIONS = 0


@dataclass(frozen=True)
class ApplicationContainer:
    controllers: ApplicationControllers
    web_configuration: WebInterfaceConfiguration


@dataclass(frozen=True)
class ContainerOverrides:
    scanner_transport: httpx.AsyncBaseTransport | None = None
    gateway_timing: EsclGatewayTiming | None = None
    free_space_reader: Callable[[Path], int] | None = None
    service_record_source: ServiceRecordSource | None = None


@dataclass(frozen=True)
class _Repositories:
    settings: JsonApplicationSettingsRepository
    scanner_endpoint: JsonScannerEndpointRepository
    scan_output: FileSystemScanOutputRepository
    document_draft: FileSystemDocumentDraftRepository
    quick_scan_slot: FileSystemQuickScanSlotRepository


@dataclass(frozen=True)
class _ScannerAccess:
    http_client: httpx.AsyncClient
    gateway_timing: EsclGatewayTiming
    service_record_source: ServiceRecordSource


@dataclass(frozen=True)
class _SharedServices:
    """A single clock, scan encoder, renderers and storage guard for the whole container."""

    clock: Clock
    crop_detection: PageCropDetectionService
    image_view: PageImageViewService
    page_framing_renderer: PageFramingRenderer
    scan_encoder: ScanEncoder
    output_renderer: QuickScanOutputRenderer
    storage_guard: StorageGuardService
    thumbnail: ThumbnailService


@dataclass(frozen=True)
class _Services:
    scan: ScanService
    settings: ApplicationSettingsService
    state: ApplicationStateService
    printer_connection: PrinterConnectionService
    progress_tracker: ScanProgressTracker
    document_draft: DocumentDraftService
    last_scan_edit: LastScanEditService
    last_scan_view: LastScanViewService


def build_scanner_http_client(scanner_transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=scanner_transport,
        # The scanner is on loopback (USB bridge) or the local network: never send it through a proxy.
        trust_env=False,
        follow_redirects=False,
        timeout=httpx.Timeout(
            SCANNER_DEFAULT_TIMEOUT_SECONDS,
            connect=SCANNER_CONNECT_TIMEOUT_SECONDS,
            read=SCANNER_READ_TIMEOUT_SECONDS,
        ),
        limits=httpx.Limits(max_keepalive_connections=NO_IDLE_CONNECTIONS),
    )


def build_container(
    configuration: ApplicationConfiguration,
    overrides: ContainerOverrides | None = None,
) -> ApplicationContainer:
    raise_decompression_limit_to_scanner_size()
    chosen_overrides = overrides if overrides is not None else ContainerOverrides()
    configuration.data_directory.mkdir(parents=True, exist_ok=True)
    clock = SystemClock()
    repositories = _build_repositories(configuration, clock)
    # R12: a second copy stops here (DraftFolderInUseError), before it touches the output folder, the saved
    # scanner address or the draft folder of the copy that is already running.
    repositories.document_draft.claim_exclusive_access()
    _prepare_saved_output_folder(repositories.settings)
    scanner_access = _build_scanner_access(chosen_overrides)
    shared_services = _build_shared_services(clock, chosen_overrides, repositories.settings)
    services = _build_services(repositories, scanner_access, shared_services)
    # Before the server answers (6.6.2); recover_draft never raises, so the server always starts.
    services.document_draft.recover_draft()
    services.last_scan_edit.restore_after_start()
    _apply_scanner_address_override(configuration, services.printer_connection)
    error_message_catalog = ErrorMessageCatalog()
    return ApplicationContainer(
        controllers=_build_controllers(services, error_message_catalog),
        web_configuration=_build_web_configuration(configuration, scanner_access.http_client, error_message_catalog),
    )


def _build_repositories(configuration: ApplicationConfiguration, clock: Clock) -> _Repositories:
    file_writer = AtomicFileWriter()
    default_settings = ApplicationSettings(
        output_folder=configuration.default_output_folder,
        output_format=OutputFormat.PDF,
        scan_settings=ScanPreset.DOCUMENT.settings,
    )
    settings_repository = JsonApplicationSettingsRepository(
        configuration.data_directory / SETTINGS_FILE_NAME, default_settings, file_writer
    )
    return _Repositories(
        settings=settings_repository,
        scanner_endpoint=JsonScannerEndpointRepository(
            configuration.data_directory / SCANNER_ENDPOINT_FILE_NAME, file_writer
        ),
        scan_output=FileSystemScanOutputRepository(settings_repository, ScanFileNamingPolicy(clock), file_writer),
        document_draft=FileSystemDocumentDraftRepository(
            configuration.data_directory / DRAFTS_FOLDER_NAME, file_writer, clock
        ),
        quick_scan_slot=FileSystemQuickScanSlotRepository(
            configuration.data_directory / QUICK_SCAN_FOLDER_NAME, file_writer, clock
        ),
    )


def _prepare_saved_output_folder(settings_repository: ApplicationSettingsRepository) -> None:
    # The saved folder (the default until the user picks another) is the one scans go to; a missing external
    # disk must not stop the server, because the page reports the folder as unavailable.
    output_folder = settings_repository.load().output_folder
    try:
        prepare_output_folder(output_folder)
    except (OutputFolderUnavailableError, InsufficientStorageError) as error:
        logger.warning("The output folder is not ready at startup: %s", error)


def _build_scanner_access(overrides: ContainerOverrides) -> _ScannerAccess:
    gateway_timing = overrides.gateway_timing
    if gateway_timing is None:
        gateway_timing = EsclGatewayTiming()
    service_record_source = overrides.service_record_source
    if service_record_source is None:
        service_record_source = DnsServiceDiscoveryRecordSource()
    return _ScannerAccess(
        http_client=build_scanner_http_client(overrides.scanner_transport),
        gateway_timing=gateway_timing,
        service_record_source=service_record_source,
    )


def _build_storage_guard_service(overrides: ContainerOverrides) -> StorageGuardService:
    if overrides.free_space_reader is None:
        return StorageGuardService(read_free_space_in_bytes)
    return StorageGuardService(overrides.free_space_reader)


def _build_gateway_factory(scanner_access: _ScannerAccess) -> Callable[[ScannerEndpoint], ScannerGateway]:
    def build_gateway(endpoint: ScannerEndpoint) -> ScannerGateway:
        return EsclScannerGateway(scanner_access.http_client, endpoint.base_address, scanner_access.gateway_timing)

    return build_gateway


def _build_shared_services(
    clock: Clock, overrides: ContainerOverrides, settings_repository: ApplicationSettingsRepository
) -> _SharedServices:
    thumbnail_service = ThumbnailService()
    page_framing_renderer = PageFramingRenderer()
    scan_encoder = ScanEncoder(JpegResolutionService(), PdfAssemblyService(), thumbnail_service)
    return _SharedServices(
        clock=clock,
        crop_detection=PageCropDetectionService(lambda: settings_repository.load().adjustment.crop_margin),
        image_view=PageImageViewService(),
        page_framing_renderer=page_framing_renderer,
        scan_encoder=scan_encoder,
        output_renderer=QuickScanOutputRenderer(page_framing_renderer, scan_encoder),
        storage_guard=_build_storage_guard_service(overrides),
        thumbnail=thumbnail_service,
    )


def _build_services(
    repositories: _Repositories, scanner_access: _ScannerAccess, shared_services: _SharedServices
) -> _Services:
    progress_tracker = ScanProgressTracker(shared_services.clock)
    printer_connection_service = PrinterConnectionService(
        BonjourScannerDiscovery(scanner_access.service_record_source),
        repositories.scanner_endpoint,
        _build_gateway_factory(scanner_access),
    )
    scan_output_parts = ScanOutputParts(
        scan_encoder=shared_services.scan_encoder,
        output_renderer=shared_services.output_renderer,
        crop_detection_service=shared_services.crop_detection,
        storage_guard_service=shared_services.storage_guard,
        scan_identifier_factory=functools.partial(secrets.token_hex, SCAN_IDENTIFIER_SIZE_IN_BYTES),
    )
    scan_output_service = ScanOutputService(scan_output_parts, repositories.scan_output, repositories.quick_scan_slot)
    scan_service = ScanService(printer_connection_service, scan_output_service, progress_tracker)
    return _Services(
        scan=scan_service,
        settings=ApplicationSettingsService(repositories.settings, prepare_output_folder),
        state=ApplicationStateService(progress_tracker, repositories.settings, shared_services.storage_guard),
        printer_connection=printer_connection_service,
        progress_tracker=progress_tracker,
        document_draft=_build_document_draft_service(repositories, shared_services, scan_service),
        last_scan_edit=LastScanEditService(
            progress_tracker,
            LastScanEditParts(
                slot_repository=repositories.quick_scan_slot,
                scan_output_repository=repositories.scan_output,
                output_renderer=shared_services.output_renderer,
                crop_detection_service=shared_services.crop_detection,
                thumbnail_service=shared_services.thumbnail,
            ),
        ),
        last_scan_view=LastScanViewService(
            progress_tracker, repositories.quick_scan_slot, shared_services.image_view
        ),
    )


def _build_document_draft_service(
    repositories: _Repositories, shared_services: _SharedServices, scan_service: ScanService
) -> DocumentDraftService:
    draft_store = DocumentDraftStore(
        repositories.document_draft,
        shared_services.storage_guard,
        DraftIdentitySource(draft_session=generate_draft_session(), page_identifier_factory=generate_page_identifier),
    )
    page_capture = DocumentPageCapture(shared_services.scan_encoder, draft_store, shared_services.crop_detection)
    pdf_assembler = DocumentPdfAssembler(PageFramingRenderer(), PdfAssemblyService())
    finalizer = DocumentFinalizer(pdf_assembler, repositories.scan_output, shared_services.storage_guard)
    # The destination is bound once here, so DocumentDraftService never depends on DocumentPageCapture.
    page_scanner = functools.partial(scan_service.scan_document_page, page_capture=page_capture)
    return DocumentDraftService(
        scan_service,
        DocumentDraftCollaborators(
            draft_store,
            page_scanner,
            finalizer,
            DocumentPageCropDetector(draft_store, shared_services.crop_detection),
            DocumentPageViewService(draft_store, shared_services.image_view),
        ),
        shared_services.clock,
    )


def _build_controllers(services: _Services, error_message_catalog: ErrorMessageCatalog) -> ApplicationControllers:
    return ApplicationControllers(
        scan=ScanController(services.scan, services.settings, error_message_catalog),
        state=StateController(services.state, services.document_draft, error_message_catalog),
        settings=SettingsController(services.settings, error_message_catalog),
        printer=PrinterController(services.printer_connection, error_message_catalog),
        preview=PreviewController(services.last_scan_view, error_message_catalog),
        document=DocumentController(services.document_draft, services.settings, error_message_catalog),
        last_scan=LastScanController(services.last_scan_edit, error_message_catalog),
    )


def _build_web_configuration(
    configuration: ApplicationConfiguration,
    http_client: httpx.AsyncClient,
    error_message_catalog: ErrorMessageCatalog,
) -> WebInterfaceConfiguration:
    return WebInterfaceConfiguration(
        allowed_hosts=frozenset({f"{configuration.host}:{configuration.port}", f"localhost:{configuration.port}"}),
        static_directory=STATIC_DIRECTORY,
        error_message_catalog=error_message_catalog,
        shutdown_callbacks=(http_client.aclose,),
    )


def _apply_scanner_address_override(
    configuration: ApplicationConfiguration, printer_connection_service: PrinterConnectionService
) -> None:
    if configuration.scanner_address_override is not None:
        printer_connection_service.use_manual_address(configuration.scanner_address_override)
