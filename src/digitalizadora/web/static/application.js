"use strict";

// Uses IDLE_PHASE, SPACE_KEY_ACTIONS, decide_space_key_action and can_start_capture from
// scan-trigger-policy.js, the quality and duration rules from scan-quality-policy.js, ErrorBanner from error-banner.js,
// CAPTURE_MODES, ENTER_KEY_CODE and the can_, should_ and describe_ rules from document-page-policy.js, the addresses
// and texts of last-scan-policy.js, PageFrameEditor from page-frame-editor.js, DocumentPanel from document-panel.js
// and LastScanPanel from last-scan-panel.js; index.html loads them first, in this order.

const REQUIRED_HEADER_NAME = "X-Requested-With";
const REQUIRED_HEADER_VALUE = "digitalizadora";
const RECOVERY_SWITCH_STORAGE_KEY = "digitalizadora.recovery_switch_session";

const PREPARING_PHASE = "preparing";
const PHASE_MESSAGES = {
  preparing: () => "Preparando…",
  scanning: (dots_per_inch) => `Digitalizando… (${describe_expected_scan_duration(dots_per_inch)})`,
  saving: () => "Salvando…",
};
const SCAN_REQUEST_PATHS = Object.freeze({ single: "/api/scans", document: "/api/document/pages" });
const READY_MESSAGE = "Pronto para digitalizar. Coloque a folha no vidro e aperte Espaço.";
const LAST_SCAN_FAILED_MESSAGE = "A última digitalização falhou.";
const SERVER_UNREACHABLE_MESSAGE = "Não consegui falar com o Digitalizadora. Ele ainda está aberto no Terminal?";
const UNEXPECTED_ERROR_MESSAGE = "Algo inesperado aconteceu. Veja o registro em ~/Library/Logs/Digitalizadora.";
const SERVER_UNREACHABLE_CODE = "server_unreachable";
const UNEXPECTED_ERROR_CODE = "unexpected_error";

const SCAN_BUTTON_READY_LABEL = "Digitalizar";
const SCAN_BUTTON_ADD_PAGE_LABEL = "Adicionar página";
const SCAN_BUTTON_BUSY_LABEL = "Digitalizando…";
const SCAN_BUTTON_SAVING_LABEL = "Salvando…";

const ACTIVE_POLL_INTERVAL_MILLISECONDS = 500;
const IDLE_POLL_INTERVAL_MILLISECONDS = 2000;
const PRINTER_POLL_INTERVAL_MILLISECONDS = 15000;
// Gate 0: the printer reports Processing for 4 to 5 s after each delivery.
const POST_SCAN_PRINTER_REFRESH_DELAY_MILLISECONDS = 6000;
const IMMEDIATE_REFRESH_MILLISECONDS = 0;
// A key held on the quality slider changes it many times a second: only the last value is saved.
const QUALITY_SAVE_DELAY_MILLISECONDS = 300;

const BYTES_PER_UNIT = 1000;
const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"];
const ROUNDING_SCALE = 10;
const EXTERNAL_DISK_WARNING_BYTES = 5 * BYTES_PER_UNIT ** 3;
const OUTPUT_FOLDER_UNAVAILABLE_TEXT = "Pasta de saída indisponível. Se for um disco externo, confira se está conectado.";
const DRAFT_STORAGE_UNAVAILABLE_TEXT = "Espaço no Mac para as páginas: não consegui ler o disco do Mac.";
const SINGLE_PAGE_COUNT = 1;

const PORTUGUESE_LOCALE = "pt-BR";
const ONE_DECIMAL_FORMAT = { minimumFractionDigits: 1, maximumFractionDigits: 1 };
const CLOCK_TIME_FORMAT = { hour: "2-digit", minute: "2-digit", second: "2-digit" };

const PRINTER_PRESENTATIONS = {
  searching: { condition: "searching", icon: "…", text: "Procurando…" },
  ready: { condition: "ready", icon: "✔", text: "Impressora pronta" },
  busy: { condition: "busy", icon: "⏳", text: "Impressora ocupada" },
  missing: { condition: "missing", icon: "⚠", text: "Impressora não encontrada" },
};
const PRINTER_ROUTE_LABELS = { usb: "USB", network: "Wi-Fi" };
const READY_SCANNER_STATE = "idle";

