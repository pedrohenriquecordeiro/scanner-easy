"use strict";

// Pure rules of the Documento mode (no DOM); document-panel.js and application.js wire them to the page.
// Uses IDLE_PHASE, SPACE_KEY_CODE, BUTTON_TAG_NAME, KEYBOARD_RESERVED_TAG_NAMES and can_start_scan from
// scan-trigger-policy.js and describe_expected_scan_duration from scan-quality-policy.js, which index.html loads
// first. The texts of the frame dialog are shared with the quick mode (last-scan-policy.js).

const DOCUMENT_PATH = "/api/document";
const DOCUMENT_PAGES_PATH = `${DOCUMENT_PATH}/pages`;

const CAPTURE_MODES = Object.freeze({ SINGLE: "single", DOCUMENT: "document" });
const LARGE_DOCUMENT_PAGE_COUNT = 300;
const LARGE_DOCUMENT_SIZE_IN_BYTES = 1024 ** 3;
// The draft guard asks for 1 GiB plus 3 pages (SAFETY_MARGIN_PAGES), so the warning comes before the refusal.
const DRAFT_STORAGE_WARNING_PAGES = 3;
const PAGE_PLACEMENTS = Object.freeze({ BEFORE: "before", AFTER: "after" });
const DOCUMENT_KEY_ACTIONS = Object.freeze({
  IGNORE: "ignore",
  SUPPRESS: "suppress",
  DISCARD_LAST_PAGE: "discard_last_page",
  REQUEST_FINALIZE: "request_finalize",
  FOCUS_SCAN_BUTTON: "focus_scan_button",
});
const CONFIRMATION_KEY_ACTIONS = Object.freeze({ IGNORE: "ignore", SUPPRESS: "suppress" });
const DOCUMENT_EVENTS = Object.freeze({
  NONE: "none",
  PAGE_ADDED: "page_added",
  PAGE_FAILED: "page_failed",
  EDITED: "edited",
});
const DOCUMENT_ACTIONS = Object.freeze({
  MOVE: "move",
  DELETE: "delete",
  DISCARD_LAST: "discard_last",
  ROTATE: "rotate",
  FRAME_CLOSED: "frame_closed",
  DROP: "drop",
  NAME_SAVED: "name_saved",
  DIALOG_CLOSED: "dialog_closed",
  FINALIZED: "finalized",
  CANCELLED: "cancelled",
});
const FOCUS_TARGETS = Object.freeze({
  SCAN_BUTTON: "scan_button",
  SAME_BUTTON: "same_button",
  DELETE_BUTTON: "delete_button",
  ROTATE_BUTTON: "rotate_button",
  ENLARGE_BUTTON: "enlarge_button",
});
const DRAFT_ENDINGS = Object.freeze({
  FINALIZED: "finalized",
  CANCELLED: "cancelled",
  LAST_PAGE_REMOVED_HERE: "last_page_removed_here",
  ENDED_ELSEWHERE: "ended_elsewhere",
});
const NAME_FIELD_DECISIONS = Object.freeze({ KEEP: "keep", CLEAR: "clear" });
const RECOVERY_OUTCOMES = Object.freeze({
  RESUMED: "resumed",
  PAGES_LOST: "pages_lost",
  SET_ASIDE: "set_aside",
  FAILED: "failed",
});
const DOCUMENT_RELOAD_ERROR_CODES = Object.freeze(["invalid_page_order", "page_not_found", "no_open_document"]);

const BACKSPACE_KEY_CODE = "Backspace";
const ENTER_KEY_CODE = "Enter";
const NUMPAD_ENTER_KEY_CODE = "NumpadEnter";
const ESCAPE_KEY_CODE = "Escape";
const PAGE_SHORTCUT_KEY_CODES_HIDDEN_FROM_DIALOGS = Object.freeze([SPACE_KEY_CODE, BACKSPACE_KEY_CODE]);
const DOCUMENT_SHORTCUT_KEY_CODES = Object.freeze([BACKSPACE_KEY_CODE, ENTER_KEY_CODE, NUMPAD_ENTER_KEY_CODE]);
const SCAN_BUTTON_FOCUS_ACTIONS = Object.freeze([
  DOCUMENT_ACTIONS.DISCARD_LAST,
  DOCUMENT_ACTIONS.NAME_SAVED,
  DOCUMENT_ACTIONS.DIALOG_CLOSED,
  DOCUMENT_ACTIONS.FINALIZED,
  DOCUMENT_ACTIONS.CANCELLED,
  DOCUMENT_ACTIONS.DROP,
]);
const FIRST_POSITION = 1;
const SINGLE_PAGE = 1;
const HALF = 2;
const CLOCK_TIME_PATTERN = /T(\d{2}):(\d{2})/;
const NUMBER_LOCALE = "pt-BR";
const ACTIVE_PAGE_PHASE_TEXTS = Object.freeze({
  preparing: (page_number) => `Preparando a página ${page_number}…`,
  scanning: (page_number, dots_per_inch) =>
    `Digitalizando a página ${page_number}… (${describe_expected_scan_duration(dots_per_inch)})`,
  saving: (page_number) => `Guardando a página ${page_number}…`,
});
const PAGE_REMOVAL_VERBS = Object.freeze({ discard_last: "descartada", delete: "excluída" });
const NEXT_SHEET_TEXT = "Coloque a próxima folha e aperte Espaço; Enter salva.";
const FRAME_PAGE_GONE_TEXT = "Essa página não está mais no documento.";
const PAGE_SUBJECT_TEXT = "nesta página";
const TWO_FRAMES_COUNT = 2;

