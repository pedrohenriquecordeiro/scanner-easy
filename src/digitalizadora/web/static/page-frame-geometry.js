"use strict";

// Pure geometry of the crop frames of a page (no DOM). A frame is a convex quadrilateral: four corners in fractions
// from 0 to 1 of the page as it is displayed (after the page rotation), {top_left, top_right, bottom_right,
// bottom_left}, each one {x, y}, clockwise on the screen. It is exactly the crop the server stores and sends, and
// an axis-aligned rectangle is just the special case. The rules of validity, the turns and the reading order are the
// ones of the server (domain/imaging/page_crop.py, domain/imaging/page_framing.py); tests/fixtures/page-crop-vectors.json holds
// the shared test vectors both sides read. page-frame-editor.js, document-panel.js and last-scan-panel.js wire
// these functions to the page; index.html loads this file before them.

const CORNER_ROLES = Object.freeze(["top_left", "top_right", "bottom_right", "bottom_left"]);
const EDGE_CORNER_ROLES = Object.freeze({
  top: ["top_left", "top_right"],
  right: ["top_right", "bottom_right"],
  bottom: ["bottom_right", "bottom_left"],
  left: ["bottom_left", "top_left"],
});
const MAXIMUM_FRAMES = 2;
const MINIMUM_FRAME_EDGE = 0.02;
const MINIMUM_CORNER_TRIANGLE_SHARE = 0.05;
const READING_ORDER_ROW_OVERLAP_SHARE = 0.5;
const FRAME_PRECISION_DIGITS = 6;
const FRAME_TOLERANCE = 1e-9;
const FRAME_COMPARISON_TOLERANCE = 0.0005;
const STYLE_PRECISION_DIGITS = 2;
const PERCENT_SCALE = 100;
const PERCENT_COMPARISON_DIGITS = 4;
const FINE_NUDGE_STEP = 0.005;
const COARSE_NUDGE_STEP = 0.05;
const FINE_ROTATION_NUDGE_DEGREES = 0.5;
const COARSE_ROTATION_NUDGE_DEGREES = 5;
const ROTATE_HANDLE_OFFSET_SHARE = 0.06;
// The handles are 44 px touch areas: the rotate handle keeps a gap from the handle of the top edge.
const MINIMUM_ROTATE_HANDLE_OFFSET_PIXELS = 52;
const MINIMUM_HANDLE_POSITION = 0.02;
const QUARTER_TURN_DEGREES = 90;
const HALF_TURN_DEGREES = 180;
const FULL_TURN_DEGREES = 360;
const TILT_REPORT_THRESHOLD_DEGREES = 1;
const NEW_FRAME_SIDE_SHARE = 0.4;
const NUDGE_DIRECTIONS = Object.freeze({ LEFT: "left", RIGHT: "right", UP: "up", DOWN: "down" });
const NUDGE_DIRECTIONS_BY_KEY_CODE = Object.freeze({
  ArrowLeft: NUDGE_DIRECTIONS.LEFT,
  ArrowRight: NUDGE_DIRECTIONS.RIGHT,
  ArrowUp: NUDGE_DIRECTIONS.UP,
  ArrowDown: NUDGE_DIRECTIONS.DOWN,
});
const ARROW_VECTORS = Object.freeze({
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
  up: { x: 0, y: -1 },
  down: { x: 0, y: 1 },
});
const CORNER_LABELS = Object.freeze({
  top_left: "Canto superior esquerdo",
  top_right: "Canto superior direito",
  bottom_right: "Canto inferior direito",
  bottom_left: "Canto inferior esquerdo",
});
const CORNER_TEXTS = Object.freeze({
  top_left: "superior esquerdo",
  top_right: "superior direito",
  bottom_right: "inferior direito",
  bottom_left: "inferior esquerdo",
});
const EDGE_LABELS = Object.freeze({
  top: "Borda de cima",
  right: "Borda direita",
  bottom: "Borda de baixo",
  left: "Borda esquerda",
});
const TOP_SIDE_TEXTS = Object.freeze({
  1: "à direita",
  2: "embaixo",
  3: "à esquerda",
});
const WHOLE_PAGE_DESCRIPTION = "Sem corte: a página inteira será usada.";
const SQUARE_SURFACE = Object.freeze({ width: 1, height: 1 });