class RequestError extends Error {
  constructor(status_code, error_body) {
    super(error_body.message);
    this.status_code = status_code;
    this.error_code = error_body.code;
    // Only damaged_document_page names a page; the panel marks that page in the grid.
    this.page_identifier = error_body.page_identifier ?? null;
  }
}

function format_byte_count(size_in_bytes) {
  let scaled_value = size_in_bytes;
  let unit_index = 0;
  const last_unit_index = BYTE_UNITS.length - 1;
  while (
    unit_index < last_unit_index &&
    Math.round(scaled_value * ROUNDING_SCALE) / ROUNDING_SCALE >= BYTES_PER_UNIT
  ) {
    scaled_value /= BYTES_PER_UNIT;
    unit_index += 1;
  }
  if (unit_index === 0) {
    return `${scaled_value} ${BYTE_UNITS[0]}`;
  }
  return `${scaled_value.toLocaleString(PORTUGUESE_LOCALE, ONE_DECIMAL_FORMAT)} ${BYTE_UNITS[unit_index]}`;
}

function describe_pages_remaining(page_count) {
  if (page_count === SINGLE_PAGE_COUNT) {
    return `cabe ~${SINGLE_PAGE_COUNT} página`;
  }
  return `cabem ~${page_count.toLocaleString(PORTUGUESE_LOCALE)} páginas`;
}

function is_output_folder_unavailable(storage) {
  // A missing key means an older server that always reported an available folder.
  return storage.output_folder_available === false;
}

function describe_storage(storage) {
  if (is_output_folder_unavailable(storage)) {
    return OUTPUT_FOLDER_UNAVAILABLE_TEXT;
  }
  const free_space_text = format_byte_count(storage.free_space_in_bytes);
  return `Espaço livre: ${free_space_text} — ${describe_pages_remaining(storage.estimated_pages_remaining)}`;
}

function should_recommend_external_disk(storage) {
  return !is_output_folder_unavailable(storage) && storage.free_space_in_bytes < EXTERNAL_DISK_WARNING_BYTES;
}

function describe_draft_storage(draft_storage) {
  if (!draft_storage.available) {
    return DRAFT_STORAGE_UNAVAILABLE_TEXT;
  }
  const free_space_text = format_byte_count(draft_storage.free_space_in_bytes);
  const pages_remaining_text = describe_pages_remaining(draft_storage.estimated_pages_remaining);
  return `Espaço no Mac para as páginas: ${free_space_text} — ${pages_remaining_text}`;
}

function choose_thumbnail_revision(state) {
  // A server from before the rotation of the last scan sends no revision: each scan is then a new thumbnail.
  return state.last_result_revision ?? state.scans_completed;
}

function format_scan_time(scanned_at) {
  return new Date(scanned_at).toLocaleTimeString(PORTUGUESE_LOCALE, CLOCK_TIME_FORMAT);
}

function describe_scan_status(state) {
  if (state.scan_phase !== IDLE_PHASE) {
    const describe_phase = PHASE_MESSAGES[state.scan_phase];
    return describe_phase === undefined ? "" : describe_phase(state.settings.dots_per_inch);
  }
  if (state.last_error !== null) {
    return LAST_SCAN_FAILED_MESSAGE;
  }
  if (state.last_result !== null) {
    return describe_saved_scan_status(state.last_result);
  }
  return READY_MESSAGE;
}

function choose_scan_button_label(scan_button_state) {
  if (scan_button_state.is_scanning) {
    return SCAN_BUTTON_BUSY_LABEL;
  }
  if (scan_button_state.is_finalizing) {
    return SCAN_BUTTON_SAVING_LABEL;
  }
  const is_document_mode = scan_button_state.capture_mode === CAPTURE_MODES.DOCUMENT;
  return is_document_mode ? SCAN_BUTTON_ADD_PAGE_LABEL : SCAN_BUTTON_READY_LABEL;
}

function classify_printer(printer) {
  if (!printer.connected) {
    return "missing";
  }
  return printer.scanner_state === READY_SCANNER_STATE ? "ready" : "busy";
}

function describe_printer(printer) {
  const presentation = PRINTER_PRESENTATIONS[classify_printer(printer)];
  const route_label = PRINTER_ROUTE_LABELS[printer.route];
  if (presentation !== PRINTER_PRESENTATIONS.ready || route_label === undefined) {
    return presentation;
  }
  return { ...presentation, text: `${presentation.text} (${route_label})` };
}

