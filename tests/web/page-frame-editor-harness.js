"use strict";

// Plays the scenarios of the enlarged view of a page (the crop frame dialog) named on the command line against the
// real static scripts in the fake browser and prints one JSON object with what the page did in each.
// tests/web/test_page_frame_editor_behaviour.py asserts on it. The fixtures come from document-page-fixtures.js.

const { build_deferred_response, build_event, build_json_response } = require("./fake-browser.js");
const {
  FIRST_PAGE,
  SECOND_PAGE,
  THIRD_PAGE,
  FOURTH_PAGE,
  THREE_PAGES,
  FOUR_PAGES,
  DAMAGED_PAGE_BODY,
  INVALID_CROP_BODY,
  SCAN_ALREADY_RUNNING_BODY,
  build_document_body,
  build_state,
  respond,
  load_page,
} = require("./document-page-fixtures.js");

const STAGE_BOX = Object.freeze({ left: 0, top: 0, width: 500, height: 400 });
const SECOND_PAGE_CROP = Object.freeze({ left: 0.13, top: 0.115, right: 0.914, bottom: 0.915 });
const WEST_DRAGGED_CROP = Object.freeze({ left: 0.23, top: 0.115, right: 0.914, bottom: 0.915 });
const TURNED_SECOND_PAGE_CROP = Object.freeze({ left: 0.085, top: 0.13, right: 0.885, bottom: 0.914 });
const DETECTED_CROP = Object.freeze({ left: 0.12, top: 0.11, right: 0.92, bottom: 0.93 });
const CENTER_OF_THE_STAGE = Object.freeze({ x: 250, y: 200 });
const FRAMED_SECOND_PAGE = { [SECOND_PAGE]: { rotation_degrees: 0, crop: SECOND_PAGE_CROP } };
const PUT_CROP_KEY = `PUT /api/document/pages/${SECOND_PAGE}/crop`;
const DETECT_KEY = `POST /api/document/pages/${SECOND_PAGE}/crop/detect`;
const ROTATION_KEY = `POST /api/document/pages/${SECOND_PAGE}/rotation`;
const FIRST_PAGE_DETECT_KEY = `POST /api/document/pages/${FIRST_PAGE}/crop/detect`;
const HANDLE_IDENTIFIERS = [
  "frame-handle-north",
  "frame-handle-north-east",
  "frame-handle-east",
  "frame-handle-south-east",
  "frame-handle-south",
  "frame-handle-south-west",
  "frame-handle-west",
  "frame-handle-north-west",
];

function build_body(body_parts) {
  return build_document_body({ page_identifiers: THREE_PAGES, ...body_parts });
}

function respond_with_the_framed_second_page() {
  return { "GET /api/document": respond(build_body({ revision: 1, framings: FRAMED_SECOND_PAGE })) };
}

function build_framings(rotation_degrees, crop) {
  return { [SECOND_PAGE]: { rotation_degrees, crop } };
}

function read_style(element) {
  return { left: element.style.left, top: element.style.top, width: element.style.width, height: element.style.height };
}

function read_dialog(page) {
  return {
    open: page.element("page-frame-dialog").open,
    title: page.element("page-frame-title").textContent,
    status: page.element("frame-status").textContent,
    image_source: page.element("frame-image").src,
    image_alt: page.element("frame-image").alt,
    stage_loading: page.element("frame-stage").classList.contains("is-loading"),
    frame_box: read_style(page.element("frame-box")),
    cutout: read_style(page.element("frame-cutout")),
    apply_disabled: page.element("frame-apply-button").disabled,
    detect_disabled: page.element("frame-detect-button").disabled,
    rotate_disabled: page.element("frame-rotate-button").disabled,
    clear_disabled: page.element("frame-clear-button").disabled,
  };
}

function announcement(page) {
  return page.element("document-announcement").textContent;
}