function round_to_digits(value, digits) {
  const scale = 10 ** digits;
  // The sum turns a -0 into 0.
  return Math.round(value * scale) / scale + 0;
}

function round_fraction(value) {
  return round_to_digits(value, FRAME_PRECISION_DIGITS);
}

function to_percent(fraction) {
  // toFixed first, so a product like 91.49999999999999 rounds as the 91.5 it stands for.
  return Math.round(Number((fraction * PERCENT_SCALE).toFixed(PERCENT_COMPARISON_DIGITS)));
}

function clamp_fraction(value) {
  return Math.min(Math.max(value, 0), 1);
}

function limit_between(value, lowest, highest) {
  return Math.min(Math.max(value, lowest), highest);
}

function read_surface(surface) {
  const is_usable = surface !== undefined && surface !== null && surface.width > 0 && surface.height > 0;
  return is_usable ? surface : SQUARE_SURFACE;
}

function build_frame_from_corner_list(corner_list) {
  const frame = {};
  CORNER_ROLES.forEach((role, index) => {
    frame[role] = { x: round_fraction(corner_list[index].x), y: round_fraction(corner_list[index].y) };
  });
  return frame;
}

function list_frame_corners(frame) {
  return CORNER_ROLES.map((role) => frame[role]);
}

function copy_frame(frame) {
  return build_frame_from_corner_list(list_frame_corners(frame));
}

function build_rectangle_frame(edges) {
  return build_frame_from_corner_list([
    { x: edges.left, y: edges.top },
    { x: edges.right, y: edges.top },
    { x: edges.right, y: edges.bottom },
    { x: edges.left, y: edges.bottom },
  ]);
}

const WHOLE_PAGE_FRAME = Object.freeze(build_rectangle_frame({ left: 0, top: 0, right: 1, bottom: 1 }));

function twice_signed_area(corners) {
  // Positive for clockwise corners on the screen, where y grows downwards.
  return corners.reduce((sum, corner, index) => {
    const following = corners[(index + 1) % corners.length];
    return sum + corner.x * following.y - following.x * corner.y;
  }, 0);
}

function twice_corner_triangle_area(previous, corner, following) {
  return (corner.x - previous.x) * (following.y - previous.y) - (corner.y - previous.y) * (following.x - previous.x);
}

