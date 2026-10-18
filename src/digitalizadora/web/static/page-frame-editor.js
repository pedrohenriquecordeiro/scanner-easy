"use strict";

// The enlarged view where the crop frames of a page (or of the last scan of the quick mode) are checked and adjusted
// (the <dialog id="page-frame-dialog">). It wires the dialog to the pure functions of page-frame-geometry.js and the
// texts of frame-dialog-policy.js and decides nothing by itself. build_scan_page (application.js) creates one editor
// and hands it to the DocumentPanel and to the LastScanPanel; whoever opens it is the "owner" of the session:
//   owner = {find_target(identifier), attempt_edit(edit_request), report_failure(failure), can_edit(), announce(text),
//            restore_focus({target_identifier, action_origin})}
//   target = {title_text, image_alt_text, subject_text, gone_text, progress_text, rotation_degrees, crops,
//             build_preview_address(rotation_degrees), requests: {rotate_page(), set_crops(frames), detect_crops()},
//             describe_rotation(rotation_degrees, frame_count), describe_application(frame_count)}
// The owner calls handle_target_change(owner) whenever the thing being edited may have changed.
//
// What the dialog shows is a draft of the frames (0 to 2): dragging and pushing only change the draft, and "Aplicar"
// sends it. "Detectar automaticamente" and "Girar" are edits the server saves at once; every answer of the server
// enters through handle_target_change, so the draft turns with the page and the buttons follow the target.

const PRIMARY_POINTER_BUTTON = 0; // also what touch and pen report
const CLOSE_OUTCOMES = Object.freeze({ CANCELLED: "cancelled", APPLIED: "applied", TARGET_GONE: "target_gone" });
const GRIP_KINDS = Object.freeze({ CORNER: "corner", EDGE: "edge", MOVE: "move", ROTATE: "rotate" });
const DIALOG_KEY_EVENT_TYPES_HIDDEN_FROM_THE_PAGE = ["keydown", "keyup"];
const LOADING_STAGE_CLASS = "is-loading";
const NO_FRAME_INDEX = -1;
const FIRST_FRAME_INDEX = 0;

class PageFrameEditor {
  constructor(elements) {
    this.elements = elements;
    this.session = null;
    this.overlay = create_frame_overlay();
  }

  bind_events() {
    const { page_frame_dialog, frame_image, frame_move_button, frame_rotate_handle, frame_stage } = this.elements;
    this.elements.frame_overlay_host.append(this.overlay.container);
    this.bind_grip(frame_move_button, { kind: GRIP_KINDS.MOVE, name: GRIP_KINDS.MOVE });
    this.bind_grip(frame_rotate_handle, { kind: GRIP_KINDS.ROTATE, name: GRIP_KINDS.ROTATE });
    for (const [corner, handle_button] of Object.entries(this.elements.frame_corner_handles)) {
      this.bind_grip(handle_button, { kind: GRIP_KINDS.CORNER, name: corner });
    }
    for (const [edge, handle_button] of Object.entries(this.elements.frame_edge_handles)) {
      this.bind_grip(handle_button, { kind: GRIP_KINDS.EDGE, name: edge });
    }
    frame_stage.addEventListener("contextmenu", (menu_event) => menu_event.preventDefault());
    frame_image.addEventListener("load", () => this.mark_image_ready());
    frame_image.addEventListener("error", () => this.show_image_failure());
    this.elements.frame_select_button.addEventListener("click", () => this.select_other_frame());
    this.elements.frame_add_button.addEventListener("click", () => this.add_frame());
    this.elements.frame_remove_button.addEventListener("click", () => this.remove_frame());
    this.elements.frame_turn_button.addEventListener("click", () => this.turn_frame_output());
    this.elements.frame_detect_button.addEventListener("click", () => this.detect_frames());
    this.elements.frame_clear_button.addEventListener("click", () => this.clear_frames());
    this.elements.frame_rotate_button.addEventListener("click", () => this.rotate_page());
    this.elements.frame_cancel_button.addEventListener("click", () => this.close_with(CLOSE_OUTCOMES.CANCELLED));
    this.elements.frame_apply_button.addEventListener("click", () => this.apply_frames());
    page_frame_dialog.addEventListener("close", () => this.finish_session());
    for (const event_type of DIALOG_KEY_EVENT_TYPES_HIDDEN_FROM_THE_PAGE) {
      page_frame_dialog.addEventListener(event_type, (key_event) => this.keep_page_shortcuts_out(key_event), true);
    }
  }

