"use strict";

// Wires the Documento section of the page to the pure rules of document-page-policy.js; it decides nothing by itself.
// build_scan_page (application.js) creates it with page_services = {send_request, format_byte_count, error_banner,
// frame_editor, focus_scan_button, refresh_page_controls}. Uses IDLE_PHASE from scan-trigger-policy.js,
// DEFAULT_DOTS_PER_INCH from scan-quality-policy.js, the page addresses and texts of document-page-policy.js and the
// frame functions of page-frame-geometry.js.

const LAST_PAGE_PATH = `${DOCUMENT_PAGES_PATH}/last`;
const PAGE_ORDER_PATH = `${DOCUMENT_PATH}/page-order`;
const DOCUMENT_NAME_PATH = `${DOCUMENT_PATH}/name`;
const FINALIZE_DOCUMENT_PATH = `${DOCUMENT_PATH}/finalize`;
const DAMAGED_PAGE_ERROR_CODE = "damaged_document_page";
const DIALOG_ACCEPTED = "accepted";
const DIALOG_INITIAL_FOCUS = Object.freeze({ ACCEPT: "accept", REJECT: "reject" });
const KEYDOWN_EVENT_TYPE = "keydown";
const KEYUP_EVENT_TYPE = "keyup";
const DIALOG_KEY_EVENT_TYPES = [KEYDOWN_EVENT_TYPE, KEYUP_EVENT_TYPE];
const ENTER_KEY_CODES = [ENTER_KEY_CODE, NUMPAD_ENTER_KEY_CODE];
const DRAG_DATA_FORMAT = "text/plain";
const DRAG_EFFECT = "move";
const KEYBOARD_ACTIVATION_DETAIL = 0;
const KEYBOARD_ORIGIN = Object.freeze({ is_keyboard_initiated: true });
const MOVE_LEFT_OFFSET = -1;
const MOVE_RIGHT_OFFSET = 1;
const POINTER_ORIGIN = Object.freeze({ is_keyboard_initiated: false });
const DAMAGED_PAGE_CLASS = "is-damaged";
const DROP_BEFORE_CLASS = "is-drop-before";
const DROP_AFTER_CLASS = "is-drop-after";
const DECIMAL_RADIX = 10;
const SAVE_ACCEPT_LABEL = "Salvar";
const CANCEL_ACCEPT_LABEL = "Cancelar documento";
const DOCUMENT_CANCELLED_ANNOUNCEMENT = "Documento cancelado.";

function read_action_origin(event) {
  // A click made with Enter or Space carries detail 0; a pointer click counts its clicks.
  return { is_keyboard_initiated: event.detail === KEYBOARD_ACTIVATION_DETAIL };
}

function read_body_version(body) {
  return { draft_session: body.draft_session, revision: body.revision };
}

function show_optional_text(element, text) {
  element.hidden = text === null;
  element.textContent = text ?? "";
}

class DocumentPanel {
  constructor(elements, page_services) {
    this.elements = elements;
    this.page_services = page_services;
    this.is_shown = false;
    this.rendered_body = null;
    this.saved_name = "";
    this.is_name_save_deferred = false;
    this.page_tiles = new Map();
    this.previous_observation = null;
    this.last_event = DOCUMENT_EVENTS.NONE;
    this.scan_activity = { scan_phase: IDLE_PHASE, is_start_request_pending: false };
    this.dots_per_inch = DEFAULT_DOTS_PER_INCH;
    this.is_edit_pending = false;
    this.is_finalizing = false;
    this.is_dialog_armed = true;
    this.is_key_held = false;
    this.pending_draft_ending = null;
    this.damaged_page_identifier = null;
  }

