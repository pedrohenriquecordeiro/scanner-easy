"use strict";

// Plays the Documento mode scenarios named on the command line against the real static scripts in the fake browser
// of fake-browser.js and prints one JSON object with what the page did in each. The three test modules
// tests/web/test_document_panel_*.py each ask for their own scenarios, so each Node run stays short. The fixtures
// come from document-page-fixtures.js.

const { BlockedStorage, FakeStorage, build_deferred_response, build_json_response } = require("./fake-browser.js");
const fixtures = require("./document-page-fixtures.js");

const {
  DRAFT_SESSION,
  FIRST_PAGE,
  SECOND_PAGE,
  THIRD_PAGE,
  FOURTH_PAGE,
  THREE_PAGES,
  FOUR_PAGES,
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
  DAMAGED_PAGE_BODY,
  rectangle_crop,
  quadrilateral_crop,
  read_overlay,
  build_document_body,
  build_state,
  respond,
  build_default_responses,
  build_recovered_quick_responses,
  load_page,
} = fixtures;

async function play_first_page_after_a_draft_end(page) {
  const name_requests_before = page.count_name_requests();
  page.responses["GET /api/document"] = respond(build_document_body({ revision: 5, page_identifiers: [FIRST_PAGE] }));
  await page.poll(build_state({ revision: 5, page_count: 1, scans_completed: 1 }));
  return page.count_name_requests() - name_requests_before;
}

const TURNED_SECOND_PAGE = { [SECOND_PAGE]: { rotation_degrees: 90, crops: [] } };
const SECOND_PAGE_CROP = rectangle_crop(0.13, 0.115, 0.914, 0.915);
const FRAMED_SECOND_PAGE = { [SECOND_PAGE]: { rotation_degrees: 90, crops: [SECOND_PAGE_CROP] } };
const FIRST_PAGE_CROP = rectangle_crop(0.2, 0.1, 0.7, 0.9);
const TILTED_CROP = quadrilateral_crop([[0.4, 0.55], [0.93, 0.44], [0.97, 0.8], [0.44, 0.91]]);
const UPPER_CROP = rectangle_crop(0.05, 0.02, 0.9, 0.55);
const LOWER_CROP = rectangle_crop(0.05, 0.6, 0.9, 0.95);

async function load_page_with_a_framed_second_page() {
  const body = respond(build_document_body({ revision: 1, page_identifiers: THREE_PAGES, framings: FRAMED_SECOND_PAGE }));
  return load_page({ "GET /api/document": body });
}

function respond_with_the_second_page_turned() {
  return respond(build_document_body({ revision: 2, page_identifiers: THREE_PAGES, framings: TURNED_SECOND_PAGE }));
}

