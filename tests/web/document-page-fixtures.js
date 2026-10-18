"use strict";

// What the Documento mode scenarios share: the fixtures (pages, settings, state and error bodies), the scripted
// answers of a page with three scanned pages, and DocumentPageUnderTest, the fake browser page with the helpers to
// find tiles, buttons and focus. document-panel-harness.js and page-frame-editor-harness.js both build on it.

const { BrowserPage, build_json_response } = require("./fake-browser.js");
const DRAFT_SESSION = "5c0f9a2e7b1d4c38";
const FIRST_PAGE = "0000000000000001";
const SECOND_PAGE = "0000000000000002";
const THIRD_PAGE = "0000000000000003";
const FOURTH_PAGE = "0000000000000004";
const THREE_PAGES = [FIRST_PAGE, SECOND_PAGE, THIRD_PAGE];
const FOUR_PAGES = [...THREE_PAGES, FOURTH_PAGE];
const PAGE_SIZE_IN_BYTES = 806123;
const SCANNED_AT = "2026-10-17T10:00:00-03:00";
const POLL_DELAYS_MILLISECONDS = [0, 500, 2000];
const TILE_BUTTON_INDEXES = Object.freeze({ move_left: 0, move_right: 1, delete: 2, rotate: 3, move_to: 4, enlarge: 5 });
const RECOVERY_SWITCH_STORAGE_KEY = "digitalizadora.recovery_switch_session";
const TILE_ACTIONS_INDEX = 4;
const RIGHT_HALF_POSITION = 90;

const QUICK_SETTINGS = {
  output_folder: "/Users/teste/Digitalizadora",
  output_format: "pdf",
  dots_per_inch: 300,
  color_mode: "color",
  capture_mode: "single",
  auto_crop: false,
};
const DOCUMENT_SETTINGS = { ...QUICK_SETTINGS, capture_mode: "document" };
const AVAILABLE_STORAGE = { free_space_in_bytes: 12e9, estimated_pages_remaining: 4000, output_folder_available: true };
const DRAFT_STORAGE = { free_space_in_bytes: 12e9, estimated_pages_remaining: 4000, available: true };
const PRINTER = { connected: true, display_name: "DeskJet 2800", scanner_state: "idle", route: "usb", error: null };
const ACCEPTED_BODY = { accepted: true };
const FINALIZED_BODY = {
  file_name: "Contrato.pdf",
  output_folder: "/Users/teste/Digitalizadora",
  page_count: 3,
  size_in_bytes: 2418369,
};
const LAST_FINISHED_DOCUMENT = { ...FINALIZED_BODY, finalized_at: "2026-10-17T10:05:00-03:00" };
const LAST_SCAN_RESULT = {
  scan_identifier: "9f3c1d2e4b5a6978",
  file_names: ["2026-10-17_00001.pdf"],
  output_folder: "/Users/teste/Digitalizadora",
  output_format: "pdf",
  total_size_in_bytes: 1234567,
  scanned_at: "2026-10-17T09:00:00-03:00",
  rotation_degrees: 0,
  crops: [],
  is_editable: true,
};
const RESUMED_RECOVERY = { outcome: "resumed", kept_page_count: 3, dropped_page_positions: [], set_aside_folder: null };
const SCAN_ALREADY_RUNNING_BODY = {
  code: "scan_already_running",
  message: "Já existe uma digitalização em andamento.",
};
const DOCUMENT_BUSY_BODY = {
  code: "document_busy",
  message: "O documento está sendo salvo ou alterado. Aguarde um instante e tente de novo.",
};
const INVALID_PAGE_ORDER_BODY = {
  code: "invalid_page_order",
  message: "A nova ordem das páginas não confere com o documento. A lista foi atualizada; tente de novo.",
};
const INVALID_DOCUMENT_NAME_BODY = {
  code: "invalid_document_name",
  message:
    "Nome de documento inválido: comprido demais ou só com pontos e caracteres invisíveis. " +
    "Use um nome mais curto, com letras ou números.",
};
const ROTATION_PATH_KEY = `POST /api/document/pages/${SECOND_PAGE}/rotation`;
const INVALID_CROP_BODY = {
  code: "invalid_crop",
  message: "A moldura de corte é inválida. Ajuste e tente de novo.",
};
const PAGE_NOT_FOUND_BODY = { code: "page_not_found", message: "Essa página não existe mais no documento." };
const DAMAGED_PAGE_BODY = {
  code: "damaged_document_page",
  message:
    "Uma página guardada do documento está danificada ou sumiu do disco do Mac. " +
    "Ela está marcada na grade: exclua-a e digitalize-a de novo.",
  page_identifier: SECOND_PAGE,
};