  bind_events() {
    // Enter clicks a button on keydown and Space on keyup, so only Enter is still held when its dialog opens.
    document.addEventListener(
      KEYDOWN_EVENT_TYPE,
      () => {
        this.is_key_held = true;
      },
      true,
    );
    document.addEventListener(
      KEYUP_EVENT_TYPE,
      () => {
        this.is_key_held = false;
      },
      true,
    );
    const name_input = this.elements.document_name_input;
    name_input.addEventListener("blur", () => this.save_name_after_leaving_field());
    name_input.addEventListener("keydown", (event) => {
      if (ENTER_KEY_CODES.includes(event.code)) {
        event.preventDefault();
        // Leaving the field saves the name (blur). During a scan the disabled button takes no focus, so the focus
        // rests on the page and moves to the button when the page lands; either way the next Space adds a page.
        name_input.blur();
        this.apply_focus({ action: DOCUMENT_ACTIONS.NAME_SAVED, is_keyboard_initiated: true });
      }
    });
    this.elements.discard_last_page_button.addEventListener("click", (event) =>
      this.discard_last_page(read_action_origin(event)),
    );
    this.elements.cancel_document_button.addEventListener("click", (event) =>
      this.request_cancel(read_action_origin(event)),
    );
    this.elements.save_document_button.addEventListener("click", (event) =>
      this.request_finalize(read_action_origin(event)),
    );
    this.page_services.frame_editor.bind_events();
    this.bind_dialog_buttons(this.elements.confirmation_accept_button, this.elements.confirmation_reject_button);
    this.bind_dialog_buttons(this.elements.move_page_accept_button, this.elements.move_page_reject_button);
    this.elements.move_page_position_input.addEventListener("keydown", (event) => {
      if (ENTER_KEY_CODES.includes(event.code)) {
        event.preventDefault();
        this.elements.move_page_dialog.close(DIALOG_ACCEPTED);
      }
    });
    for (const dialog of [this.elements.confirmation_dialog, this.elements.move_page_dialog]) {
      DIALOG_KEY_EVENT_TYPES.forEach((event_type) => {
        dialog.addEventListener(event_type, (event) => this.filter_dialog_key(event), true);
      });
    }
  }

  bind_dialog_buttons(accept_button, reject_button) {
    accept_button.addEventListener("click", () => this.find_open_dialog().close(DIALOG_ACCEPTED));
    reject_button.addEventListener("click", () => this.find_open_dialog().close());
  }

  find_open_dialog() {
    const { confirmation_dialog, move_page_dialog } = this.elements;
    return confirmation_dialog.open ? confirmation_dialog : move_page_dialog;
  }

  filter_dialog_key(event) {
    const action = decide_confirmation_key_action(event, { is_armed: this.is_dialog_armed });
    if (action === CONFIRMATION_KEY_ACTIONS.SUPPRESS) {
      event.preventDefault();
      event.stopPropagation();
    }
    // Opened by the keyboard, the dialog arms on the keyup of the key that opened it.
    if (event.type === KEYUP_EVENT_TYPE) {
      this.is_dialog_armed = true;
    }
  }

  show() {
    this.is_shown = true;
    this.elements.document_section.hidden = false;
  }

  hide() {
    this.is_shown = false;
    this.elements.document_section.hidden = true;
  }

  apply_scan_activity(scan_activity) {
    this.scan_activity = scan_activity;
    this.render_controls();
    if (this.is_name_save_deferred && this.can_edit()) {
      this.is_name_save_deferred = false;
      this.save_name();
    }
  }

  apply_summary(document_summary, scan_observation) {
    const observation = {
      draft_session: document_summary.draft_session,
      revision: document_summary.revision,
      page_count: document_summary.page_count,
      scans_completed: scan_observation.scans_completed,
      last_error_code: scan_observation.last_error_code,
      capture_mode: scan_observation.capture_mode,
    };
    this.last_event = next_document_event(this.previous_observation, observation, this.last_event);
    this.previous_observation = observation;
    this.dots_per_inch = scan_observation.dots_per_inch;
    const rendered_version = this.read_rendered_version();
    const is_rendered =
      rendered_version !== null &&
      rendered_version.draft_session === document_summary.draft_session &&
      rendered_version.revision === document_summary.revision;
    if (!is_rendered) {
      this.refresh_document();
    }
  }

  read_rendered_version() {
    return this.rendered_body === null ? null : read_body_version(this.rendered_body);
  }

  async refresh_document() {
    let body;
    try {
      body = await this.page_services.send_request("GET", DOCUMENT_PATH);
    } catch {
      // The /api/state poll reports a lost connection; the next summary asks again.
      return null;
    }
    this.accept_body(body);
    return body;
  }

  accept_body(body) {
    if (should_render_document_body(this.read_rendered_version(), read_body_version(body))) {
      this.render_document(body);
    }
  }

