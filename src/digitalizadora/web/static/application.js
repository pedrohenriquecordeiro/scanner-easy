"use strict";

// Uses IDLE_PHASE, SPACE_KEY_ACTIONS, decide_space_key_action and can_start_scan from scan-trigger-policy.js,
// which index.html loads first.

const REQUIRED_HEADER_NAME = "X-Requested-With";
const REQUIRED_HEADER_VALUE = "digitalizadora";

const PREPARING_PHASE = "preparing";
const PHASE_MESSAGES = {
  preparing: "Preparando…",
  scanning: "Digitalizando… (cerca de 15 s; no modo Foto, cerca de 75 s)",
  saving: "Salvando…",
};
const READY_MESSAGE = "Pronto para digitalizar. Coloque a folha no vidro e aperte Espaço.";
const LAST_SCAN_FAILED_MESSAGE = "A última digitalização falhou.";
const SERVER_UNREACHABLE_MESSAGE = "Não consegui falar com o Digitalizadora. Ele ainda está aberto no Terminal?";
const UNEXPECTED_ERROR_MESSAGE = "Algo inesperado aconteceu. Veja o registro em ~/Library/Logs/Digitalizadora.";
const SERVER_UNREACHABLE_CODE = "server_unreachable";
const UNEXPECTED_ERROR_CODE = "unexpected_error";

const SCAN_BUTTON_READY_LABEL = "Digitalizar";
const SCAN_BUTTON_BUSY_LABEL = "Digitalizando…";

const ACTIVE_POLL_INTERVAL_MILLISECONDS = 500;
const IDLE_POLL_INTERVAL_MILLISECONDS = 2000;
const PRINTER_POLL_INTERVAL_MILLISECONDS = 15000;
// Gate 0: the printer reports Processing for 4 to 5 s after each delivery.
const POST_SCAN_PRINTER_REFRESH_DELAY_MILLISECONDS = 6000;
const IMMEDIATE_REFRESH_MILLISECONDS = 0;

const BYTES_PER_UNIT = 1000;
const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"];
const ROUNDING_SCALE = 10;
const EXTERNAL_DISK_WARNING_BYTES = 5 * BYTES_PER_UNIT ** 3;
const OUTPUT_FOLDER_UNAVAILABLE_TEXT = "Pasta de saída indisponível. Se for um disco externo, confira se está conectado.";
const SINGLE_PAGE_COUNT = 1;

const PORTUGUESE_LOCALE = "pt-BR";
const ONE_DECIMAL_FORMAT = { minimumFractionDigits: 1, maximumFractionDigits: 1 };
const CLOCK_TIME_FORMAT = { hour: "2-digit", minute: "2-digit", second: "2-digit" };

const ENTER_KEY_CODE = "Enter";

const PRINTER_PRESENTATIONS = {
  searching: { condition: "searching", icon: "…", text: "Procurando…" },
  ready: { condition: "ready", icon: "✔", text: "Impressora pronta" },
  busy: { condition: "busy", icon: "⏳", text: "Impressora ocupada" },
  missing: { condition: "missing", icon: "⚠", text: "Impressora não encontrada" },
};
const PRINTER_ROUTE_LABELS = { usb: "USB", network: "Wi-Fi" };
const READY_SCANNER_STATE = "idle";