const SCENARIOS = {
  async idle_document_page() {
    const page = await load_page({});
    return {
      button_label: page.element("scan-button-label").textContent,
      status_text: page.element("status-line").textContent,
      section_hidden: page.element("document-section").hidden,
      output_format_hidden: page.element("output-format-group").hidden,
      summary_text: page.element("document-summary").textContent,
      storage_line_hidden: page.element("storage-line").hidden,
      draft_storage_text: page.element("draft-storage-line").textContent,
    };
  },
  async grid_tiles() {
    const page = await load_page({});
    const first_tile = page.tile_at(1);
    const thumbnail = page.tile_thumbnail(1);
    return {
      page_identifiers: page.grid_page_identifiers(),
      first_tile_label: first_tile.getAttribute("aria-label"),
      thumbnail_source: thumbnail.src,
      thumbnail_loading: thumbnail.loading,
      thumbnail_class: thumbnail.className,
      thumbnail_frame_class: first_tile.children[0].className,
      thumbnail_text: thumbnail.alt,
      first_left_disabled: page.tile_button(1, "move_left").disabled,
      last_right_disabled: page.tile_button(3, "move_right").disabled,
      delete_label: page.tile_button(2, "delete").getAttribute("aria-label"),
      rotate_text: page.tile_button(2, "rotate").textContent,
      rotate_class: page.tile_button(2, "rotate").className,
      draggable: first_tile.draggable,
      first_tile_action_labels: first_tile.children[TILE_ACTIONS_INDEX].children.map((button) =>
        button.getAttribute("aria-label"),
      ),
    };
  },
  async framed_tiles() {
    const page = await load_page_with_a_framed_second_page();
    return {
      overlays: [1, 2, 3].map((position) => read_overlay(page.tile_overlay(position))),
      labels: [1, 2, 3].map((position) => page.tile_at(position).getAttribute("aria-label")),
      thumbnail_source: page.tile_thumbnail(2).src,
    };
  },
  async tiles_with_two_frames_and_a_tilted_frame() {
    const page = await load_page({
      "GET /api/document": respond(
        build_document_body({
          revision: 1,
          page_identifiers: THREE_PAGES,
          framings: {
            [FIRST_PAGE]: { rotation_degrees: 0, crops: [UPPER_CROP, LOWER_CROP] },
            [SECOND_PAGE]: { rotation_degrees: 0, crops: [TILTED_CROP] },
          },
        }),
      ),
    });
    return {
      two_frames: read_overlay(page.tile_overlay(1)),
      tilted: read_overlay(page.tile_overlay(2)),
      count_texts: [1, 2, 3].map((position) => ({
        hidden: page.tile_crop_count(position).hidden,
        text: page.tile_crop_count(position).textContent,
      })),
      labels: [1, 2, 3].map((position) => page.tile_at(position).getAttribute("aria-label")),
    };
  },
  async rotate_a_page_with_two_frames() {
    const page = await load_page({
      "GET /api/document": respond(
        build_document_body({
          revision: 1,
          page_identifiers: THREE_PAGES,
          framings: { [SECOND_PAGE]: { rotation_degrees: 0, crops: [UPPER_CROP, LOWER_CROP] } },
        }),
      ),
      [ROTATION_PATH_KEY]: respond(
        build_document_body({
          revision: 2,
          page_identifiers: THREE_PAGES,
          framings: { [SECOND_PAGE]: { rotation_degrees: 90, crops: [UPPER_CROP, LOWER_CROP] } },
        }),
      ),
    });
    await page.click(page.tile_button(2, "rotate"));
    return { announcement: page.element("document-announcement").textContent };
  },
  async tile_enlarge_buttons() {
    const page = await load_page({});
    const enlarge_button = page.tile_button(2, "enlarge");
    return {
      text: enlarge_button.textContent,
      class_name: enlarge_button.className,
      label: enlarge_button.getAttribute("aria-label"),
      labels_of_all_tiles: [1, 2, 3].map((position) => page.tile_button(position, "enlarge").getAttribute("aria-label")),
    };
  },
  async enlarge_buttons_while_a_page_scans() {
    const page = await load_page({});
    await page.poll(build_state({ revision: 1, page_count: 3, scans_completed: 3, scan_phase: "scanning" }));
    return { disabled: [1, 2, 3].map((position) => page.tile_button(position, "enlarge").disabled) };
  },
  async thumbnail_proportion() {
    const page = await load_page({});
    const frame = page.tile_at(1).children[0];
    const proportion_before_loading = frame.style.aspectRatio ?? null;
    const thumbnail = page.tile_thumbnail(1);
    thumbnail.naturalWidth = 640;
    thumbnail.naturalHeight = 480;
    page.dispatch_simple_event(thumbnail, "load");
    const proportion_of_a_lying_page = frame.style.aspectRatio;
    thumbnail.naturalWidth = 0;
    thumbnail.naturalHeight = 0;
    page.dispatch_simple_event(thumbnail, "load");
    return { proportion_before_loading, proportion_of_a_lying_page, proportion_after_an_empty_load: frame.style.aspectRatio };
  },
  async crop_added_and_removed_later() {
    const page = await load_page({});
    const first_tile = page.tile_at(1);
    page.responses["GET /api/document"] = respond(
      build_document_body({
        revision: 2,
        page_identifiers: THREE_PAGES,
        framings: { [FIRST_PAGE]: { rotation_degrees: 0, crops: [FIRST_PAGE_CROP] } },
      }),
    );
    await page.poll(build_state({ revision: 2, page_count: 3 }));
    const framed = read_overlay(page.tile_overlay(1));
    const framed_label = page.tile_at(1).getAttribute("aria-label");
    page.responses["GET /api/document"] = respond(build_document_body({ revision: 3, page_identifiers: THREE_PAGES }));
    await page.poll(build_state({ revision: 3, page_count: 3 }));
    return {
      framed,
      framed_label,
      hidden_again: page.tile_overlay(1).hidden,
      label_again: page.tile_at(1).getAttribute("aria-label"),
      same_tile_kept: page.tile_at(1) === first_tile,
      thumbnail_source: page.tile_thumbnail(1).src,
    };
  },
  async thumbnail_that_fails_to_load() {
    const page = await load_page({});
    page.dispatch_simple_event(page.tile_thumbnail(2), "error");
    const after_the_failure = {
      frame_hidden: page.tile_at(2).children[0].hidden,
      placeholder_hidden: page.tile_at(2).children[1].hidden,
    };
    page.responses["GET /api/document"] = respond(
      build_document_body({ revision: 2, page_identifiers: THREE_PAGES, framings: TURNED_SECOND_PAGE }),
    );
    await page.poll(build_state({ revision: 2, page_count: 3 }));
    return {
      after_the_failure,
      frame_hidden_after_another_address: page.tile_at(2).children[0].hidden,
      placeholder_hidden_after_another_address: page.tile_at(2).children[1].hidden,
    };
  },
  async thumbnail_that_stays_after_a_new_body() {
    const page = await load_page({});
    const thumbnail = page.tile_thumbnail(1);
    page.dispatch_simple_event(thumbnail, "error");
    page.responses["GET /api/document"] = respond(build_document_body({ revision: 2, page_identifiers: THREE_PAGES }));
    await page.poll(build_state({ revision: 2, page_count: 3 }));
    return { frame_hidden: page.tile_at(1).children[0].hidden, same_image_kept: page.tile_thumbnail(1) === thumbnail };
  },
  async space_in_document_mode() {
    const page = await load_page({});
    await page.press_key("Space");
    return {
      page_requests: page.count_requests("POST /api/document/pages"),
      scan_requests: page.count_requests("POST /api/scans"),
    };
  },
  async space_after_clicking_discard_last() {
    const page = await load_page({});
    await page.click(page.element("discard-last-page-button"));
    await page.press_key("Space");
    return {
      discard_requests: page.count_requests("DELETE /api/document/pages/last"),
      page_requests: page.count_requests("POST /api/document/pages"),
    };
  },
  async space_after_clicking_move_left() {
    const page = await load_page({
      "PUT /api/document/page-order": respond(
        build_document_body({ revision: 2, page_identifiers: [SECOND_PAGE, FIRST_PAGE, THIRD_PAGE] }),
      ),
    });
    await page.click(page.tile_button(2, "move_left"));
    await page.press_key("Space");
    return {
      order_requests: page.count_requests("PUT /api/document/page-order"),
      page_requests: page.count_requests("POST /api/document/pages"),
    };
  },
  async keyboard_move_left() {
    const page = await load_page({
      "PUT /api/document/page-order": respond(
        build_document_body({ revision: 2, page_identifiers: [FIRST_PAGE, THIRD_PAGE, SECOND_PAGE] }),
      ),
    });
    await page.press_with_keyboard(page.tile_button(3, "move_left"));
    return {
      order_body: page.find_request("PUT /api/document/page-order").body,
      focus: page.describe_focus(),
      announcement: page.element("document-announcement").textContent,
    };
  },
  async keyboard_move_left_to_the_first_position() {
    const page = await load_page({
      "PUT /api/document/page-order": respond(
        build_document_body({ revision: 2, page_identifiers: [SECOND_PAGE, FIRST_PAGE, THIRD_PAGE] }),
      ),
    });
    await page.press_with_keyboard(page.tile_button(2, "move_left"));
    return { focus: page.describe_focus() };
  },
  async keyboard_delete() {
    const page = await load_page({});
    await page.press_with_keyboard(page.tile_button(2, "delete"));
    return {
      delete_requests: page.count_requests(`DELETE /api/document/pages/${SECOND_PAGE}`),
      focus: page.describe_focus(),
      announcement: page.element("document-announcement").textContent,
    };
  },
  async enter_on_the_save_button() {
    const page = await load_page({});
    await page.press_with_keyboard(page.element("save-document-button"));
    const dialog = page.element("confirmation-dialog");
    return {
      dialog_shown_times: dialog.show_count,
      accept_label: page.element("confirmation-accept-button").textContent,
      finalize_requests: page.count_requests("POST /api/document/finalize"),
    };
  },
  async keyboard_rotate() {
    const page = await load_page({
      [ROTATION_PATH_KEY]: respond_with_the_second_page_turned(),
    });
    await page.press_with_keyboard(page.tile_button(2, "rotate"));
    return {
      rotation_requests: page.count_requests(ROTATION_PATH_KEY),
      request_headers: page.find_request(ROTATION_PATH_KEY).headers,
      page_identifiers: page.grid_page_identifiers(),
      thumbnail_source: page.tile_thumbnail(2).src,
      first_thumbnail_source: page.tile_thumbnail(1).src,
      focus: page.describe_focus(),
      announcement: page.element("document-announcement").textContent,
    };
  },
  async pointer_rotate() {
    const page = await load_page({
      [ROTATION_PATH_KEY]: respond_with_the_second_page_turned(),
    });
    await page.click(page.tile_button(2, "rotate"));
    return { scan_button_focused: page.is_focused("scan-button") };
  },
  async space_after_clicking_rotate() {
    const page = await load_page({
      [ROTATION_PATH_KEY]: respond_with_the_second_page_turned(),
    });
    await page.click(page.tile_button(2, "rotate"));
    await page.press_key("Space");
    return {
      rotation_requests: page.count_requests(ROTATION_PATH_KEY),
      page_requests: page.count_requests("POST /api/document/pages"),
    };
  },
  async rotate_while_a_page_scans() {
    const page = await load_page({});
    await page.poll(build_state({ revision: 1, page_count: 3, scans_completed: 3, scan_phase: "scanning" }));
    const rotate_disabled = page.tile_button(2, "rotate").disabled;
    await page.click(page.tile_button(2, "rotate"));
    return { rotate_disabled, rotation_requests: page.count_requests(ROTATION_PATH_KEY) };
  },
  async rotate_while_the_request_is_pending() {
    const rotation_answer = build_deferred_response();
    const page = await load_page({ [ROTATION_PATH_KEY]: rotation_answer });
    await page.click(page.tile_button(2, "rotate"));
    const disabled_during = [1, 2, 3].map((position) => page.tile_button(position, "rotate").disabled);
    rotation_answer.answer(respond_with_the_second_page_turned());
    await page.flush();
    return { disabled_during, disabled_after: page.tile_button(2, "rotate").disabled };
  },
  async rotate_refused_by_a_conflict() {
    const page = await load_page({ [ROTATION_PATH_KEY]: build_json_response(409, SCAN_ALREADY_RUNNING_BODY) });
    await page.press_with_keyboard(page.tile_button(2, "rotate"));
    return { banner: page.banner(), page_identifiers: page.grid_page_identifiers(), focus: page.describe_focus() };
  },
  async rotate_a_damaged_page() {
    const page = await load_page({ [ROTATION_PATH_KEY]: build_json_response(409, DAMAGED_PAGE_BODY) });
    await page.press_with_keyboard(page.tile_button(2, "rotate"));
    const damaged_identifiers = page
      .element("document-page-grid")
      .children.filter((tile) => tile.classList.contains("is-damaged"))
      .map((tile) => tile.dataset.pageIdentifier);
    return { damaged_identifiers, focus: page.describe_focus(), banner: page.banner() };
  },
  async held_backspace() {
    const page = await load_page({});
    const first_key_down = await page.key_down("Backspace");
    await page.repeat_key_down("Backspace");
    await page.repeat_key_down("Backspace");
    await page.key_up("Backspace", first_key_down);
    return { discard_requests: page.count_requests("DELETE /api/document/pages/last") };
  },
  async enter_on_the_scan_button() {
    const page = await load_page({});
    page.element("scan-button").focus();
    await page.press_key("Enter");
    return {
      dialog_open: page.element("confirmation-dialog").open,
      accept_button_focused: page.is_focused("confirmation-accept-button"),
      question: page.element("confirmation-text").textContent,
      page_requests: page.count_requests("POST /api/document/pages"),
      finalize_requests: page.count_requests("POST /api/document/finalize"),
    };
  },
  async a_page_with_two_frames_counts_two_pages_in_the_pdf() {
    const page = await load_page({
      "GET /api/document": respond(
        build_document_body({
          revision: 1,
          page_identifiers: THREE_PAGES,
          framings: { [FIRST_PAGE]: { rotation_degrees: 0, crops: [UPPER_CROP, LOWER_CROP] } },
        }),
      ),
    });
    page.element("scan-button").focus();
    await page.press_key("Enter");
    return {
      summary_text: page.element("document-summary").textContent,
      question: page.element("confirmation-text").textContent,
    };
  },
  async held_enter() {
    const page = await load_page({});
    page.element("scan-button").focus();
    const first_key_down = await page.key_down("Enter");
    await page.repeat_key_down("Enter");
    await page.repeat_key_down("Enter");
    await page.key_up("Enter", first_key_down);
    return {
      dialog_open: page.element("confirmation-dialog").open,
      finalize_requests: page.count_requests("POST /api/document/finalize"),
    };
  },
  async second_enter_confirms() {
    const page = await load_page({});
    page.element("scan-button").focus();
    await page.press_key("Enter");
    await page.press_key("Enter");
    return { finalize_requests: page.count_requests("POST /api/document/finalize") };
  },
  async space_opened_confirmation_takes_the_first_enter() {
    const page = await load_page({});
    page.element("save-document-button").focus();
    await page.press_key("Space");
    await page.press_key("Enter");
    return { finalize_requests: page.count_requests("POST /api/document/finalize") };
  },
  async space_in_the_confirmation() {
    const page = await load_page({});
    await page.click(page.element("save-document-button"));
    await page.press_key("Space");
    return {
      dialog_open: page.element("confirmation-dialog").open,
      finalize_requests: page.count_requests("POST /api/document/finalize"),
      page_requests: page.count_requests("POST /api/document/pages"),
    };
  },
  async escape_in_the_confirmation() {
    const page = await load_page({});
    page.element("scan-button").focus();
    await page.press_key("Enter");
    await page.press_key("Escape");
    return {
      dialog_open: page.element("confirmation-dialog").open,
      finalize_requests: page.count_requests("POST /api/document/finalize"),
      scan_button_focused: page.is_focused("scan-button"),
    };
  },
  async move_to_dialog() {
    const page = await load_page({});
    await page.click(page.tile_button(3, "move_to"));
    const position_input = page.element("move-page-position-input");
    return { position_value: position_input.value, is_position_selected: position_input.is_text_selected };
  },
  async name_after_finalizing() {
    const page = await load_page({});
    await page.type_name("Contrato");
    page.responses["GET /api/document"] = respond(
      build_document_body({ revision: 3, page_identifiers: [], last_finished_document: LAST_FINISHED_DOCUMENT }),
    );
    await page.open_and_accept_the_finalize_confirmation();
    const name_field = page.element("document-name-input").value;
    return {
      name_field,
      finished_text: page.element("document-finished-message").textContent,
      scan_button_focused: page.is_focused("scan-button"),
      name_requests_for_the_next_first_page: await play_first_page_after_a_draft_end(page),
    };
  },
  async name_after_cancelling() {
    const page = await load_page({});
    await page.type_name("Contrato");
    await page.click(page.element("cancel-document-button"));
    const reject_button_focused = page.is_focused("confirmation-reject-button");
    const question = page.element("confirmation-text").textContent;
    await page.click(page.element("confirmation-accept-button"));
    return {
      reject_button_focused,
      question,
      cancel_requests: page.count_requests("DELETE /api/document"),
      name_field: page.element("document-name-input").value,
      name_requests_for_the_next_first_page: await play_first_page_after_a_draft_end(page),
    };
  },
  async name_after_removing_the_only_page_here() {
    const page = await load_page({
      "GET /api/state": respond(build_state({ revision: 1, page_count: 1 })),
      "GET /api/document": respond(
        build_document_body({ revision: 1, page_identifiers: [FIRST_PAGE], name: "Contrato" }),
      ),
      "DELETE /api/document/pages/last": respond(build_document_body({ revision: 2, page_identifiers: [] })),
    });
    await page.click(page.element("discard-last-page-button"));
    const name_field = page.element("document-name-input").value;
    await play_first_page_after_a_draft_end(page);
    const name_request = page.find_request("PUT /api/document/name");
    return { name_field, name_request_body: name_request === null ? null : name_request.body };
  },
  async name_left_while_a_page_scans() {
    const page = await load_page({ "PUT /api/document/name": build_json_response(409, SCAN_ALREADY_RUNNING_BODY) });
    await page.press_key("Space");
    await page.poll(build_state({ revision: 1, page_count: 3, scans_completed: 3, scan_phase: "scanning" }));
    await page.type_name("Contrato");
    page.element("output-folder-input").focus();
    await page.flush();
    const name_requests_during_the_scan = page.count_name_requests();
    page.responses["PUT /api/document/name"] = respond(
      build_document_body({ revision: 3, page_identifiers: FOUR_PAGES, name: "Contrato" }),
    );
    page.responses["GET /api/document"] = respond(build_document_body({ revision: 2, page_identifiers: FOUR_PAGES }));
    await page.poll(build_state({ revision: 2, page_count: 4, scans_completed: 4 }));
    return {
      name_requests_during_the_scan,
      name_bodies_after_the_page_lands: page.list_name_request_bodies().slice(name_requests_during_the_scan),
      name_field: page.element("document-name-input").value,
    };
  },
  async enter_in_the_name_field_during_a_scan() {
    const page = await load_page({
      "PUT /api/document/name": respond(
        build_document_body({ revision: 3, page_identifiers: FOUR_PAGES, name: "Contrato" }),
      ),
    });
    await page.press_key("Space");
    await page.poll(build_state({ revision: 1, page_count: 3, scans_completed: 3, scan_phase: "scanning" }));
    await page.type_name("Contrato");
    await page.press_key("Enter");
    page.responses["GET /api/document"] = respond(build_document_body({ revision: 2, page_identifiers: FOUR_PAGES }));
    await page.poll(build_state({ revision: 2, page_count: 4, scans_completed: 4 }));
    const page_requests_before = page.count_requests("POST /api/document/pages");
    await page.press_key("Space");
    return {
      name_requests: page.count_name_requests(),
      new_page_requests: page.count_requests("POST /api/document/pages") - page_requests_before,
    };
  },
  async refused_name_on_finalize() {
    const page = await load_page({ "PUT /api/document/name": build_json_response(422, INVALID_DOCUMENT_NAME_BODY) });
    await page.type_name("Nome recusado");
    await page.open_and_accept_the_finalize_confirmation();
    return {
      finalize_requests: page.count_requests("POST /api/document/finalize"),
      name_field_focused: page.is_focused("document-name-input"),
      banner: page.banner(),
    };
  },
  async during_finalization() {
    const finalize_answer = build_deferred_response();
    const page = await load_page({ "POST /api/document/finalize": finalize_answer });
    await page.open_and_accept_the_finalize_confirmation();
    const during = {
      button_disabled: page.element("scan-button").disabled,
      button_label: page.element("scan-button-label").textContent,
      status_text: page.element("status-line").textContent,
    };
    await page.press_key("Space");
    return { ...during, page_requests: page.count_requests("POST /api/document/pages") };
  },
  async older_answer_after_a_newer_one() {
    const older_answer = build_deferred_response();
    const page = await load_page({});
    page.responses["GET /api/document"] = [
      older_answer,
      respond(build_document_body({ revision: 3, page_identifiers: [THIRD_PAGE] })),
    ];
    await page.poll(build_state({ revision: 2, page_count: 2 }));
    await page.poll(build_state({ revision: 3, page_count: 1 }));
    older_answer.answer(respond(build_document_body({ revision: 2, page_identifiers: [FIRST_PAGE, THIRD_PAGE] })));
    await page.flush();
    return { page_identifiers: page.grid_page_identifiers() };
  },
  async conflict_on_discard() {
    const page = await load_page({
      "DELETE /api/document/pages/last": build_json_response(409, SCAN_ALREADY_RUNNING_BODY),
    });
    await page.click(page.element("discard-last-page-button"));
    return { banner: page.banner(), page_identifiers: page.grid_page_identifiers() };
  },
  async busy_document_on_add_page() {
    const page = await load_page({ "POST /api/document/pages": build_json_response(409, DOCUMENT_BUSY_BODY) });
    await page.press_key("Space");
    return { banner: page.banner() };
  },
  async stale_page_order() {
    const page = await load_page({ "PUT /api/document/page-order": build_json_response(422, INVALID_PAGE_ORDER_BODY) });
    const document_requests_before = page.count_requests("GET /api/document");
    await page.click(page.tile_button(2, "move_right"));
    return {
      banner: page.banner(),
      extra_document_requests: page.count_requests("GET /api/document") - document_requests_before,
    };
  },
  async damaged_page_on_finalize() {
    const page = await load_page({ "POST /api/document/finalize": build_json_response(409, DAMAGED_PAGE_BODY) });
    await page.open_and_accept_the_finalize_confirmation();
    const damaged_identifiers = page
      .element("document-page-grid")
      .children.filter((tile) => tile.classList.contains("is-damaged"))
      .map((tile) => tile.dataset.pageIdentifier);
    return { damaged_identifiers, focus: page.describe_focus(), banner: page.banner() };
  },
  async recovered_draft_in_quick_mode() {
    const page = await load_page(build_recovered_quick_responses());
    const settings_request = page.find_request("PUT /api/settings");
    return {
      settings_request_body: settings_request === null ? null : settings_request.body,
      section_hidden: page.element("document-section").hidden,
      notice_hidden: page.element("document-recovery-notice").hidden,
      notice_text: page.element("document-recovery-notice").textContent,
      remembered_draft_session: page.storage.getItem(RECOVERY_SWITCH_STORAGE_KEY),
    };
  },
  async recovered_draft_already_switched_in_quick_mode() {
    const storage = new FakeStorage({ [RECOVERY_SWITCH_STORAGE_KEY]: DRAFT_SESSION });
    const page = await load_page(build_recovered_quick_responses(), storage);
    return {
      settings_requests: page.count_requests("PUT /api/settings"),
      section_hidden: page.element("document-section").hidden,
    };
  },
  async recovered_draft_with_blocked_storage() {
    const page = await load_page(build_recovered_quick_responses(), new BlockedStorage());
    return { settings_requests: page.count_requests("PUT /api/settings") };
  },
  async reload_with_a_draft_in_quick_mode() {
    const page = await load_page({
      "GET /api/settings": respond(QUICK_SETTINGS),
      "GET /api/state": respond(build_state({ revision: 4, page_count: 3, settings: QUICK_SETTINGS })),
      "GET /api/document": respond(build_document_body({ revision: 4, page_identifiers: THREE_PAGES })),
    });
    return {
      settings_requests: page.count_requests("PUT /api/settings"),
      section_hidden: page.element("document-section").hidden,
      pending_notice_hidden: page.element("document-pending-notice").hidden,
      pending_text: page.element("document-pending-text").textContent,
      button_label: page.element("scan-button-label").textContent,
    };
  },
  async return_to_document_mode() {
    const page = await load_page({
      "GET /api/settings": respond(QUICK_SETTINGS),
      "GET /api/state": respond(build_state({ revision: 4, page_count: 3, settings: QUICK_SETTINGS })),
    });
    await page.click(page.element("return-to-document-button"));
    return {
      settings_request_body: page.find_request("PUT /api/settings").body,
      section_hidden: page.element("document-section").hidden,
      pending_notice_hidden: page.element("document-pending-notice").hidden,
    };
  },
  async return_button_during_a_quick_scan() {
    const page = await load_page({
      "GET /api/settings": respond(QUICK_SETTINGS),
      "GET /api/state": respond(
        build_state({ revision: 4, page_count: 3, settings: QUICK_SETTINGS, scan_phase: "scanning" }),
      ),
      "GET /api/document": respond(build_document_body({ revision: 4, page_identifiers: THREE_PAGES })),
    });
    const return_button = page.element("return-to-document-button");
    const is_disabled_while_scanning = return_button.disabled;
    await page.click(return_button);
    return {
      is_disabled_while_scanning,
      settings_requests: page.count_requests("PUT /api/settings"),
    };
  },
  async mode_selector() {
    const page = await load_page({ "PUT /api/settings": respond(QUICK_SETTINGS) });
    const single_mode_input = page.element("capture-mode-single");
    single_mode_input.checked = true;
    page.dispatch_simple_event(single_mode_input, "change");
    await page.flush();
    return {
      settings_request_body: page.find_request("PUT /api/settings").body,
      section_hidden: page.element("document-section").hidden,
      button_label: page.element("scan-button-label").textContent,
    };
  },
  async last_scan_panel_in_document_mode() {
    const page = await load_page({
      "GET /api/state": respond(
        build_state({ revision: 1, page_count: 3, scans_completed: 1, last_result: LAST_SCAN_RESULT }),
      ),
    });
    return { last_scan_panel_hidden: page.element("last-scan-panel").hidden };
  },
  async finished_document_seen_from_another_tab() {
    const page = await load_page({
      "GET /api/state": respond(build_state({ revision: 6, page_count: 0 })),
      "GET /api/document": respond(
        build_document_body({ revision: 6, page_identifiers: [], last_finished_document: LAST_FINISHED_DOCUMENT }),
      ),
    });
    return {
      finished_hidden: page.element("document-finished-message").hidden,
      finished_text: page.element("document-finished-message").textContent,
    };
  },
  async page_added() {
    const page = await load_page({});
    page.responses["GET /api/document"] = respond(build_document_body({ revision: 2, page_identifiers: FOUR_PAGES }));
    await page.poll(build_state({ revision: 2, page_count: 4, scans_completed: 1 }));
    return { status_text: page.element("status-line").textContent, page_count: page.grid_page_identifiers().length };
  },
  async status_after_discarding_an_added_page() {
    const page = await load_page({
      "DELETE /api/document/pages/last": respond(build_document_body({ revision: 3, page_identifiers: THREE_PAGES })),
    });
    page.responses["GET /api/document"] = respond(build_document_body({ revision: 2, page_identifiers: FOUR_PAGES }));
    await page.poll(build_state({ revision: 2, page_count: 4, scans_completed: 1 }));
    page.element("scan-button").focus();
    await page.press_key("Backspace");
    return { status_text: page.element("status-line").textContent };
  },
  async drag_and_drop() {
    const page = await load_page({
      "PUT /api/document/page-order": respond(
        build_document_body({ revision: 2, page_identifiers: [SECOND_PAGE, THIRD_PAGE, FIRST_PAGE] }),
      ),
    });
    const dragged_tile = page.tile_at(1);
    await page.drag_and_drop({
      dragged_element: dragged_tile,
      target_element: page.tile_at(3),
      pointer_horizontal_position: RIGHT_HALF_POSITION,
    });
    return {
      order_body: page.find_request("PUT /api/document/page-order").body,
      same_tile_kept: page.tile_at(3) === dragged_tile,
      scan_button_focused: page.is_focused("scan-button"),
    };
  },
  async escape_in_the_name_field() {
    const page = await load_page({});
    await page.type_name("Contrato");
    await page.press_key("Escape");
    return {
      scan_button_focused: page.is_focused("scan-button"),
      name_request_body: page.find_request("PUT /api/document/name").body,
    };
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