async function build_request_error(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const code = payload !== null && typeof payload.code === "string" ? payload.code : UNEXPECTED_ERROR_CODE;
  const message = payload !== null && typeof payload.message === "string" ? payload.message : UNEXPECTED_ERROR_MESSAGE;
  const page_identifier =
    payload !== null && typeof payload.page_identifier === "string" ? payload.page_identifier : null;
  return new RequestError(response.status, { code, message, page_identifier });
}

async function send_request(method, path, body) {
  const options = { method, headers: {}, cache: "no-store" };
  if (method !== "GET") {
    options.headers[REQUIRED_HEADER_NAME] = REQUIRED_HEADER_VALUE;
  }
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new RequestError(0, { code: SERVER_UNREACHABLE_CODE, message: SERVER_UNREACHABLE_MESSAGE });
  }
  if (!response.ok) {
    throw await build_request_error(response);
  }
  return response.json();
}

function collect_elements() {
  return {
    printer_status_chip: document.getElementById("printer-status-chip"),
    printer_status_icon: document.getElementById("printer-status-icon"),
    printer_status_text: document.getElementById("printer-status-text"),
    printer_detail: document.getElementById("printer-detail"),
    error_banner_content: document.getElementById("error-banner-content"),
    error_banner_text: document.getElementById("error-banner-text"),
    capture_mode_inputs: {
      single: document.getElementById("capture-mode-single"),
      document: document.getElementById("capture-mode-document"),
    },
    scan_button: document.getElementById("scan-button"),
    scan_button_label: document.getElementById("scan-button-label"),
    status_line: document.getElementById("status-line"),
    document_pending_notice: document.getElementById("document-pending-notice"),
    document_pending_text: document.getElementById("document-pending-text"),
    return_to_document_button: document.getElementById("return-to-document-button"),
    document_section: document.getElementById("document-section"),
    document_name_input: document.getElementById("document-name-input"),
    document_recovery_notice: document.getElementById("document-recovery-notice"),
    document_previous_save_notice: document.getElementById("document-previous-save-notice"),
    document_finished_message: document.getElementById("document-finished-message"),
    document_empty_message: document.getElementById("document-empty-message"),
    document_page_grid: document.getElementById("document-page-grid"),
    document_summary: document.getElementById("document-summary"),
    document_large_warning: document.getElementById("document-large-warning"),
    discard_last_page_button: document.getElementById("discard-last-page-button"),
    cancel_document_button: document.getElementById("cancel-document-button"),
    save_document_button: document.getElementById("save-document-button"),
    draft_storage_line: document.getElementById("draft-storage-line"),
    draft_storage_warning: document.getElementById("draft-storage-warning"),
    document_announcement: document.getElementById("document-announcement"),
    output_format_group: document.getElementById("output-format-group"),
    format_inputs: {
      pdf: document.getElementById("output-format-pdf"),
      jpg: document.getElementById("output-format-jpg"),
    },
    resolution_select: document.getElementById("resolution-select"),
    color_mode_select: document.getElementById("color-mode-select"),
    resolution_warning: document.getElementById("resolution-warning"),
    resolution_warning_text: document.getElementById("resolution-warning-text"),
    auto_crop_checkbox: document.getElementById("auto-crop-checkbox"),
    crop_margin_checkbox: document.getElementById("crop-margin-checkbox"),
    jpeg_quality_input: document.getElementById("jpeg-quality-input"),
    jpeg_quality_value: document.getElementById("jpeg-quality-value"),
    output_folder_input: document.getElementById("output-folder-input"),
    output_folder_save_button: document.getElementById("output-folder-save-button"),
    output_folder_message: document.getElementById("output-folder-message"),
    storage_line: document.getElementById("storage-line"),
    storage_warning: document.getElementById("storage-warning"),
    last_scan_panel: document.getElementById("last-scan-panel"),
    last_scan_thumbnail_frame: document.getElementById("last-scan-thumbnail-frame"),
    last_scan_thumbnail: document.getElementById("last-scan-thumbnail"),
    last_scan_file_names: document.getElementById("last-scan-file-names"),
    last_scan_size: document.getElementById("last-scan-size"),
    last_scan_time: document.getElementById("last-scan-time"),
    last_scan_rotate_button: document.getElementById("last-scan-rotate-button"),
    last_scan_enlarge_button: document.getElementById("last-scan-enlarge-button"),
    last_scan_hint: document.getElementById("last-scan-hint"),
    last_scan_status: document.getElementById("last-scan-status"),
    session_counter: document.getElementById("session-counter"),
    confirmation_dialog: document.getElementById("confirmation-dialog"),
    confirmation_text: document.getElementById("confirmation-text"),
    confirmation_accept_button: document.getElementById("confirmation-accept-button"),
    confirmation_reject_button: document.getElementById("confirmation-reject-button"),
    move_page_dialog: document.getElementById("move-page-dialog"),
    move_page_position_input: document.getElementById("move-page-position-input"),
    move_page_accept_button: document.getElementById("move-page-accept-button"),
    move_page_reject_button: document.getElementById("move-page-reject-button"),
    page_frame_dialog: document.getElementById("page-frame-dialog"),
    page_frame_title: document.getElementById("page-frame-title"),
    frame_stage: document.getElementById("frame-stage"),
    frame_image: document.getElementById("frame-image"),
    frame_overlay_host: document.getElementById("frame-overlay-host"),
    frame_move_button: document.getElementById("frame-move-button"),
    frame_select_button: document.getElementById("frame-select-button"),
    frame_rotate_handle: document.getElementById("frame-rotate-handle"),
    frame_corner_handles: {
      top_left: document.getElementById("frame-corner-top-left"),
      top_right: document.getElementById("frame-corner-top-right"),
      bottom_right: document.getElementById("frame-corner-bottom-right"),
      bottom_left: document.getElementById("frame-corner-bottom-left"),
    },
    frame_edge_handles: {
      top: document.getElementById("frame-edge-top"),
      right: document.getElementById("frame-edge-right"),
      bottom: document.getElementById("frame-edge-bottom"),
      left: document.getElementById("frame-edge-left"),
    },
    frame_status: document.getElementById("frame-status"),
    frame_add_button: document.getElementById("frame-add-button"),
    frame_remove_button: document.getElementById("frame-remove-button"),
    frame_turn_button: document.getElementById("frame-turn-button"),
    frame_detect_button: document.getElementById("frame-detect-button"),
    frame_clear_button: document.getElementById("frame-clear-button"),
    frame_rotate_button: document.getElementById("frame-rotate-button"),
    frame_cancel_button: document.getElementById("frame-cancel-button"),
    frame_apply_button: document.getElementById("frame-apply-button"),
  };
}

