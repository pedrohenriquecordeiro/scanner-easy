"use strict";

// Draws the crop frames over a picture: the outside darkened, one outline per frame (the first blue and solid, the
// second orange and dashed) and the number of each frame at its first corner. The tiles of the Documento mode, the
// panel of the last scan and the frame dialog all use it, so a frame looks the same everywhere. It only writes the
// attributes that describe_shade_path, describe_frame_outline and describe_handle_style of page-frame-geometry.js give.
// index.html loads it after page-frame-geometry.js.

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const OVERLAY_CLASS_NAME = "frame-overlay";
const OVERLAY_DRAWING_CLASS_NAME = "frame-overlay-drawing";
const OVERLAY_SHADE_CLASS_NAME = "frame-overlay-shade";
const OVERLAY_OUTLINE_CLASS_NAME = "frame-overlay-outline";
const OVERLAY_BADGE_CLASS_NAME = "frame-overlay-badge";
const OVERLAY_ACTIVE_CLASS_NAME = "is-active";
const OVERLAY_COLOUR_CLASS_NAMES = Object.freeze(["frame-colour-first", "frame-colour-second"]);
const NO_ACTIVE_FRAME = -1;
const OVERLAY_VIEW_BOX = "0 0 100 100";

function create_svg_element(tag_name, class_name) {
  const element = document.createElementNS(SVG_NAMESPACE, tag_name);
  element.classList.add(class_name);
  return element;
}

function create_frame_overlay() {
  const container = document.createElement("div");
  container.classList.add(OVERLAY_CLASS_NAME);
  container.setAttribute("aria-hidden", "true");
  container.hidden = true;
  const drawing = create_svg_element("svg", OVERLAY_DRAWING_CLASS_NAME);
  drawing.setAttribute("viewBox", OVERLAY_VIEW_BOX);
  drawing.setAttribute("preserveAspectRatio", "none");
  const shade = create_svg_element("path", OVERLAY_SHADE_CLASS_NAME);
  shade.setAttribute("fill-rule", "evenodd");
  const outlines = OVERLAY_COLOUR_CLASS_NAMES.map((colour_class_name) => {
    const outline = create_svg_element("polygon", OVERLAY_OUTLINE_CLASS_NAME);
    outline.classList.add(colour_class_name);
    return outline;
  });
  drawing.append(shade, ...outlines);
  const badges = OVERLAY_COLOUR_CLASS_NAMES.map((colour_class_name, index) => {
    const badge = document.createElement("span");
    badge.classList.add(OVERLAY_BADGE_CLASS_NAME, colour_class_name);
    badge.textContent = String(index + 1);
    return badge;
  });
  container.append(drawing, ...badges);
  return { container, shade, outlines, badges };
}

function update_frame_overlay(overlay, frames, active_index) {
  overlay.container.hidden = frames.length === 0;
  overlay.shade.setAttribute("d", describe_shade_path(frames));
  overlay.outlines.forEach((outline, index) => {
    const frame = frames[index];
    outline.style.display = frame === undefined ? "none" : "";
    outline.classList.toggle(OVERLAY_ACTIVE_CLASS_NAME, index === active_index);
    if (frame !== undefined) {
      outline.setAttribute("points", describe_frame_outline(frame));
    }
  });
  overlay.badges.forEach((badge, index) => {
    const frame = frames[index];
    badge.hidden = frame === undefined;
    if (frame !== undefined) {
      const { left_percent, top_percent } = describe_handle_style(frame.top_left);
      badge.style.left = `${left_percent}%`;
      badge.style.top = `${top_percent}%`;
    }
  });
}