function build_page_path(page_identifier) {
  return `${DOCUMENT_PAGES_PATH}/${page_identifier}`;
}

function build_page_rotation_path(page_identifier) {
  return `${build_page_path(page_identifier)}/rotation`;
}

function build_page_crops_path(page_identifier) {
  return `${build_page_path(page_identifier)}/crops`;
}

function build_page_crops_detection_path(page_identifier) {
  return `${build_page_crops_path(page_identifier)}/detect`;
}

function build_page_thumbnail_address(page_identifier, rotation_degrees) {
  // The rotation is part of the address: the answer is a pure function of the page and the rotation, so it can be
  // kept for good and a turned page simply asks for another address.
  return `${build_page_path(page_identifier)}/thumbnail?rotation_degrees=${rotation_degrees}`;
}

function build_page_preview_address(page_identifier, rotation_degrees) {
  return `${build_page_path(page_identifier)}/preview?rotation_degrees=${rotation_degrees}`;
}

function move_page(page_identifiers, page_identifier, target_index) {
  const moved_order = page_identifiers.filter((identifier) => identifier !== page_identifier);
  moved_order.splice(target_index, 0, page_identifier);
  return moved_order;
}

function move_page_by_offset(page_identifiers, page_identifier, offset) {
  const current_index = page_identifiers.indexOf(page_identifier);
  const target_index = current_index + offset;
  if (current_index < 0 || target_index < 0 || target_index >= page_identifiers.length) {
    return [...page_identifiers];
  }
  return move_page(page_identifiers, page_identifier, target_index);
}

function move_page_to_position(page_identifiers, page_identifier, position) {
  if (!page_identifiers.includes(page_identifier)) {
    return [...page_identifiers];
  }
  const limited_position = Math.min(Math.max(position, FIRST_POSITION), page_identifiers.length);
  return move_page(page_identifiers, page_identifier, limited_position - FIRST_POSITION);
}

function move_page_next_to(page_identifiers, page_drop) {
  const { dragged_identifier, target_identifier, placement } = page_drop;
  const is_known = page_identifiers.includes(dragged_identifier) && page_identifiers.includes(target_identifier);
  if (!is_known || dragged_identifier === target_identifier) {
    return [...page_identifiers];
  }
  const remaining_identifiers = page_identifiers.filter((identifier) => identifier !== dragged_identifier);
  const target_index = remaining_identifiers.indexOf(target_identifier);
  const insertion_index = placement === PAGE_PLACEMENTS.BEFORE ? target_index : target_index + 1;
  remaining_identifiers.splice(insertion_index, 0, dragged_identifier);
  return remaining_identifiers;
}

function choose_drop_placement(pointer_horizontal_position, tile_box) {
  const middle = tile_box.left + tile_box.width / HALF;
  return pointer_horizontal_position < middle ? PAGE_PLACEMENTS.BEFORE : PAGE_PLACEMENTS.AFTER;
}

function is_same_order(first_identifiers, second_identifiers) {
  return (
    first_identifiers.length === second_identifiers.length &&
    first_identifiers.every((identifier, index) => identifier === second_identifiers[index])
  );
}

function should_render_document_body(rendered_version, body_version) {
  if (rendered_version === null || rendered_version.draft_session !== body_version.draft_session) {
    return true;
  }
  // A late answer from an older revision never undoes a newer edit on screen (R19).
  return body_version.revision >= rendered_version.revision;
}

function can_edit_document(document_activity) {
  return (
    document_activity.scan_phase === IDLE_PHASE &&
    !document_activity.is_start_request_pending &&
    !document_activity.is_edit_request_pending
  );
}