function build_scan_page(elements) {
  const error_banner = new ErrorBanner(elements);
  let scan_page = null;
  // One frame editor serves both modes: whoever opens it is its owner for that session.
  const frame_editor = new PageFrameEditor(elements);
  const document_panel = new DocumentPanel(elements, {
    send_request,
    format_byte_count,
    error_banner,
    frame_editor,
    focus_scan_button: () => elements.scan_button.focus(),
    refresh_page_controls: () => scan_page.render_activity(),
  });
  const last_scan_panel = new LastScanPanel(elements, {
    send_request,
    format_byte_count,
    error_banner,
    frame_editor,
    focus_scan_button: () => elements.scan_button.focus(),
    refresh_page_controls: () => scan_page.render_activity(),
    request_state_refresh: () => scan_page.schedule_state_refresh(IMMEDIATE_REFRESH_MILLISECONDS),
  });
  scan_page = new ScanPage(elements, { document_panel, last_scan_panel, error_banner });
  return scan_page;
}

class ScanPage {
  constructor(elements, page_parts) {
    this.elements = elements;
    this.document_panel = page_parts.document_panel;
    this.last_scan_panel = page_parts.last_scan_panel;
    this.error_banner = page_parts.error_banner;
    this.scan_phase = IDLE_PHASE;
    this.is_start_request_pending = false;
    this.saved_settings = null;
    this.quality_edit_count = 0;
    this.quality_edits_sent = 0;
    this.quality_requests_pending = 0;
    this.quality_save_timer = null;
    this.last_state = null;
    this.state_timer = null;
    this.printer_timer = null;
  }