  bind_grip(grip_element, grip) {
    grip_element.addEventListener("pointerdown", (pointer_event) =>
      this.start_drag({ grip_element, grip, pointer_event }),
    );
    grip_element.addEventListener("pointermove", (pointer_event) => this.continue_drag(pointer_event));
    grip_element.addEventListener("pointerup", (pointer_event) => this.end_drag(pointer_event));
    grip_element.addEventListener("pointercancel", (pointer_event) => this.end_drag(pointer_event));
    grip_element.addEventListener("keydown", (key_event) => this.nudge_with_key({ grip, key_event }));
  }

  keep_page_shortcuts_out(key_event) {
    // Space and Backspace are page shortcuts (scan, discard a page); inside the dialog they never reach the page.
    if (should_hide_key_from_page_shortcuts(key_event)) {
      key_event.stopPropagation();
    }
  }

  open(opening) {
    const { owner, target_identifier, action_origin } = opening;
    const target = owner.find_target(target_identifier);
    if (target === null || this.session !== null) {
      return;
    }
    const saved_frames = read_frames_from_crops(target.crops);
    this.session = {
      owner,
      target_identifier,
      action_origin,
      target,
      rotation_degrees: target.rotation_degrees,
      saved_frames,
      draft_frames: saved_frames.map(copy_frame),
      active_index: saved_frames.length === 0 ? NO_FRAME_INDEX : FIRST_FRAME_INDEX,
      outcome: CLOSE_OUTCOMES.CANCELLED,
      drag: null,
      is_opening_status_shown: false,
    };
    this.show_image();
    this.elements.page_frame_dialog.showModal();
    this.render();
    this.show_status(this.describe_opening());
    this.session.is_opening_status_shown = true;
    this.focus_the_active_frame();
  }

  describe_opening() {
    const { draft_frames } = this.session;
    if (draft_frames.length === 0) {
      return WHOLE_PAGE_DESCRIPTION;
    }
    const frame_text = this.describe_active_frame();
    return draft_frames.length === 1
      ? frame_text
      : `${describe_selected_frame(this.session.active_index + 1, draft_frames.length)} ${frame_text}`;
  }

  describe_active_frame() {
    const { draft_frames, active_index } = this.session;
    if (active_index === NO_FRAME_INDEX) {
      return WHOLE_PAGE_DESCRIPTION;
    }
    const label = describe_frame_label(active_index + 1);
    return describe_frame(draft_frames[active_index], { label, surface: this.read_stage_surface() });
  }

  focus_the_active_frame() {
    const { session } = this;
    const has_frame = session !== null && session.active_index !== NO_FRAME_INDEX;
    (has_frame ? this.elements.frame_move_button : this.elements.frame_add_button).focus();
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
    if (session.outcome === CLOSE_OUTCOMES.TARGET_GONE) {
      session.owner.announce(session.target.gone_text);
    } else if (session.outcome === CLOSE_OUTCOMES.CANCELLED && this.is_dirty(session)) {
      session.owner.announce(FRAME_CHANGES_DISCARDED_TEXT);
    }
    session.owner.restore_focus({
      target_identifier: session.target_identifier,
      action_origin: session.action_origin,
    });
  }

  is_dirty(session) {
    return !frame_lists_are_equal(session.draft_frames, session.saved_frames);
  }

  // The thing being edited may have changed (an answer of this dialog's own edits, another tab, a new page): the
  // target the dialog shows follows it. A call from an owner that is not the one editing means nothing here.
  handle_target_change(owner) {
    if (this.session === null || this.session.owner !== owner) {
      return;
    }
    const target = owner.find_target(this.session.target_identifier);
    if (target === null) {
      this.close_with(CLOSE_OUTCOMES.TARGET_GONE);
      return;
    }
    this.follow_target(target);
  }

