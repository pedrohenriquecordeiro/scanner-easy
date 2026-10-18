"use strict";

// Reads a JSON list of expressions from stdin, evaluates each one against the real pure rule scripts in a Node vm
// context (no DOM) and prints {expression: result} as JSON. tests/web/test_document_page_policy.py asserts on it.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const STATIC_DIRECTORY = path.resolve(__dirname, "..", "..", "src", "digitalizadora", "web", "static");
const SCRIPT_FILE_NAMES = [
  "scan-trigger-policy.js",
  "scan-quality-policy.js",
  "document-page-policy.js",
  "page-frame-geometry.js",
];
const STANDARD_INPUT_DESCRIPTOR = 0;

const SCAN_BUTTON = Object.freeze({ tagName: "BUTTON" });
const OTHER_BUTTON = Object.freeze({ tagName: "BUTTON" });
const TEXT_FIELD = Object.freeze({ tagName: "INPUT" });
const PAGE_BODY = Object.freeze({ tagName: "BODY" });
const EDITABLE_AREA = Object.freeze({ tagName: "DIV", isContentEditable: true });
const DEFAULT_DOCUMENT_ACTIVITY = Object.freeze({
  capture_mode: "document",
  page_count: 2,
  can_edit: true,
  is_confirmation_open: false,
  scan_button: SCAN_BUTTON,
});
const DEFAULT_PAGE_ACTIVITY = Object.freeze({
  scan_phase: "idle",
  is_start_request_pending: false,
  is_edit_request_pending: false,
});
const DEFAULT_ACTION_CONTEXT = Object.freeze({
  action: "move",
  is_keyboard_initiated: true,
  page_identifiers_after: ["a", "b", "c"],
  acted_page_identifier: "b",
  acted_position: 2,
});
const DEFAULT_OBSERVATION = Object.freeze({
  draft_session: "s1",
  revision: 3,
  page_count: 2,
  scans_completed: 5,
  last_error_code: null,
  capture_mode: "document",
});
const DEFAULT_DOCUMENT_PROGRESS = Object.freeze({
  page_count: 2,
  last_event: "none",
  dots_per_inch: 300,
  is_finalizing: false,
});
const DEFAULT_RECOVERY = Object.freeze({
  outcome: "resumed",
  kept_page_count: 41,
  dropped_page_positions: [],
  set_aside_folder: null,
});
const DEFAULT_DRAFT_DOCUMENT = Object.freeze({ finished_document_path: null, finalization_started_at: null });
const DEFAULT_MODE_SWITCH = Object.freeze({
  draft_session: "s1",
  recovery: DEFAULT_RECOVERY,
  capture_mode: "single",
  switched_draft_session: null,
});

function key_on(code, target) {
  return { code, target, repeat: false };
}

function repeated_key_on(code, target) {
  return { code, target, repeat: true };
}

function page_activity(changes) {
  return { ...DEFAULT_PAGE_ACTIVITY, ...changes };
}

function document_activity(changes) {
  return { ...DEFAULT_DOCUMENT_ACTIVITY, ...changes };
}

function action_context(changes) {
  return { ...DEFAULT_ACTION_CONTEXT, ...changes };
}

function observation(changes) {
  return { ...DEFAULT_OBSERVATION, ...changes };
}

function document_progress(changes) {
  return { ...DEFAULT_DOCUMENT_PROGRESS, ...changes };
}

function recovery(changes) {
  return { ...DEFAULT_RECOVERY, ...changes };
}

function draft_document(changes) {
  return { ...DEFAULT_DRAFT_DOCUMENT, ...changes };
}

function mode_switch_check(changes) {
  const { draft_session, recovery, capture_mode, switched_draft_session } = { ...DEFAULT_MODE_SWITCH, ...changes };
  return { document_body: { draft_session, recovery }, capture_mode, switched_draft_session };
}

function build_context() {
  const context = vm.createContext({
    SCAN_BUTTON,
    OTHER_BUTTON,
    TEXT_FIELD,
    PAGE_BODY,
    EDITABLE_AREA,
    key_on,
    repeated_key_on,
    page_activity,
    document_activity,
    action_context,
    observation,
    document_progress,
    recovery,
    draft_document,
    mode_switch_check,
  });
  for (const file_name of SCRIPT_FILE_NAMES) {
    vm.runInContext(fs.readFileSync(path.join(STATIC_DIRECTORY, file_name), "utf8"), context, { filename: file_name });
  }
  return context;
}

function main() {
  const expressions = JSON.parse(fs.readFileSync(STANDARD_INPUT_DESCRIPTOR, "utf8"));
  const context = build_context();
  const results = {};
  for (const expression of expressions) {
    results[expression] = vm.runInContext(expression, context) ?? null;
  }
  process.stdout.write(JSON.stringify(results));
}

main();
