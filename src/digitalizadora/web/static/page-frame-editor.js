"use strict";

// The enlarged view of one page, where its crop frame is checked and adjusted (the <dialog id="page-frame-dialog">).
// It wires the dialog to the pure functions of page-frame-geometry.js and the texts of document-page-policy.js and
// decides nothing by itself. build_scan_page (application.js) creates it with editor_services = {attempt_edit,
// report_failure, can_edit, find_page, announce, restore_focus}, all of them answered by the DocumentPanel.
//
// What the dialog shows is a draft of the frame: dragging and pushing only change the draft, and "Aplicar" sends it.
// "Detectar automaticamente" and "Girar" are edits the server saves at once; every answer of the server enters through
// handle_document_change, so the draft turns with the page and the buttons follow the document.

const MOVE_GRIP_NAME = "move";
const PRIMARY_POINTER_BUTTON = 0; // also what touch and pen report
const CLOSE_OUTCOMES = Object.freeze({ CANCELLED: "cancelled", APPLIED: "applied", PAGE_GONE: "page_gone" });
const DIALOG_KEY_EVENT_TYPES_HIDDEN_FROM_THE_PAGE = ["keydown", "keyup"];
const LOADING_STAGE_CLASS = "is-loading";

function place_frame_on_element(element, frame) {
  const { left_percent, top_percent, width_percent, height_percent } = describe_frame_style(frame);
  element.style.left = `${left_percent}%`;
  element.style.top = `${top_percent}%`;
  element.style.width = `${width_percent}%`;
  element.style.height = `${height_percent}%`;
}

class PageFrameEditor {
  constructor(elements, editor_services) {
    this.elements = elements;
    this.editor_services = editor_services;
    this.session = null;
  }

  bind_events() {
    const { page_frame_dialog, frame_image, frame_move_button, frame_handles } = this.elements;
    this.bind_grip(frame_move_button, MOVE_GRIP_NAME);
    for (const [handle, handle_button] of Object.entries(frame_handles)) {
      handle_button.setAttribute("aria-label", read_handle_label(handle));
      this.bind_grip(handle_button, handle);
    }
    this.elements.frame_stage.addEventListener("contextmenu", (menu_event) => menu_event.preventDefault());
    frame_image.addEventListener("load", () => this.mark_image_ready());
    frame_image.addEventListener("error", () => this.show_status(FRAME_IMAGE_FAILED_TEXT));
    this.elements.frame_detect_button.addEventListener("click", () => this.detect_frame());
    this.elements.frame_clear_button.addEventListener("click", () => this.clear_frame());
    this.elements.frame_rotate_button.addEventListener("click", () => this.rotate_page());
    this.elements.frame_cancel_button.addEventListener("click", () => this.close_with(CLOSE_OUTCOMES.CANCELLED));
    this.elements.frame_apply_button.addEventListener("click", () => this.apply_frame());
    page_frame_dialog.addEventListener("close", () => this.finish_session());
    for (const event_type of DIALOG_KEY_EVENT_TYPES_HIDDEN_FROM_THE_PAGE) {
      page_frame_dialog.addEventListener(event_type, (key_event) => this.keep_page_shortcuts_out(key_event), true);
    }
  }

  bind_grip(grip_element, grip_name) {
    grip_element.addEventListener("pointerdown", (pointer_event) =>
      this.start_drag({ grip_element, grip_name, pointer_event }),
    );
    grip_element.addEventListener("pointermove", (pointer_event) => this.continue_drag(pointer_event));
    grip_element.addEventListener("pointerup", (pointer_event) => this.end_drag(pointer_event));
    grip_element.addEventListener("pointercancel", (pointer_event) => this.end_drag(pointer_event));
    grip_element.addEventListener("keydown", (key_event) => this.nudge_with_key({ grip_name, key_event }));
  }

  keep_page_shortcuts_out(key_event) {
    // Space and Backspace are page shortcuts (scan, discard a page); inside the dialog they never reach the page.
    if (should_hide_key_from_page_shortcuts(key_event)) {
      key_event.stopPropagation();
    }
  }