  follow_target(target) {
    const session = this.session;
    const quarter_turns = count_quarter_turns(session.rotation_degrees, target.rotation_degrees);
    const was_clean = !this.is_dirty(session);
    const saved_frames = read_frames_from_crops(target.crops);
    // Frames that were only a draft turn with the page; ones that were just the saved frames become the new saved ones.
    const draft_frames = was_clean
      ? saved_frames.map(copy_frame)
      : turn_frames_by_quarter_turns(session.draft_frames, quarter_turns);
    session.target = target;
    session.saved_frames = saved_frames;
    session.draft_frames = draft_frames;
    session.active_index = this.keep_active_frame(draft_frames);
    if (quarter_turns !== 0) {
      session.rotation_degrees = target.rotation_degrees;
      this.show_image();
    }
    this.render();
  }

  keep_active_frame(draft_frames) {
    if (draft_frames.length === 0) {
      return NO_FRAME_INDEX;
    }
    return Math.min(Math.max(this.session.active_index, FIRST_FRAME_INDEX), draft_frames.length - 1);
  }

  show_image() {
    const session = this.session;
    this.elements.frame_stage.classList.add(LOADING_STAGE_CLASS);
    this.elements.frame_image.alt = session.target.image_alt_text;
    this.elements.frame_image.src = session.target.build_preview_address(session.rotation_degrees);
  }

  mark_image_ready() {
    this.elements.frame_stage.classList.remove(LOADING_STAGE_CLASS);
    const session = this.session;
    if (session === null) {
      return;
    }
    // The size of the picture is only known now: the angles in the texts and the place of the rotate handle depend on it.
    this.render();
    if (session.is_opening_status_shown) {
      this.show_status(this.describe_opening());
      session.is_opening_status_shown = true;
    }
  }

  show_image_failure() {
    if (this.session !== null) {
      this.show_status(describe_frame_image_failed(this.session.target.subject_text));
    }
  }

  read_stage_surface() {
    const stage_box = this.elements.frame_stage.getBoundingClientRect();
    return { width: stage_box.width, height: stage_box.height };
  }

  render() {
    const session = this.session;
    this.elements.page_frame_title.textContent = session.target.title_text;
    update_frame_overlay(this.overlay, session.draft_frames, session.active_index);
    this.render_handles();
    this.render_other_frame();
    this.render_controls();
  }

  render_handles() {
    const { draft_frames, active_index } = this.session;
    const has_frame = active_index !== NO_FRAME_INDEX;
    const handle_elements = [
      this.elements.frame_move_button,
      this.elements.frame_rotate_handle,
      ...Object.values(this.elements.frame_corner_handles),
      ...Object.values(this.elements.frame_edge_handles),
    ];
    handle_elements.forEach((element) => {
      element.hidden = !has_frame;
    });
    if (!has_frame) {
      return;
    }
    const frame = draft_frames[active_index];
    const surface = this.read_stage_surface();
    const frame_context = { frame_number: active_index + 1, frame_count: draft_frames.length };
    this.elements.frame_move_button.style.clipPath = describe_clip_path(frame);
    this.elements.frame_move_button.setAttribute("aria-label", describe_grip_label(MOVE_HANDLE_LABEL, frame_context));
    for (const [corner, handle_button] of Object.entries(this.elements.frame_corner_handles)) {
      this.place_handle(handle_button, frame[corner]);
      handle_button.setAttribute("aria-label", describe_handle_label(read_corner_label(corner), frame_context));
    }
    for (const [edge, handle_button] of Object.entries(this.elements.frame_edge_handles)) {
      this.place_handle(handle_button, find_edge_midpoint(frame, edge));
      handle_button.setAttribute("aria-label", describe_handle_label(read_edge_label(edge), frame_context));
    }
    this.place_handle(this.elements.frame_rotate_handle, find_rotate_handle_point(frame, surface));
    this.elements.frame_rotate_handle.setAttribute(
      "aria-label",
      describe_grip_label(ROTATE_HANDLE_LABEL, frame_context),
    );
  }