function can_start_document_page(document_activity) {
  return can_start_scan(document_activity) && !document_activity.is_edit_request_pending;
}

function is_text_entry(target) {
  return KEYBOARD_RESERVED_TAG_NAMES.includes(target.tagName) || target.isContentEditable === true;
}

function decide_document_key_action(key_event, document_activity) {
  if (document_activity.capture_mode !== CAPTURE_MODES.DOCUMENT || document_activity.is_confirmation_open) {
    return DOCUMENT_KEY_ACTIONS.IGNORE;
  }
  if (key_event.code === ESCAPE_KEY_CODE) {
    return DOCUMENT_KEY_ACTIONS.FOCUS_SCAN_BUTTON;
  }
  if (!DOCUMENT_SHORTCUT_KEY_CODES.includes(key_event.code) || is_text_entry(key_event.target)) {
    return DOCUMENT_KEY_ACTIONS.IGNORE;
  }
  const is_backspace = key_event.code === BACKSPACE_KEY_CODE;
  const is_other_button =
    key_event.target.tagName === BUTTON_TAG_NAME && key_event.target !== document_activity.scan_button;
  // Enter on any other button activates that button natively (×, ◀, ▶, Cancelar…).
  if (!is_backspace && is_other_button) {
    return DOCUMENT_KEY_ACTIONS.IGNORE;
  }
  if (key_event.repeat || document_activity.page_count === 0 || !document_activity.can_edit) {
    return DOCUMENT_KEY_ACTIONS.SUPPRESS;
  }
  return is_backspace ? DOCUMENT_KEY_ACTIONS.DISCARD_LAST_PAGE : DOCUMENT_KEY_ACTIONS.REQUEST_FINALIZE;
}

function decide_confirmation_key_action(key_event, confirmation_state) {
  if (key_event.code === ESCAPE_KEY_CODE) {
    return CONFIRMATION_KEY_ACTIONS.IGNORE;
  }
  // A held key, the "add page" reflex on Space or the key that opened the dialog never confirms it.
  if (key_event.repeat || key_event.code === SPACE_KEY_CODE || !confirmation_state.is_armed) {
    return CONFIRMATION_KEY_ACTIONS.SUPPRESS;
  }
  return CONFIRMATION_KEY_ACTIONS.IGNORE;
}

function focus_on_scan_button() {
  return { target: FOCUS_TARGETS.SCAN_BUTTON, page_identifier: null };
}

function decide_focus_after_action(action_context) {
  const { action, is_keyboard_initiated, page_identifiers_after, acted_page_identifier, acted_position } =
    action_context;
  if (SCAN_BUTTON_FOCUS_ACTIONS.includes(action) || !is_keyboard_initiated) {
    return focus_on_scan_button();
  }
  if (action === DOCUMENT_ACTIONS.MOVE) {
    return { target: FOCUS_TARGETS.SAME_BUTTON, page_identifier: acted_page_identifier };
  }
  if (action === DOCUMENT_ACTIONS.FRAME_CLOSED) {
    return { target: FOCUS_TARGETS.ENLARGE_BUTTON, page_identifier: acted_page_identifier };
  }
  if (page_identifiers_after.length === 0) {
    return focus_on_scan_button();
  }
  if (action === DOCUMENT_ACTIONS.ROTATE) {
    // A rotation only changes the page's metadata: it is still the same page, with the same buttons.
    return { target: FOCUS_TARGETS.ROTATE_BUTTON, page_identifier: acted_page_identifier };
  }
  const focused_position = Math.min(acted_position, page_identifiers_after.length);
  const focused_page_identifier = page_identifiers_after[focused_position - FIRST_POSITION];
  return { target: FOCUS_TARGETS.DELETE_BUTTON, page_identifier: focused_page_identifier };
}

function should_hide_key_from_page_shortcuts(key_event) {
  // The Espaço that scans and the Backspace that discards a page must not reach the page from inside a dialog.
  return PAGE_SHORTCUT_KEY_CODES_HIDDEN_FROM_DIALOGS.includes(key_event.code);
}

function next_document_event(previous_observation, observation, previous_event) {
  if (previous_observation === null || previous_observation.draft_session !== observation.draft_session) {
    return DOCUMENT_EVENTS.NONE;
  }
  if (previous_observation.capture_mode !== observation.capture_mode) {
    return DOCUMENT_EVENTS.EDITED;
  }
  if (
    observation.page_count > previous_observation.page_count &&
    observation.scans_completed > previous_observation.scans_completed
  ) {
    return DOCUMENT_EVENTS.PAGE_ADDED;
  }
  if (previous_observation.last_error_code === null && observation.last_error_code !== null) {
    return DOCUMENT_EVENTS.PAGE_FAILED;
  }
  if (observation.revision !== previous_observation.revision) {
    return DOCUMENT_EVENTS.EDITED;
  }
  return previous_event;
}