const NO_FRAMING = Object.freeze({ rotation_degrees: 0, crops: [] });

// A crop of the server's body: four corners in fractions of the page, clockwise from the top left.
function rectangle_crop(left, top, right, bottom) {
  return {
    top_left: { x: left, y: top },
    top_right: { x: right, y: top },
    bottom_right: { x: right, y: bottom },
    bottom_left: { x: left, y: bottom },
  };
}

function quadrilateral_crop(points) {
  const [top_left, top_right, bottom_right, bottom_left] = points.map(([x, y]) => ({ x, y }));
  return { top_left, top_right, bottom_right, bottom_left };
}

// What an overlay of frames (frame-overlay.js) shows: the container, its drawing and its numbered badges.
function read_overlay(container) {
  const [drawing, ...badges] = container.children;
  const [shade, ...outlines] = drawing.children;
  return {
    hidden: container.hidden,
    aria_hidden: container.getAttribute("aria-hidden"),
    shade_path: shade.getAttribute("d"),
    outlines: outlines.map((outline) => ({
      visible: outline.style.display !== "none",
      points: outline.getAttribute("points"),
      is_active: outline.classList.contains("is-active"),
      is_second_colour: outline.classList.contains("frame-colour-second"),
    })),
    badges: badges.map((badge) => ({
      hidden: badge.hidden,
      text: badge.textContent,
      left: badge.style.left ?? null,
      top: badge.style.top ?? null,
    })),
  };
}

function build_page(page_identifier, framing) {
  return {
    page_identifier,
    scanned_at: SCANNED_AT,
    dots_per_inch: 300,
    color_mode: "color",
    size_in_bytes: PAGE_SIZE_IN_BYTES,
    ...(framing ?? NO_FRAMING),
  };
}

function build_draft(draft_parts) {
  const { page_identifiers, name, framings } = draft_parts;
  const pages = page_identifiers.map((page_identifier) => build_page(page_identifier, (framings ?? {})[page_identifier]));
  return {
    name,
    created_at: SCANNED_AT,
    page_count: page_identifiers.length,
    output_page_count: pages.reduce((total, page) => total + Math.max(page.crops.length, 1), 0),
    estimated_size_in_bytes: page_identifiers.length * PAGE_SIZE_IN_BYTES,
    finalization_started_at: null,
    finished_document_path: null,
    pages,
  };
}

function build_document_body(body_parts) {
  const { revision, page_identifiers, name, framings, recovery, last_finished_document } = body_parts;
  return {
    draft_session: DRAFT_SESSION,
    revision,
    document:
      page_identifiers.length === 0 ? null : build_draft({ page_identifiers, name: name ?? "", framings }),
    recovery: recovery ?? null,
    last_finished_document: last_finished_document ?? null,
  };
}

function build_state(state_parts) {
  const { revision, page_count, scans_completed, last_result, last_result_revision, settings } = state_parts;
  return {
    scan_phase: state_parts.scan_phase ?? "idle",
    scans_completed: scans_completed ?? 0,
    last_result: last_result ?? null,
    ...(last_result_revision === undefined ? {} : { last_result_revision }),
    last_error: null,
    settings: settings ?? DOCUMENT_SETTINGS,
    storage: AVAILABLE_STORAGE,
    document: {
      draft_session: DRAFT_SESSION,
      revision,
      page_count,
      output_page_count: state_parts.output_page_count ?? page_count,
      estimated_size_in_bytes: page_count * PAGE_SIZE_IN_BYTES,
      draft_storage: DRAFT_STORAGE,
    },
  };
}

function respond(body) {
  return build_json_response(200, body);
}

function build_default_responses() {
  return {
    "GET /api/settings": respond(DOCUMENT_SETTINGS),
    "PUT /api/settings": respond(DOCUMENT_SETTINGS),
    "GET /api/state": respond(build_state({ revision: 1, page_count: 3 })),
    "GET /api/printer": respond(PRINTER),
    "GET /api/document": respond(build_document_body({ revision: 1, page_identifiers: THREE_PAGES })),
    "POST /api/document/pages": build_json_response(202, ACCEPTED_BODY),
    "DELETE /api/document/pages/last": respond(
      build_document_body({ revision: 2, page_identifiers: [FIRST_PAGE, SECOND_PAGE] }),
    ),
    [`DELETE /api/document/pages/${SECOND_PAGE}`]: respond(
      build_document_body({ revision: 2, page_identifiers: [FIRST_PAGE, THIRD_PAGE] }),
    ),
    "PUT /api/document/name": respond(
      build_document_body({ revision: 2, page_identifiers: THREE_PAGES, name: "Contrato" }),
    ),
    "POST /api/document/finalize": respond(FINALIZED_BODY),
    "DELETE /api/document": respond(build_document_body({ revision: 2, page_identifiers: [] })),
  };
}