  start() {
    this.bind_events();
    this.render_printer(PRINTER_PRESENTATIONS.searching);
    this.load_settings_and_document();
    this.refresh_state();
    this.refresh_printer();
  }

  bind_events() {
    const { scan_button, output_folder_input, output_folder_save_button, format_inputs } = this.elements;
    scan_button.addEventListener("click", () => this.start_scan());
    document.addEventListener("keydown", (event) => this.handle_key_down(event));
    document.addEventListener("keyup", (event) => this.handle_key_up(event));
    Object.values(format_inputs).forEach((input) => {
      input.addEventListener("change", (event) =>
        this.change_setting_then_focus_scan_button({ output_format: event.target.value }),
      );
    });
    Object.values(this.elements.capture_mode_inputs).forEach((input) => {
      input.addEventListener("change", (event) =>
        this.change_setting_then_focus_scan_button({ capture_mode: event.target.value }),
      );
    });
    this.elements.return_to_document_button.addEventListener("click", () =>
      this.change_setting_then_focus_scan_button({ capture_mode: CAPTURE_MODES.DOCUMENT }),
    );
    this.bind_quality_events();
    output_folder_save_button.addEventListener("click", () => this.save_output_folder());
    output_folder_input.addEventListener("keydown", (event) => {
      if (event.code === ENTER_KEY_CODE) {
        this.save_output_folder();
      }
    });
    this.document_panel.bind_events();
    this.last_scan_panel.bind_events();
  }

  bind_quality_events() {
    const { resolution_select, color_mode_select, auto_crop_checkbox } = this.elements;
    resolution_select.addEventListener("change", () =>
      this.change_setting({ dots_per_inch: Number(resolution_select.value) }),
    );
    color_mode_select.addEventListener("change", () => this.change_setting({ color_mode: color_mode_select.value }));
    auto_crop_checkbox.addEventListener("change", () =>
      this.change_setting_then_focus_scan_button({ auto_crop: auto_crop_checkbox.checked }),
    );
    this.elements.crop_margin_checkbox.addEventListener("change", () =>
      this.change_setting({ crop_margin: this.elements.crop_margin_checkbox.checked }),
    );
    const { jpeg_quality_input, jpeg_quality_value } = this.elements;
    // The number follows the slider while it moves (a screen reader reads it); the setting is saved a moment after
    // the slider is let go or the last key press.
    jpeg_quality_input.addEventListener("input", () => {
      jpeg_quality_value.textContent = String(parse_jpeg_quality(jpeg_quality_input.value));
    });
    jpeg_quality_input.addEventListener("change", () => this.schedule_quality_save());
  }

  schedule_quality_save() {
    this.quality_edit_count += 1;
    window.clearTimeout(this.quality_save_timer);
    this.quality_save_timer = window.setTimeout(() => this.save_quality(), QUALITY_SAVE_DELAY_MILLISECONDS);
  }

  async save_quality() {
    this.quality_save_timer = null;
    this.quality_edits_sent = this.quality_edit_count;
    this.quality_requests_pending += 1;
    try {
      await this.change_setting({ jpeg_quality: parse_jpeg_quality(this.elements.jpeg_quality_input.value) });
    } finally {
      this.quality_requests_pending -= 1;
    }
  }

  // An answer about an older value never takes the slider back from a newer one the person already chose.
  has_newer_quality_than_the_answer() {
    return this.quality_edit_count > this.quality_edits_sent || this.quality_requests_pending > 1;
  }

  capture_mode() {
    // A server from before the Documento mode sends no capture_mode: that is the quick mode.
    return this.saved_settings?.capture_mode ?? CAPTURE_MODES.SINGLE;
  }

  is_document_mode() {
    return this.capture_mode() === CAPTURE_MODES.DOCUMENT;
  }

  handle_key_down(event) {
    const action = decide_space_key_action(event, this.elements.scan_button);
    if (action === SPACE_KEY_ACTIONS.IGNORE) {
      this.document_panel.handle_key_down(event);
      return;
    }
    event.preventDefault();
    if (action === SPACE_KEY_ACTIONS.START_SCAN) {
      this.start_scan();
    }
  }

  handle_key_up(event) {
    // Firefox clicks a focused button on keyup; the keydown already started the scan.
    if (decide_space_key_action(event, this.elements.scan_button) !== SPACE_KEY_ACTIONS.IGNORE) {
      event.preventDefault();
    }
  }

