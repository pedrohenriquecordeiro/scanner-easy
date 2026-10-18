"use strict";

// Wires the "Última digitalização" panel of the quick mode to the pure rules of last-scan-policy.js; it decides nothing
// by itself. build_scan_page (application.js) creates it with panel_services = {send_request, format_byte_count,
// error_banner, frame_editor, focus_scan_button, refresh_page_controls, request_state_refresh}. The panel shows the
// files of the last scan with their frames over a thumbnail, turns the scan with "Girar" and opens the same frame
// editor as the Documento mode with "Ampliar"; every adjustment rewrites the saved files from the original the server
// kept. Uses IDLE_PHASE and can_edit_last_scan of scan-trigger-policy.js, the frame functions of page-frame-geometry.js,
// the texts of frame-dialog-policy.js, create_frame_overlay and update_frame_overlay of frame-overlay.js and
// read_action_origin of document-panel.js.

const LAST_SCAN_EDIT_STATUS_CLEARED = "";
const LAST_SCAN_ENLARGED_ALT_TEXT = "Última digitalização ampliada";

class LastScanPanel {
  constructor(elements, panel_services) {
    this.elements = elements;
    this.panel_services = panel_services;
    this.overlay = create_frame_overlay();
    this.last_result = null;
    this.shown_thumbnail_address = null;
    this.server_revision = 0;
    this.edit_serial = 0;
    this.is_edit_pending = false;
    this.is_shown_in_this_mode = true;
    this.scan_activity = { scan_phase: IDLE_PHASE, is_start_request_pending: false };
    this.editor_owner = this.build_editor_owner();
  }

  bind_events() {
    const { last_scan_thumbnail, last_scan_thumbnail_frame } = this.elements;
    last_scan_thumbnail_frame.append(this.overlay.container);
    last_scan_thumbnail.addEventListener("load", () => this.fit_thumbnail_frame());
    // A click on the picture is a convenience of the mouse; the keyboard has the "Ampliar" button.
    last_scan_thumbnail_frame.addEventListener("click", () => this.enlarge_last_scan(POINTER_ORIGIN));
    this.elements.last_scan_rotate_button.addEventListener("click", (event) =>
      this.rotate_last_scan(read_action_origin(event)),
    );
    this.elements.last_scan_enlarge_button.addEventListener("click", (event) =>
      this.enlarge_last_scan(read_action_origin(event)),
    );
  }

  fit_thumbnail_frame() {
    const thumbnail = this.elements.last_scan_thumbnail;
    const { naturalWidth, naturalHeight } = thumbnail;
    if (naturalWidth > 0 && naturalHeight > 0) {
      this.elements.last_scan_thumbnail_frame.style.aspectRatio = `${naturalWidth} / ${naturalHeight}`;
    }
  }

  // What the frame editor needs from its owner (see page-frame-editor.js).
  build_editor_owner() {
    return {
      find_target: (scan_identifier) => this.build_editor_target(scan_identifier),
      attempt_edit: (edit_request) => this.attempt_edit(edit_request),
      report_failure: (failure) => this.report_failure(failure),
      can_edit: () => this.can_edit(),
      announce: (text) => this.show_status(text),
      restore_focus: (focus_request) => this.restore_focus(focus_request.action_origin),
    };
  }

  build_editor_target(scan_identifier) {
    const result = this.last_result;
    if (result === null || result.scan_identifier !== scan_identifier) {
      return null;
    }
    return {
      title_text: LAST_SCAN_TITLE_TEXT,
      image_alt_text: LAST_SCAN_ENLARGED_ALT_TEXT,
      subject_text: LAST_SCAN_SUBJECT_TEXT,
      gone_text: LAST_SCAN_GONE_TEXT,
      progress_text: FRAME_REWRITING_TEXT,
      rotation_degrees: result.rotation_degrees,
      crops: result.crops,
      build_preview_address: (rotation_degrees) => build_last_scan_preview_address(scan_identifier, rotation_degrees),
      requests: {
        rotate_page: () => ({ method: "POST", path: LAST_SCAN_ROTATION_PATH }),
        set_crops: (frames) => ({ method: "PUT", path: LAST_SCAN_CROPS_PATH, body: build_crops_request_body(frames) }),
        detect_crops: () => ({ method: "POST", path: LAST_SCAN_CROPS_DETECTION_PATH }),
      },
      describe_rotation: (rotation_degrees, frame_count) =>
        describe_last_scan_rotation_for_dialog(rotation_degrees, frame_count),
      // The panel itself says what an application did to the files.
      describe_application: () => null,
    };
  }

  apply_scan_activity(scan_activity) {
    this.scan_activity = scan_activity;
    this.render_controls();
  }

  // The state of the server. A state asked for before the last adjustment ended is older than what the panel shows.
  apply_server_state(server_state) {
    const { last_result, last_result_revision, edit_epoch } = server_state;
    if (this.is_edit_pending || edit_epoch !== this.edit_serial) {
      return;
    }
    this.last_result = last_result;
    this.server_revision = last_result_revision;
    this.render();
    this.panel_services.frame_editor.handle_target_change(this.editor_owner);
  }

  read_edit_epoch() {
    // Each adjustment that ends moves it on, so a state asked for before it ended can be told from a newer one.
    return this.edit_serial;
  }

