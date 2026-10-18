"use strict";

// Plays the scenarios of the last scan of the quick mode (its panel, "Girar", "Ampliar" and the frame dialog opened from
// it) named on the command line against the real static scripts in the fake browser and prints one JSON object with what
// the page did in each. tests/web/test_last_scan_panel.py and test_last_scan_dialog.py assert on it.

const { build_deferred_response, build_json_response } = require("./fake-browser.js");
const { read_dialog } = require("./frame-dialog-reader.js");
const {
  QUICK_SETTINGS,
  DOCUMENT_SETTINGS,
  rectangle_crop,
  read_overlay,
  build_document_body,
  build_state,
  respond,
  load_page,
} = require("./document-page-fixtures.js");

const STAGE_BOX = Object.freeze({ left: 0, top: 0, width: 500, height: 400 });
const CENTER_OF_THE_STAGE = Object.freeze({ x: 250, y: 200 });
const SCAN_IDENTIFIER = "9f3c1d2e4b5a6978";
const OTHER_SCAN_IDENTIFIER = "0a1b2c3d4e5f6071";
const FIRST_FILE = "2026_10_18__16_14_03_000000006.pdf";
const SECOND_FILE = "2026_10_18__16_14_03_000000007.pdf";
const THIRD_FILE = "2026_10_18__16_14_03_000000008.pdf";
const PAIR_FIRST_FILE = "2026_10_18__16_14_03_000000006__1.pdf";
const PAIR_SECOND_FILE = "2026_10_18__16_14_03_000000006__2.pdf";
const NEW_PAIR_FIRST_FILE = "2026_10_18__16_14_03_000000009__1.pdf";
const NEW_PAIR_SECOND_FILE = "2026_10_18__16_14_03_000000009__2.pdf";
const UPPER_CROP = rectangle_crop(0.05, 0.02, 0.9, 0.55);
const LOWER_CROP = rectangle_crop(0.05, 0.6, 0.9, 0.95);
const WHOLE_CROP = rectangle_crop(0.1, 0.1, 0.8, 0.9);
const DETECTED_CROP = rectangle_crop(0.12, 0.11, 0.92, 0.93);
const TURNED_CROP = rectangle_crop(0.1, 0.2, 0.9, 0.8);
const ROTATE_KEY = "POST /api/scans/last/rotation";
const CROPS_KEY = "PUT /api/scans/last/crops";
const DETECT_KEY = "POST /api/scans/last/crops/detect";
const SCAN_KEY = "POST /api/scans";
const NO_LAST_SCAN_BODY = { code: "no_last_scan", message: "Ainda não há uma digitalização para ajustar." };
const SCAN_REPLACED_BODY = {
  code: "last_scan_replaced",
  message: "Essa digitalização já foi substituída por outra mais nova.",
};
const INVALID_CROP_BODY = { code: "invalid_crop", message: "A moldura de corte é inválida. Ajuste e tente de novo." };
const BUSY_BODY = {
  code: "last_scan_busy",
  message: "A última digitalização está sendo ajustada. Aguarde um instante e tente de novo.",
};
const FIRST_REVISION = 3;

function build_last_result(changes) {
  return {
    scan_identifier: SCAN_IDENTIFIER,
    file_names: [FIRST_FILE],
    output_folder: "/Users/teste/Digitalizadora",
    output_format: "pdf",
    total_size_in_bytes: 412345,
    scanned_at: "2026-10-18T12:41:03-03:00",
    rotation_degrees: 0,
    crops: [],
    is_editable: true,
    ...changes,
  };
}

const ONE_FILE_RESULT = build_last_result({});
const TWO_PHOTOS_RESULT = build_last_result({ file_names: [PAIR_FIRST_FILE, PAIR_SECOND_FILE], crops: [UPPER_CROP, LOWER_CROP] });
const ONE_PHOTO_RESULT = build_last_result({ crops: [WHOLE_CROP] });

const ONE_PHOTO_NEW_FILE_RESULT = build_last_result({ file_names: [SECOND_FILE], crops: [WHOLE_CROP] });

function build_answer(last_result, extra) {
  return { last_result, ...extra };
}

function build_quick_state(last_result, changes) {
  return build_state({
    revision: 0,
    page_count: 0,
    scans_completed: 1,
    last_result,
    last_result_revision: FIRST_REVISION,
    settings: QUICK_SETTINGS,
    ...changes,
  });
}