class RequestError extends Error {
  constructor(status_code, error_code, message) {
    super(message);
    this.status_code = status_code;
    this.error_code = error_code;
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

function build_thumbnail_address(version) {
  return `/api/scans/last/thumbnail?version=${version}`;
}

function format_scan_time(scanned_at) {
  return new Date(scanned_at).toLocaleTimeString(PORTUGUESE_LOCALE, CLOCK_TIME_FORMAT);
}

function describe_scan_status(state) {
  if (state.scan_phase !== IDLE_PHASE) {
    return PHASE_MESSAGES[state.scan_phase] ?? "";
  }
  if (state.last_error !== null) {
    return LAST_SCAN_FAILED_MESSAGE;
  }
  if (state.last_result !== null) {
    return `Pronto! Salvo como ${state.last_result.file_name}`;
  }
  return READY_MESSAGE;
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
  const error_code = payload !== null && typeof payload.code === "string" ? payload.code : UNEXPECTED_ERROR_CODE;
  const message = payload !== null && typeof payload.message === "string" ? payload.message : UNEXPECTED_ERROR_MESSAGE;
  return new RequestError(response.status, error_code, message);
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
    throw new RequestError(0, SERVER_UNREACHABLE_CODE, SERVER_UNREACHABLE_MESSAGE);
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
    scan_button: document.getElementById("scan-button"),
    scan_button_label: document.getElementById("scan-button-label"),
    status_line: document.getElementById("status-line"),
    format_inputs: {
      pdf: document.getElementById("output-format-pdf"),
      jpg: document.getElementById("output-format-jpg"),
    },
    preset_select: document.getElementById("preset-select"),
    output_folder_input: document.getElementById("output-folder-input"),
    output_folder_save_button: document.getElementById("output-folder-save-button"),
    output_folder_message: document.getElementById("output-folder-message"),
    storage_line: document.getElementById("storage-line"),
    storage_warning: document.getElementById("storage-warning"),
    last_scan_panel: document.getElementById("last-scan-panel"),
    last_scan_thumbnail: document.getElementById("last-scan-thumbnail"),
    last_scan_file_name: document.getElementById("last-scan-file-name"),
    last_scan_size: document.getElementById("last-scan-size"),
    last_scan_time: document.getElementById("last-scan-time"),
    session_counter: document.getElementById("session-counter"),
  };
}

class ScanPage {
  constructor(elements) {
    this.elements = elements;
    this.scan_phase = IDLE_PHASE;
    this.is_start_request_pending = false;
    this.saved_settings = null;
    this.shown_thumbnail_version = null;
    this.connection_error_message = null;
    this.action_error_message = null;
    this.scan_error_message = null;
    this.state_timer = null;
    this.printer_timer = null;
  }

  start() {
    this.bind_events();
    this.render_printer(PRINTER_PRESENTATIONS.searching);
    this.load_settings();
    this.refresh_state();
    this.refresh_printer();
  }

  bind_events() {
    const { scan_button, preset_select, output_folder_input, output_folder_save_button, format_inputs } = this.elements;
    scan_button.addEventListener("click", () => this.start_scan());
    document.addEventListener("keydown", (event) => this.handle_key_down(event));
    document.addEventListener("keyup", (event) => this.handle_key_up(event));
    Object.values(format_inputs).forEach((input) => {
      input.addEventListener("change", (event) => this.change_setting({ output_format: event.target.value }));
    });
    preset_select.addEventListener("change", () => this.change_setting({ scan_preset: preset_select.value }));
    output_folder_save_button.addEventListener("click", () => this.save_output_folder());
    output_folder_input.addEventListener("keydown", (event) => {
      if (event.code === ENTER_KEY_CODE) {
        this.save_output_folder();
      }
    });
  }