  set_shown_in_this_mode(is_shown) {
    this.is_shown_in_this_mode = is_shown;
    this.render();
  }

  is_edit_request_pending() {
    return this.is_edit_pending;
  }

  can_edit() {
    const result = this.last_result;
    return (
      result !== null &&
      can_edit_last_scan(this.scan_activity, { is_editable: result.is_editable === true, is_edit_pending: this.is_edit_pending })
    );
  }

  show_status(text) {
    // Emptied first, so the same text written again is a change a screen reader announces.
    this.elements.last_scan_status.textContent = LAST_SCAN_EDIT_STATUS_CLEARED;
    this.elements.last_scan_status.textContent = text;
  }

  clear_status() {
    this.elements.last_scan_status.textContent = LAST_SCAN_EDIT_STATUS_CLEARED;
  }

  render() {
    const result = this.last_result;
    this.elements.last_scan_panel.hidden = result === null || !this.is_shown_in_this_mode;
    if (result === null) {
      return;
    }
    const { last_scan_thumbnail, last_scan_hint } = this.elements;
    const thumbnail_address = build_last_scan_thumbnail_address(
      choose_last_scan_thumbnail_version({ revision: this.server_revision, edit_serial: this.edit_serial }),
    );
    // The page keeps the address itself: a browser answers img.src with the full address, never the one it was given.
    if (this.shown_thumbnail_address !== thumbnail_address) {
      last_scan_thumbnail.src = thumbnail_address;
      this.shown_thumbnail_address = thumbnail_address;
    }
    last_scan_thumbnail.alt = describe_last_scan_thumbnail_label(result.file_names);
    update_frame_overlay(this.overlay, read_frames_from_crops(result.crops), NO_ACTIVE_FRAME);
    this.elements.last_scan_file_names.textContent = result.file_names.join("\n");
    this.elements.last_scan_size.textContent = this.panel_services.format_byte_count(result.total_size_in_bytes);
    this.elements.last_scan_time.textContent = format_scan_time(result.scanned_at);
    last_scan_hint.textContent = result.is_editable === true ? LAST_SCAN_HINT_TEXT : LAST_SCAN_NOT_EDITABLE_HINT_TEXT;
    this.render_controls();
  }

  render_controls() {
    const can_edit = this.can_edit();
    this.elements.last_scan_rotate_button.disabled = !can_edit;
    this.elements.last_scan_enlarge_button.disabled = !can_edit;
    this.panel_services.frame_editor.render_controls();
  }

  notify_activity_change() {
    this.render_controls();
    this.panel_services.refresh_page_controls();
  }

  async attempt_edit(edit_request) {
    const previous_file_names = this.last_result === null ? [] : [...this.last_result.file_names];
    this.is_edit_pending = true;
    this.show_status(FRAME_REWRITING_TEXT);
    this.notify_activity_change();
    let answer = null;
    let failure = null;
    try {
      answer = await this.panel_services.send_request(edit_request.method, edit_request.path, edit_request.body);
      this.panel_services.error_banner.report_action_error(null);
      this.accept_edit_answer({ edit_request, previous_file_names, answer });
    } catch (error) {
      failure = error;
      this.clear_status();
    } finally {
      this.is_edit_pending = false;
      this.edit_serial += 1;
      this.notify_activity_change();
    }
    return { body: answer, failure };
  }

  accept_edit_answer(edited) {
    const { edit_request, previous_file_names, answer } = edited;
    this.last_result = answer.last_result;
    this.show_status(
      describe_last_scan_edit({ action: classify_last_scan_edit(edit_request), previous_file_names, answer }),
    );
    this.render();
    this.panel_services.frame_editor.handle_target_change(this.editor_owner);
    // The state brings the new revision of the files and the size of the thumbnail.
    this.panel_services.request_state_refresh();
  }

  report_failure(failure) {
    this.panel_services.error_banner.report_action_error(failure.message);
    if (LAST_SCAN_RELOAD_ERROR_CODES.includes(failure.error_code)) {
      this.panel_services.request_state_refresh();
    }
  }

  restore_focus(action_origin) {
    // A keyboard user comes back to the button that opened the dialog; after a click the next Space scans again.
    const { last_scan_enlarge_button } = this.elements;
    if (action_origin.is_keyboard_initiated && !last_scan_enlarge_button.disabled) {
      last_scan_enlarge_button.focus();
    } else {
      this.panel_services.focus_scan_button();
    }
  }

  async rotate_last_scan(action_origin) {
    if (!this.can_edit()) {
      return;
    }
    const { failure } = await this.attempt_edit({ method: "POST", path: LAST_SCAN_ROTATION_PATH });
    if (failure !== null) {
      this.report_failure(failure);
    }
    // A keyboard user stays on the button; after a click the next Space scans again.
    const { last_scan_rotate_button } = this.elements;
    if (action_origin.is_keyboard_initiated) {
      last_scan_rotate_button.focus();
    } else {
      this.panel_services.focus_scan_button();
    }
  }

  enlarge_last_scan(action_origin) {
    if (!this.can_edit()) {
      return;
    }
    this.panel_services.frame_editor.open({
      owner: this.editor_owner,
      target_identifier: this.last_result.scan_identifier,
      action_origin,
    });
  }
}