async function open_second_page(page) {
  await page.click(page.tile_button(2, "enlarge"));
  page.element("frame-stage").box = STAGE_BOX;
  const image = page.element("frame-image");
  page.dispatch_simple_event(image, "load");
}

async function open_second_page_by_keyboard(page) {
  await page.press_with_keyboard(page.tile_button(2, "enlarge"));
  page.element("frame-stage").box = STAGE_BOX;
  page.dispatch_simple_event(page.element("frame-image"), "load");
}

async function load_framed_page(response_overrides) {
  return load_page({ ...respond_with_the_framed_second_page(), ...response_overrides });
}

async function open_framed_second_page(response_overrides) {
  const page = await load_framed_page(response_overrides);
  await open_second_page(page);
  return page;
}

async function drag_handle(page, handle_identifier) {
  // 50 pixels to the right of a stage that is 500 pixels wide: a tenth of the page.
  const start = CENTER_OF_THE_STAGE;
  const end = { x: start.x + 50, y: start.y };
  await page.drag_pointer(page.element(handle_identifier), { from: start, to: end });
}

async function poll_document(page, body) {
  page.responses["GET /api/document"] = respond(body);
  await page.poll(build_state({ revision: body.revision, page_count: body.document === null ? 0 : body.document.page_count }));
}

function collect_focusable_identifiers(page) {
  const identifiers_by_element = new Map([...page.document.elements].map(([identifier, element]) => [element, identifier]));
  const collected = [];
  const visit = (element) => {
    if (element.tagName === "BUTTON") {
      collected.push(identifiers_by_element.get(element));
    }
    element.children.forEach(visit);
  };
  visit(page.element("page-frame-dialog"));
  return collected;
}