  open(opening) {
    const found_page = this.editor_services.find_page(opening.page_identifier);
    if (found_page === null || this.session !== null) {
      return;
    }
    const saved_frame = read_frame_from_crop(found_page.page.crop);
    this.session = {
      page_identifier: opening.page_identifier,
      action_origin: opening.action_origin,
      rotation_degrees: found_page.page.rotation_degrees,
      position: found_page.position,
      page_count: found_page.page_count,
      saved_frame,
      draft_frame: { ...saved_frame },
      outcome: CLOSE_OUTCOMES.CANCELLED,
      drag: null,
    };
    this.show_image();
    this.render();
    this.show_status(describe_frame(saved_frame));
    this.elements.page_frame_dialog.showModal();
    this.elements.frame_move_button.focus();
  }

  close_with(outcome) {
    if (this.session === null) {
      return;
    }
    this.session.outcome = outcome;
    this.elements.page_frame_dialog.close();
  }

  finish_session() {
    const session = this.session;
    if (session === null) {
      return;
    }
    this.session = null;
    if (session.outcome === CLOSE_OUTCOMES.PAGE_GONE) {
      this.editor_services.announce(FRAME_PAGE_GONE_TEXT);
    } else if (session.outcome === CLOSE_OUTCOMES.CANCELLED && this.is_dirty(session)) {
      this.editor_services.announce(FRAME_CHANGES_DISCARDED_TEXT);
    }
    this.editor_services.restore_focus({
      action: DOCUMENT_ACTIONS.FRAME_CLOSED,
      acted_page_identifier: session.page_identifier,
      ...session.action_origin,
    });
  }

  is_dirty(session) {
    return !frames_are_equal(session.draft_frame, session.saved_frame);
  }

  // The document changed (an answer of this dialog's own edits, another tab, a new page): the page the dialog shows
  // follows it.
  handle_document_change() {
    if (this.session === null) {
      return;
    }
    const found_page = this.editor_services.find_page(this.session.page_identifier);
    if (found_page === null) {
      this.close_with(CLOSE_OUTCOMES.PAGE_GONE);
      return;
    }
    this.follow_page(found_page);
  }

  follow_page(found_page) {
    const session = this.session;
    const quarter_turns = count_quarter_turns(session.rotation_degrees, found_page.page.rotation_degrees);
    const was_clean = !this.is_dirty(session);
    const saved_frame = read_frame_from_crop(found_page.page.crop);
    // A frame that was only a draft turns with the page; one that was just the saved frame becomes the new saved one.
    const turned_draft_frame = turn_frame_by_quarter_turns(session.draft_frame, quarter_turns);
    session.draft_frame = was_clean ? { ...saved_frame } : turned_draft_frame;
    session.saved_frame = saved_frame;
    session.position = found_page.position;
    session.page_count = found_page.page_count;
    if (quarter_turns !== 0) {
      session.rotation_degrees = found_page.page.rotation_degrees;
      this.show_image();
    }
    this.render();
  }

  show_image() {
    const session = this.session;
    this.elements.frame_stage.classList.add(LOADING_STAGE_CLASS);
    this.elements.frame_image.alt = `Página ${session.position} ampliada`;
    this.elements.frame_image.src = build_page_preview_address(session.page_identifier, session.rotation_degrees);
  }

  mark_image_ready() {
    this.elements.frame_stage.classList.remove(LOADING_STAGE_CLASS);
  }

  render() {
    const session = this.session;
    this.elements.page_frame_title.textContent = describe_frame_dialog_title(session);
    this.render_frame();
    this.render_controls();
  }

  render_frame() {
    place_frame_on_element(this.elements.frame_box, this.session.draft_frame);
    place_frame_on_element(this.elements.frame_cutout, this.session.draft_frame);
  }

  // Also called by the DocumentPanel whenever a scan or an edit starts or ends.
  render_controls() {
    const session = this.session;
    if (session === null) {
      return;
    }
    const can_edit = this.editor_services.can_edit();
    this.elements.frame_detect_button.disabled = !can_edit;
    this.elements.frame_rotate_button.disabled = !can_edit;
    this.elements.frame_apply_button.disabled = !can_edit || !this.is_dirty(session);
  }

  show_status(text) {
    this.elements.frame_status.textContent = text;
  }

  start_drag(drag_start) {
    const { grip_element, grip_name, pointer_event } = drag_start;
    if (this.session === null || pointer_event.button !== PRIMARY_POINTER_BUTTON) {
      return;
    }
    grip_element.setPointerCapture(pointer_event.pointerId);
    this.session.drag = {
      grip_element,
      grip_name,
      pointer_identifier: pointer_event.pointerId,
      start_frame: this.session.draft_frame,
      start_position: { x: pointer_event.clientX, y: pointer_event.clientY },
    };
  }