  place_handle(handle_button, point) {
    const { left_percent, top_percent } = describe_handle_style(point);
    handle_button.style.left = `${left_percent}%`;
    handle_button.style.top = `${top_percent}%`;
  }

  render_other_frame() {
    const { draft_frames, active_index } = this.session;
    const select_button = this.elements.frame_select_button;
    const other_index = draft_frames.length === MAXIMUM_FRAMES ? MAXIMUM_FRAMES - 1 - active_index : NO_FRAME_INDEX;
    select_button.hidden = other_index === NO_FRAME_INDEX;
    if (other_index === NO_FRAME_INDEX) {
      return;
    }
    select_button.style.clipPath = describe_clip_path(draft_frames[other_index]);
    select_button.setAttribute("aria-label", describe_select_frame_label(other_index + 1));
  }

  // Also called by the owners whenever a scan or an edit starts or ends.
  render_controls() {
    const session = this.session;
    if (session === null) {
      return;
    }
    const can_edit = session.owner.can_edit();
    const frame_count = session.draft_frames.length;
    const has_frame = session.active_index !== NO_FRAME_INDEX;
    this.elements.frame_add_button.disabled = frame_count >= MAXIMUM_FRAMES;
    this.elements.frame_remove_button.disabled = !has_frame;
    this.elements.frame_turn_button.disabled = !has_frame;
    this.elements.frame_turn_button.setAttribute(
      "aria-label",
      has_frame ? describe_rotate_frame_label(session.active_index + 1) : "Girar a moldura 90 graus para a direita",
    );
    this.elements.frame_detect_button.disabled = !can_edit;
    this.elements.frame_rotate_button.disabled = !can_edit;
    this.elements.frame_apply_button.disabled = !can_edit || !this.is_dirty(session);
  }

  show_status(text) {
    if (this.session !== null) {
      this.session.is_opening_status_shown = false;
    }
    this.elements.frame_status.textContent = text;
  }

  read_active_frame() {
    const { draft_frames, active_index } = this.session;
    return draft_frames[active_index];
  }

  replace_active_frame(frame) {
    const { draft_frames, active_index } = this.session;
    this.session.draft_frames = draft_frames.map((existing_frame, index) => (index === active_index ? frame : existing_frame));
  }

  // Two frames are always kept in reading order, like the server keeps them; the selected one stays the selected one.
  settle_frame_order() {
    const session = this.session;
    const active_frame = session.draft_frames[session.active_index];
    session.draft_frames = put_frames_in_reading_order(session.draft_frames);
    session.active_index = session.draft_frames.indexOf(active_frame);
  }

  start_drag(drag_start) {
    const { grip_element, grip, pointer_event } = drag_start;
    if (this.session === null || this.session.active_index === NO_FRAME_INDEX) {
      return;
    }
    // A second finger on another handle does not take the drag from the first one.
    if (pointer_event.button !== PRIMARY_POINTER_BUTTON || this.session.drag !== null) {
      return;
    }
    grip_element.setPointerCapture(pointer_event.pointerId);
    this.session.drag = {
      grip_element,
      grip,
      pointer_identifier: pointer_event.pointerId,
      start_frame: this.read_active_frame(),
      start_position: { x: pointer_event.clientX, y: pointer_event.clientY },
      was_refused: false,
    };
  }

  continue_drag(pointer_event) {
    const drag = this.session === null ? null : this.session.drag;
    if (drag === null || drag.pointer_identifier !== pointer_event.pointerId) {
      return;
    }
    const moved_frame = this.measure_dragged_frame(drag, pointer_event);
    // A move that would bend the frame out of shape is ignored; the frame keeps the last good place.
    drag.was_refused = moved_frame === null;
    if (moved_frame !== null) {
      this.replace_active_frame(moved_frame);
      this.render();
    }
  }

