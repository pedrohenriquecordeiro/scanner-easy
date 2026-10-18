"use strict";

// Plays the scenarios of the enlarged view of a page of the Documento mode (the frame dialog) named on the command
// line against the real static scripts in the fake browser and prints one JSON object with what the page did in each.
// tests/web/test_page_frame_editor_*.py assert on it. The fixtures come from document-page-fixtures.js. The same dialog
// serves the quick mode: tests/web/last-scan-harness.js plays that side.

const { build_deferred_response, build_event, build_json_response } = require("./fake-browser.js");
const { read_dialog } = require("./frame-dialog-reader.js");
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
  rectangle_crop,
  quadrilateral_crop,
  read_overlay,
  build_document_body,
  build_state,
  respond,
  load_page,
} = require("./document-page-fixtures.js");

const STAGE_BOX = Object.freeze({ left: 0, top: 0, width: 500, height: 400 });
const SECOND_PAGE_CROP = rectangle_crop(0.13, 0.115, 0.914, 0.915);
const WEST_DRAGGED_CROP = rectangle_crop(0.23, 0.115, 0.914, 0.915);
const TURNED_SECOND_PAGE_CROP = rectangle_crop(0.085, 0.13, 0.885, 0.914);
const DETECTED_CROP = rectangle_crop(0.12, 0.11, 0.92, 0.93);
const UPPER_CROP = rectangle_crop(0.05, 0.02, 0.9, 0.55);
const LOWER_CROP = rectangle_crop(0.05, 0.6, 0.9, 0.95);
const LEFT_CROP = rectangle_crop(0.05, 0.1, 0.45, 0.9);
const TILTED_CROP = quadrilateral_crop([
  [0.4, 0.55],
  [0.93, 0.44],
  [0.97, 0.8],
  [0.44, 0.91],
]);
const CENTER_OF_THE_STAGE = Object.freeze({ x: 250, y: 200 });
const FRAMED_SECOND_PAGE = { [SECOND_PAGE]: { rotation_degrees: 0, crops: [SECOND_PAGE_CROP] } };
const TWO_FRAMES_ON_THE_SECOND_PAGE = { [SECOND_PAGE]: { rotation_degrees: 0, crops: [UPPER_CROP, LOWER_CROP] } };
const SIDE_BY_SIDE_FRAMES = {
  [SECOND_PAGE]: { rotation_degrees: 0, crops: [rectangle_crop(0.1, 0.1, 0.4, 0.9), rectangle_crop(0.5, 0.1, 0.9, 0.9)] },
};
const PUT_CROPS_KEY = `PUT /api/document/pages/${SECOND_PAGE}/crops`;
const DETECT_KEY = `POST /api/document/pages/${SECOND_PAGE}/crops/detect`;
const ROTATION_KEY = `POST /api/document/pages/${SECOND_PAGE}/rotation`;
const FIRST_PAGE_DETECT_KEY = `POST /api/document/pages/${FIRST_PAGE}/crops/detect`;
function build_body(body_parts) {
  return build_document_body({ page_identifiers: THREE_PAGES, ...body_parts });
}

function respond_with_the_framed_second_page() {
  return { "GET /api/document": respond(build_body({ revision: 1, framings: FRAMED_SECOND_PAGE })) };
}

function build_framings(rotation_degrees, crops) {
  return { [SECOND_PAGE]: { rotation_degrees, crops } };
}

function announcement(page) {
  return page.element("document-announcement").textContent;
}

function size_the_stage(page) {
  page.element("frame-stage").box = STAGE_BOX;
  page.dispatch_simple_event(page.element("frame-image"), "load");
}

async function open_second_page(page) {
  page.element("frame-stage").box = STAGE_BOX;
  await page.click(page.tile_button(2, "enlarge"));
  size_the_stage(page);
}

async function open_second_page_by_keyboard(page) {
  page.element("frame-stage").box = STAGE_BOX;
  await page.press_with_keyboard(page.tile_button(2, "enlarge"));
  size_the_stage(page);
}

async function load_framed_page(response_overrides) {
  return load_page({ ...respond_with_the_framed_second_page(), ...response_overrides });
}

