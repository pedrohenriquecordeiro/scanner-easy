"use strict";

// Pure addresses and texts of the last scan of the quick mode (no DOM); last-scan-panel.js and application.js wire them
// to the page. Uses describe_no_frame_detected from frame-dialog-policy.js, which index.html loads first.

const LAST_SCAN_PATH = "/api/scans/last";
const LAST_SCAN_ROTATION_PATH = `${LAST_SCAN_PATH}/rotation`;
const LAST_SCAN_CROPS_PATH = `${LAST_SCAN_PATH}/crops`;
const LAST_SCAN_CROPS_DETECTION_PATH = `${LAST_SCAN_CROPS_PATH}/detect`;
const LAST_SCAN_ACTIONS = Object.freeze({ ROTATE: "rotate", SET_CROPS: "set_crops", DETECT: "detect_crops" });
// The answers that say the page and the server disagree about the last scan: the state is read again at once.
const LAST_SCAN_RELOAD_ERROR_CODES = Object.freeze([
  "no_last_scan",
  "last_scan_file_missing",
  "saved_scan_unreadable",
  "last_scan_not_editable",
]);
const LAST_SCAN_SUBJECT_TEXT = "nesta digitalização";
const LAST_SCAN_TITLE_TEXT = "Última digitalização: moldura de corte";
const LAST_SCAN_GONE_TEXT = "Essa digitalização foi substituída por outra.";
const LAST_SCAN_HINT_TEXT = "Ajustes regravam os arquivos salvos.";
const LAST_SCAN_NOT_EDITABLE_HINT_TEXT =
  "O original desta digitalização não foi guardado; os arquivos foram salvos normalmente.";
const LAST_SCAN_ROTATED_TEXT = "Última digitalização girada 90° para a direita.";
const SINGLE_FILE_COUNT = 1;

function classify_last_scan_edit(edit_request) {
  if (edit_request.path === LAST_SCAN_ROTATION_PATH) {
    return LAST_SCAN_ACTIONS.ROTATE;
  }
  return edit_request.path === LAST_SCAN_CROPS_DETECTION_PATH ? LAST_SCAN_ACTIONS.DETECT : LAST_SCAN_ACTIONS.SET_CROPS;
}

function choose_last_scan_thumbnail_version(thumbnail_version) {
  // The state brings the revision of the files; an adjustment made here adds a serial, so the picture reloads at once.
  const { revision, edit_serial } = thumbnail_version;
  return edit_serial === 0 ? String(revision) : `${revision}-${edit_serial}`;
}

function build_last_scan_thumbnail_address(thumbnail_version) {
  return `${LAST_SCAN_PATH}/thumbnail?version=${thumbnail_version}`;
}

function build_last_scan_preview_address(scan_identifier, rotation_degrees) {
  // The scan and the rotation are in the address: the answer never changes, so the browser can keep it for good.
  return `${LAST_SCAN_PATH}/preview?scan_identifier=${scan_identifier}&rotation_degrees=${rotation_degrees}`;
}

function join_names(names) {
  if (names.length <= SINGLE_FILE_COUNT) {
    return names.join("");
  }
  return `${names.slice(0, -1).join(", ")} e ${names[names.length - 1]}`;
}

function describe_file_count(file_count) {
  return file_count === SINGLE_FILE_COUNT ? `${SINGLE_FILE_COUNT} arquivo` : `${file_count} arquivos`;
}

function describe_saved_scan_status(last_result) {
  const { file_names } = last_result;
  if (file_names.length === SINGLE_FILE_COUNT) {
    return `Pronto! Salvo como ${file_names[0]}`;
  }
  return `Pronto! ${file_names.length} arquivos salvos: ${join_names(file_names)}`;
}

function describe_deleted_files(previous_file_names, deleted_file_names) {
  return deleted_file_names.map((file_name) => {
    const frame_number = previous_file_names.indexOf(file_name) + 1;
    return `O arquivo ${file_name} foi apagado porque a moldura ${frame_number} foi removida.`;
  });
}

function describe_kept_files(kept_file_names) {
  return kept_file_names.map((file_name) => `Mantive ${file_name} porque ele foi alterado depois de gravado.`);
}

function describe_created_files(previous_file_names, current_file_names) {
  const created_names = current_file_names.filter((file_name) => !previous_file_names.includes(file_name));
  if (created_names.length === 0) {
    return [];
  }
  const lead = created_names.length === SINGLE_FILE_COUNT ? "Novo arquivo" : "Novos arquivos";
  return [`${lead}: ${join_names(created_names)}.`];
}

function describe_last_scan_action(action, edited_scan) {
  const file_count = edited_scan.file_names.length;
  if (action === LAST_SCAN_ACTIONS.ROTATE) {
    return LAST_SCAN_ROTATED_TEXT;
  }
  if (action === LAST_SCAN_ACTIONS.DETECT) {
    return `Molduras detectadas: ${describe_file_count(file_count)}.`;
  }
  return edited_scan.crops.length === 0
    ? `Corte removido: ${describe_file_count(file_count)}.`
    : `Moldura aplicada: ${describe_file_count(file_count)}.`;
}

function describe_last_scan_edit(edit) {
  // What an adjustment did to the saved files, in one text for the status line of the panel.
  const { action, previous_file_names, answer } = edit;
  if (action === LAST_SCAN_ACTIONS.DETECT && answer.crops_detected === false) {
    return describe_no_frame_detected(LAST_SCAN_SUBJECT_TEXT);
  }
  const edited_scan = answer.last_result;
  return [
    describe_last_scan_action(action, edited_scan),
    ...describe_created_files(previous_file_names, edited_scan.file_names),
    ...describe_deleted_files(previous_file_names, answer.deleted_file_names),
    ...describe_kept_files(answer.kept_file_names),
  ].join(" ");
}

function describe_last_scan_rotation_for_dialog(rotation_degrees, frame_count) {
  const total_text = rotation_degrees === 0 ? "de volta à posição original" : `total: ${rotation_degrees}°`;
  const rotation_text = `Última digitalização girada 90° para a direita (${total_text}).`;
  if (frame_count === 0) {
    return rotation_text;
  }
  return frame_count === SINGLE_FILE_COUNT
    ? `${rotation_text} A moldura acompanhou o giro.`
    : `${rotation_text} As molduras acompanharam o giro.`;
}

function describe_last_scan_thumbnail_label(file_names) {
  return file_names.length === SINGLE_FILE_COUNT
    ? "Miniatura da última digitalização"
    : `Miniatura da última digitalização (${file_names.length} fotos)`;
}