  measure_dragged_frame(drag, pointer_event) {
    // Always measured from where the drag began, so rounding never piles up.
    const box = this.elements.frame_stage.getBoundingClientRect();
    const surface = { width: box.width, height: box.height };
    const shift = convert_pointer_shift(
      {
        horizontal_pixels: pointer_event.clientX - drag.start_position.x,
        vertical_pixels: pointer_event.clientY - drag.start_position.y,
      },
      surface,
    );
    const { kind, name } = drag.grip;
    if (kind === GRIP_KINDS.MOVE) {
      return move_frame(drag.start_frame, shift);
    }
    if (kind === GRIP_KINDS.CORNER) {
      return move_corner(drag.start_frame, { corner: name, ...shift });
    }
    if (kind === GRIP_KINDS.EDGE) {
      return move_edge(drag.start_frame, { edge: name, ...shift, surface });
    }
    const centre = find_frame_centre(drag.start_frame);
    const turn_points = {
      centre: { x: box.left + centre.x * box.width, y: box.top + centre.y * box.height },
      start_point: drag.start_position,
      current_point: { x: pointer_event.clientX, y: pointer_event.clientY },
    };
    return rotate_frame(drag.start_frame, { degrees: measure_pointer_turn(turn_points), surface });
  }

  end_drag(pointer_event) {
    const drag = this.session === null ? null : this.session.drag;
    if (drag === null || drag.pointer_identifier !== pointer_event.pointerId) {
      return;
    }
    drag.grip_element.releasePointerCapture(drag.pointer_identifier);
    this.session.drag = null;
    this.settle_frame_order();
    this.render();
    this.show_status(drag.was_refused ? INVALID_FRAME_MOVE_TEXT : this.describe_active_frame());
  }

  nudge_with_key(key_press) {
    const { grip, key_event } = key_press;
    const direction = read_nudge_direction(key_event.code);
    if (this.session === null || this.session.active_index === NO_FRAME_INDEX || direction === null) {
      return;
    }
    key_event.preventDefault();
    const nudged_frame = this.measure_nudged_frame({ grip, direction, key_event });
    if (nudged_frame === null) {
      this.show_status(INVALID_FRAME_MOVE_TEXT);
      return;
    }
    this.replace_active_frame(nudged_frame);
    this.settle_frame_order();
    this.render();
    this.show_status(this.describe_nudged_handle(grip));
  }

  measure_nudged_frame(nudge) {
    const { grip, direction, key_event } = nudge;
    const frame = this.read_active_frame();
    const surface = this.read_stage_surface();
    const step = read_nudge_step(key_event);
    if (grip.kind === GRIP_KINDS.CORNER) {
      return nudge_corner(frame, { corner: grip.name, direction, step });
    }
    if (grip.kind === GRIP_KINDS.EDGE) {
      return nudge_edge(frame, { edge: grip.name, direction, step, surface });
    }
    if (grip.kind === GRIP_KINDS.ROTATE) {
      return nudge_rotation(frame, { direction, degrees: read_rotation_nudge_degrees(key_event), surface });
    }
    return nudge_whole_frame(frame, { direction, step });
  }

  describe_nudged_handle(grip) {
    const frame = this.read_active_frame();
    if (grip.kind === GRIP_KINDS.CORNER) {
      return describe_corner_position(frame, grip.name);
    }
    if (grip.kind === GRIP_KINDS.EDGE) {
      return describe_edge_position(frame, grip.name);
    }
    return this.describe_active_frame();
  }

  select_other_frame() {
    const session = this.session;
    if (session === null || session.draft_frames.length !== MAXIMUM_FRAMES) {
      return;
    }
    session.active_index = MAXIMUM_FRAMES - 1 - session.active_index;
    this.render();
    this.show_status(
      `${describe_selected_frame(session.active_index + 1, session.draft_frames.length)} ${this.describe_active_frame()}`,
    );
    this.elements.frame_move_button.focus();
  }

