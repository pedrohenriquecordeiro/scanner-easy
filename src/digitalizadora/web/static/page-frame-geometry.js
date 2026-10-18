"use strict";

// Pure geometry of the crop frame of a page (no DOM). A frame is {left, top, right, bottom}: fractions from 0 to 1 of
// the page as it is displayed, after the page rotation, the same numbers the server stores as the crop of the page.
// page-frame-editor.js and document-panel.js wire these functions to the page; index.html loads this file before them.

const MINIMUM_FRAME_SIDE = 0.02;
const FINE_NUDGE_STEP = 0.005;
const COARSE_NUDGE_STEP = 0.05;
const FRAME_COMPARISON_TOLERANCE = 0.0005;
const FRAME_PRECISION_DIGITS = 4;
const STYLE_PRECISION_DIGITS = 2;
const PERCENT_SCALE = 100;
const PERCENT_COMPARISON_DIGITS = 4;
const QUARTER_TURN_DEGREES = 90;
const FULL_TURN_DEGREES = 360;
const WHOLE_PAGE_FRAME = Object.freeze({ left: 0, top: 0, right: 1, bottom: 1 });
const FRAME_HANDLES = Object.freeze({
  NORTH: "north",
  NORTH_EAST: "north_east",
  EAST: "east",
  SOUTH_EAST: "south_east",
  SOUTH: "south",
  SOUTH_WEST: "south_west",
  WEST: "west",
  NORTH_WEST: "north_west",
});
const NUDGE_DIRECTIONS = Object.freeze({ LEFT: "left", RIGHT: "right", UP: "up", DOWN: "down" });
const NUDGE_DIRECTIONS_BY_KEY_CODE = Object.freeze({
  ArrowLeft: NUDGE_DIRECTIONS.LEFT,
  ArrowRight: NUDGE_DIRECTIONS.RIGHT,
  ArrowUp: NUDGE_DIRECTIONS.UP,
  ArrowDown: NUDGE_DIRECTIONS.DOWN,
});
const HANDLE_LABELS = Object.freeze({
  north: "Borda de cima",
  north_east: "Canto superior direito",
  east: "Borda direita",
  south_east: "Canto inferior direito",
  south: "Borda de baixo",
  south_west: "Canto inferior esquerdo",
  west: "Borda esquerda",
  north_west: "Canto superior esquerdo",
});
const EDGE_LABELS = Object.freeze({ left: "esquerda", top: "topo", right: "direita", bottom: "base" });
const EDGES_OF_EDGE_HANDLES = Object.freeze({ north: "top", east: "right", south: "bottom", west: "left" });
const WHOLE_PAGE_DESCRIPTION = "Sem corte: a página inteira será usada.";