  render_document(body) {
    const had_document = this.rendered_body !== null && this.rendered_body.document !== null;
    this.rendered_body = body;
    const draft = body.document;
    if (draft === null && had_document) {
      this.end_draft();
    }
    if (draft !== null) {
      this.adopt_name(draft, had_document);
    }
    this.render_grid(draft === null ? [] : draft.pages);
    this.render_notices(body);
    // The page count changed, so the big button and the status line change with it.
    this.notify_activity_change();
    this.page_services.frame_editor.handle_document_change();
  }

  end_draft() {
    const draft_ending = this.pending_draft_ending ?? DRAFT_ENDINGS.ENDED_ELSEWHERE;
    this.pending_draft_ending = null;
    this.saved_name = "";
    this.is_name_save_deferred = false;
    this.damaged_page_identifier = null;
    if (decide_name_field_after_draft_end(draft_ending) === NAME_FIELD_DECISIONS.CLEAR) {
      this.elements.document_name_input.value = "";
    }
  }

  adopt_name(draft, had_document) {
    const name_input = this.elements.document_name_input;
    if (!had_document) {
      // The name typed while there was no draft goes with the first page this tab sees.
      const pending_name = decide_name_to_send({
        typed_name: name_input.value,
        saved_name: this.saved_name,
        document_exists: true,
      });
      this.saved_name = draft.name;
      if (pending_name !== null) {
        this.send_name(pending_name);
        return;
      }
    }
    this.saved_name = draft.name;
    // A name left in the field while a page was scanning is still unsent: the field keeps it until it goes.
    if (document.activeElement !== name_input && !this.is_name_save_deferred) {
      name_input.value = draft.name;
    }
  }

  render_grid(pages) {
    const page_count = pages.length;
    const tiles = pages.map((page, index) => {
      const tile = this.page_tiles.get(page.page_identifier) ?? this.build_tile(page.page_identifier);
      this.label_tile(tile, { position: index + 1, page_count, page });
      return tile;
    });
    this.page_tiles = new Map(tiles.map((tile) => [tile.page_identifier, tile]));
    this.elements.document_page_grid.replaceChildren(...tiles.map((tile) => tile.item));
  }

  build_tile(page_identifier) {
    const item = document.createElement("li");
    item.className = "page-tile";
    item.draggable = true;
    item.dataset.pageIdentifier = page_identifier;
    // The frame of the thumbnail takes the proportion of the picture, so the crop frame, drawn in percentages of it,
    // falls exactly on the page even when the page lies down.
    const thumbnail_frame = this.build_element("div", "page-thumbnail-frame");
    const thumbnail = this.build_element("img", "page-thumbnail");
    thumbnail.loading = "lazy";
    thumbnail.decoding = "async";
    const overlay = this.build_element("div", "page-crop-overlay");
    overlay.setAttribute("aria-hidden", "true");
    overlay.hidden = true;
    thumbnail_frame.append(thumbnail, overlay);
    const placeholder = this.build_element("span", "page-placeholder");
    placeholder.hidden = true;
    const number = this.build_element("span", "page-number");
    const tile = {
      page_identifier,
      item,
      thumbnail_frame,
      thumbnail,
      overlay,
      placeholder,
      number,
      position: 0,
      shown_rotation_degrees: null,
      move_left_button: this.build_tile_button("page-move-left", "◀"),
      move_right_button: this.build_tile_button("page-move-right", "▶"),
      delete_button: this.build_tile_button("page-delete", "×"),
      rotate_button: this.build_tile_button("page-rotate", "Girar ↻"),
      move_to_button: this.build_tile_button("page-move-to", "Mover para…"),
      enlarge_button: this.build_tile_button("page-enlarge", "Ampliar"),
    };
    const actions = this.build_element("div", "page-actions");
    // The DOM order is the Tab order, so it follows the visual order: ◀ ▶ × on the first row, then "Girar ↻" and
    // "Mover para…", then "Ampliar" across the whole width.
    actions.append(
      tile.move_left_button,
      tile.move_right_button,
      tile.delete_button,
      tile.rotate_button,
      tile.move_to_button,
      tile.enlarge_button,
    );
    item.append(thumbnail_frame, placeholder, number, actions);
    this.bind_tile(tile);
    return tile;
  }

  build_element(tag_name, class_name) {
    const element = document.createElement(tag_name);
    element.className = class_name;
    return element;
  }

  build_tile_button(class_name, text) {
    const button = this.build_element("button", class_name);
    button.type = "button";
    button.textContent = text;
    return button;
  }