  read_scan_activity() {
    return {
      scan_phase: this.scan_phase,
      is_start_request_pending: this.is_start_request_pending,
      is_edit_request_pending:
        this.document_panel.is_edit_request_pending() || this.last_scan_panel.is_edit_request_pending(),
    };
  }

  is_ready_to_scan() {
    return can_start_capture(this.read_scan_activity());
  }

  async start_scan() {
    if (!this.is_ready_to_scan()) {
      return;
    }
    this.is_start_request_pending = true;
    this.error_banner.report_action_error(null);
    this.last_scan_panel.clear_status();
    this.render_activity();
    try {
      await send_request("POST", SCAN_REQUEST_PATHS[this.capture_mode()]);
      this.scan_phase = PREPARING_PHASE;
    } catch (error) {
      this.error_banner.report_action_error(error.message);
    } finally {
      this.is_start_request_pending = false;
    }
    this.render_activity();
    this.schedule_state_refresh(IMMEDIATE_REFRESH_MILLISECONDS);
  }

  schedule_state_refresh(delay_milliseconds) {
    window.clearTimeout(this.state_timer);
    this.state_timer = window.setTimeout(() => this.refresh_state(), delay_milliseconds);
  }

  next_state_interval() {
    return this.scan_phase === IDLE_PHASE ? IDLE_POLL_INTERVAL_MILLISECONDS : ACTIVE_POLL_INTERVAL_MILLISECONDS;
  }

  async refresh_state() {
    const edit_epoch = this.last_scan_panel.read_edit_epoch();
    try {
      this.apply_state(await send_request("GET", "/api/state"), edit_epoch);
    } catch (error) {
      this.error_banner.set_connection_error(error.message);
    } finally {
      this.schedule_state_refresh(this.next_state_interval());
    }
  }

  apply_state(state, edit_epoch) {
    const previous_phase = this.scan_phase;
    this.scan_phase = state.scan_phase;
    this.last_state = state;
    this.error_banner.set_connection_error(null);
    this.error_banner.set_scan_error(state.last_error === null ? null : state.last_error.message);
    if (previous_phase !== IDLE_PHASE && state.scan_phase === IDLE_PHASE) {
      this.error_banner.report_action_error(null);
      // Ask once the printer has settled; asking now would show "busy" until the next 15 s poll.
      this.schedule_printer_refresh(POST_SCAN_PRINTER_REFRESH_DELAY_MILLISECONDS);
    }
    // A server from before the Documento mode sends no "document" summary.
    if (state.document !== undefined) {
      this.document_panel.apply_summary(state.document, {
        scan_phase: state.scan_phase,
        scans_completed: state.scans_completed,
        last_error_code: state.last_error === null ? null : state.last_error.code,
        capture_mode: this.capture_mode(),
        dots_per_inch: state.settings.dots_per_inch,
      });
    }
    this.render_activity();
    this.render_state_panels(edit_epoch);
    this.elements.session_counter.textContent = `Digitalizações nesta sessão: ${state.scans_completed}`;
  }

  schedule_printer_refresh(delay_milliseconds) {
    window.clearTimeout(this.printer_timer);
    this.printer_timer = window.setTimeout(() => this.run_scheduled_printer_refresh(), delay_milliseconds);
  }

  async run_scheduled_printer_refresh() {
    if (this.scan_phase !== IDLE_PHASE) {
      this.schedule_printer_refresh(PRINTER_POLL_INTERVAL_MILLISECONDS);
      return;
    }
    await this.refresh_printer();
  }

  async refresh_printer() {
    try {
      this.apply_printer(await send_request("GET", "/api/printer"));
    } catch (error) {
      this.apply_printer({
        connected: false,
        display_name: null,
        scanner_state: null,
        route: null,
        error: { message: error.message },
      });
    } finally {
      this.schedule_printer_refresh(PRINTER_POLL_INTERVAL_MILLISECONDS);
    }
  }

  apply_printer(printer) {
    this.render_printer(describe_printer(printer));
    this.elements.printer_status_chip.title = printer.display_name ?? "";
    const detail = printer.error === null ? "" : printer.error.message;
    this.elements.printer_detail.textContent = detail;
    this.elements.printer_detail.hidden = detail === "";
  }