const SCENARIOS = {
  async open_by_the_enlarge_button() {
    const page = await open_framed_second_page({});
    return {
      dialog: read_dialog(page),
      focused_move_button: page.is_focused("frame-move-button"),
      handle_labels: HANDLE_IDENTIFIERS.map((identifier) => page.element(identifier).getAttribute("aria-label")),
    };
  },
  async open_by_the_thumbnail() {
    const page = await load_framed_page({});
    await page.click(page.tile_at(2).children[0]);
    return { open: page.element("page-frame-dialog").open, title: page.element("page-frame-title").textContent };
  },
  async open_a_page_without_a_crop() {
    const page = await load_framed_page({});
    await page.click(page.tile_button(1, "enlarge"));
    return read_dialog(page);
  },
  async open_a_turned_page() {
    const page = await load_page({
      "GET /api/document": respond(build_body({ revision: 1, framings: build_framings(270, SECOND_PAGE_CROP) })),
    });
    await page.click(page.tile_button(2, "enlarge"));
    return read_dialog(page);
  },
  async stage_while_the_image_loads() {
    const page = await load_framed_page({});
    await page.click(page.tile_button(2, "enlarge"));
    const while_loading = page.element("frame-stage").classList.contains("is-loading");
    page.dispatch_simple_event(page.element("frame-image"), "load");
    return { while_loading, after_loading: page.element("frame-stage").classList.contains("is-loading") };
  },
  async image_that_fails_to_load() {
    const page = await load_framed_page({});
    await page.click(page.tile_button(2, "enlarge"));
    page.dispatch_simple_event(page.element("frame-image"), "error");
    return { status: page.element("frame-status").textContent, open: page.element("page-frame-dialog").open };
  },
  async open_while_a_page_scans() {
    const page = await load_framed_page({});
    await page.poll(build_state({ revision: 1, page_count: 3, scans_completed: 3, scan_phase: "scanning" }));
    await open_second_page(page);
    return read_dialog(page);
  },
  async tab_order_of_the_dialog() {
    const page = await load_framed_page({});
    return { identifiers: collect_focusable_identifiers(page) };
  },
  async drag_the_west_handle() {
    const page = await open_framed_second_page({});
    const west_handle = page.element("frame-handle-west");
    page.dispatch_pointer(west_handle, "pointerdown", CENTER_OF_THE_STAGE);
    const captured_while_dragging = west_handle.hasPointerCapture(1);
    page.dispatch_pointer(west_handle, "pointermove", { x: 300, y: 200 });
    const during = read_dialog(page);
    page.dispatch_pointer(west_handle, "pointerup", { x: 300, y: 200 });
    return {
      captured_while_dragging,
      released_after: !west_handle.hasPointerCapture(1),
      during,
      after: read_dialog(page),
    };
  },
  async drag_a_corner() {
    const page = await open_framed_second_page({});
    await page.drag_pointer(page.element("frame-handle-north-west"), {
      from: CENTER_OF_THE_STAGE,
      to: { x: 300, y: 240 },
    });
    return read_dialog(page);
  },
  async drag_the_whole_frame() {
    const page = await open_framed_second_page({});
    await page.drag_pointer(page.element("frame-move-button"), { from: CENTER_OF_THE_STAGE, to: { x: 275, y: 220 } });
    return read_dialog(page);
  },
  async drag_is_measured_from_where_it_began() {
    const page = await open_framed_second_page({});
    const west_handle = page.element("frame-handle-west");
    page.dispatch_pointer(west_handle, "pointerdown", CENTER_OF_THE_STAGE);
    page.dispatch_pointer(west_handle, "pointermove", { x: 5000, y: 200 });
    page.dispatch_pointer(west_handle, "pointermove", { x: 300, y: 200 });
    page.dispatch_pointer(west_handle, "pointerup", { x: 300, y: 200 });
    return read_dialog(page);
  },
  async drag_past_the_page() {
    const page = await open_framed_second_page({});
    await page.drag_pointer(page.element("frame-handle-west"), { from: CENTER_OF_THE_STAGE, to: { x: 5000, y: 200 } });
    return read_dialog(page);
  },
  async cancelled_drag() {
    const page = await open_framed_second_page({});
    const west_handle = page.element("frame-handle-west");
    page.dispatch_pointer(west_handle, "pointerdown", CENTER_OF_THE_STAGE);
    page.dispatch_pointer(west_handle, "pointermove", { x: 300, y: 200 });
    page.dispatch_pointer(west_handle, "pointercancel", { x: 300, y: 200 });
    page.dispatch_pointer(west_handle, "pointermove", { x: 450, y: 200 });
    return { released: !west_handle.hasPointerCapture(1), dialog: read_dialog(page) };
  },
  async drag_with_the_secondary_button() {
    const page = await open_framed_second_page({});
    const west_handle = page.element("frame-handle-west");
    page.dispatch_pointer(west_handle, "pointerdown", { ...CENTER_OF_THE_STAGE, button: 2 });
    const captured = west_handle.hasPointerCapture(1);
    page.dispatch_pointer(west_handle, "pointermove", { x: 300, y: 200 });
    return { captured, dialog: read_dialog(page) };
  },
  async drag_with_the_middle_button_on_the_move_area() {
    const page = await open_framed_second_page({});
    const move_button = page.element("frame-move-button");
    page.dispatch_pointer(move_button, "pointerdown", { ...CENTER_OF_THE_STAGE, button: 1 });
    page.dispatch_pointer(move_button, "pointermove", { x: 300, y: 260 });
    return read_dialog(page);
  },
  async context_menu_on_the_stage() {
    const page = await open_framed_second_page({});
    const menu_request = build_event("contextmenu", {});
    page.document.dispatch(page.element("frame-stage"), menu_request);
    return { prevented: menu_request.defaultPrevented };
  },
  async move_without_pressing() {
    const page = await open_framed_second_page({});
    page.dispatch_pointer(page.element("frame-handle-west"), "pointermove", { x: 300, y: 200 });
    return read_dialog(page);
  },
  async arrow_on_the_left_edge() {
    const page = await open_framed_second_page({});
    page.element("frame-handle-west").focus();
    const key_event = await page.key_down("ArrowRight");
    return { dialog: read_dialog(page), default_prevented: key_event.defaultPrevented };
  },
  async shift_arrow_on_the_left_edge() {
    const page = await open_framed_second_page({});
    page.element("frame-handle-west").focus();
    await page.key_down_with_shift("ArrowLeft");
    return read_dialog(page);
  },
  async arrow_on_a_corner() {
    const page = await open_framed_second_page({});
    page.element("frame-handle-south-east").focus();
    await page.key_down_with_shift("ArrowLeft");
    await page.key_down_with_shift("ArrowUp");
    return read_dialog(page);
  },
  async arrow_on_the_move_button() {
    const page = await open_framed_second_page({});
    await page.key_down_with_shift("ArrowLeft");
    return read_dialog(page);
  },
  async other_key_on_a_handle() {
    const page = await open_framed_second_page({});
    page.element("frame-handle-west").focus();
    const key_event = await page.key_down("KeyA");
    return { default_prevented: key_event.defaultPrevented, dialog: read_dialog(page) };
  },
  async no_crop_button() {
    const page = await open_framed_second_page({});
    await page.click(page.element("frame-clear-button"));
    return read_dialog(page);
  },
  async no_crop_button_on_a_page_without_a_crop() {
    const page = await load_framed_page({});
    await page.click(page.tile_button(1, "enlarge"));
    await page.click(page.element("frame-clear-button"));
    return read_dialog(page);
  },
  async apply_a_dragged_frame() {
    const page = await open_framed_second_page({
      [PUT_CROP_KEY]: respond(build_body({ revision: 2, framings: build_framings(0, WEST_DRAGGED_CROP) })),
    });
    await drag_handle(page, "frame-handle-west");
    await page.click(page.element("frame-apply-button"));
    return {
      requests: page.count_requests(PUT_CROP_KEY),
      body: page.find_request(PUT_CROP_KEY).body,
      headers: page.find_request(PUT_CROP_KEY).headers,
      open: page.element("page-frame-dialog").open,
      announcement: announcement(page),
      scan_button_focused: page.is_focused("scan-button"),
      tile_overlay: read_style(page.tile_overlay(2)),
    };
  },
  async apply_after_opening_by_keyboard() {
    const page = await load_framed_page({
      [PUT_CROP_KEY]: respond(build_body({ revision: 2, framings: build_framings(0, WEST_DRAGGED_CROP) })),
    });
    await open_second_page_by_keyboard(page);
    await drag_handle(page, "frame-handle-west");
    await page.click(page.element("frame-apply-button"));
    return { focus: page.describe_focus() };
  },
  async apply_without_a_crop() {
    const page = await open_framed_second_page({
      [PUT_CROP_KEY]: respond(build_body({ revision: 2 })),
    });
    await page.click(page.element("frame-clear-button"));
    await page.click(page.element("frame-apply-button"));
    return {
      body: page.find_request(PUT_CROP_KEY).body,
      announcement: announcement(page),
      overlay_hidden: page.tile_overlay(2).hidden,
    };
  },
  async apply_with_nothing_changed() {
    const page = await open_framed_second_page({});
    const apply_disabled = page.element("frame-apply-button").disabled;
    await page.click(page.element("frame-apply-button"));
    return { apply_disabled, requests: page.count_requests(PUT_CROP_KEY), open: page.element("page-frame-dialog").open };
  },
  async apply_enabled_after_a_change() {
    const page = await open_framed_second_page({});
    await drag_handle(page, "frame-handle-west");
    return { apply_disabled: page.element("frame-apply-button").disabled };
  },
  async apply_refused() {
    const page = await open_framed_second_page({ [PUT_CROP_KEY]: build_json_response(422, INVALID_CROP_BODY) });
    await drag_handle(page, "frame-handle-west");
    await page.click(page.element("frame-apply-button"));
    return {
      dialog: read_dialog(page),
      banner: page.banner(),
      apply_focused: page.is_focused("frame-apply-button"),
    };
  },
  async apply_while_a_page_scans() {
    const page = await open_framed_second_page({});
    await drag_handle(page, "frame-handle-west");
    await page.poll(build_state({ revision: 1, page_count: 3, scans_completed: 3, scan_phase: "scanning" }));
    const disabled_while_scanning = page.element("frame-apply-button").disabled;
    await page.click(page.element("frame-apply-button"));
    return { disabled_while_scanning, requests: page.count_requests(PUT_CROP_KEY) };
  },
  async apply_conflict() {
    const page = await open_framed_second_page({ [PUT_CROP_KEY]: build_json_response(409, SCAN_ALREADY_RUNNING_BODY) });
    await drag_handle(page, "frame-handle-west");
    await page.click(page.element("frame-apply-button"));
    return { open: page.element("page-frame-dialog").open, status: page.element("frame-status").textContent };
  },
  async apply_with_space_on_the_button() {
    const page = await open_framed_second_page({
      [PUT_CROP_KEY]: respond(build_body({ revision: 2, framings: build_framings(0, WEST_DRAGGED_CROP) })),
    });
    await drag_handle(page, "frame-handle-west");
    page.element("frame-apply-button").focus();
    await page.press_key("Space");
    return {
      crop_requests: page.count_requests(PUT_CROP_KEY),
      page_requests: page.count_requests("POST /api/document/pages"),
      open: page.element("page-frame-dialog").open,
    };
  },
  async detect_that_finds_a_frame() {
    const page = await open_framed_second_page({
      [DETECT_KEY]: respond({
        ...build_body({ revision: 2, framings: build_framings(0, DETECTED_CROP) }),
        crop_detected: true,
      }),
    });
    await drag_handle(page, "frame-handle-west");
    await page.click(page.element("frame-detect-button"));
    return {
      dialog: read_dialog(page),
      headers: page.find_request(DETECT_KEY).headers,
      detect_focused: page.is_focused("frame-detect-button"),
      tile_overlay: read_style(page.tile_overlay(2)),
    };
  },
  async detect_that_finds_nothing() {
    const page = await open_framed_second_page({
      [DETECT_KEY]: respond({ ...build_body({ revision: 1, framings: FRAMED_SECOND_PAGE }), crop_detected: false }),
    });
    await drag_handle(page, "frame-handle-west");
    await page.click(page.element("frame-detect-button"));
    return read_dialog(page);
  },
  async detect_on_a_damaged_page() {
    const page = await open_framed_second_page({ [DETECT_KEY]: build_json_response(409, DAMAGED_PAGE_BODY) });
    await page.click(page.element("frame-detect-button"));
    return { dialog: read_dialog(page), banner: page.banner() };
  },
  async detect_while_a_page_scans() {
    const page = await open_framed_second_page({});
    await page.poll(build_state({ revision: 1, page_count: 3, scans_completed: 3, scan_phase: "scanning" }));
    const disabled_while_scanning = page.element("frame-detect-button").disabled;
    await page.click(page.element("frame-detect-button"));
    return { disabled_while_scanning, requests: page.count_requests(DETECT_KEY) };
  },
  async detect_on_a_page_without_a_frame() {
    const page = await load_framed_page({
      [FIRST_PAGE_DETECT_KEY]: respond({
        ...build_body({ revision: 2, framings: { [FIRST_PAGE]: { rotation_degrees: 0, crop: DETECTED_CROP } } }),
        crop_detected: true,
      }),
    });
    await page.click(page.tile_button(1, "enlarge"));
    await page.click(page.element("frame-detect-button"));
    return { dialog: read_dialog(page), tile_overlay: read_style(page.tile_overlay(1)) };
  },
  async rotate_in_the_dialog() {
    const page = await open_framed_second_page({
      [ROTATION_KEY]: respond(build_body({ revision: 2, framings: build_framings(90, TURNED_SECOND_PAGE_CROP) })),
    });
    await page.click(page.element("frame-rotate-button"));
    const right_after = read_dialog(page);
    page.dispatch_simple_event(page.element("frame-image"), "load");
    return {
      right_after,
      after_loading: read_dialog(page),
      headers: page.find_request(ROTATION_KEY).headers,
      rotate_focused: page.is_focused("frame-rotate-button"),
      tile_thumbnail: page.tile_thumbnail(2).src,
    };
  },
  async rotate_with_a_draft_in_the_dialog() {
    const page = await open_framed_second_page({
      [ROTATION_KEY]: respond(build_body({ revision: 2, framings: build_framings(90, TURNED_SECOND_PAGE_CROP) })),
    });
    await drag_handle(page, "frame-handle-west");
    await page.click(page.element("frame-rotate-button"));
    return read_dialog(page);
  },
  async rotate_a_page_without_a_frame_in_the_dialog() {
    const page = await load_framed_page({
      [`POST /api/document/pages/${FIRST_PAGE}/rotation`]: respond(
        build_body({ revision: 2, framings: { [FIRST_PAGE]: { rotation_degrees: 90, crop: null } } }),
      ),
    });
    await page.click(page.tile_button(1, "enlarge"));
    await page.click(page.element("frame-rotate-button"));
    return read_dialog(page);
  },
  async rotate_while_the_request_is_pending() {
    const rotation_answer = build_deferred_response();
    const page = await open_framed_second_page({ [ROTATION_KEY]: rotation_answer });
    await page.click(page.element("frame-rotate-button"));
    const during = read_dialog(page);
    rotation_answer.answer(
      respond(build_body({ revision: 2, framings: build_framings(90, TURNED_SECOND_PAGE_CROP) })),
    );
    await page.flush();
    return { during, after: read_dialog(page) };
  },
  async cancel_after_a_drag() {
    const page = await open_framed_second_page({});
    await drag_handle(page, "frame-handle-west");
    await page.click(page.element("frame-cancel-button"));
    return {
      open: page.element("page-frame-dialog").open,
      announcement: announcement(page),
      crop_requests: page.count_requests(PUT_CROP_KEY),
      scan_button_focused: page.is_focused("scan-button"),
    };
  },
  async cancel_without_changes() {
    const page = await open_framed_second_page({});
    await page.click(page.element("frame-cancel-button"));
    return { open: page.element("page-frame-dialog").open, announcement: announcement(page) };
  },
  async cancel_after_opening_by_keyboard() {
    const page = await load_framed_page({});
    await open_second_page_by_keyboard(page);
    await page.click(page.element("frame-cancel-button"));
    return { focus: page.describe_focus() };
  },
  async escape_after_a_drag() {
    const page = await open_framed_second_page({});
    await drag_handle(page, "frame-handle-west");
    await page.key_down("Escape");
    return {
      open: page.element("page-frame-dialog").open,
      announcement: announcement(page),
      scan_button_focused: page.is_focused("scan-button"),
    };
  },
  async reopen_after_a_discarded_drag() {
    const page = await open_framed_second_page({});
    await drag_handle(page, "frame-handle-west");
    await page.click(page.element("frame-cancel-button"));
    await page.click(page.tile_button(2, "enlarge"));
    return read_dialog(page);
  },
  async open_twice() {
    const page = await open_framed_second_page({});
    await page.click(page.tile_button(2, "enlarge"));
    return { show_count: page.element("page-frame-dialog").show_count };
  },
  async page_deleted_elsewhere() {
    const page = await open_framed_second_page({});
    await poll_document(page, build_body({ revision: 2, page_identifiers: [FIRST_PAGE, THIRD_PAGE] }));
    return {
      open: page.element("page-frame-dialog").open,
      announcement: announcement(page),
      scan_button_focused: page.is_focused("scan-button"),
    };
  },
  async document_finished_elsewhere() {
    const page = await open_framed_second_page({});
    await poll_document(page, build_body({ revision: 2, page_identifiers: [] }));
    return { open: page.element("page-frame-dialog").open, announcement: announcement(page) };
  },
  async page_added_while_open() {
    const page = await open_framed_second_page({});
    await poll_document(page, build_body({ revision: 2, page_identifiers: FOUR_PAGES, framings: FRAMED_SECOND_PAGE }));
    return read_dialog(page);
  },
  async page_inserted_before_while_open() {
    const page = await open_framed_second_page({});
    await poll_document(
      page,
      build_body({
        revision: 2,
        page_identifiers: [FOURTH_PAGE, FIRST_PAGE, SECOND_PAGE, THIRD_PAGE],
        framings: FRAMED_SECOND_PAGE,
      }),
    );
    return read_dialog(page);
  },
  async crop_changed_elsewhere() {
    const page = await open_framed_second_page({});
    await poll_document(page, build_body({ revision: 2, framings: build_framings(0, DETECTED_CROP) }));
    return read_dialog(page);
  },
  async crop_changed_elsewhere_with_a_draft() {
    const page = await open_framed_second_page({});
    await drag_handle(page, "frame-handle-west");
    await poll_document(page, build_body({ revision: 2, framings: build_framings(0, DETECTED_CROP) }));
    return read_dialog(page);
  },
  async rotated_elsewhere_with_a_draft() {
    const page = await open_framed_second_page({});
    await drag_handle(page, "frame-handle-west");
    await poll_document(page, build_body({ revision: 2, framings: build_framings(90, TURNED_SECOND_PAGE_CROP) }));
    return read_dialog(page);
  },
  async space_on_a_handle() {
    const page = await open_framed_second_page({});
    page.element("frame-handle-west").focus();
    await page.press_key("Space");
    return { page_requests: page.count_requests("POST /api/document/pages"), scan_requests: page.count_requests("POST /api/scans") };
  },
  async space_on_the_dialog_itself() {
    const page = await open_framed_second_page({});
    const dialog = page.element("page-frame-dialog");
    const key_down = page.dispatch_key("keydown", { code: "Space", target: dialog, repeat: false });
    const key_up = page.dispatch_key("keyup", { code: "Space", target: dialog, repeat: false });
    await page.flush();
    return {
      page_requests: page.count_requests("POST /api/document/pages"),
      key_down_default_prevented: key_down.defaultPrevented,
      key_up_default_prevented: key_up.defaultPrevented,
    };
  },
  async backspace_in_the_dialog() {
    const page = await open_framed_second_page({});
    await page.press_key("Backspace");
    const dialog = page.element("page-frame-dialog");
    page.dispatch_key("keydown", { code: "Backspace", target: dialog, repeat: false });
    await page.flush();
    return { discard_requests: page.count_requests("DELETE /api/document/pages/last") };
  },
  async enter_in_the_dialog() {
    const page = await open_framed_second_page({});
    page.element("frame-handle-west").focus();
    await page.press_key("Enter");
    const dialog = page.element("page-frame-dialog");
    page.dispatch_key("keydown", { code: "Enter", target: dialog, repeat: false });
    await page.flush();
    return {
      confirmation_shown: page.element("confirmation-dialog").show_count,
      finalize_requests: page.count_requests("POST /api/document/finalize"),
    };
  },
  async arrows_do_not_reach_the_page_shortcuts() {
    const page = await open_framed_second_page({});
    await page.key_down("ArrowLeft");
    return { requests: page.requests.filter((request) => request.key.startsWith("POST") || request.key.startsWith("DELETE")).length };
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