  bind_tile(tile) {
    const { page_identifier, item, thumbnail, thumbnail_frame, placeholder } = tile;
    thumbnail.addEventListener("error", () => {
      thumbnail_frame.hidden = true;
      placeholder.hidden = false;
    });
    thumbnail.addEventListener("load", () => this.fit_thumbnail_frame(tile));
    // A click on the picture is a convenience of the mouse; the keyboard has the "Ampliar" button.
    thumbnail_frame.addEventListener("click", () => this.enlarge_page(page_identifier, POINTER_ORIGIN));
    tile.enlarge_button.addEventListener("click", (event) =>
      this.enlarge_page(page_identifier, read_action_origin(event)),
    );
    tile.move_left_button.addEventListener("click", (event) =>
      this.move_page({ page_identifier, offset: MOVE_LEFT_OFFSET }, read_action_origin(event)),
    );
    tile.move_right_button.addEventListener("click", (event) =>
      this.move_page({ page_identifier, offset: MOVE_RIGHT_OFFSET }, read_action_origin(event)),
    );
    tile.move_to_button.addEventListener("click", (event) =>
      this.move_page_to(page_identifier, read_action_origin(event)),
    );
    tile.delete_button.addEventListener("click", (event) =>
      this.delete_page(page_identifier, read_action_origin(event)),
    );
    tile.rotate_button.addEventListener("click", (event) =>
      this.rotate_page(page_identifier, read_action_origin(event)),
    );
    item.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData(DRAG_DATA_FORMAT, page_identifier);
      event.dataTransfer.effectAllowed = DRAG_EFFECT;
    });
    item.addEventListener("dragover", (event) => this.mark_drop_side(tile, event));
    item.addEventListener("dragleave", () => this.clear_drop_side(tile));
    item.addEventListener("dragend", () => this.clear_drop_side(tile));
    item.addEventListener("drop", (event) => this.handle_drop(tile, event));
  }

  fit_thumbnail_frame(tile) {
    const { naturalWidth, naturalHeight } = tile.thumbnail;
    if (naturalWidth > 0 && naturalHeight > 0) {
      tile.thumbnail_frame.style.aspectRatio = `${naturalWidth} / ${naturalHeight}`;
    }
  }

  label_tile(tile, tile_state) {
    const { position, page_count, page } = tile_state;
    tile.position = position;
    tile.item.setAttribute("aria-label", describe_tile_label({ position, page_count, crop: page.crop }));
    tile.item.classList.toggle(DAMAGED_PAGE_CLASS, tile.page_identifier === this.damaged_page_identifier);
    this.show_thumbnail(tile, page.rotation_degrees);
    this.show_crop_overlay(tile, page.crop);
    tile.thumbnail.alt = `Miniatura da página ${position}`;
    tile.placeholder.textContent = `Página ${position}`;
    tile.number.textContent = String(position);
    tile.move_left_button.setAttribute("aria-label", `Mover a página ${position} para a esquerda`);
    tile.move_right_button.setAttribute("aria-label", `Mover a página ${position} para a direita`);
    tile.move_to_button.setAttribute("aria-label", `Mover a página ${position} para outra posição`);
    tile.delete_button.setAttribute("aria-label", `Excluir a página ${position}`);
    tile.rotate_button.setAttribute("aria-label", `Girar a página ${position} 90 graus para a direita`);
    tile.enlarge_button.setAttribute("aria-label", describe_enlarge_label(position));
  }

  show_thumbnail(tile, rotation_degrees) {
    if (tile.shown_rotation_degrees === rotation_degrees) {
      return;
    }
    tile.shown_rotation_degrees = rotation_degrees;
    // Another address is another try: a thumbnail that failed to load may work now.
    tile.thumbnail_frame.hidden = false;
    tile.placeholder.hidden = true;
    tile.thumbnail.src = build_page_thumbnail_address(tile.page_identifier, rotation_degrees);
  }

  show_crop_overlay(tile, crop) {
    tile.overlay.hidden = crop === null;
    if (crop === null) {
      return;
    }
    place_frame_on_element(tile.overlay, read_frame_from_crop(crop));
  }

  render_notices(body) {
    const draft = body.document;
    const { format_byte_count } = this.page_services;
    show_optional_text(this.elements.document_recovery_notice, describe_recovery(body.recovery));
    show_optional_text(this.elements.document_previous_save_notice, describe_possible_previous_save(draft));
    show_optional_text(
      this.elements.document_finished_message,
      draft === null ? describe_finished_document(body.last_finished_document) : null,
    );
    this.elements.document_empty_message.hidden = draft !== null;
    show_optional_text(
      this.elements.document_summary,
      draft === null
        ? null
        : `${describe_page_count(draft.page_count)} · ~${format_byte_count(draft.estimated_size_in_bytes)}`,
    );
    this.elements.document_large_warning.hidden = draft === null || !should_warn_about_large_document(draft);
  }

  render_controls() {
    const can_edit = this.can_edit();
    const page_count = this.page_tiles.size;
    for (const tile of this.page_tiles.values()) {
      tile.item.draggable = can_edit;
      tile.move_left_button.disabled = !can_edit || tile.position === 1;
      tile.move_right_button.disabled = !can_edit || tile.position === page_count;
      tile.move_to_button.disabled = !can_edit || page_count === 1;
      tile.delete_button.disabled = !can_edit;
      tile.rotate_button.disabled = !can_edit;
    }
    const { discard_last_page_button, cancel_document_button, save_document_button } = this.elements;
    for (const button of [discard_last_page_button, cancel_document_button, save_document_button]) {
      button.disabled = !can_edit || page_count === 0;
    }
    this.page_services.frame_editor.render_controls();
  }

  notify_activity_change() {
    this.render_controls();
    this.page_services.refresh_page_controls();
  }

  can_edit() {
    return can_edit_document({ ...this.scan_activity, is_edit_request_pending: this.is_edit_pending });
  }

  describe_status(scan_phase) {
    return describe_document_status(scan_phase, {
      page_count: this.page_tiles.size,
      last_event: this.last_event,
      dots_per_inch: this.dots_per_inch,
      is_finalizing: this.is_finalizing,
    });
  }

  is_edit_request_pending() {
    return this.is_edit_pending;
  }

  is_finalizing_document() {
    return this.is_finalizing;
  }

  is_confirmation_open() {
    const { confirmation_dialog, move_page_dialog, page_frame_dialog } = this.elements;
    return confirmation_dialog.open || move_page_dialog.open || page_frame_dialog.open;
  }

  find_page(page_identifier) {
    const draft = this.rendered_body === null ? null : this.rendered_body.document;
    const index = draft === null ? -1 : draft.pages.findIndex((page) => page.page_identifier === page_identifier);
    if (index < 0) {
      return null;
    }
    return { page: draft.pages[index], position: index + FIRST_POSITION, page_count: draft.pages.length };
  }

  has_pages() {
    return this.page_tiles.size > 0;
  }

  read_page_identifiers() {
    return [...this.page_tiles.keys()];
  }

  handle_key_down(event) {
    const action = decide_document_key_action(event, {
      capture_mode: this.is_shown ? CAPTURE_MODES.DOCUMENT : CAPTURE_MODES.SINGLE,
      page_count: this.page_tiles.size,
      can_edit: this.can_edit(),
      is_confirmation_open: this.is_confirmation_open(),
      scan_button: this.elements.scan_button,
    });
    if (action === DOCUMENT_KEY_ACTIONS.IGNORE) {
      return;
    }
    event.preventDefault();
    if (action === DOCUMENT_KEY_ACTIONS.DISCARD_LAST_PAGE) {
      this.discard_last_page(KEYBOARD_ORIGIN);
    } else if (action === DOCUMENT_KEY_ACTIONS.REQUEST_FINALIZE) {
      this.request_finalize(KEYBOARD_ORIGIN);
    } else if (action === DOCUMENT_KEY_ACTIONS.FOCUS_SCAN_BUTTON) {
      this.page_services.focus_scan_button();
    }
  }

  announce(text) {
    this.elements.document_announcement.textContent = text;
  }

  async run_edit(edit_request) {
    const { body, failure } = await this.attempt_edit(edit_request);
    // Reported once the controls are enabled again, so the damaged page's × can take the focus.
    if (failure !== null) {
      this.report_failure(failure);
    }
    return body;
  }

  async attempt_edit(edit_request) {
    this.is_edit_pending = true;
    this.notify_activity_change();
    let body = null;
    let failure = null;
    try {
      this.pending_draft_ending = edit_request.draft_ending ?? null;
      body = await this.page_services.send_request(edit_request.method, edit_request.path, edit_request.body);
      this.page_services.error_banner.report_action_error(null);
      // An accepted edit replaces the last scan event, so the status line never reports a page this tab removed.
      this.last_event = DOCUMENT_EVENTS.EDITED;
      this.accept_body(body);
    } catch (error) {
      failure = error;
    } finally {
      this.pending_draft_ending = null;
      this.is_edit_pending = false;
      this.notify_activity_change();
    }
    return { body, failure };
  }

  report_failure(error) {
    this.page_services.error_banner.report_action_error(error.message);
    if (error.error_code === DAMAGED_PAGE_ERROR_CODE) {
      this.mark_damaged_page(error.page_identifier);
    }
    if (should_reload_document_after_error(error.error_code)) {
      this.refresh_document();
    }
  }

  mark_damaged_page(page_identifier) {
    this.damaged_page_identifier = page_identifier;
    const tile = this.page_tiles.get(page_identifier);
    if (tile !== undefined) {
      tile.item.classList.add(DAMAGED_PAGE_CLASS);
      tile.delete_button.focus();
    }
  }

  apply_focus(action_context) {
    const focus = decide_focus_after_action({
      page_identifiers_after: this.read_page_identifiers(),
      acted_page_identifier: null,
      acted_position: 0,
      ...action_context,
    });
    const tile = this.page_tiles.get(focus.page_identifier);
    if (focus.target === FOCUS_TARGETS.SCAN_BUTTON || tile === undefined) {
      this.page_services.focus_scan_button();
    } else if (focus.target === FOCUS_TARGETS.DELETE_BUTTON) {
      tile.delete_button.focus();
    } else if (focus.target === FOCUS_TARGETS.ROTATE_BUTTON) {
      tile.rotate_button.focus();
    } else if (focus.target === FOCUS_TARGETS.ENLARGE_BUTTON) {
      tile.enlarge_button.focus();
    } else {
      // The arrow that was used, or the other one once the page reached that end of the grid.
      const used_button = action_context.offset === MOVE_LEFT_OFFSET ? tile.move_left_button : tile.move_right_button;
      const other_button = used_button === tile.move_left_button ? tile.move_right_button : tile.move_left_button;
      (used_button.disabled ? other_button : used_button).focus();
    }
  }

  async discard_last_page(action_origin) {
    if (!this.can_edit() || !this.has_pages()) {
      return;
    }
    const position = this.page_tiles.size;
    const body = await this.run_edit({
      method: "DELETE",
      path: LAST_PAGE_PATH,
      draft_ending: DRAFT_ENDINGS.LAST_PAGE_REMOVED_HERE,
    });
    if (body !== null) {
      this.announce(
        describe_page_removal({
          action: DOCUMENT_ACTIONS.DISCARD_LAST,
          position,
          remaining_page_count: this.page_tiles.size,
        }),
      );
    }
    this.apply_focus({ action: DOCUMENT_ACTIONS.DISCARD_LAST, ...action_origin });
  }

  async delete_page(page_identifier, action_origin) {
    if (!this.can_edit()) {
      return;
    }
    const position = this.read_page_identifiers().indexOf(page_identifier) + 1;
    const body = await this.run_edit({
      method: "DELETE",
      path: build_page_path(page_identifier),
      draft_ending: DRAFT_ENDINGS.LAST_PAGE_REMOVED_HERE,
    });
    if (body !== null) {
      this.announce(
        describe_page_removal({
          action: DOCUMENT_ACTIONS.DELETE,
          position,
          remaining_page_count: this.page_tiles.size,
        }),
      );
    }
    this.apply_focus({
      action: DOCUMENT_ACTIONS.DELETE,
      acted_page_identifier: page_identifier,
      acted_position: position,
      ...action_origin,
    });
  }

  async rotate_page(page_identifier, action_origin) {
    if (!this.can_edit()) {
      return;
    }
    const position = this.read_page_identifiers().indexOf(page_identifier) + 1;
    const body = await this.run_edit({ method: "POST", path: build_page_rotation_path(page_identifier) });
    if (body !== null) {
      const turned_page = this.find_page(page_identifier);
      const crop = turned_page === null ? null : turned_page.page.crop;
      this.announce(describe_page_rotation_result({ position, crop }));
    }
    // A damaged page already took the focus on its × (report_failure); otherwise the Girar button of the page gets it
    // back.
    if (body !== null || this.damaged_page_identifier !== page_identifier) {
      this.apply_focus({
        action: DOCUMENT_ACTIONS.ROTATE,
        acted_page_identifier: page_identifier,
        acted_position: position,
        ...action_origin,
      });
    }
  }

  enlarge_page(page_identifier, action_origin) {
    this.page_services.frame_editor.open({ page_identifier, action_origin });
  }

  async reorder_pages(page_reorder) {
    const { page_identifier, page_order } = page_reorder;
    const current_order = this.read_page_identifiers();
    if (is_same_order(current_order, page_order)) {
      return;
    }
    const body = await this.run_edit({ method: "PUT", path: PAGE_ORDER_PATH, body: { page_identifiers: page_order } });
    if (body !== null) {
      const position_before = current_order.indexOf(page_identifier) + 1;
      this.announce(describe_page_move(position_before, page_order.indexOf(page_identifier) + 1));
    }
  }

  async move_page(page_move, action_origin) {
    if (!this.can_edit()) {
      return;
    }
    const { page_identifier, offset } = page_move;
    const page_order = move_page_by_offset(this.read_page_identifiers(), page_identifier, offset);
    await this.reorder_pages({ page_identifier, page_order });
    this.apply_focus({
      action: DOCUMENT_ACTIONS.MOVE,
      acted_page_identifier: page_identifier,
      offset,
      ...action_origin,
    });
  }

  async move_page_to(page_identifier, action_origin) {
    if (!this.can_edit()) {
      return;
    }
    const page_identifiers = this.read_page_identifiers();
    const position_input = this.elements.move_page_position_input;
    position_input.value = String(page_identifiers.indexOf(page_identifier) + 1);
    position_input.max = String(page_identifiers.length);
    const is_accepted = await this.show_dialog({
      dialog: this.elements.move_page_dialog,
      initial_focus_element: position_input,
      opened_by_keyboard: action_origin.is_keyboard_initiated,
    });
    const position = Number.parseInt(position_input.value, DECIMAL_RADIX);
    if (is_accepted && Number.isInteger(position) && this.can_edit()) {
      const page_order = move_page_to_position(page_identifiers, page_identifier, position);
      await this.reorder_pages({ page_identifier, page_order });
    }
    this.apply_focus({ action: DOCUMENT_ACTIONS.DIALOG_CLOSED, ...action_origin });
  }

  async drop_page(page_drop) {
    if (this.can_edit()) {
      const page_order = move_page_next_to(this.read_page_identifiers(), page_drop);
      await this.reorder_pages({ page_identifier: page_drop.dragged_identifier, page_order });
    }
    this.apply_focus({ action: DOCUMENT_ACTIONS.DROP, is_keyboard_initiated: false });
  }

  mark_drop_side(tile, event) {
    if (!this.can_edit()) {
      return;
    }
    // Accepting the dragover is what lets the browser deliver the drop.
    event.preventDefault();
    event.dataTransfer.dropEffect = DRAG_EFFECT;
    const placement = choose_drop_placement(event.clientX, tile.item.getBoundingClientRect());
    tile.item.classList.toggle(DROP_BEFORE_CLASS, placement === PAGE_PLACEMENTS.BEFORE);
    tile.item.classList.toggle(DROP_AFTER_CLASS, placement === PAGE_PLACEMENTS.AFTER);
  }

  clear_drop_side(tile) {
    tile.item.classList.remove(DROP_BEFORE_CLASS, DROP_AFTER_CLASS);
  }

  handle_drop(tile, event) {
    event.preventDefault();
    this.clear_drop_side(tile);
    this.drop_page({
      dragged_identifier: event.dataTransfer.getData(DRAG_DATA_FORMAT),
      target_identifier: tile.page_identifier,
      placement: choose_drop_placement(event.clientX, tile.item.getBoundingClientRect()),
    });
  }

  save_name_after_leaving_field() {
    if (this.can_edit()) {
      this.save_name();
      return;
    }
    // While a page is scanning the server refuses edits (409); the name goes once the scan ends.
    this.is_name_save_deferred = true;
  }

  async save_name() {
    const name_to_send = decide_name_to_send({
      typed_name: this.elements.document_name_input.value,
      saved_name: this.saved_name,
      document_exists: this.has_pages(),
    });
    return name_to_send === null ? true : this.send_name(name_to_send);
  }

  async send_name(name) {
    try {
      const body = await this.page_services.send_request("PUT", DOCUMENT_NAME_PATH, { name });
      this.page_services.error_banner.report_action_error(null);
      this.accept_body(body);
      if (body.document !== null) {
        this.saved_name = body.document.name;
        this.elements.document_name_input.value = body.document.name;
      }
      return true;
    } catch (error) {
      this.report_failure(error);
      return false;
    }
  }

  async request_finalize(action_origin) {
    if (!this.can_edit() || !this.has_pages()) {
      return;
    }
    const is_confirmed = await this.confirm_action({
      question: `Salvar o PDF com ${describe_page_count(this.page_tiles.size)}?`,
      accept_label: SAVE_ACCEPT_LABEL,
      initial_focus: DIALOG_INITIAL_FOCUS.ACCEPT,
      opened_by_keyboard: action_origin.is_keyboard_initiated,
    });
    if (!is_confirmed || !this.can_edit()) {
      this.apply_focus({ action: DOCUMENT_ACTIONS.DIALOG_CLOSED, ...action_origin });
      return;
    }
    await this.finalize_document(action_origin);
  }

  async finalize_document(action_origin) {
    this.is_finalizing = true;
    this.is_edit_pending = true;
    this.notify_activity_change();
    let is_name_saved = false;
    let failure = null;
    try {
      is_name_saved = await this.save_name();
      if (is_name_saved) {
        await this.page_services.send_request("POST", FINALIZE_DOCUMENT_PATH);
        this.page_services.error_banner.report_action_error(null);
        this.pending_draft_ending = DRAFT_ENDINGS.FINALIZED;
        const body = await this.refresh_document();
        this.announce(body === null ? "" : describe_finished_document(body.last_finished_document) ?? "");
      }
    } catch (error) {
      failure = error;
    } finally {
      this.pending_draft_ending = null;
      this.is_finalizing = false;
      this.is_edit_pending = false;
      this.notify_activity_change();
    }
    if (!is_name_saved) {
      // The refused name is already in the banner; the field gets the focus to fix it before saving.
      this.elements.document_name_input.focus();
    } else if (failure !== null) {
      this.report_failure(failure);
    } else {
      this.apply_focus({ action: DOCUMENT_ACTIONS.FINALIZED, ...action_origin });
    }
  }

  async request_cancel(action_origin) {
    if (!this.can_edit() || !this.has_pages()) {
      return;
    }
    const is_confirmed = await this.confirm_action({
      question: `Cancelar o documento e apagar ${describe_page_count(this.page_tiles.size)}?`,
      accept_label: CANCEL_ACCEPT_LABEL,
      initial_focus: DIALOG_INITIAL_FOCUS.REJECT,
      opened_by_keyboard: action_origin.is_keyboard_initiated,
    });
    if (is_confirmed && this.can_edit()) {
      const body = await this.run_edit({
        method: "DELETE",
        path: DOCUMENT_PATH,
        draft_ending: DRAFT_ENDINGS.CANCELLED,
      });
      if (body !== null) {
        this.announce(DOCUMENT_CANCELLED_ANNOUNCEMENT);
      }
    }
    const action = is_confirmed ? DOCUMENT_ACTIONS.CANCELLED : DOCUMENT_ACTIONS.DIALOG_CLOSED;
    this.apply_focus({ action, ...action_origin });
  }

  confirm_action(confirmation) {
    const { confirmation_dialog, confirmation_text, confirmation_accept_button, confirmation_reject_button } =
      this.elements;
    confirmation_text.textContent = confirmation.question;
    confirmation_accept_button.textContent = confirmation.accept_label;
    const is_accept_first = confirmation.initial_focus === DIALOG_INITIAL_FOCUS.ACCEPT;
    const initial_focus_element = is_accept_first ? confirmation_accept_button : confirmation_reject_button;
    return this.show_dialog({
      dialog: confirmation_dialog,
      initial_focus_element,
      opened_by_keyboard: confirmation.opened_by_keyboard,
    });
  }

  show_dialog(dialog_opening) {
    const { dialog, initial_focus_element, opened_by_keyboard } = dialog_opening;
    return new Promise((resolve) => {
      dialog.addEventListener("close", () => resolve(dialog.returnValue === DIALOG_ACCEPTED), { once: true });
      this.is_dialog_armed = !(opened_by_keyboard && this.is_key_held);
      dialog.returnValue = "";
      dialog.showModal();
      initial_focus_element.focus();
      // The position field comes prefilled with the current position; selected, what is typed replaces it.
      initial_focus_element.select?.();
    });
  }
}