  render_printer(presentation) {
    this.elements.printer_status_chip.dataset.printerCondition = presentation.condition;
    this.elements.printer_status_icon.textContent = presentation.icon;
    this.elements.printer_status_text.textContent = presentation.text;
  }

  render_activity() {
    this.render_scan_controls();
    this.render_status_line();
  }

  render_scan_controls() {
    const { scan_button, scan_button_label } = this.elements;
    const can_scan = this.is_ready_to_scan();
    const was_disabled = scan_button.disabled;
    scan_button.disabled = !can_scan;
    scan_button.setAttribute("aria-busy", String(!can_scan));
    scan_button_label.textContent = choose_scan_button_label({
      capture_mode: this.capture_mode(),
      is_scanning: this.scan_phase !== IDLE_PHASE || this.is_start_request_pending,
      is_finalizing: this.document_panel.is_finalizing_document(),
    });
    const can_change_mode = can_edit_document(this.read_scan_activity());
    Object.values(this.elements.capture_mode_inputs).forEach((input) => {
      input.disabled = !can_change_mode;
    });
    this.elements.return_to_document_button.disabled = !can_change_mode;
    const scan_activity = { scan_phase: this.scan_phase, is_start_request_pending: this.is_start_request_pending };
    this.last_scan_panel.apply_scan_activity(scan_activity);
    this.document_panel.apply_scan_activity(scan_activity);
    if (was_disabled && can_scan && document.activeElement === document.body) {
      scan_button.focus();
    }
  }

  render_status_line() {
    if (this.last_state === null) {
      return;
    }
    this.elements.status_line.textContent = this.is_document_mode()
      ? this.document_panel.describe_status(this.scan_phase)
      : describe_scan_status(this.last_state);
  }

  render_state_panels(edit_epoch) {
    if (this.last_state === null) {
      return;
    }
    this.render_storage(this.last_state);
    this.render_last_scan({ state: this.last_state, edit_epoch });
    this.render_pending_document(this.last_state.document);
  }

  // The mode changed: what each panel shows stays as it is, only which of them is on the page changes.
  render_mode_panels() {
    if (this.last_state === null) {
      return;
    }
    this.render_storage(this.last_state);
    this.last_scan_panel.set_shown_in_this_mode(!this.is_document_mode());
    this.render_pending_document(this.last_state.document);
  }

  render_storage(state) {
    const is_document_mode = this.is_document_mode();
    this.elements.storage_line.textContent = describe_storage(state.storage);
    // In the Documento mode the disk that matters is the Mac's, where the pages wait.
    this.elements.storage_line.hidden = is_document_mode;
    this.elements.storage_warning.hidden = is_document_mode || !should_recommend_external_disk(state.storage);
    if (state.document !== undefined) {
      const draft_storage = state.document.draft_storage;
      this.elements.draft_storage_line.textContent = describe_draft_storage(draft_storage);
      this.elements.draft_storage_warning.hidden = !should_warn_about_draft_storage(draft_storage);
    }
  }

  render_last_scan(last_scan_view) {
    const { state, edit_epoch } = last_scan_view;
    // A render caused by the page itself (no state was just fetched) is not older than anything.
    this.last_scan_panel.apply_server_state({
      last_result: state.last_result,
      last_result_revision: choose_thumbnail_revision(state),
      edit_epoch: edit_epoch ?? this.last_scan_panel.read_edit_epoch(),
    });
    this.last_scan_panel.set_shown_in_this_mode(!this.is_document_mode());
  }

  render_pending_document(document_summary) {
    const page_count = document_summary === undefined ? 0 : document_summary.page_count;
    this.elements.document_pending_notice.hidden = this.is_document_mode() || page_count === 0;
    this.elements.document_pending_text.textContent =
      page_count === 0 ? "" : describe_pending_document(page_count, document_summary.output_page_count);
  }

  render_capture_mode() {
    const capture_mode = this.capture_mode();
    this.elements.capture_mode_inputs[capture_mode].checked = true;
    this.elements.output_format_group.hidden = capture_mode === CAPTURE_MODES.DOCUMENT;
    if (capture_mode === CAPTURE_MODES.DOCUMENT) {
      this.document_panel.show();
    } else {
      this.document_panel.hide();
    }
    this.render_activity();
    this.render_mode_panels();
  }

