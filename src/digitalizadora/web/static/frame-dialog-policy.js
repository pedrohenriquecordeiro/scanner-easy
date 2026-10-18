"use strict";

// Pure texts and rules of the frame dialog (the enlarged view where the crop frames are adjusted), shared by the
// Documento mode and the quick mode (no DOM). page-frame-editor.js, document-panel.js and last-scan-panel.js wire
// them to the page; index.html loads this file after page-frame-geometry.js.

const FRAME_CHANGES_DISCARDED_TEXT = "Alterações da moldura descartadas.";
const FRAME_LIMIT_TEXT = "Só dá para ter 2 molduras.";
const FRAME_REWRITING_TEXT = "Regravando…";
const INVALID_FRAME_MOVE_TEXT = "Esse movimento deixaria a moldura torta demais. Ela ficou como estava.";
const MORE_THAN_TWO_PHOTOS_TEXT = "Achei mais de 2 fotos; usei as 2 maiores.";
const MOVE_HANDLE_LABEL = "Mover a moldura";
const ROTATE_HANDLE_LABEL = "Girar a moldura";
const SINGLE_FRAME_COUNT = 1;

function describe_frame_label(frame_number) {
  return `Moldura ${frame_number}`;
}

function describe_selected_frame(frame_number, frame_count) {
  return `Moldura ${frame_number} de ${frame_count} selecionada.`;
}

function describe_select_frame_label(frame_number) {
  return `Selecionar moldura ${frame_number}`;
}

function describe_frame_added(frame_number) {
  return `Moldura ${frame_number} adicionada.`;
}

function describe_frame_removed(frame_number) {
  return `Moldura ${frame_number} removida.`;
}

function describe_frame_output_turned(frame_number) {
  return `Moldura ${frame_number} girada: o lado de cima da foto mudou.`;
}

function describe_rotate_frame_label(frame_number) {
  return `Girar a moldura ${frame_number} em 90 graus para a direita: muda o lado de cima da foto recortada`;
}

function describe_handle_label(handle_label, frame_context) {
  // With two frames the handles belong to the selected one, and the label says which.
  const { frame_number, frame_count } = frame_context;
  return frame_count > SINGLE_FRAME_COUNT ? `${handle_label} da moldura ${frame_number}` : handle_label;
}

function describe_grip_label(grip_label, frame_context) {
  // "Mover a moldura" already names the frame: with two of them it only gets the number.
  const { frame_number, frame_count } = frame_context;
  return frame_count > SINGLE_FRAME_COUNT ? `${grip_label} ${frame_number}` : grip_label;
}

function describe_frame_image_failed(subject_text) {
  return `Não consegui carregar a imagem ampliada ${subject_text}.`;
}

function describe_no_frame_detected(subject_text) {
  return `Não achei uma borda confiável ${subject_text}. As molduras não mudaram.`;
}

function describe_detected_frames(detection) {
  const { frame_count, ignored_region_count } = detection;
  const found_text = frame_count === SINGLE_FRAME_COUNT ? "Achei 1 moldura e salvei." : `Achei ${frame_count} molduras e salvei.`;
  return ignored_region_count > 0 ? `${found_text} ${MORE_THAN_TWO_PHOTOS_TEXT}` : found_text;
}