function build_recovered_quick_responses() {
  return {
    "GET /api/settings": respond(QUICK_SETTINGS),
    "GET /api/state": respond(build_state({ revision: 0, page_count: 3, settings: QUICK_SETTINGS })),
    "GET /api/document": respond(
      build_document_body({ revision: 0, page_identifiers: THREE_PAGES, recovery: RESUMED_RECOVERY }),
    ),
  };
}

class DocumentPageUnderTest extends BrowserPage {
  constructor(response_overrides, storage) {
    super({ ...build_default_responses(), ...response_overrides }, storage);
  }

  tile_at(position) {
    return this.element("document-page-grid").children[position - 1];
  }

  tile_button(position, button_name) {
    return this.tile_at(position).children[TILE_ACTIONS_INDEX].children[TILE_BUTTON_INDEXES[button_name]];
  }

  tile_thumbnail(position) {
    return this.tile_at(position).children[0].children[0];
  }

  tile_overlay(position) {
    return this.tile_at(position).children[0].children[1];
  }

  tile_crop_count(position) {
    return this.tile_at(position).children[3];
  }

  grid_page_identifiers() {
    return this.element("document-page-grid").children.map((tile) => tile.dataset.pageIdentifier);
  }

  describe_focus() {
    const focused_element = this.active_element();
    const tile = focused_element.parent?.parent ?? null;
    return {
      label: focused_element.getAttribute("aria-label"),
      page_identifier: tile === null ? null : tile.dataset.pageIdentifier ?? null,
    };
  }

  banner() {
    return { hidden: this.element("error-banner-content").hidden, text: this.element("error-banner-text").textContent };
  }

  async poll(state) {
    this.responses["GET /api/state"] = respond(state);
    for (const delay_milliseconds of POLL_DELAYS_MILLISECONDS) {
      this.timers.run_pending_with_delay(delay_milliseconds);
    }
    await this.flush();
  }

  async type_name(name) {
    const name_input = this.element("document-name-input");
    name_input.focus();
    name_input.value = name;
    await this.flush();
  }

  async open_and_accept_the_finalize_confirmation() {
    await this.click(this.element("save-document-button"));
    await this.click(this.element("confirmation-accept-button"));
  }

  count_name_requests() {
    return this.count_requests("PUT /api/document/name");
  }

  list_name_request_bodies() {
    return this.requests.filter((request) => request.key === "PUT /api/document/name").map((request) => request.body);
  }
}

async function load_page(response_overrides, storage) {
  const page = new DocumentPageUnderTest(response_overrides, storage);
  await page.load();
  return page;
}

module.exports = {
  DRAFT_SESSION,
  FIRST_PAGE,
  SECOND_PAGE,
  THIRD_PAGE,
  FOURTH_PAGE,
  THREE_PAGES,
  FOUR_PAGES,
  PAGE_SIZE_IN_BYTES,
  SCANNED_AT,
  POLL_DELAYS_MILLISECONDS,
  TILE_BUTTON_INDEXES,
  RECOVERY_SWITCH_STORAGE_KEY,
  TILE_ACTIONS_INDEX,
  RIGHT_HALF_POSITION,
  QUICK_SETTINGS,
  DOCUMENT_SETTINGS,
  AVAILABLE_STORAGE,
  DRAFT_STORAGE,
  PRINTER,
  ACCEPTED_BODY,
  FINALIZED_BODY,
  LAST_FINISHED_DOCUMENT,
  LAST_SCAN_RESULT,
  RESUMED_RECOVERY,
  SCAN_ALREADY_RUNNING_BODY,
  DOCUMENT_BUSY_BODY,
  INVALID_PAGE_ORDER_BODY,
  INVALID_DOCUMENT_NAME_BODY,
  ROTATION_PATH_KEY,
  INVALID_CROP_BODY,
  PAGE_NOT_FOUND_BODY,
  NO_FRAMING,
  rectangle_crop,
  quadrilateral_crop,
  read_overlay,
  DAMAGED_PAGE_BODY,
  build_page,
  build_draft,
  build_document_body,
  build_state,
  respond,
  build_default_responses,
  build_recovered_quick_responses,
  DocumentPageUnderTest,
  load_page,
};