async function open_framed_second_page(response_overrides) {
  const page = await load_framed_page(response_overrides);
  await open_second_page(page);
  return page;
}

async function open_second_page_with_two_frames(response_overrides) {
  const page = await load_page({
    "GET /api/document": respond(build_body({ revision: 1, framings: TWO_FRAMES_ON_THE_SECOND_PAGE })),
    ...response_overrides,
  });
  await open_second_page(page);
  return page;
}

async function open_two_side_by_side_frames(response_overrides) {
  const page = await load_page({
    "GET /api/document": respond(build_body({ revision: 1, framings: SIDE_BY_SIDE_FRAMES })),
    ...response_overrides,
  });
  await open_second_page(page);
  return page;
}

async function drag_element(page, identifier, shift) {
  const start = CENTER_OF_THE_STAGE;
  await page.drag_pointer(page.element(identifier), { from: start, to: { x: start.x + shift.x, y: start.y + shift.y } });
}

async function drag_the_left_edge(page) {
  // 50 pixels to the right of a stage that is 500 pixels wide: a tenth of the page.
  await drag_element(page, "frame-edge-left", { x: 50, y: 0 });
}

async function poll_document(page, body) {
  page.responses["GET /api/document"] = respond(body);
  await page.poll(build_state({ revision: body.revision, page_count: body.document === null ? 0 : body.document.page_count }));
}

function collect_focusable_identifiers(page) {
  const identifiers_by_element = new Map([...page.document.elements].map(([identifier, element]) => [element, identifier]));
  const collected = [];
  const visit = (element) => {
    if (element.tagName === "BUTTON" && !element.hidden) {
      collected.push(identifiers_by_element.get(element));
    }
    element.children.forEach(visit);
  };
  visit(page.element("page-frame-dialog"));
  return collected;
}

function count_edits(page) {
  return page.requests.filter((request) => /^(POST|PUT|DELETE)/.test(request.key)).length;
}

const SCANNING_STATE = () => build_state({ revision: 1, page_count: 3, scans_completed: 3, scan_phase: "scanning" });