  handle_key_down(event) {
    const action = decide_space_key_action(event, this.elements.scan_button);
    if (action === SPACE_KEY_ACTIONS.IGNORE) {
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

  is_ready_to_scan() {
    return can_start_scan({ scan_phase: this.scan_phase, is_start_request_pending: this.is_start_request_pending });
  }

  async start_scan() {
    if (!this.is_ready_to_scan()) {
      return;
    }
    this.is_start_request_pending = true;
    this.action_error_message = null;
    this.render_scan_controls();
    this.render_error_banner();
    try {
      await send_request("POST", "/api/scans");
      this.scan_phase = PREPARING_PHASE;
    } catch (error) {
      this.action_error_message = error.message;
    } finally {
      this.is_start_request_pending = false;
    }
    this.render_scan_controls();
    this.render_error_banner();
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
    try {
      this.apply_state(await send_request("GET", "/api/state"));
    } catch (error) {
      this.connection_error_message = error.message;
      this.render_error_banner();
    } finally {
      this.schedule_state_refresh(this.next_state_interval());
    }
  }

  apply_state(state) {
    const previous_phase = this.scan_phase;
    this.scan_phase = state.scan_phase;
    this.connection_error_message = null;
    this.scan_error_message = state.last_error === null ? null : state.last_error.message;
    if (previous_phase !== IDLE_PHASE && state.scan_phase === IDLE_PHASE) {
      this.action_error_message = null;
      // Ask once the printer has settled; asking now would show "busy" until the next 15 s poll.
      this.schedule_printer_refresh(POST_SCAN_PRINTER_REFRESH_DELAY_MILLISECONDS);
    }
    this.render_scan_controls();
    this.render_status_line(state);
    this.render_storage(state.storage);
    this.render_last_scan(state);
    this.elements.session_counter.textContent = `Digitalizações nesta sessão: ${state.scans_completed}`;
    this.render_error_banner();
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

  render_scan_controls() {
    const { scan_button, scan_button_label } = this.elements;
    const can_scan = this.is_ready_to_scan();
    const was_disabled = scan_button.disabled;
    scan_button.disabled = !can_scan;
    scan_button.setAttribute("aria-busy", String(!can_scan));
    scan_button_label.textContent = can_scan ? SCAN_BUTTON_READY_LABEL : SCAN_BUTTON_BUSY_LABEL;
    if (was_disabled && can_scan && document.activeElement === document.body) {
      scan_button.focus();
    }
  }

  render_status_line(state) {
    this.elements.status_line.textContent = describe_scan_status(state);
  }

  render_storage(storage) {
    this.elements.storage_line.textContent = describe_storage(storage);
    this.elements.storage_warning.hidden = !should_recommend_external_disk(storage);
  }

  render_last_scan(state) {
    const result = state.last_result;
    this.elements.last_scan_panel.hidden = result === null;
    if (result === null) {
      return;
    }
    if (this.shown_thumbnail_version !== state.scans_completed) {
      this.elements.last_scan_thumbnail.src = build_thumbnail_address(state.scans_completed);
      this.shown_thumbnail_version = state.scans_completed;
    }
    this.elements.last_scan_file_name.textContent = result.file_name;
    this.elements.last_scan_size.textContent = format_byte_count(result.size_in_bytes);
    this.elements.last_scan_time.textContent = format_scan_time(result.scanned_at);
  }

  choose_error_message() {
    return this.connection_error_message ?? this.action_error_message ?? this.scan_error_message;
  }

  render_error_banner() {
    const message = this.choose_error_message();
    this.elements.error_banner_content.hidden = message === null;
    this.elements.error_banner_text.textContent = message ?? "";
  }

  async load_settings() {
    try {
      this.apply_saved_settings(await send_request("GET", "/api/settings"));
    } catch (error) {
      this.action_error_message = error.message;
      this.render_error_banner();
    }
  }

  apply_saved_settings(settings) {
    this.saved_settings = settings;
    this.elements.format_inputs[settings.output_format].checked = true;
    this.elements.preset_select.value = settings.scan_preset;
    this.elements.output_folder_input.value = settings.output_folder;
  }

  async send_settings(settings) {
    this.apply_saved_settings(await send_request("PUT", "/api/settings", settings));
    this.schedule_state_refresh(IMMEDIATE_REFRESH_MILLISECONDS);
  }

  async change_setting(changes) {
    try {
      await this.send_settings({ ...this.saved_settings, ...changes });
      this.action_error_message = null;
    } catch (error) {
      this.action_error_message = error.message;
      this.apply_saved_settings(this.saved_settings);
    }
    this.render_error_banner();
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
  new ScanPage(collect_elements()).start();
});