function round_to_digits(value, digits) {
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

function to_percent(fraction) {
  // toFixed first, so a product like 91.49999999999999 rounds as the 91.5 it stands for.
  return Math.round(Number((fraction * PERCENT_SCALE).toFixed(PERCENT_COMPARISON_DIGITS)));
}

function clamp_fraction(value) {
  return Math.min(Math.max(value, 0), 1);
}

function build_frame(edges) {
  return {
    left: round_to_digits(edges.left, FRAME_PRECISION_DIGITS),
    top: round_to_digits(edges.top, FRAME_PRECISION_DIGITS),
    right: round_to_digits(edges.right, FRAME_PRECISION_DIGITS),
    bottom: round_to_digits(edges.bottom, FRAME_PRECISION_DIGITS),
  };
}

function frames_are_equal(first_frame, second_frame) {
  return ["left", "top", "right", "bottom"].every(
    (edge_name) => Math.abs(first_frame[edge_name] - second_frame[edge_name]) <= FRAME_COMPARISON_TOLERANCE,
  );
}

function is_whole_page_frame(frame) {
  return frames_are_equal(frame, WHOLE_PAGE_FRAME);
}

function limit_between(value, lowest, highest) {
  return Math.min(Math.max(value, lowest), highest);
}

function move_frame(frame, shift) {
  const width = frame.right - frame.left;
  const height = frame.bottom - frame.top;
  const left = limit_between(frame.left + shift.delta_x, 0, 1 - width);
  const top = limit_between(frame.top + shift.delta_y, 0, 1 - height);
  return build_frame({ left, top, right: left + width, bottom: top + height });
}

function resize_frame(frame, resize) {
  const { handle, delta_x, delta_y } = resize;
  let { left, top, right, bottom } = frame;
  if (handle.includes("west")) {
    left = limit_between(left + delta_x, 0, right - MINIMUM_FRAME_SIDE);
  }
  if (handle.includes("east")) {
    right = limit_between(right + delta_x, left + MINIMUM_FRAME_SIDE, 1);
  }
  if (handle.includes("north")) {
    top = limit_between(top + delta_y, 0, bottom - MINIMUM_FRAME_SIDE);
  }
  if (handle.includes("south")) {
    bottom = limit_between(bottom + delta_y, top + MINIMUM_FRAME_SIDE, 1);
  }
  return build_frame({ left, top, right, bottom });
}

function measure_nudge(direction, step) {
  const shifts = {
    [NUDGE_DIRECTIONS.LEFT]: { delta_x: -step, delta_y: 0 },
    [NUDGE_DIRECTIONS.RIGHT]: { delta_x: step, delta_y: 0 },
    [NUDGE_DIRECTIONS.UP]: { delta_x: 0, delta_y: -step },
    [NUDGE_DIRECTIONS.DOWN]: { delta_x: 0, delta_y: step },
  };
  return shifts[direction];
}

function nudge_handle(frame, nudge) {
  const shift = measure_nudge(nudge.direction, nudge.step);
  return resize_frame(frame, { handle: nudge.handle, ...shift });
}

function nudge_whole_frame(frame, nudge) {
  return move_frame(frame, measure_nudge(nudge.direction, nudge.step));
}

function read_nudge_step(key_event) {
  return key_event.shiftKey ? COARSE_NUDGE_STEP : FINE_NUDGE_STEP;
}

function read_nudge_direction(key_code) {
  return NUDGE_DIRECTIONS_BY_KEY_CODE[key_code] ?? null;
}

function turn_frame_clockwise(frame) {
  // The point (x, y) of the page goes to (1 - y, x) when the page turns a quarter clockwise.
  return build_frame({ left: 1 - frame.bottom, top: frame.left, right: 1 - frame.top, bottom: frame.right });
}

function turn_frame_by_quarter_turns(frame, quarter_turns) {
  let turned_frame = frame;
  for (let turn = 0; turn < quarter_turns; turn += 1) {
    turned_frame = turn_frame_clockwise(turned_frame);
  }
  return turned_frame;
}

function count_quarter_turns(previous_degrees, current_degrees) {
  const turned_degrees = (current_degrees - previous_degrees + FULL_TURN_DEGREES) % FULL_TURN_DEGREES;
  return turned_degrees / QUARTER_TURN_DEGREES;
}

function convert_pointer_shift(pointer_shift, box_size) {
  if (box_size.width <= 0 || box_size.height <= 0) {
    return { delta_x: 0, delta_y: 0 };
  }
  return {
    delta_x: pointer_shift.horizontal_pixels / box_size.width,
    delta_y: pointer_shift.vertical_pixels / box_size.height,
  };
}

function describe_frame_style(frame) {
  const percent_of = (fraction) => round_to_digits(fraction * PERCENT_SCALE, STYLE_PRECISION_DIGITS);
  return {
    left_percent: percent_of(frame.left),
    top_percent: percent_of(frame.top),
    width_percent: percent_of(frame.right - frame.left),
    height_percent: percent_of(frame.bottom - frame.top),
  };
}

function describe_frame(frame) {
  if (is_whole_page_frame(frame)) {
    return WHOLE_PAGE_DESCRIPTION;
  }
  const percents = ["left", "top", "right", "bottom"].map((edge_name) => to_percent(frame[edge_name]));
  const [left, top, right, bottom] = percents;
  return `Moldura: esquerda ${left}%, topo ${top}%, direita ${right}%, base ${bottom}%.`;
}

function read_handle_label(handle) {
  return HANDLE_LABELS[handle];
}

function describe_edge_position(frame, edge_name) {
  return `${EDGE_LABELS[edge_name]} ${to_percent(frame[edge_name])}%`;
}

function describe_handle_position(frame, handle) {
  const edge_name = EDGES_OF_EDGE_HANDLES[handle];
  if (edge_name !== undefined) {
    return `${read_handle_label(handle)} em ${to_percent(frame[edge_name])}%.`;
  }
  const horizontal_edge = handle.includes("west") ? "left" : "right";
  const vertical_edge = handle.includes("north") ? "top" : "bottom";
  const edge_texts = [horizontal_edge, vertical_edge].map((name) => describe_edge_position(frame, name));
  return `${read_handle_label(handle)}: ${edge_texts.join(", ")}.`;
}

function read_frame_from_crop(crop) {
  return crop === null || crop === undefined ? { ...WHOLE_PAGE_FRAME } : build_frame(crop);
}

function build_crop_request_body(frame) {
  if (is_whole_page_frame(frame)) {
    return { crop: null };
  }
  return { crop: { left: frame.left, top: frame.top, right: frame.right, bottom: frame.bottom } };
}
