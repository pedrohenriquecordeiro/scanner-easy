import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from digitalizadora.application_factory import ApplicationControllers, WebInterfaceConfiguration
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.preview_controller import PreviewController
from digitalizadora.controllers.printer_controller import PrinterController
from digitalizadora.controllers.scan_controller import ScanController
from digitalizadora.controllers.settings_controller import SettingsController
from digitalizadora.controllers.state_controller import StateController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import InsufficientStorageError, OutputFolderUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import ApplicationSettingsRepository, ScannerGateway
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.infrastructure.bonjour_scanner_discovery import BonjourScannerDiscovery, ServiceRecordSource
from digitalizadora.infrastructure.dns_service_discovery_record_source import DnsServiceDiscoveryRecordSource
from digitalizadora.infrastructure.escl.escl_scanner_gateway import EsclGatewayTiming, EsclScannerGateway
from digitalizadora.infrastructure.system_clock import SystemClock
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_scan_output_repository import FileSystemScanOutputRepository
from digitalizadora.repositories.json_application_settings_repository import JsonApplicationSettingsRepository
from digitalizadora.repositories.json_scanner_endpoint_repository import JsonScannerEndpointRepository
from digitalizadora.repositories.output_folder_preparer import prepare_output_folder
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from digitalizadora.services.application_state_service import ApplicationStateService
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.printer_connection_service import PrinterConnectionService
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.scan_output_service import ScanOutputService
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.scan_service import ScanService
from digitalizadora.services.storage_guard_service import StorageGuardService, read_free_space_in_bytes
from digitalizadora.services.thumbnail_service import ThumbnailService

logger = logging.getLogger(__name__)

SETTINGS_FILE_NAME = "settings.json"
SCANNER_ENDPOINT_FILE_NAME = "scanner-endpoint.json"
STATIC_DIRECTORY = Path(__file__).parent / "web" / "static"

SCANNER_DEFAULT_TIMEOUT_SECONDS = 30.0
SCANNER_CONNECT_TIMEOUT_SECONDS = 5.0
# Gate 0: this printer's NextDocument blocks until the page is ready (72 s at 600 dpi in colour); 180 s leaves margin.
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


@dataclass(frozen=True)
class _ScannerAccess:
    http_client: httpx.AsyncClient
    gateway_timing: EsclGatewayTiming
    service_record_source: ServiceRecordSource


@dataclass(frozen=True)
class _Services:
    scan: ScanService
    settings: ApplicationSettingsService
    state: ApplicationStateService
    printer_connection: PrinterConnectionService
    progress_tracker: ScanProgressTracker


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
    chosen_overrides = overrides if overrides is not None else ContainerOverrides()
    configuration.data_directory.mkdir(parents=True, exist_ok=True)
    repositories = _build_repositories(configuration)
    _prepare_saved_output_folder(repositories.settings)
    scanner_access = _build_scanner_access(chosen_overrides)
    services = _build_services(repositories, scanner_access, _build_storage_guard_service(chosen_overrides))
    _apply_scanner_address_override(configuration, services.printer_connection)
    error_message_catalog = ErrorMessageCatalog()
    return ApplicationContainer(
        controllers=_build_controllers(services, error_message_catalog),
        web_configuration=_build_web_configuration(configuration, scanner_access.http_client, error_message_catalog),
    )


def _build_repositories(configuration: ApplicationConfiguration) -> _Repositories:
    file_writer = AtomicFileWriter()
    default_settings = ApplicationSettings(
        output_folder=configuration.default_output_folder,
        output_format=OutputFormat.PDF,
        scan_preset=ScanPreset.DOCUMENT,
    )
    settings_repository = JsonApplicationSettingsRepository(
        configuration.data_directory / SETTINGS_FILE_NAME, default_settings, file_writer
    )
    return _Repositories(
        settings=settings_repository,
        scanner_endpoint=JsonScannerEndpointRepository(
            configuration.data_directory / SCANNER_ENDPOINT_FILE_NAME, file_writer
        ),
        scan_output=FileSystemScanOutputRepository(settings_repository, ScanFileNamingPolicy(), file_writer),
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


def _build_scan_output_service(
    repositories: _Repositories, storage_guard_service: StorageGuardService
) -> ScanOutputService:
    scan_encoder = ScanEncoder(JpegResolutionService(), PdfAssemblyService(), ThumbnailService())
    return ScanOutputService(scan_encoder, repositories.scan_output, storage_guard_service)


def _build_services(
    repositories: _Repositories, scanner_access: _ScannerAccess, storage_guard_service: StorageGuardService
) -> _Services:
    progress_tracker = ScanProgressTracker(SystemClock())
    printer_connection_service = PrinterConnectionService(
        BonjourScannerDiscovery(scanner_access.service_record_source),
        repositories.scanner_endpoint,
        _build_gateway_factory(scanner_access),
    )
    return _Services(
        scan=ScanService(
            printer_connection_service,
            _build_scan_output_service(repositories, storage_guard_service),
            progress_tracker,
        ),
        settings=ApplicationSettingsService(repositories.settings, prepare_output_folder),
        state=ApplicationStateService(progress_tracker, repositories.settings, storage_guard_service),
        printer_connection=printer_connection_service,
        progress_tracker=progress_tracker,
    )


def _build_controllers(services: _Services, error_message_catalog: ErrorMessageCatalog) -> ApplicationControllers:
    return ApplicationControllers(
        scan=ScanController(services.scan, services.settings, error_message_catalog),
        state=StateController(services.state, error_message_catalog),
        settings=SettingsController(services.settings, error_message_catalog),
        printer=PrinterController(services.printer_connection, error_message_catalog),
        preview=PreviewController(services.progress_tracker),
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