async function load_quick_page(last_result, response_overrides) {
  const page = await load_page({
    "GET /api/settings": respond(QUICK_SETTINGS),
    "GET /api/state": respond(build_quick_state(last_result)),
    "GET /api/document": respond(build_document_body({ revision: 0, page_identifiers: [] })),
    ...response_overrides,
  });
  page.element("frame-stage").box = STAGE_BOX;
  return page;
}

async function poll_quick_state(page, last_result, changes) {
  await page.poll(build_quick_state(last_result, changes));
}

function read_panel(page) {
  const thumbnail_frame = page.element("last-scan-thumbnail-frame");
  return {
    hidden: page.element("last-scan-panel").hidden,
    thumbnail_source: page.element("last-scan-thumbnail").src,
    thumbnail_alt: page.element("last-scan-thumbnail").alt,
    file_names: page.element("last-scan-file-names").textContent,
    size: page.element("last-scan-size").textContent,
    hint: page.element("last-scan-hint").textContent,
    status: page.element("last-scan-status").textContent,
    rotate_disabled: page.element("last-scan-rotate-button").disabled,
    enlarge_disabled: page.element("last-scan-enlarge-button").disabled,
    overlay: read_overlay(thumbnail_frame.children[1]),
    status_line: page.element("status-line").textContent,
    scan_button_disabled: page.element("scan-button").disabled,
    aspect_ratio: thumbnail_frame.style.aspectRatio ?? null,
  };
}

async function open_the_dialog(page) {
  await page.click(page.element("last-scan-enlarge-button"));
  page.dispatch_simple_event(page.element("frame-image"), "load");
}

async function drag_element(page, identifier, shift) {
  const start = CENTER_OF_THE_STAGE;
  await page.drag_pointer(page.element(identifier), { from: start, to: { x: start.x + shift.x, y: start.y + shift.y } });
}

async function drag_the_first_corner(page) {
  await drag_element(page, "frame-corner-top-left", { x: 25, y: 20 });
}

function count_requests_of_the_edits(page) {
  return [ROTATE_KEY, CROPS_KEY, DETECT_KEY].reduce((sum, key) => sum + page.count_requests(key), 0);
}