  async load_settings_and_document() {
    const settings_loaded = this.load_settings();
    const document_body = await this.document_panel.refresh_document();
    await settings_loaded;
    // Only a draft brought back after a crash switches the saved quick mode to Documento, once per draft session:
    // a reload or a new tab after the user chose Rápido on purpose leaves the mode alone.
    if (document_body === null) {
      return;
    }
    const switch_check = {
      document_body,
      capture_mode: this.capture_mode(),
      switched_draft_session: this.read_switched_draft_session(),
    };
    if (should_switch_to_document_mode(switch_check)) {
      this.remember_switched_draft_session(document_body.draft_session);
      await this.change_setting_then_focus_scan_button({ capture_mode: CAPTURE_MODES.DOCUMENT });
    }
  }

  read_switched_draft_session() {
    try {
      return window.localStorage.getItem(RECOVERY_SWITCH_STORAGE_KEY);
    } catch {
      // The browser may block its storage (a private window): the switch then repeats at each load.
      return null;
    }
  }

  remember_switched_draft_session(draft_session) {
    try {
      window.localStorage.setItem(RECOVERY_SWITCH_STORAGE_KEY, draft_session);
    } catch {
      // Only a per-browser convenience; without it the switch repeats at the next load.
    }
  }

  async load_settings() {
    try {
      this.apply_saved_settings(await send_request("GET", "/api/settings"));
    } catch (error) {
      this.error_banner.report_action_error(error.message);
    }
  }

  apply_saved_settings(settings) {
    this.saved_settings = settings;
    this.elements.format_inputs[settings.output_format].checked = true;
    this.elements.output_folder_input.value = settings.output_folder;
    this.render_quality_controls(settings);
    this.render_adjustment_controls(settings);
    this.render_capture_mode();
  }

  render_quality_controls(settings) {
    const { resolution_select, color_mode_select } = this.elements;
    // A server from before these settings sends neither: the lists stay as they are.
    resolution_select.value = String(settings.dots_per_inch ?? resolution_select.value);
    color_mode_select.value = settings.color_mode ?? color_mode_select.value;
    this.render_resolution_warning(settings.dots_per_inch);
  }

  render_resolution_warning(dots_per_inch) {
    const warning_text = describe_resolution_warning(dots_per_inch);
    this.elements.resolution_warning.hidden = warning_text === null;
    this.elements.resolution_warning_text.textContent = warning_text ?? "";
  }

  render_adjustment_controls(settings) {
    const { auto_crop_checkbox, jpeg_quality_input, jpeg_quality_value } = this.elements;
    auto_crop_checkbox.checked = settings.auto_crop === true;
    // The margin only matters while the automatic crop is on; the choice stays visible but cannot change otherwise.
    this.elements.crop_margin_checkbox.checked = settings.crop_margin !== false;
    this.elements.crop_margin_checkbox.disabled = settings.auto_crop !== true;
    if (this.has_newer_quality_than_the_answer()) {
      return;
    }
    const jpeg_quality = parse_jpeg_quality(settings.jpeg_quality);
    jpeg_quality_input.value = String(jpeg_quality);
    jpeg_quality_value.textContent = String(jpeg_quality);
  }

  async send_settings(settings) {
    this.apply_saved_settings(await send_request("PUT", "/api/settings", settings));
    this.schedule_state_refresh(IMMEDIATE_REFRESH_MILLISECONDS);
  }

  async change_setting(changes) {
    try {
      await this.send_settings({ ...this.saved_settings, ...changes });
      this.error_banner.report_action_error(null);
    } catch (error) {
      this.error_banner.report_action_error(error.message);
      this.apply_saved_settings(this.saved_settings);
    }
  }

  async change_setting_then_focus_scan_button(changes) {
    await this.change_setting(changes);
    this.elements.scan_button.focus();
  }

  async save_output_folder() {
    const { output_folder_input, output_folder_message, scan_button } = this.elements;
    output_folder_message.hidden = true;
    try {
      await this.send_settings({ ...this.saved_settings, output_folder: output_folder_input.value.trim() });
    } catch (error) {
      output_folder_message.textContent = error.message;
      output_folder_message.hidden = false;
      return;
    }
    scan_button.focus();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  build_scan_page(collect_elements()).start();
});
