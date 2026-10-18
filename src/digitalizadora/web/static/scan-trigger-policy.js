"use strict";

// Pure rules for when a key press or click may start a scan; application.js wires them to the page.

const IDLE_PHASE = "idle";
const SPACE_KEY_CODE = "Space";
const BUTTON_TAG_NAME = "BUTTON";
const KEYBOARD_RESERVED_TAG_NAMES = ["INPUT", "SELECT", "TEXTAREA"];
const SPACE_KEY_ACTIONS = Object.freeze({
  IGNORE: "ignore",
  SUPPRESS: "suppress",
  START_SCAN: "start_scan",
});

function is_space_reserved_by(target, scan_button) {
  if (KEYBOARD_RESERVED_TAG_NAMES.includes(target.tagName)) {
    return true;
  }
  // Space activates any other focused button natively; only the scan button hands it to the scan.
  return target.tagName === BUTTON_TAG_NAME && target !== scan_button;
}

function decide_space_key_action(key_event, scan_button) {
  if (key_event.code !== SPACE_KEY_CODE || is_space_reserved_by(key_event.target, scan_button)) {
    return SPACE_KEY_ACTIONS.IGNORE;
  }
  // A held key repeats keydown; the repeats are swallowed so they neither scroll nor start another scan.
  return key_event.repeat ? SPACE_KEY_ACTIONS.SUPPRESS : SPACE_KEY_ACTIONS.START_SCAN;
}

function can_start_scan(scan_activity) {
  return scan_activity.scan_phase === IDLE_PHASE && !scan_activity.is_start_request_pending;
}