function is_finite_number(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function find_frame_problem(frame) {
  const corners = list_frame_corners(frame);
  const coordinates = corners.flatMap((corner) => [corner.x, corner.y]);
  if (!coordinates.every(is_finite_number)) {
    return "not_finite";
  }
  if (!coordinates.every((value) => value >= -FRAME_TOLERANCE && value <= 1 + FRAME_TOLERANCE)) {
    return "outside_the_page";
  }
  const twice_area = twice_signed_area(corners);
  if (twice_area <= FRAME_TOLERANCE) {
    return "not_clockwise_or_empty";
  }
  const following_corners = corners.map((_, index) => corners[(index + 1) % corners.length]);
  const has_short_edge = corners.some(
    (corner, index) =>
      Math.hypot(corner.x - following_corners[index].x, corner.y - following_corners[index].y) <
      MINIMUM_FRAME_EDGE - FRAME_TOLERANCE,
  );
  if (has_short_edge) {
    return "edge_too_short";
  }
  const triangles = corners.map((corner, index) =>
    twice_corner_triangle_area(corners[(index + corners.length - 1) % corners.length], corner, following_corners[index]),
  );
  if (triangles.some((triangle) => triangle <= FRAME_TOLERANCE)) {
    return "not_convex";
  }
  if (triangles.some((triangle) => triangle < MINIMUM_CORNER_TRIANGLE_SHARE * twice_area)) {
    return "corner_too_flat";
  }
  return null;
}

function validate_frame(frame) {
  const problem = find_frame_problem(frame);
  return { is_valid: problem === null, problem };
}

function build_valid_frame_or_null(corner_list) {
  const frame = build_frame_from_corner_list(corner_list);
  return find_frame_problem(frame) === null ? frame : null;
}

function frames_are_equal(first_frame, second_frame) {
  return CORNER_ROLES.every(
    (role) =>
      Math.abs(first_frame[role].x - second_frame[role].x) <= FRAME_COMPARISON_TOLERANCE &&
      Math.abs(first_frame[role].y - second_frame[role].y) <= FRAME_COMPARISON_TOLERANCE,
  );
}

function frame_lists_are_equal(first_frames, second_frames) {
  return (
    first_frames.length === second_frames.length &&
    first_frames.every((frame, index) => frames_are_equal(frame, second_frames[index]))
  );
}

function is_whole_page_frame(frame) {
  return frames_are_equal(frame, WHOLE_PAGE_FRAME);
}

function is_rectangle_frame(frame) {
  const [first, second, third, fourth] = list_frame_corners(frame);
  const same = (first_value, second_value) => Math.abs(first_value - second_value) <= FRAME_TOLERANCE;
  if (same(first.y, second.y) && same(third.y, fourth.y)) {
    return same(second.x, third.x) && same(fourth.x, first.x);
  }
  return (
    same(first.x, second.x) && same(third.x, fourth.x) && same(second.y, third.y) && same(fourth.y, first.y)
  );
}

function find_frame_bounds(frame) {
  const corners = list_frame_corners(frame);
  const horizontal_values = corners.map((corner) => corner.x);
  const vertical_values = corners.map((corner) => corner.y);
  return {
    left: Math.min(...horizontal_values),
    top: Math.min(...vertical_values),
    right: Math.max(...horizontal_values),
    bottom: Math.max(...vertical_values),
  };
}

function find_frame_centre(frame) {
  const corners = list_frame_corners(frame);
  return {
    x: corners.reduce((sum, corner) => sum + corner.x, 0) / corners.length,
    y: corners.reduce((sum, corner) => sum + corner.y, 0) / corners.length,
  };
}

function read_frame_from_crop(crop) {
  return build_frame_from_corner_list(list_frame_corners(crop));
}

function read_frames_from_crops(crops) {
  if (crops === null || crops === undefined) {
    return [];
  }
  return crops.slice(0, MAXIMUM_FRAMES).map(read_frame_from_crop);
}

function build_crops_request_body(frames) {
  // A frame that covers the whole page is the same as no frame; the server drops it too.
  return { crops: frames.filter((frame) => !is_whole_page_frame(frame)).map(copy_frame) };
}

function move_frame(frame, shift) {
  const bounds = find_frame_bounds(frame);
  const allowed_x = limit_between(shift.delta_x, -bounds.left, 1 - bounds.right);
  const allowed_y = limit_between(shift.delta_y, -bounds.top, 1 - bounds.bottom);
  return build_frame_from_corner_list(
    list_frame_corners(frame).map((corner) => ({ x: corner.x + allowed_x, y: corner.y + allowed_y })),
  );
}

function move_corner(frame, move) {
  const moved_corner = {
    x: clamp_fraction(frame[move.corner].x + move.delta_x),
    y: clamp_fraction(frame[move.corner].y + move.delta_y),
  };
  const corner_list = CORNER_ROLES.map((role) => (role === move.corner ? moved_corner : frame[role]));
  return build_valid_frame_or_null(corner_list);
}

function measure_edge_normal(frame, edge, surface) {
  const { width, height } = read_surface(surface);
  const [start_role, end_role] = EDGE_CORNER_ROLES[edge];
  const along_x = (frame[end_role].x - frame[start_role].x) * width;
  const along_y = (frame[end_role].y - frame[start_role].y) * height;
  const length = Math.hypot(along_x, along_y);
  // The frame is clockwise on the screen, so the outside of an edge is on its left-hand side.
  return length === 0 ? { x: 0, y: 0 } : { x: along_y / length, y: -along_x / length };
}

function find_largest_shift_scale(points, shift) {
  let scale = 1;
  for (const point of points) {
    for (const axis of ["x", "y"]) {
      if (shift[axis] > 0) {
        scale = Math.min(scale, (1 - point[axis]) / shift[axis]);
      } else if (shift[axis] < 0) {
        scale = Math.min(scale, point[axis] / -shift[axis]);
      }
    }
  }
  return Math.max(scale, 0);
}

function move_edge(frame, move) {
  const { width, height } = read_surface(move.surface);
  const normal = measure_edge_normal(frame, move.edge, move.surface);
  const distance = move.delta_x * width * normal.x + move.delta_y * height * normal.y;
  const wanted_shift = { x: (distance * normal.x) / width, y: (distance * normal.y) / height };
  const moved_roles = EDGE_CORNER_ROLES[move.edge];
  const scale = find_largest_shift_scale(
    moved_roles.map((role) => frame[role]),
    wanted_shift,
  );
  const corner_list = CORNER_ROLES.map((role) =>
    moved_roles.includes(role)
      ? { x: frame[role].x + wanted_shift.x * scale, y: frame[role].y + wanted_shift.y * scale }
      : frame[role],
  );
  return build_valid_frame_or_null(corner_list);
}

function rotate_frame(frame, rotation) {
  const { width, height } = read_surface(rotation.surface);
  const radians = (rotation.degrees * Math.PI) / HALF_TURN_DEGREES;
  const cosine = Math.cos(radians);
  const sine = Math.sin(radians);
  const centre = find_frame_centre(frame);
  const offsets = list_frame_corners(frame).map((corner) => {
    const pixel_x = (corner.x - centre.x) * width;
    const pixel_y = (corner.y - centre.y) * height;
    return { x: (pixel_x * cosine - pixel_y * sine) / width, y: (pixel_x * sine + pixel_y * cosine) / height };
  });
  // A turn can push a corner out of the page: the frame then shrinks around its centre, just enough to fit.
  const fitting_scale = Math.min(...offsets.map((offset) => find_largest_shift_scale([centre], offset)));
  return build_valid_frame_or_null(
    offsets.map((offset) => ({ x: centre.x + offset.x * fitting_scale, y: centre.y + offset.y * fitting_scale })),
  );
}

function turn_point_clockwise(point) {
  // The point (x, y) of the page goes to (1 - y, x) when the page turns a quarter clockwise.
  return { x: round_fraction(1 - point.y), y: round_fraction(point.x) };
}

function turn_frame_output_clockwise(frame) {
  // Only the roles advance: the cut-out photo comes out turned a quarter clockwise.
  return build_frame_from_corner_list([frame.bottom_left, frame.top_left, frame.top_right, frame.bottom_right]);
}

function find_vertical_range(frame) {
  const bounds = find_frame_bounds(frame);
  return { top: bounds.top, bottom: bounds.bottom };
}

function frames_share_a_row(first_frame, second_frame) {
  const first_range = find_vertical_range(first_frame);
  const second_range = find_vertical_range(second_frame);
  const overlap = Math.min(first_range.bottom, second_range.bottom) - Math.max(first_range.top, second_range.top);
  const shorter_height = Math.min(first_range.bottom - first_range.top, second_range.bottom - second_range.top);
  return overlap > READING_ORDER_ROW_OVERLAP_SHARE * shorter_height;
}

function put_frames_in_reading_order(frames) {
  if (frames.length !== MAXIMUM_FRAMES) {
    return [...frames];
  }
  const [first_frame, second_frame] = frames;
  const axis = frames_share_a_row(first_frame, second_frame) ? "x" : "y";
  const is_second_first = find_frame_centre(second_frame)[axis] < find_frame_centre(first_frame)[axis];
  return is_second_first ? [second_frame, first_frame] : [first_frame, second_frame];
}

function turn_frame_clockwise(frame) {
  // The points follow the page and the old left edge becomes the top: the roles advance too.
  const turned_frame = build_frame_from_corner_list(list_frame_corners(frame).map(turn_point_clockwise));
  return turn_frame_output_clockwise(turned_frame);
}

function turn_frames_by_quarter_turns(frames, quarter_turns) {
  let turned_frames = frames;
  for (let turn = 0; turn < quarter_turns; turn += 1) {
    turned_frames = put_frames_in_reading_order(turned_frames.map(turn_frame_clockwise));
  }
  return turned_frames.map(copy_frame);
}

function count_quarter_turns(previous_degrees, current_degrees) {
  const turned_degrees = (current_degrees - previous_degrees + FULL_TURN_DEGREES) % FULL_TURN_DEGREES;
  return turned_degrees / QUARTER_TURN_DEGREES;
}

function suggest_new_frame(frames) {
  if (frames.length === 0) {
    return build_rectangle_frame({ left: 0.2, top: 0.2, right: 0.8, bottom: 0.8 });
  }
  if (frames.length >= MAXIMUM_FRAMES) {
    return null;
  }
  const free_side_is_right = find_frame_centre(frames[0]).x < 0.5;
  const left = free_side_is_right ? 0.55 : 0.05;
  return build_rectangle_frame({ left, top: 0.3, right: left + NEW_FRAME_SIDE_SHARE, bottom: 0.7 });
}

function measure_nudge(direction, step) {
  const vector = ARROW_VECTORS[direction];
  return { delta_x: vector.x * step, delta_y: vector.y * step };
}

function nudge_corner(frame, nudge) {
  return move_corner(frame, { corner: nudge.corner, ...measure_nudge(nudge.direction, nudge.step) });
}

function nudge_whole_frame(frame, nudge) {
  return move_frame(frame, measure_nudge(nudge.direction, nudge.step));
}

function nudge_edge(frame, nudge) {
  const arrow = ARROW_VECTORS[nudge.direction];
  const normal = measure_edge_normal(frame, nudge.edge, nudge.surface);
  const tangent = { x: -normal.y, y: normal.x };
  const along_the_normal = Math.abs(arrow.x * normal.x + arrow.y * normal.y);
  const along_the_edge = Math.abs(arrow.x * tangent.x + arrow.y * tangent.y);
  // An arrow that points more along the edge than across it does nothing to this edge.
  if (along_the_normal <= along_the_edge) {
    return frame;
  }
  return move_edge(frame, {
    edge: nudge.edge,
    ...measure_nudge(nudge.direction, nudge.step),
    surface: nudge.surface,
  });
}

function nudge_rotation(frame, nudge) {
  const turn_signs = { [NUDGE_DIRECTIONS.LEFT]: -1, [NUDGE_DIRECTIONS.RIGHT]: 1 };
  const sign = turn_signs[nudge.direction];
  if (sign === undefined) {
    return frame;
  }
  return rotate_frame(frame, { degrees: sign * nudge.degrees, surface: nudge.surface });
}

function read_nudge_step(key_event) {
  return key_event.shiftKey ? COARSE_NUDGE_STEP : FINE_NUDGE_STEP;
}

function read_rotation_nudge_degrees(key_event) {
  return key_event.shiftKey ? COARSE_ROTATION_NUDGE_DEGREES : FINE_ROTATION_NUDGE_DEGREES;
}

function read_nudge_direction(key_code) {
  return NUDGE_DIRECTIONS_BY_KEY_CODE[key_code] ?? null;
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

function measure_pointer_turn(turn_points) {
  // The angle the pointer travelled around the centre, in degrees, clockwise on the screen; from where it began.
  const { centre, start_point, current_point } = turn_points;
  const start_angle = Math.atan2(start_point.y - centre.y, start_point.x - centre.x);
  const current_angle = Math.atan2(current_point.y - centre.y, current_point.x - centre.x);
  let degrees = ((current_angle - start_angle) * HALF_TURN_DEGREES) / Math.PI;
  if (degrees > HALF_TURN_DEGREES) {
    degrees -= FULL_TURN_DEGREES;
  } else if (degrees <= -HALF_TURN_DEGREES) {
    degrees += FULL_TURN_DEGREES;
  }
  return degrees;
}

function find_edge_midpoint(frame, edge) {
  const [start_role, end_role] = EDGE_CORNER_ROLES[edge];
  return { x: (frame[start_role].x + frame[end_role].x) / 2, y: (frame[start_role].y + frame[end_role].y) / 2 };
}

function find_rotate_handle_point(frame, surface) {
  const { width, height } = read_surface(surface);
  const midpoint = find_edge_midpoint(frame, "top");
  const normal = measure_edge_normal(frame, "top", surface);
  const frame_height = Math.hypot(
    (frame.bottom_left.x - frame.top_left.x) * width,
    (frame.bottom_left.y - frame.top_left.y) * height,
  );
  const offset = Math.max(
    ROTATE_HANDLE_OFFSET_SHARE * Math.min(width, height) + frame_height * ROTATE_HANDLE_OFFSET_SHARE,
    MINIMUM_ROTATE_HANDLE_OFFSET_PIXELS,
  );
  const outside_point = move_along_edge_normal(midpoint, { normal, offset }, { width, height });
  if (is_inside_handle_area(outside_point)) {
    return outside_point;
  }
  // No room above the frame: the handle goes inside it, on the same line, instead of sitting on the edge handle.
  const inward_offset = Math.min(offset, frame_height / 2);
  return limit_to_handle_area(move_along_edge_normal(midpoint, { normal, offset: -inward_offset }, { width, height }));
}

function move_along_edge_normal(point, shift, surface) {
  const { normal, offset } = shift;
  return { x: point.x + (normal.x * offset) / surface.width, y: point.y + (normal.y * offset) / surface.height };
}

function is_inside_handle_area(point) {
  const highest = 1 - MINIMUM_HANDLE_POSITION;
  return (
    point.x >= MINIMUM_HANDLE_POSITION && point.x <= highest && point.y >= MINIMUM_HANDLE_POSITION && point.y <= highest
  );
}

function limit_to_handle_area(point) {
  return {
    x: limit_between(point.x, MINIMUM_HANDLE_POSITION, 1 - MINIMUM_HANDLE_POSITION),
    y: limit_between(point.y, MINIMUM_HANDLE_POSITION, 1 - MINIMUM_HANDLE_POSITION),
  };
}

function describe_handle_style(point) {
  return {
    left_percent: round_to_digits(point.x * PERCENT_SCALE, STYLE_PRECISION_DIGITS),
    top_percent: round_to_digits(point.y * PERCENT_SCALE, STYLE_PRECISION_DIGITS),
  };
}

function describe_percent_pair(point) {
  const { left_percent, top_percent } = describe_handle_style(point);
  return { horizontal: left_percent, vertical: top_percent };
}

function describe_frame_outline(frame) {
  return list_frame_corners(frame)
    .map((corner) => {
      const { horizontal, vertical } = describe_percent_pair(corner);
      return `${horizontal},${vertical}`;
    })
    .join(" ");
}

function describe_shade_path(frames) {
  const hole_paths = frames.map((frame) => {
    const points = list_frame_corners(frame).map((corner) => {
      const { horizontal, vertical } = describe_percent_pair(corner);
      return `${horizontal} ${vertical}`;
    });
    return `M${points.join("L")}Z`;
  });
  return ["M0 0H100V100H0Z", ...hole_paths].join("");
}

function describe_clip_path(frame) {
  const points = list_frame_corners(frame).map((corner) => {
    const { horizontal, vertical } = describe_percent_pair(corner);
    return `${horizontal}% ${vertical}%`;
  });
  return `polygon(${points.join(", ")})`;
}

function measure_top_edge_angle(frame, surface) {
  const { width, height } = read_surface(surface);
  const along_x = (frame.top_right.x - frame.top_left.x) * width;
  const along_y = (frame.top_right.y - frame.top_left.y) * height;
  return (Math.atan2(along_y, along_x) * HALF_TURN_DEGREES) / Math.PI;
}

function measure_frame_tilt(frame, surface) {
  const angle = measure_top_edge_angle(frame, surface);
  const quarter_turns = Math.round(angle / QUARTER_TURN_DEGREES);
  return { degrees: angle - quarter_turns * QUARTER_TURN_DEGREES, quarter_turns: (quarter_turns + 4) % 4 };
}

function describe_top_side(quarter_turns) {
  const top_side_text = TOP_SIDE_TEXTS[quarter_turns];
  return top_side_text === undefined ? null : `Lado de cima da foto ${top_side_text}.`;
}

function describe_tilt(tilt_degrees) {
  const rounded_tilt = Math.round(Math.abs(tilt_degrees));
  if (rounded_tilt < TILT_REPORT_THRESHOLD_DEGREES) {
    return "torta.";
  }
  return `inclinada ${rounded_tilt}° para a ${tilt_degrees < 0 ? "esquerda" : "direita"}.`;
}

function describe_rectangle_edges(frame) {
  const bounds = find_frame_bounds(frame);
  const [left, top, right, bottom] = [bounds.left, bounds.top, bounds.right, bounds.bottom].map(to_percent);
  return `esquerda ${left}%, topo ${top}%, direita ${right}%, base ${bottom}%.`;
}

function describe_corner_coordinates(frame) {
  return CORNER_ROLES.map(
    (role) => `${CORNER_TEXTS[role]} (${to_percent(frame[role].x)}%, ${to_percent(frame[role].y)}%)`,
  ).join(", ");
}

function describe_frame(frame, subject) {
  const { label, surface } = subject;
  if (is_whole_page_frame(frame)) {
    return WHOLE_PAGE_DESCRIPTION;
  }
  const tilt = measure_frame_tilt(frame, surface);
  const top_side_sentence = describe_top_side(tilt.quarter_turns);
  const sentences = is_rectangle_frame(frame)
    ? [`${label}: ${describe_rectangle_edges(frame)}`, top_side_sentence]
    : [`${label}: ${describe_tilt(tilt.degrees)}`, top_side_sentence, `Cantos: ${describe_corner_coordinates(frame)}.`];
  return sentences.filter((sentence) => sentence !== null).join(" ");
}

function describe_corner_position(frame, corner) {
  const point = frame[corner];
  return `${CORNER_LABELS[corner]} em (${to_percent(point.x)}%, ${to_percent(point.y)}%).`;
}

function describe_edge_position(frame, edge) {
  const [start_role, end_role] = EDGE_CORNER_ROLES[edge];
  const start = frame[start_role];
  const end = frame[end_role];
  return (
    `${EDGE_LABELS[edge]}: de (${to_percent(start.x)}%, ${to_percent(start.y)}%) ` +
    `a (${to_percent(end.x)}%, ${to_percent(end.y)}%).`
  );
}

function read_corner_label(corner) {
  return CORNER_LABELS[corner];
}

function read_edge_label(edge) {
  return EDGE_LABELS[edge];
}