  continue_drag(pointer_event) {
    const drag = this.session === null ? null : this.session.drag;
    if (drag === null || drag.pointer_identifier !== pointer_event.pointerId) {
      return;
    }
    // Always measured from where the drag began, so rounding never piles up.
    const box = this.elements.frame_stage.getBoundingClientRect();
    const shift = convert_pointer_shift(
      {
        horizontal_pixels: pointer_event.clientX - drag.start_position.x,
        vertical_pixels: pointer_event.clientY - drag.start_position.y,
      },
      { width: box.width, height: box.height },
    );
    this.session.draft_frame =
      drag.grip_name === MOVE_GRIP_NAME
        ? move_frame(drag.start_frame, shift)
        : resize_frame(drag.start_frame, { handle: drag.grip_name, ...shift });
    this.render();
  }

  end_drag(pointer_event) {
    const drag = this.session === null ? null : this.session.drag;
    if (drag === null || drag.pointer_identifier !== pointer_event.pointerId) {
      return;
    }
    drag.grip_element.releasePointerCapture(drag.pointer_identifier);
    this.session.drag = null;
    this.show_status(describe_frame(this.session.draft_frame));
  }

  nudge_with_key(key_press) {
    const { grip_name, key_event } = key_press;
    const direction = read_nudge_direction(key_event.code);
    if (this.session === null || direction === null) {
      return;
    }
    key_event.preventDefault();
    const nudge = { direction, step: read_nudge_step(key_event) };
    const is_move_grip = grip_name === MOVE_GRIP_NAME;
    const frame = this.session.draft_frame;
    this.session.draft_frame = is_move_grip
      ? nudge_whole_frame(frame, nudge)
      : nudge_handle(frame, { handle: grip_name, ...nudge });
    this.render();
    this.show_status(
      is_move_grip
        ? describe_frame(this.session.draft_frame)
        : describe_handle_position(this.session.draft_frame, grip_name),
    );
  }

  clear_frame() {
    if (this.session === null) {
      return;
    }
    this.session.draft_frame = { ...WHOLE_PAGE_FRAME };
    this.render();
    this.show_status(describe_frame(this.session.draft_frame));
  }

  async detect_frame() {
    if (this.session === null) {
      return;
    }
    const session = this.session;
    const body = await this.run_page_edit({
      button: this.elements.frame_detect_button,
      edit_request: { method: "POST", path: build_page_crop_detection_path(session.page_identifier) },
    });
    if (body === null || this.session === null) {
      return;
    }
    if (body.crop_detected) {
      this.session.draft_frame = { ...this.session.saved_frame };
      this.render();
      this.show_status(describe_detected_frame(this.session.draft_frame));
    } else {
      this.show_status(NO_FRAME_DETECTED_TEXT);
    }
  }

  async rotate_page() {
    if (this.session === null) {
      return;
    }
    const session = this.session;
    const body = await this.run_page_edit({
      button: this.elements.frame_rotate_button,
      edit_request: { method: "POST", path: build_page_rotation_path(session.page_identifier) },
    });
    if (body === null || this.session === null) {
      return;
    }
    const { position, rotation_degrees, saved_frame } = this.session;
    const crop = build_crop_request_body(saved_frame).crop;
    this.show_status(describe_page_rotation_result({ position, rotation_degrees, crop }));
  }

  async apply_frame() {
    const session = this.session;
    if (session === null || !this.editor_services.can_edit() || !this.is_dirty(session)) {
      return;
    }
    const crop_request = build_crop_request_body(session.draft_frame);
    const body = await this.run_page_edit({
      button: this.elements.frame_apply_button,
      edit_request: { method: "PUT", path: build_page_crop_path(session.page_identifier), body: crop_request },
    });
    if (body === null || this.session === null) {
      return;
    }
    this.editor_services.announce(
      describe_crop_application({ position: this.session.position, crop: crop_request.crop }),
    );
    this.close_with(CLOSE_OUTCOMES.APPLIED);
  }

  async run_page_edit(page_edit) {
    const { button, edit_request } = page_edit;
    if (this.session === null || !this.editor_services.can_edit()) {
      return null;
    }
    const { body, failure } = await this.editor_services.attempt_edit(edit_request);
    if (failure !== null) {
      this.editor_services.report_failure(failure);
      this.show_status(failure.message);
    }
    // The buttons were disabled while the edit ran, which took the focus off the one that was used.
    if (this.session !== null) {
      button.focus();
    }
    return body;
  }
}