const SCENARIOS = {
  async open_by_the_enlarge_button() {
    const page = await open_framed_second_page({});
    return { dialog: read_dialog(page), focused_move_button: page.is_focused("frame-move-button") };
  },
  async open_by_the_thumbnail() {
    const page = await load_framed_page({});
    await page.click(page.tile_at(2).children[0]);
    return { open: page.element("page-frame-dialog").open, title: page.element("page-frame-title").textContent };
  },
  async open_a_page_without_a_frame() {
    const page = await load_framed_page({});
    await page.click(page.tile_button(1, "enlarge"));
    return { dialog: read_dialog(page), focused_add_button: page.is_focused("frame-add-button") };
  },
  async open_a_page_with_two_frames() {
    const page = await open_second_page_with_two_frames({});
    return { dialog: read_dialog(page), focused_move_button: page.is_focused("frame-move-button") };
  },
  async open_a_tilted_frame() {
    const page = await load_page({
      "GET /api/document": respond(build_body({ revision: 1, framings: build_framings(0, [TILTED_CROP]) })),
    });
    await open_second_page(page);
    return read_dialog(page);
  },
  async open_a_turned_page() {
    const page = await load_page({
      "GET /api/document": respond(build_body({ revision: 1, framings: build_framings(270, [SECOND_PAGE_CROP]) })),
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
    await page.poll(SCANNING_STATE());
    await open_second_page(page);
    return read_dialog(page);
  },
  async tab_order_with_one_frame() {
    const page = await open_framed_second_page({});
    return { identifiers: collect_focusable_identifiers(page) };
  },
  async tab_order_with_two_frames() {
    const page = await open_second_page_with_two_frames({});
    return { identifiers: collect_focusable_identifiers(page) };
  },
  async tab_order_without_a_frame() {
    const page = await load_framed_page({});
    await page.click(page.tile_button(1, "enlarge"));
    return { identifiers: collect_focusable_identifiers(page) };
  },
  async drag_the_left_edge() {
    const page = await open_framed_second_page({});
    const edge = page.element("frame-edge-left");
    page.dispatch_pointer(edge, "pointerdown", CENTER_OF_THE_STAGE);
    const captured_while_dragging = edge.hasPointerCapture(1);
    page.dispatch_pointer(edge, "pointermove", { x: 300, y: 200 });
    const during = read_dialog(page);
    page.dispatch_pointer(edge, "pointerup", { x: 300, y: 200 });
    return { captured_while_dragging, released_after: !edge.hasPointerCapture(1), during, after: read_dialog(page) };
  },
  async drag_a_corner() {
    const page = await open_framed_second_page({});
    await drag_element(page, "frame-corner-top-left", { x: 50, y: 40 });
    return read_dialog(page);
  },
  async drag_a_corner_of_a_tilted_frame() {
    const page = await load_page({
      "GET /api/document": respond(build_body({ revision: 1, framings: build_framings(0, [TILTED_CROP]) })),
    });
    await open_second_page(page);
    await drag_element(page, "frame-corner-top-right", { x: -50, y: 40 });
    return read_dialog(page);
  },
  async drag_the_whole_frame() {
    const page = await open_framed_second_page({});
    await drag_element(page, "frame-move-button", { x: 25, y: 20 });
    return read_dialog(page);
  },
  async drag_the_whole_frame_past_the_page() {
    const page = await open_framed_second_page({});
    await drag_element(page, "frame-move-button", { x: 5000, y: 5000 });
    return read_dialog(page);
  },
  async drag_the_rotate_handle() {
    const page = await open_framed_second_page({});
    // The frame is centred at (261, 206) px; the pointer goes from straight above the centre to straight right of it.
    const handle = page.element("frame-rotate-handle");
    page.dispatch_pointer(handle, "pointerdown", { x: 261, y: 106 });
    page.dispatch_pointer(handle, "pointermove", { x: 361, y: 206 });
    page.dispatch_pointer(handle, "pointerup", { x: 361, y: 206 });
    return read_dialog(page);
  },
  async drag_the_rotate_handle_of_a_frame_that_does_not_fit_when_turned() {
    const page = await open_framed_second_page({});
    const handle = page.element("frame-rotate-handle");
    page.dispatch_pointer(handle, "pointerdown", { x: 261, y: 106 });
    page.dispatch_pointer(handle, "pointermove", { x: 261 + 70, y: 206 - 70 });
    page.dispatch_pointer(handle, "pointerup", { x: 261 + 70, y: 206 - 70 });
    return read_dialog(page);
  },
  async drag_is_measured_from_where_it_began() {
    const page = await open_framed_second_page({});
    const edge = page.element("frame-edge-left");
    page.dispatch_pointer(edge, "pointerdown", CENTER_OF_THE_STAGE);
    page.dispatch_pointer(edge, "pointermove", { x: 5000, y: 200 });
    page.dispatch_pointer(edge, "pointermove", { x: 300, y: 200 });
    page.dispatch_pointer(edge, "pointerup", { x: 300, y: 200 });
    return read_dialog(page);
  },
  async drag_a_corner_past_the_opposite_corner() {
    const page = await open_framed_second_page({});
    const corner = page.element("frame-corner-top-left");
    page.dispatch_pointer(corner, "pointerdown", CENTER_OF_THE_STAGE);
    page.dispatch_pointer(corner, "pointermove", { x: 300, y: 240 });
    const valid_place = read_dialog(page);
    page.dispatch_pointer(corner, "pointermove", { x: 5000, y: 5000 });
    const during_the_refusal = read_dialog(page);
    page.dispatch_pointer(corner, "pointerup", { x: 5000, y: 5000 });
    return { valid_place, during_the_refusal, after: read_dialog(page) };
  },
  async drag_a_corner_back_to_a_good_place_after_a_refusal() {
    const page = await open_framed_second_page({});
    const corner = page.element("frame-corner-top-left");
    page.dispatch_pointer(corner, "pointerdown", CENTER_OF_THE_STAGE);
    page.dispatch_pointer(corner, "pointermove", { x: 5000, y: 5000 });
    page.dispatch_pointer(corner, "pointermove", { x: 300, y: 240 });
    page.dispatch_pointer(corner, "pointerup", { x: 300, y: 240 });
    return read_dialog(page);
  },
  async second_finger_does_not_take_the_drag() {
    const page = await open_framed_second_page({});
    const edge = page.element("frame-edge-left");
    const corner = page.element("frame-corner-top-left");
    page.dispatch_pointer(edge, "pointerdown", { ...CENTER_OF_THE_STAGE, pointer_identifier: 1 });
    page.dispatch_pointer(corner, "pointerdown", { ...CENTER_OF_THE_STAGE, pointer_identifier: 2 });
    const second_captured = corner.hasPointerCapture(2);
    page.dispatch_pointer(corner, "pointermove", { x: 300, y: 240, pointer_identifier: 2 });
    page.dispatch_pointer(edge, "pointermove", { x: 300, y: 200, pointer_identifier: 1 });
    page.dispatch_pointer(edge, "pointerup", { x: 300, y: 200, pointer_identifier: 1 });
    return { second_captured, dialog: read_dialog(page) };
  },
  async open_before_the_size_of_the_picture_is_known() {
    const page = await load_page({
      "GET /api/document": respond(build_body({ revision: 1, framings: build_framings(0, [TILTED_CROP]) })),
    });
    page.element("frame-stage").box = { left: 0, top: 0, width: 0, height: 0 };
    await page.click(page.tile_button(2, "enlarge"));
    const before_loading = read_dialog(page);
    size_the_stage(page);
    return { before_loading, after_loading: read_dialog(page) };
  },
  async status_the_user_already_changed_is_kept_when_the_picture_loads() {
    const page = await open_framed_second_page({});
    await drag_the_left_edge(page);
    const after_the_drag = page.element("frame-status").textContent;
    page.dispatch_simple_event(page.element("frame-image"), "load");
    return { after_the_drag, after_loading: page.element("frame-status").textContent };
  },
  async cancelled_drag() {
    const page = await open_framed_second_page({});
    const edge = page.element("frame-edge-left");
    page.dispatch_pointer(edge, "pointerdown", CENTER_OF_THE_STAGE);
    page.dispatch_pointer(edge, "pointermove", { x: 300, y: 200 });
    page.dispatch_pointer(edge, "pointercancel", { x: 300, y: 200 });
    page.dispatch_pointer(edge, "pointermove", { x: 450, y: 200 });
    return { released: !edge.hasPointerCapture(1), dialog: read_dialog(page) };
  },
  async drag_with_the_secondary_button() {
    const page = await open_framed_second_page({});
    const edge = page.element("frame-edge-left");
    page.dispatch_pointer(edge, "pointerdown", { ...CENTER_OF_THE_STAGE, button: 2 });
    const captured = edge.hasPointerCapture(1);
    page.dispatch_pointer(edge, "pointermove", { x: 300, y: 200 });
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
    page.dispatch_pointer(page.element("frame-edge-left"), "pointermove", { x: 300, y: 200 });
    return read_dialog(page);
  },
  async drag_the_second_frame_before_the_first() {
    const page = await open_two_side_by_side_frames({});
    await page.click(page.element("frame-select-button"));
    await drag_element(page, "frame-move-button", { x: -230, y: 0 });
    return read_dialog(page);
  },
  async arrow_on_the_left_edge() {
    const page = await open_framed_second_page({});
    page.element("frame-edge-left").focus();
    const key_event = await page.key_down("ArrowRight");
    return { dialog: read_dialog(page), default_prevented: key_event.defaultPrevented };
  },
  async shift_arrow_on_the_left_edge() {
    const page = await open_framed_second_page({});
    page.element("frame-edge-left").focus();
    await page.key_down_with_shift("ArrowLeft");
    return read_dialog(page);
  },
  async tangent_arrow_on_the_left_edge() {
    const page = await open_framed_second_page({});
    page.element("frame-edge-left").focus();
    const key_event = await page.key_down("ArrowUp");
    return { dialog: read_dialog(page), default_prevented: key_event.defaultPrevented };
  },
  async arrows_on_a_corner() {
    const page = await open_framed_second_page({});
    page.element("frame-corner-bottom-right").focus();
    await page.key_down_with_shift("ArrowLeft");
    await page.key_down_with_shift("ArrowUp");
    return read_dialog(page);
  },
  async arrow_on_the_move_button() {
    const page = await open_framed_second_page({});
    await page.key_down_with_shift("ArrowLeft");
    return read_dialog(page);
  },
  async arrows_on_the_rotate_handle() {
    const page = await open_framed_second_page({});
    page.element("frame-rotate-handle").focus();
    await page.key_down_with_shift("ArrowRight");
    return read_dialog(page);
  },
  async vertical_arrow_on_the_rotate_handle() {
    const page = await open_framed_second_page({});
    page.element("frame-rotate-handle").focus();
    await page.key_down("ArrowUp");
    return read_dialog(page);
  },
  async arrow_that_would_bend_the_frame() {
    const page = await open_framed_second_page({});
    page.element("frame-corner-top-left").focus();
    for (let press = 0; press < 18; press += 1) {
      await page.key_down_with_shift("ArrowRight");
    }
    return read_dialog(page);
  },
  async other_key_on_a_handle() {
    const page = await open_framed_second_page({});
    page.element("frame-edge-left").focus();
    const key_event = await page.key_down("KeyA");
    return { default_prevented: key_event.defaultPrevented, dialog: read_dialog(page) };
  },
  async arrow_on_a_page_without_a_frame() {
    const page = await load_framed_page({});
    await page.click(page.tile_button(1, "enlarge"));
    const key_event = await page.key_down("ArrowRight");
    return { default_prevented: key_event.defaultPrevented };
  },
  async add_a_frame_to_a_page_without_a_frame() {
    const page = await load_framed_page({});
    await page.click(page.tile_button(1, "enlarge"));
    await page.click(page.element("frame-add-button"));
    return { dialog: read_dialog(page), focused_move_button: page.is_focused("frame-move-button") };
  },
  async add_a_second_frame_next_to_the_first() {
    const page = await open_framed_second_page({});
    await page.click(page.element("frame-add-button"));
    return { dialog: read_dialog(page), focused_move_button: page.is_focused("frame-move-button") };
  },
  async add_a_second_frame_to_the_right_of_a_frame_on_the_left() {
    const page = await load_page({
      "GET /api/document": respond(build_body({ revision: 1, framings: build_framings(0, [LEFT_CROP]) })),
    });
    await open_second_page(page);
    await page.click(page.element("frame-add-button"));
    return read_dialog(page);
  },
  async remove_one_of_two_frames() {
    const page = await open_second_page_with_two_frames({});
    await page.click(page.element("frame-remove-button"));
    return { dialog: read_dialog(page), focused_move_button: page.is_focused("frame-move-button") };
  },
  async remove_the_only_frame() {
    const page = await open_framed_second_page({});
    await page.click(page.element("frame-remove-button"));
    return { dialog: read_dialog(page), focused_add_button: page.is_focused("frame-add-button") };
  },
  async turn_the_frame_output() {
    const page = await open_framed_second_page({});
    await page.click(page.element("frame-turn-button"));
    return read_dialog(page);
  },
  async select_the_other_frame_with_the_pointer() {
    const page = await open_second_page_with_two_frames({});
    await page.click(page.element("frame-select-button"));
    return { dialog: read_dialog(page), focused_move_button: page.is_focused("frame-move-button") };
  },
  async select_the_other_frame_with_the_keyboard() {
    const page = await open_second_page_with_two_frames({});
    page.element("frame-select-button").focus();
    await page.press_key("Enter");
    return read_dialog(page);
  },
  async select_the_other_frame_twice() {
    const page = await open_second_page_with_two_frames({});
    await page.click(page.element("frame-select-button"));
    await page.click(page.element("frame-select-button"));
    return read_dialog(page);
  },
  async no_crop_button() {
    const page = await open_framed_second_page({});
    await page.click(page.element("frame-clear-button"));
    return read_dialog(page);
  },
  async no_crop_button_with_two_frames() {
    const page = await open_second_page_with_two_frames({});
    await page.click(page.element("frame-clear-button"));
    return read_dialog(page);
  },
  async no_crop_button_on_a_page_without_a_frame() {
    const page = await load_framed_page({});
    await page.click(page.tile_button(1, "enlarge"));
    await page.click(page.element("frame-clear-button"));
    return read_dialog(page);
  },
  async apply_a_dragged_frame() {
    const page = await open_framed_second_page({
      [PUT_CROPS_KEY]: respond(build_body({ revision: 2, framings: build_framings(0, [WEST_DRAGGED_CROP]) })),
    });
    await drag_the_left_edge(page);
    await page.click(page.element("frame-apply-button"));
    return {
      requests: page.count_requests(PUT_CROPS_KEY),
      body: page.find_request(PUT_CROPS_KEY).body,
      headers: page.find_request(PUT_CROPS_KEY).headers,
      open: page.element("page-frame-dialog").open,
      announcement: announcement(page),
      scan_button_focused: page.is_focused("scan-button"),
      tile_overlay: read_overlay(page.tile_overlay(2)),
    };
  },
  async apply_two_frames() {
    const page = await open_framed_second_page({
      [PUT_CROPS_KEY]: respond(
        build_body({ revision: 2, framings: build_framings(0, [SECOND_PAGE_CROP, rectangle_crop(0.6, 0.3, 0.95, 0.7)]) }),
      ),
    });
    await page.click(page.element("frame-add-button"));
    await page.click(page.element("frame-apply-button"));
    return {
      body: page.find_request(PUT_CROPS_KEY).body,
      announcement: announcement(page),
      tile_label: page.tile_at(2).getAttribute("aria-label"),
    };
  },
  async apply_the_frames_in_reading_order() {
    const page = await open_two_side_by_side_frames({
      [PUT_CROPS_KEY]: respond(build_body({ revision: 2, framings: SIDE_BY_SIDE_FRAMES })),
    });
    await page.click(page.element("frame-select-button"));
    await drag_element(page, "frame-move-button", { x: -230, y: 0 });
    await page.click(page.element("frame-apply-button"));
    return { body: page.find_request(PUT_CROPS_KEY).body };
  },
  async apply_after_opening_by_keyboard() {
    const page = await load_framed_page({
      [PUT_CROPS_KEY]: respond(build_body({ revision: 2, framings: build_framings(0, [WEST_DRAGGED_CROP]) })),
    });
    await open_second_page_by_keyboard(page);
    await drag_the_left_edge(page);
    await page.click(page.element("frame-apply-button"));
    return { focus: page.describe_focus() };
  },
  async apply_without_a_frame() {
    const page = await open_framed_second_page({ [PUT_CROPS_KEY]: respond(build_body({ revision: 2 })) });
    await page.click(page.element("frame-clear-button"));
    await page.click(page.element("frame-apply-button"));
    return {
      body: page.find_request(PUT_CROPS_KEY).body,
      announcement: announcement(page),
      overlay_hidden: page.tile_overlay(2).hidden,
    };
  },
  async apply_a_frame_that_covers_the_whole_page() {
    const page = await open_framed_second_page({ [PUT_CROPS_KEY]: respond(build_body({ revision: 2 })) });
    await drag_element(page, "frame-corner-top-left", { x: -5000, y: -5000 });
    await drag_element(page, "frame-corner-bottom-right", { x: 5000, y: 5000 });
    await drag_element(page, "frame-corner-top-right", { x: 5000, y: -5000 });
    await drag_element(page, "frame-corner-bottom-left", { x: -5000, y: 5000 });
    await page.click(page.element("frame-apply-button"));
    return { body: page.find_request(PUT_CROPS_KEY).body, announcement: announcement(page) };
  },
  async apply_with_nothing_changed() {
    const page = await open_framed_second_page({});
    const apply_disabled = page.element("frame-apply-button").disabled;
    await page.click(page.element("frame-apply-button"));
    return { apply_disabled, requests: page.count_requests(PUT_CROPS_KEY), open: page.element("page-frame-dialog").open };
  },
  async apply_enabled_after_a_change() {
    const page = await open_framed_second_page({});
    await drag_the_left_edge(page);
    return { apply_disabled: page.element("frame-apply-button").disabled };
  },
  async apply_refused() {
    const page = await open_framed_second_page({ [PUT_CROPS_KEY]: build_json_response(422, INVALID_CROP_BODY) });
    await drag_the_left_edge(page);
    await page.click(page.element("frame-apply-button"));
    return { dialog: read_dialog(page), banner: page.banner(), apply_focused: page.is_focused("frame-apply-button") };
  },
  async apply_while_a_page_scans() {
    const page = await open_framed_second_page({});
    await drag_the_left_edge(page);
    await page.poll(SCANNING_STATE());
    const disabled_while_scanning = page.element("frame-apply-button").disabled;
    await page.click(page.element("frame-apply-button"));
    return { disabled_while_scanning, requests: page.count_requests(PUT_CROPS_KEY) };
  },
  async apply_conflict() {
    const page = await open_framed_second_page({
      [PUT_CROPS_KEY]: build_json_response(409, SCAN_ALREADY_RUNNING_BODY),
    });
    await drag_the_left_edge(page);
    await page.click(page.element("frame-apply-button"));
    return { open: page.element("page-frame-dialog").open, status: page.element("frame-status").textContent };
  },
  async apply_with_space_on_the_button() {
    const page = await open_framed_second_page({
      [PUT_CROPS_KEY]: respond(build_body({ revision: 2, framings: build_framings(0, [WEST_DRAGGED_CROP]) })),
    });
    await drag_the_left_edge(page);
    page.element("frame-apply-button").focus();
    await page.press_key("Space");
    return {
      crop_requests: page.count_requests(PUT_CROPS_KEY),
      page_requests: page.count_requests("POST /api/document/pages"),
      open: page.element("page-frame-dialog").open,
    };
  },
  async detect_that_finds_two_frames() {
    const page = await open_framed_second_page({
      [DETECT_KEY]: respond({
        ...build_body({ revision: 2, framings: build_framings(0, [UPPER_CROP, LOWER_CROP]) }),
        crops_detected: true,
        ignored_region_count: 0,
      }),
    });
    await drag_the_left_edge(page);
    await page.click(page.element("frame-detect-button"));
    return {
      dialog: read_dialog(page),
      headers: page.find_request(DETECT_KEY).headers,
      detect_focused: page.is_focused("frame-detect-button"),
      tile_overlay: read_overlay(page.tile_overlay(2)),
    };
  },
  async detect_that_finds_one_frame() {
    const page = await open_framed_second_page({
      [DETECT_KEY]: respond({
        ...build_body({ revision: 2, framings: build_framings(0, [DETECTED_CROP]) }),
        crops_detected: true,
        ignored_region_count: 0,
      }),
    });
    await page.click(page.element("frame-detect-button"));
    return read_dialog(page);
  },
  async detect_that_finds_more_than_two_photos() {
    const page = await open_framed_second_page({
      [DETECT_KEY]: respond({
        ...build_body({ revision: 2, framings: build_framings(0, [UPPER_CROP, LOWER_CROP]) }),
        crops_detected: true,
        ignored_region_count: 1,
      }),
    });
    await page.click(page.element("frame-detect-button"));
    return read_dialog(page);
  },
  async detect_that_finds_nothing() {
    const page = await open_framed_second_page({
      [DETECT_KEY]: respond({
        ...build_body({ revision: 1, framings: FRAMED_SECOND_PAGE }),
        crops_detected: false,
        ignored_region_count: 0,
      }),
    });
    await drag_the_left_edge(page);
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
    await page.poll(SCANNING_STATE());
    const disabled_while_scanning = page.element("frame-detect-button").disabled;
    await page.click(page.element("frame-detect-button"));
    return { disabled_while_scanning, requests: page.count_requests(DETECT_KEY) };
  },
  async detect_on_a_page_without_a_frame() {
    const page = await load_framed_page({
      [FIRST_PAGE_DETECT_KEY]: respond({
        ...build_body({ revision: 2, framings: { [FIRST_PAGE]: { rotation_degrees: 0, crops: [DETECTED_CROP] } } }),
        crops_detected: true,
        ignored_region_count: 0,
      }),
    });
    await page.click(page.tile_button(1, "enlarge"));
    await page.click(page.element("frame-detect-button"));
    return { dialog: read_dialog(page), tile_overlay: read_overlay(page.tile_overlay(1)) };
  },
  async rotate_in_the_dialog() {
    const page = await open_framed_second_page({
      [ROTATION_KEY]: respond(build_body({ revision: 2, framings: build_framings(90, [TURNED_SECOND_PAGE_CROP]) })),
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
      [ROTATION_KEY]: respond(build_body({ revision: 2, framings: build_framings(90, [TURNED_SECOND_PAGE_CROP]) })),
    });
    await drag_the_left_edge(page);
    await page.click(page.element("frame-rotate-button"));
    return read_dialog(page);
  },
  async rotate_a_page_with_two_frames_in_the_dialog() {
    const page = await open_second_page_with_two_frames({
      [ROTATION_KEY]: respond(
        build_body({
          revision: 2,
          framings: build_framings(90, [rectangle_crop(0.45, 0.05, 0.98, 0.9), rectangle_crop(0.02, 0.05, 0.4, 0.9)]),
        }),
      ),
    });
    await page.click(page.element("frame-rotate-button"));
    return read_dialog(page);
  },
  async rotate_a_page_without_a_frame_in_the_dialog() {
    const page = await load_framed_page({
      [`POST /api/document/pages/${FIRST_PAGE}/rotation`]: respond(
        build_body({ revision: 2, framings: { [FIRST_PAGE]: { rotation_degrees: 90, crops: [] } } }),
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
      respond(build_body({ revision: 2, framings: build_framings(90, [TURNED_SECOND_PAGE_CROP]) })),
    );
    await page.flush();
    return { during, after: read_dialog(page) };
  },
  async cancel_after_a_drag() {
    const page = await open_framed_second_page({});
    await drag_the_left_edge(page);
    await page.click(page.element("frame-cancel-button"));
    return {
      open: page.element("page-frame-dialog").open,
      announcement: announcement(page),
      crop_requests: page.count_requests(PUT_CROPS_KEY),
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
    await drag_the_left_edge(page);
    await page.key_down("Escape");
    return {
      open: page.element("page-frame-dialog").open,
      announcement: announcement(page),
      scan_button_focused: page.is_focused("scan-button"),
    };
  },
  async reopen_after_a_discarded_drag() {
    const page = await open_framed_second_page({});
    await drag_the_left_edge(page);
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
  async frames_changed_elsewhere() {
    const page = await open_framed_second_page({});
    await poll_document(page, build_body({ revision: 2, framings: build_framings(0, [UPPER_CROP, LOWER_CROP]) }));
    return read_dialog(page);
  },
  async frames_changed_elsewhere_with_a_draft() {
    const page = await open_framed_second_page({});
    await drag_the_left_edge(page);
    await poll_document(page, build_body({ revision: 2, framings: build_framings(0, [DETECTED_CROP]) }));
    return read_dialog(page);
  },
  async rotated_elsewhere_with_a_draft() {
    const page = await open_framed_second_page({});
    await drag_the_left_edge(page);
    await poll_document(page, build_body({ revision: 2, framings: build_framings(90, [TURNED_SECOND_PAGE_CROP]) }));
    return read_dialog(page);
  },
  async space_on_a_handle() {
    const page = await open_framed_second_page({});
    page.element("frame-edge-left").focus();
    await page.press_key("Space");
    return {
      page_requests: page.count_requests("POST /api/document/pages"),
      scan_requests: page.count_requests("POST /api/scans"),
    };
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
    page.element("frame-edge-left").focus();
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
    return { edits: count_edits(page) };
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