  add_frame() {
    const session = this.session;
    if (session === null) {
      return;
    }
    const new_frame = suggest_new_frame(session.draft_frames);
    if (new_frame === null) {
      this.show_status(FRAME_LIMIT_TEXT);
      return;
    }
    session.draft_frames = put_frames_in_reading_order([...session.draft_frames, new_frame]);
    session.active_index = session.draft_frames.indexOf(new_frame);
    this.render();
    this.show_status(`${describe_frame_added(session.active_index + 1)} ${this.describe_active_frame()}`);
    this.elements.frame_move_button.focus();
  }

  remove_frame() {
    const session = this.session;
    if (session === null || session.active_index === NO_FRAME_INDEX) {
      return;
    }
    const removed_number = session.active_index + 1;
    session.draft_frames = session.draft_frames.filter((_, index) => index !== session.active_index);
    session.active_index = session.draft_frames.length === 0 ? NO_FRAME_INDEX : FIRST_FRAME_INDEX;
    this.render();
    this.show_status(describe_frame_removed(removed_number));
    this.focus_the_active_frame();
  }

  turn_frame_output() {
    const session = this.session;
    if (session === null || session.active_index === NO_FRAME_INDEX) {
      return;
    }
    this.replace_active_frame(turn_frame_output_clockwise(this.read_active_frame()));
    this.render();
    this.show_status(describe_frame_output_turned(session.active_index + 1));
  }

  clear_frames() {
    const session = this.session;
    if (session === null) {
      return;
    }
    session.draft_frames = [];
    session.active_index = NO_FRAME_INDEX;
    this.render();
    this.show_status(WHOLE_PAGE_DESCRIPTION);
  }

  async detect_frames() {
    if (this.session === null) {
      return;
    }
    const { target } = this.session;
    const body = await this.run_edit({
      button: this.elements.frame_detect_button,
      edit_request: target.requests.detect_crops(),
    });
    if (body === null || this.session === null) {
      return;
    }
    if (body.crops_detected) {
      const session = this.session;
      session.draft_frames = session.saved_frames.map(copy_frame);
      session.active_index = session.draft_frames.length === 0 ? NO_FRAME_INDEX : FIRST_FRAME_INDEX;
      this.render();
      this.show_status(
        describe_detected_frames({
          frame_count: session.draft_frames.length,
          ignored_region_count: body.ignored_region_count ?? 0,
        }),
      );
    } else {
      this.show_status(describe_no_frame_detected(target.subject_text));
    }
  }

  async rotate_page() {
    if (this.session === null) {
      return;
    }
    const body = await this.run_edit({
      button: this.elements.frame_rotate_button,
      edit_request: this.session.target.requests.rotate_page(),
    });
    if (body === null || this.session === null) {
      return;
    }
    const { target, rotation_degrees, saved_frames } = this.session;
    this.show_status(target.describe_rotation(rotation_degrees, saved_frames.length));
  }

  async apply_frames() {
    const session = this.session;
    if (session === null || !session.owner.can_edit() || !this.is_dirty(session)) {
      return;
    }
    const crops_request = build_crops_request_body(session.draft_frames);
    const body = await this.run_edit({
      button: this.elements.frame_apply_button,
      edit_request: session.target.requests.set_crops(session.draft_frames),
    });
    if (body === null || this.session === null) {
      return;
    }
    const application_text = this.session.target.describe_application(crops_request.crops.length);
    if (application_text !== null) {
      this.session.owner.announce(application_text);
    }
    this.close_with(CLOSE_OUTCOMES.APPLIED);
  }

  async run_edit(frame_edit) {
    const { button, edit_request } = frame_edit;
    const { session } = this;
    if (session === null || !session.owner.can_edit()) {
      return null;
    }
    if (session.target.progress_text !== null) {
      this.show_status(session.target.progress_text);
    }
    const { body, failure } = await session.owner.attempt_edit(edit_request);
    if (failure !== null) {
      session.owner.report_failure(failure);
      this.show_status(failure.message);
    }
    // The buttons were disabled while the edit ran, which took the focus off the one that was used.
    if (this.session !== null) {
      button.focus();
    }
    return body;
  }
}