function decide_name_field_after_draft_end(draft_ending) {
  // Only removing the last page here keeps the typed name for the next first page (R3).
  return draft_ending === DRAFT_ENDINGS.LAST_PAGE_REMOVED_HERE ? NAME_FIELD_DECISIONS.KEEP : NAME_FIELD_DECISIONS.CLEAR;
}

function decide_name_to_send(name_field) {
  if (!name_field.document_exists) {
    return null;
  }
  const trimmed_name = name_field.typed_name.trim();
  return trimmed_name === name_field.saved_name ? null : trimmed_name;
}

function should_switch_to_document_mode(switch_check) {
  const { document_body, capture_mode, switched_draft_session } = switch_check;
  const recovery = document_body.recovery;
  return (
    recovery !== null &&
    recovery.outcome === RECOVERY_OUTCOMES.RESUMED &&
    capture_mode === CAPTURE_MODES.SINGLE &&
    document_body.draft_session !== switched_draft_session
  );
}

function should_warn_about_large_document(document_size) {
  return (
    document_size.page_count > LARGE_DOCUMENT_PAGE_COUNT ||
    document_size.estimated_size_in_bytes > LARGE_DOCUMENT_SIZE_IN_BYTES
  );
}

function should_warn_about_draft_storage(draft_storage) {
  return !draft_storage.available || draft_storage.estimated_pages_remaining < DRAFT_STORAGE_WARNING_PAGES;
}

function should_reload_document_after_error(error_code) {
  return DOCUMENT_RELOAD_ERROR_CODES.includes(error_code);
}

function describe_page_count(page_count) {
  if (page_count === SINGLE_PAGE) {
    return `${SINGLE_PAGE} página`;
  }
  return `${page_count.toLocaleString(NUMBER_LOCALE)} páginas`;
}

function describe_document_status(scan_phase, document_progress) {
  const { page_count, last_event, dots_per_inch, is_finalizing } = document_progress;
  const describe_active_phase = ACTIVE_PAGE_PHASE_TEXTS[scan_phase];
  if (describe_active_phase !== undefined) {
    return describe_active_phase(page_count + 1, dots_per_inch);
  }
  if (is_finalizing) {
    return `Salvando o PDF (${describe_page_count(page_count)})…`;
  }
  if (last_event === DOCUMENT_EVENTS.PAGE_FAILED) {
    return "A última página não foi adicionada. Coloque a folha de novo e aperte Espaço.";
  }
  if (page_count === 0) {
    return "Modo Documento: coloque a primeira folha no vidro e aperte Espaço.";
  }
  if (last_event === DOCUMENT_EVENTS.PAGE_ADDED) {
    return `Página ${page_count} adicionada. ${NEXT_SHEET_TEXT}`;
  }
  return `${describe_page_count(page_count)} no documento. ${NEXT_SHEET_TEXT}`;
}

function describe_page_removal(page_removal) {
  const { action, position, remaining_page_count } = page_removal;
  const removal_text = `Página ${position} ${PAGE_REMOVAL_VERBS[action]}.`;
  if (remaining_page_count === 0) {
    return `${removal_text} O documento foi encerrado.`;
  }
  return `${removal_text} O documento tem ${describe_page_count(remaining_page_count)}.`;
}

function describe_page_move(position_before, position_after) {
  return `Página ${position_before} movida para a posição ${position_after}`;
}

// The total is in the text so that turning the same page again changes what a screen reader reads.
function describe_page_rotation(page_rotation) {
  const { position, rotation_degrees } = page_rotation;
  const total_text = rotation_degrees === 0 ? "de volta à posição original" : `total: ${rotation_degrees}°`;
  return `Página ${position} girada 90° para a direita (${total_text}).`;
}

function describe_page_rotation_result(rotation_result) {
  const { position, rotation_degrees, crop_count } = rotation_result;
  const rotation_text = describe_page_rotation({ position, rotation_degrees });
  if (crop_count === 0) {
    return rotation_text;
  }
  return crop_count === 1 ? `${rotation_text} A moldura acompanhou o giro.` : `${rotation_text} As molduras acompanharam o giro.`;
}

