"use strict";

// What the frame dialog (page-frame-dialog) shows, read from the fake browser page: shared by the harnesses of the
// Documento mode (page-frame-editor-harness.js) and of the quick mode (last-scan-harness.js), because one dialog serves both.

const { read_overlay } = require("./document-page-fixtures.js");

const CORNER_IDENTIFIERS = {
  top_left: "frame-corner-top-left",
  top_right: "frame-corner-top-right",
  bottom_right: "frame-corner-bottom-right",
  bottom_left: "frame-corner-bottom-left",
};
const EDGE_IDENTIFIERS = {
  top: "frame-edge-top",
  right: "frame-edge-right",
  bottom: "frame-edge-bottom",
  left: "frame-edge-left",
};

function read_handle(element) {
  return {
    hidden: element.hidden,
    left: element.style.left ?? null,
    top: element.style.top ?? null,
    label: element.getAttribute("aria-label"),
  };
}

function read_clipped_button(element) {
  return { hidden: element.hidden, clip_path: element.style.clipPath ?? null, label: element.getAttribute("aria-label") };
}

function read_dialog(page) {
  const read_all = (identifiers) =>
    Object.fromEntries(Object.entries(identifiers).map(([name, identifier]) => [name, read_handle(page.element(identifier))]));
  return {
    open: page.element("page-frame-dialog").open,
    title: page.element("page-frame-title").textContent,
    status: page.element("frame-status").textContent,
    image_source: page.element("frame-image").src,
    image_alt: page.element("frame-image").alt,
    stage_loading: page.element("frame-stage").classList.contains("is-loading"),
    overlay: read_overlay(page.element("frame-overlay-host").children[0]),
    corners: read_all(CORNER_IDENTIFIERS),
    edges: read_all(EDGE_IDENTIFIERS),
    rotate_handle: read_handle(page.element("frame-rotate-handle")),
    move: read_clipped_button(page.element("frame-move-button")),
    select: read_clipped_button(page.element("frame-select-button")),
    turn_label: page.element("frame-turn-button").getAttribute("aria-label"),
    disabled: {
      add: page.element("frame-add-button").disabled,
      remove: page.element("frame-remove-button").disabled,
      turn: page.element("frame-turn-button").disabled,
      detect: page.element("frame-detect-button").disabled,
      clear: page.element("frame-clear-button").disabled,
      rotate: page.element("frame-rotate-button").disabled,
      apply: page.element("frame-apply-button").disabled,
      cancel: page.element("frame-cancel-button").disabled,
    },
  };
}

module.exports = { read_dialog };