const SCENARIOS = {
  async panel_after_two_photos() {
    const page = await load_quick_page(TWO_PHOTOS_RESULT);
    return read_panel(page);
  },
  async panel_after_one_file() {
    const page = await load_quick_page(ONE_FILE_RESULT);
    return read_panel(page);
  },
  async panel_after_one_photo_with_a_frame() {
    const page = await load_quick_page(ONE_PHOTO_RESULT);
    return read_panel(page);
  },
  async panel_before_any_scan() {
    const page = await load_quick_page(null);
    return read_panel(page);
  },
  async panel_of_a_scan_whose_original_was_not_kept() {
    const page = await load_quick_page(build_last_result({ is_editable: false, crops: [WHOLE_CROP] }));
    return read_panel(page);
  },
  async panel_of_a_server_without_revisions() {
    const state = build_quick_state(ONE_FILE_RESULT, { scans_completed: 7 });
    delete state.last_result_revision;
    const page = await load_quick_page(ONE_FILE_RESULT, { "GET /api/state": respond(state) });
    return read_panel(page);
  },
  async panel_in_the_document_mode() {
    const page = await load_quick_page(TWO_PHOTOS_RESULT, {
      "GET /api/settings": respond(DOCUMENT_SETTINGS),
      "GET /api/state": respond(build_quick_state(TWO_PHOTOS_RESULT, { settings: DOCUMENT_SETTINGS })),
    });
    return read_panel(page);
  },
  async panel_proportion_follows_the_loaded_thumbnail() {
    const page = await load_quick_page(TWO_PHOTOS_RESULT);
    const thumbnail = page.element("last-scan-thumbnail");
    const before_loading = page.element("last-scan-thumbnail-frame").style.aspectRatio ?? null;
    thumbnail.naturalWidth = 480;
    thumbnail.naturalHeight = 320;
    page.dispatch_simple_event(thumbnail, "load");
    const after_loading = page.element("last-scan-thumbnail-frame").style.aspectRatio;
    thumbnail.naturalWidth = 0;
    thumbnail.naturalHeight = 0;
    page.dispatch_simple_event(thumbnail, "load");
    return { before_loading, after_loading, after_an_empty_load: page.element("last-scan-thumbnail-frame").style.aspectRatio };
  },
  async panel_follows_a_new_scan() {
    const page = await load_quick_page(ONE_FILE_RESULT);
    const next_result = build_last_result({
      scan_identifier: OTHER_SCAN_IDENTIFIER,
      file_names: [NEW_PAIR_FIRST_FILE, NEW_PAIR_SECOND_FILE],
      crops: [UPPER_CROP, LOWER_CROP],
    });
    await poll_quick_state(page, next_result, { last_result_revision: FIRST_REVISION + 1 });
    return read_panel(page);
  },
  async panel_while_scanning() {
    const page = await load_quick_page(TWO_PHOTOS_RESULT);
    await poll_quick_state(page, TWO_PHOTOS_RESULT, { scan_phase: "scanning" });
    return read_panel(page);
  },
  async rotate_by_pointer() {
    const turned_result = build_last_result({ file_names: [SECOND_FILE], rotation_degrees: 90, crops: [TURNED_CROP] });
    const page = await load_quick_page(ONE_PHOTO_RESULT, {
      [ROTATE_KEY]: respond(build_answer(turned_result)),
    });
    await page.click(page.element("last-scan-rotate-button"));
    const right_after = read_panel(page);
    const state_requests_before = page.count_requests("GET /api/state");
    await poll_quick_state(page, turned_result, { last_result_revision: FIRST_REVISION + 1 });
    return {
      rotation_requests: page.count_requests(ROTATE_KEY),
      request_headers: page.find_request(ROTATE_KEY).headers,
      right_after,
      thumbnail_after_the_next_state: read_panel(page).thumbnail_source,
      state_requests_after: page.count_requests("GET /api/state") - state_requests_before,
      scan_button_focused: page.is_focused("scan-button"),
    };
  },
  async rotate_asks_for_the_state_at_once() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, {
      [ROTATE_KEY]: respond(build_answer(build_last_result({ file_names: [SECOND_FILE], rotation_degrees: 90, crops: [TURNED_CROP] }))),
    });
    const state_requests_before = page.count_requests("GET /api/state");
    await page.click(page.element("last-scan-rotate-button"));
    page.timers.run_pending_with_delay(0);
    await page.flush();
    return { extra_state_requests: page.count_requests("GET /api/state") - state_requests_before };
  },
  async rotate_while_the_answer_is_pending() {
    const rotation_answer = build_deferred_response();
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: rotation_answer });
    await page.click(page.element("last-scan-rotate-button"));
    await page.click(page.element("last-scan-rotate-button"));
    const during = read_panel(page);
    rotation_answer.answer(respond(build_answer(ONE_PHOTO_NEW_FILE_RESULT)));
    await page.flush();
    return { during, after: read_panel(page), rotation_requests: page.count_requests(ROTATE_KEY) };
  },
  async rotate_by_keyboard() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: respond(build_answer(ONE_PHOTO_NEW_FILE_RESULT)) });
    await page.press_with_keyboard(page.element("last-scan-rotate-button"));
    return {
      rotation_requests: page.count_requests(ROTATE_KEY),
      rotate_button_focused: page.is_focused("last-scan-rotate-button"),
    };
  },
  async space_after_clicking_rotate() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: respond(build_answer(ONE_PHOTO_NEW_FILE_RESULT)) });
    await page.click(page.element("last-scan-rotate-button"));
    await page.press_key("Space");
    return { rotation_requests: page.count_requests(ROTATE_KEY), scan_requests: page.count_requests(SCAN_KEY) };
  },
  async rotate_again_empties_the_status_until_the_answer() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: respond(build_answer(ONE_PHOTO_NEW_FILE_RESULT)) });
    await page.click(page.element("last-scan-rotate-button"));
    const status_after_the_first = read_panel(page).status;
    const second_answer = build_deferred_response();
    page.responses[ROTATE_KEY] = second_answer;
    await page.click(page.element("last-scan-rotate-button"));
    const status_while_the_second_is_pending = read_panel(page).status;
    second_answer.answer(respond(build_answer(ONE_PHOTO_NEW_FILE_RESULT)));
    await page.flush();
    return { status_after_the_first, status_while_the_second_is_pending, status_after_the_second: read_panel(page).status };
  },
  async rotate_refused() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: build_json_response(404, NO_LAST_SCAN_BODY) });
    const state_requests_before = page.count_requests("GET /api/state");
    await page.click(page.element("last-scan-rotate-button"));
    page.timers.run_pending_with_delay(0);
    await page.flush();
    return {
      banner_text: page.element("error-banner-text").textContent,
      panel: read_panel(page),
      extra_state_requests: page.count_requests("GET /api/state") - state_requests_before,
    };
  },
  async rotate_refused_for_another_reason() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: build_json_response(409, BUSY_BODY) });
    const state_requests_before = page.count_requests("GET /api/state");
    await page.click(page.element("last-scan-rotate-button"));
    page.timers.run_pending_with_delay(0);
    await page.flush();
    return { extra_state_requests: page.count_requests("GET /api/state") - state_requests_before };
  },
  async rotate_while_scanning() {
    const page = await load_quick_page(ONE_PHOTO_RESULT);
    await poll_quick_state(page, ONE_PHOTO_RESULT, { scan_phase: "scanning" });
    await page.click(page.element("last-scan-rotate-button"));
    return { panel: read_panel(page), edits: count_requests_of_the_edits(page) };
  },
  async scan_button_while_an_adjustment_runs() {
    const rotation_answer = build_deferred_response();
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: rotation_answer });
    await page.click(page.element("last-scan-rotate-button"));
    const disabled_during = page.element("scan-button").disabled;
    page.dispatch_key("keydown", { code: "Space", target: page.document.body, repeat: false });
    await page.flush();
    const scan_requests_during = page.count_requests(SCAN_KEY);
    rotation_answer.answer(respond(build_answer(ONE_PHOTO_NEW_FILE_RESULT)));
    await page.flush();
    return {
      disabled_during,
      scan_requests_during,
      disabled_after: page.element("scan-button").disabled,
    };
  },
  async rotation_message_goes_away_with_the_next_scan() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: respond(build_answer(ONE_PHOTO_NEW_FILE_RESULT)) });
    await page.click(page.element("last-scan-rotate-button"));
    await page.press_key("Space");
    return { status: read_panel(page).status };
  },
  async older_state_arriving_after_an_adjustment() {
    const turned_result = build_last_result({ file_names: [SECOND_FILE], rotation_degrees: 90, crops: [TURNED_CROP] });
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: respond(build_answer(turned_result)) });
    const old_state_answer = build_deferred_response();
    page.responses["GET /api/state"] = old_state_answer;
    page.timers.run_pending_with_delay(2000);
    await page.flush();
    await page.click(page.element("last-scan-rotate-button"));
    old_state_answer.answer(respond(build_quick_state(ONE_PHOTO_RESULT)));
    await page.flush();
    return read_panel(page);
  },
  async state_arriving_while_an_adjustment_runs() {
    const rotation_answer = build_deferred_response();
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: rotation_answer });
    await page.click(page.element("last-scan-rotate-button"));
    await poll_quick_state(page, ONE_PHOTO_RESULT, { last_result_revision: FIRST_REVISION + 1 });
    const panel = read_panel(page);
    rotation_answer.answer(respond(build_answer(ONE_PHOTO_NEW_FILE_RESULT)));
    await page.flush();
    return panel;
  },
  async enlarge_by_the_button() {
    const page = await load_quick_page(TWO_PHOTOS_RESULT);
    await open_the_dialog(page);
    return { dialog: read_dialog(page), focused_move_button: page.is_focused("frame-move-button") };
  },
  async enlarge_by_the_thumbnail() {
    const page = await load_quick_page(TWO_PHOTOS_RESULT);
    await page.click(page.element("last-scan-thumbnail-frame"));
    return { open: page.element("page-frame-dialog").open, title: page.element("page-frame-title").textContent };
  },
  async enlarge_a_scan_without_frames() {
    const page = await load_quick_page(ONE_FILE_RESULT);
    await open_the_dialog(page);
    return { dialog: read_dialog(page), focused_add_button: page.is_focused("frame-add-button") };
  },
  async enlarge_while_scanning() {
    const page = await load_quick_page(TWO_PHOTOS_RESULT);
    await poll_quick_state(page, TWO_PHOTOS_RESULT, { scan_phase: "scanning" });
    await page.click(page.element("last-scan-enlarge-button"));
    await page.click(page.element("last-scan-thumbnail-frame"));
    return { open: page.element("page-frame-dialog").open };
  },
  async enlarge_a_scan_whose_original_was_not_kept() {
    const page = await load_quick_page(build_last_result({ is_editable: false }));
    await page.click(page.element("last-scan-thumbnail-frame"));
    return { open: page.element("page-frame-dialog").open };
  },
  async apply_a_dragged_frame_of_one_file() {
    const applied_result = build_last_result({ file_names: [SECOND_FILE], crops: [rectangle_crop(0.15, 0.12, 0.8, 0.9)] });
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [CROPS_KEY]: respond(build_answer(applied_result)) });
    await open_the_dialog(page);
    await drag_the_first_corner(page);
    await page.click(page.element("frame-apply-button"));
    return {
      body: page.find_request(CROPS_KEY).body,
      headers: page.find_request(CROPS_KEY).headers,
      open: page.element("page-frame-dialog").open,
      panel: read_panel(page),
      scan_button_focused: page.is_focused("scan-button"),
    };
  },
  async apply_after_opening_by_keyboard() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [CROPS_KEY]: respond(build_answer(ONE_PHOTO_RESULT)) });
    page.element("last-scan-enlarge-button").focus();
    await page.press_key("Enter");
    page.dispatch_simple_event(page.element("frame-image"), "load");
    await drag_the_first_corner(page);
    await page.click(page.element("frame-apply-button"));
    return { enlarge_button_focused: page.is_focused("last-scan-enlarge-button") };
  },
  async apply_a_second_frame_that_writes_two_new_files() {
    const applied_result = build_last_result({ file_names: [NEW_PAIR_FIRST_FILE, NEW_PAIR_SECOND_FILE], crops: [WHOLE_CROP, LOWER_CROP] });
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [CROPS_KEY]: respond(build_answer(applied_result)) });
    await open_the_dialog(page);
    await page.click(page.element("frame-add-button"));
    await page.click(page.element("frame-apply-button"));
    return { body: page.find_request(CROPS_KEY).body, panel: read_panel(page) };
  },
  async apply_a_removed_frame_that_writes_one_new_file() {
    const applied_result = build_last_result({ file_names: [THIRD_FILE], crops: [UPPER_CROP] });
    const page = await load_quick_page(TWO_PHOTOS_RESULT, { [CROPS_KEY]: respond(build_answer(applied_result)) });
    await open_the_dialog(page);
    await page.click(page.element("frame-select-button"));
    await page.click(page.element("frame-remove-button"));
    await page.click(page.element("frame-apply-button"));
    return { body: page.find_request(CROPS_KEY).body, panel: read_panel(page) };
  },
  async apply_without_frames() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, {
      [CROPS_KEY]: respond(build_answer(build_last_result({ file_names: [SECOND_FILE] }))),
    });
    await open_the_dialog(page);
    await page.click(page.element("frame-clear-button"));
    await page.click(page.element("frame-apply-button"));
    return { body: page.find_request(CROPS_KEY).body, panel: read_panel(page) };
  },
  async apply_while_the_answer_is_pending() {
    const crops_answer = build_deferred_response();
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [CROPS_KEY]: crops_answer });
    await open_the_dialog(page);
    await drag_the_first_corner(page);
    await page.click(page.element("frame-apply-button"));
    const during = { dialog: read_dialog(page), panel: read_panel(page) };
    crops_answer.answer(respond(build_answer(ONE_PHOTO_RESULT)));
    await page.flush();
    return during;
  },
  async apply_refused() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [CROPS_KEY]: build_json_response(422, INVALID_CROP_BODY) });
    await open_the_dialog(page);
    await drag_the_first_corner(page);
    await page.click(page.element("frame-apply-button"));
    return {
      dialog: read_dialog(page),
      panel: read_panel(page),
      banner_text: page.element("error-banner-text").textContent,
    };
  },
  async apply_when_the_scan_was_replaced() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [CROPS_KEY]: build_json_response(409, SCAN_REPLACED_BODY) });
    const state_requests_before = page.count_requests("GET /api/state");
    await open_the_dialog(page);
    await drag_the_first_corner(page);
    await page.click(page.element("frame-apply-button"));
    page.timers.run_pending_with_delay(0);
    await page.flush();
    return {
      open: page.element("page-frame-dialog").open,
      banner_text: page.element("error-banner-text").textContent,
      extra_state_requests: page.count_requests("GET /api/state") - state_requests_before,
    };
  },
  async detect_that_finds_two_photos() {
    const detected_result = build_last_result({ file_names: [NEW_PAIR_FIRST_FILE, NEW_PAIR_SECOND_FILE], crops: [UPPER_CROP, LOWER_CROP] });
    const page = await load_quick_page(ONE_FILE_RESULT, {
      [DETECT_KEY]: respond(
        build_answer(detected_result, { crops_detected: true, ignored_region_count: 0 }),
      ),
    });
    await open_the_dialog(page);
    await page.click(page.element("frame-detect-button"));
    return { dialog: read_dialog(page), panel: read_panel(page), headers: page.find_request(DETECT_KEY).headers };
  },
  async detect_that_finds_nothing() {
    const page = await load_quick_page(ONE_PHOTO_RESULT, {
      [DETECT_KEY]: respond(build_answer(ONE_PHOTO_RESULT, { crops_detected: false, ignored_region_count: 0 })),
    });
    await open_the_dialog(page);
    await drag_the_first_corner(page);
    await page.click(page.element("frame-detect-button"));
    return { dialog: read_dialog(page), panel: read_panel(page) };
  },
  async rotate_in_the_dialog() {
    const turned_result = build_last_result({ file_names: [SECOND_FILE], rotation_degrees: 90, crops: [TURNED_CROP] });
    const page = await load_quick_page(ONE_PHOTO_RESULT, { [ROTATE_KEY]: respond(build_answer(turned_result)) });
    await open_the_dialog(page);
    await page.click(page.element("frame-rotate-button"));
    return { dialog: read_dialog(page), panel: read_panel(page) };
  },
  async cancel_after_a_drag() {
    const page = await load_quick_page(ONE_PHOTO_RESULT);
    await open_the_dialog(page);
    await drag_the_first_corner(page);
    await page.click(page.element("frame-cancel-button"));
    return {
      open: page.element("page-frame-dialog").open,
      edits: count_requests_of_the_edits(page),
      panel: read_panel(page),
      scan_button_focused: page.is_focused("scan-button"),
    };
  },
  async cancel_after_opening_by_keyboard() {
    const page = await load_quick_page(ONE_PHOTO_RESULT);
    page.element("last-scan-enlarge-button").focus();
    await page.press_key("Enter");
    await page.click(page.element("frame-cancel-button"));
    return { enlarge_button_focused: page.is_focused("last-scan-enlarge-button") };
  },
  async scan_replaced_while_the_dialog_is_open() {
    const page = await load_quick_page(TWO_PHOTOS_RESULT);
    await open_the_dialog(page);
    const next_result = build_last_result({ scan_identifier: OTHER_SCAN_IDENTIFIER });
    await poll_quick_state(page, next_result, { last_result_revision: FIRST_REVISION + 1 });
    return { open: page.element("page-frame-dialog").open, panel: read_panel(page) };
  },
  async frames_changed_elsewhere_while_the_dialog_is_open() {
    const page = await load_quick_page(ONE_PHOTO_RESULT);
    await open_the_dialog(page);
    const changed_result = build_last_result({ file_names: [PAIR_FIRST_FILE, PAIR_SECOND_FILE], crops: [DETECTED_CROP, LOWER_CROP] });
    await poll_quick_state(page, changed_result, { last_result_revision: FIRST_REVISION + 1 });
    return read_dialog(page);
  },
  async rotated_elsewhere_while_the_dialog_is_open() {
    const page = await load_quick_page(ONE_PHOTO_RESULT);
    await open_the_dialog(page);
    const turned_result = build_last_result({ file_names: [SECOND_FILE], rotation_degrees: 90, crops: [TURNED_CROP] });
    await poll_quick_state(page, turned_result, { last_result_revision: FIRST_REVISION + 1 });
    return read_dialog(page);
  },
  async dialog_buttons_while_scanning_elsewhere() {
    const page = await load_quick_page(ONE_PHOTO_RESULT);
    await open_the_dialog(page);
    await drag_the_first_corner(page);
    await poll_quick_state(page, ONE_PHOTO_RESULT, { scan_phase: "scanning" });
    return read_dialog(page).disabled;
  },
  async space_in_the_dialog_never_scans() {
    const page = await load_quick_page(ONE_PHOTO_RESULT);
    await open_the_dialog(page);
    page.element("frame-edge-left").focus();
    await page.press_key("Space");
    return { scan_requests: page.count_requests(SCAN_KEY), edits: count_requests_of_the_edits(page) };
  },
};

async function main() {
  const results = {};
  for (const scenario_name of process.argv.slice(2)) {
    results[scenario_name] = await SCENARIOS[scenario_name]();
  }
  process.stdout.write(JSON.stringify(results));
}

main().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exitCode = 1;
});