function describe_pages_of_the_pdf(page_count, output_page_count) {
  // A page with two frames becomes two pages of the PDF, so the count of the scanned pages is not the count of the PDF.
  if (output_page_count === page_count) {
    return describe_page_count(page_count);
  }
  return `${describe_page_count(page_count)} (${output_page_count.toLocaleString(NUMBER_LOCALE)} no PDF)`;
}

function describe_tile_label(tile_label) {
  const { position, page_count, crop_count } = tile_label;
  const position_text = `Página ${position} de ${page_count}`;
  if (crop_count === 0) {
    return position_text;
  }
  if (crop_count === 1) {
    return `${position_text}, com moldura de corte`;
  }
  return `${position_text}, com ${crop_count} molduras de corte (${crop_count} páginas no PDF)`;
}

function describe_crop_count(crop_count) {
  // Said in words on the tile for whoever does not see the colours; one frame needs no count.
  return crop_count >= TWO_FRAMES_COUNT ? `${crop_count} molduras` : null;
}

function describe_enlarge_label(position) {
  return `Ampliar a página ${position} e ajustar a moldura de corte`;
}

function describe_frame_dialog_title(page_position) {
  return `Página ${page_position.position} de ${page_position.page_count}: moldura de corte`;
}

function describe_page_crop_application(crop_application) {
  const { position, crop_count } = crop_application;
  if (crop_count === 0) {
    return `Corte removido da página ${position}.`;
  }
  if (crop_count === 1) {
    return `Moldura aplicada à página ${position}.`;
  }
  return `Molduras aplicadas à página ${position} (${crop_count} páginas no PDF).`;
}

function join_positions(positions) {
  if (positions.length === SINGLE_PAGE) {
    return String(positions[0]);
  }
  return `${positions.slice(0, -1).join(", ")} e ${positions[positions.length - 1]}`;
}

function describe_dropped_pages(dropped_page_positions) {
  if (dropped_page_positions.length === 0) {
    return "";
  }
  if (dropped_page_positions.length === SINGLE_PAGE) {
    return ` A página ${dropped_page_positions[0]} não pôde ser recuperada; digitalize-a de novo.`;
  }
  return ` As páginas ${join_positions(dropped_page_positions)} não puderam ser recuperadas; digitalize-as de novo.`;
}

function describe_set_aside_files(set_aside_folder) {
  return set_aside_folder === null ? "" : ` Os arquivos danificados foram guardados em ${set_aside_folder}.`;
}

function describe_recovery(recovery) {
  if (recovery === null) {
    return null;
  }
  if (recovery.outcome === RECOVERY_OUTCOMES.RESUMED) {
    return (
      `Documento em andamento recuperado: ${describe_page_count(recovery.kept_page_count)}.` +
      describe_dropped_pages(recovery.dropped_page_positions) +
      describe_set_aside_files(recovery.set_aside_folder)
    );
  }
  if (recovery.outcome === RECOVERY_OUTCOMES.PAGES_LOST) {
    return (
      "Não consegui recuperar nenhuma página do documento em andamento." +
      describe_set_aside_files(recovery.set_aside_folder)
    );
  }
  if (recovery.outcome === RECOVERY_OUTCOMES.SET_ASIDE) {
    return `Não consegui ler o documento em andamento. As páginas foram guardadas em ${recovery.set_aside_folder}.`;
  }
  return (
    "Não consegui abrir o documento em andamento. Nada foi apagado: feche o Digitalizadora e abra de novo. " +
    "Detalhes em ~/Library/Logs/Digitalizadora."
  );
}

function format_clock_time(moment_text) {
  const [, hours, minutes] = CLOCK_TIME_PATTERN.exec(moment_text);
  return `${hours}:${minutes}`;
}

function describe_possible_previous_save(document) {
  if (document === null) {
    return null;
  }
  if (document.finished_document_path !== null) {
    return (
      `Este documento talvez já tenha sido salvo como ${document.finished_document_path}. ` +
      "Confira antes de salvar de novo."
    );
  }
  if (document.finalization_started_at !== null) {
    // The server's local time, as written in the manifest, so the text matches what the user saw on the clock.
    return (
      `Uma finalização deste documento foi interrompida às ${format_clock_time(document.finalization_started_at)}. ` +
      "Confira na pasta de saída se o PDF já existe antes de salvar de novo."
    );
  }
  return null;
}

function describe_pending_document(page_count, output_page_count) {
  return `Documento em andamento: ${describe_pages_of_the_pdf(page_count, output_page_count)}`;
}

function describe_finished_document(last_finished_document) {
  if (last_finished_document === null) {
    return null;
  }
  const { file_name, page_count } = last_finished_document;
  return `Pronto! Salvo como ${file_name} (${describe_page_count(page_count)})`;
}
