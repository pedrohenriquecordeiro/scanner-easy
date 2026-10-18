import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE_EXECUTABLE = shutil.which("node")
HARNESS_PATH = Path(__file__).resolve().parent / "document-page-policy-harness.js"
HARNESS_TIMEOUT_SECONDS = 30
NEXT_SHEET_TEXT = "Coloque a próxima folha e aperte Espaço; Enter finaliza."
FOCUS_ON_SCAN_BUTTON = {"target": "scan_button", "page_identifier": None}

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so document-page-policy.js cannot be exercised"
)

MOVE_CASES = [
    pytest.param("move_page_by_offset(['a', 'b', 'c'], 'b', -1)", ["b", "a", "c"], id="left-in-the-middle"),
    pytest.param("move_page_by_offset(['a', 'b', 'c'], 'b', 1)", ["a", "c", "b"], id="right-in-the-middle"),
    pytest.param("move_page_by_offset(['a', 'b', 'c'], 'a', -1)", ["a", "b", "c"], id="left-of-the-first-page"),
    pytest.param("move_page_by_offset(['a', 'b', 'c'], 'c', 1)", ["a", "b", "c"], id="right-of-the-last-page"),
    pytest.param("move_page_by_offset(['a', 'b', 'c'], 'z', 1)", ["a", "b", "c"], id="unknown-page"),
    pytest.param(
        "(() => { const order = ['a', 'b', 'c']; return move_page_by_offset(order, 'c', 1) !== order; })()",
        True,
        id="always-a-new-list",
    ),
    pytest.param("move_page_to_position(['a', 'b', 'c'], 'c', 1)", ["c", "a", "b"], id="to-position-1"),
    pytest.param("move_page_to_position(['a', 'b', 'c'], 'a', 3)", ["b", "c", "a"], id="to-the-last-position"),
    pytest.param("move_page_to_position(['a', 'b', 'c'], 'c', 0)", ["c", "a", "b"], id="position-0-goes-first"),
    pytest.param("move_page_to_position(['a', 'b', 'c'], 'a', 4)", ["b", "c", "a"], id="past-the-end-goes-last"),
    pytest.param("move_page_to_position(['a', 'b', 'c'], 'b', 2)", ["a", "b", "c"], id="to-its-own-position"),
]

DROP_CASES = [
    pytest.param(
        "move_page_next_to(['a', 'b', 'c'], {dragged_identifier: 'c', target_identifier: 'a', placement: 'before'})",
        ["c", "a", "b"],
        id="before-the-first-page",
    ),
    pytest.param(
        "move_page_next_to(['a', 'b', 'c'], {dragged_identifier: 'a', target_identifier: 'c', placement: 'after'})",
        ["b", "c", "a"],
        id="after-the-last-page",
    ),
    pytest.param(
        "move_page_next_to(['a', 'b', 'c'], {dragged_identifier: 'a', target_identifier: 'b', placement: 'after'})",
        ["b", "a", "c"],
        id="after-a-middle-page",
    ),
    pytest.param(
        "move_page_next_to(['a', 'b', 'c'], {dragged_identifier: 'b', target_identifier: 'b', placement: 'before'})",
        ["a", "b", "c"],
        id="on-itself",
    ),
    pytest.param("choose_drop_placement(10, {left: 0, width: 100})", "before", id="left-half-of-the-tile"),
    pytest.param("choose_drop_placement(90, {left: 0, width: 100})", "after", id="right-half-of-the-tile"),
    pytest.param("choose_drop_placement(50, {left: 0, width: 100})", "after", id="exact-middle-of-the-tile"),
    pytest.param("choose_drop_placement(149, {left: 100, width: 100})", "before", id="tile-away-from-the-edge"),
    pytest.param("is_same_order(['a', 'b'], ['a', 'b'])", True, id="same-order"),
    pytest.param("is_same_order(['a', 'b'], ['b', 'a'])", False, id="other-order"),
    pytest.param("is_same_order(['a', 'b'], ['a', 'b', 'c'])", False, id="other-length"),
]

RENDER_CASES = [
    pytest.param("should_render_document_body(null, {draft_session: 's1', revision: 0})", True, id="nothing-rendered"),
    pytest.param(
        "should_render_document_body({draft_session: 's1', revision: 5}, {draft_session: 's2', revision: 0})",
        True,
        id="other-session",
    ),
    pytest.param(
        "should_render_document_body({draft_session: 's1', revision: 5}, {draft_session: 's1', revision: 4})",
        False,
        id="lower-revision-is-ignored",
    ),
    pytest.param(
        "should_render_document_body({draft_session: 's1', revision: 5}, {draft_session: 's1', revision: 5})",
        True,
        id="equal-revision",
    ),
    pytest.param(
        "should_render_document_body({draft_session: 's1', revision: 5}, {draft_session: 's1', revision: 6})",
        True,
        id="higher-revision",
    ),
]

ACTIVITY_CASES = [
    pytest.param("can_edit_document(page_activity({}))", True, id="edit-when-idle"),
    pytest.param("can_edit_document(page_activity({scan_phase: 'scanning'}))", False, id="no-edit-during-a-scan"),
    pytest.param("can_edit_document(page_activity({is_start_request_pending: true}))", False,
                 id="no-edit-while-a-page-request-is-pending"),
    pytest.param("can_edit_document(page_activity({is_edit_request_pending: true}))", False,
                 id="no-edit-while-an-edit-is-pending"),
    pytest.param("can_start_document_page(page_activity({}))", True, id="page-when-idle"),
    pytest.param("can_start_document_page(page_activity({is_edit_request_pending: true}))", False,
                 id="no-page-while-finalizing"),
    pytest.param("can_start_document_page(page_activity({scan_phase: 'saving'}))", False, id="no-page-during-a-scan"),
    pytest.param("can_start_document_page(page_activity({is_start_request_pending: true}))", False,
                 id="no-page-while-a-page-request-is-pending"),
]

DOCUMENT_KEY_CASES = [
    pytest.param("decide_document_key_action(key_on('Backspace', PAGE_BODY), document_activity({}))",
                 "discard_last_page", id="backspace-on-the-page"),
    pytest.param("decide_document_key_action(key_on('Backspace', TEXT_FIELD), document_activity({}))",
                 "ignore", id="backspace-in-a-text-field"),
    pytest.param("decide_document_key_action(key_on('Backspace', EDITABLE_AREA), document_activity({}))",
                 "ignore", id="backspace-in-editable-content"),
    pytest.param("decide_document_key_action(key_on('Backspace', OTHER_BUTTON), document_activity({}))",
                 "discard_last_page", id="backspace-on-another-button"),
    pytest.param("decide_document_key_action(key_on('Enter', SCAN_BUTTON), document_activity({}))",
                 "request_finalize", id="enter-on-the-scan-button"),
    pytest.param("decide_document_key_action(key_on('NumpadEnter', PAGE_BODY), document_activity({}))",
                 "request_finalize", id="numpad-enter-on-the-page"),
    pytest.param("decide_document_key_action(key_on('Enter', OTHER_BUTTON), document_activity({}))",
                 "ignore", id="enter-on-the-delete-button"),
    pytest.param("decide_document_key_action(key_on('Enter', TEXT_FIELD), document_activity({}))",
                 "ignore", id="enter-in-a-text-field"),
    pytest.param("decide_document_key_action(repeated_key_on('Backspace', PAGE_BODY), document_activity({}))",
                 "suppress", id="held-backspace"),
    pytest.param("decide_document_key_action(repeated_key_on('Enter', SCAN_BUTTON), document_activity({}))",
                 "suppress", id="held-enter"),
    pytest.param("decide_document_key_action(key_on('Enter', SCAN_BUTTON), document_activity({page_count: 0}))",
                 "suppress", id="enter-on-the-scan-button-without-pages"),
    pytest.param("decide_document_key_action(key_on('Backspace', PAGE_BODY), document_activity({can_edit: false}))",
                 "suppress", id="backspace-while-editing-is-blocked"),
    pytest.param(
        "decide_document_key_action(key_on('Enter', PAGE_BODY), document_activity({is_confirmation_open: true}))",
        "ignore",
        id="confirmation-open",
    ),
    pytest.param(
        "decide_document_key_action(key_on('Backspace', PAGE_BODY), document_activity({capture_mode: 'single'}))",
        "ignore",
        id="single-mode",
    ),
    pytest.param("decide_document_key_action(key_on('Escape', PAGE_BODY), document_activity({}))",
                 "focus_scan_button", id="escape-on-the-page"),
    pytest.param("decide_document_key_action(key_on('Escape', TEXT_FIELD), document_activity({}))",
                 "focus_scan_button", id="escape-in-the-name-field"),
    pytest.param("decide_document_key_action(key_on('Space', PAGE_BODY), document_activity({}))",
                 "ignore", id="space-keeps-its-own-rule"),
    pytest.param("decide_document_key_action(key_on('KeyA', PAGE_BODY), document_activity({}))",
                 "ignore", id="other-key"),
]

CONFIRMATION_KEY_CASES = [
    pytest.param("decide_confirmation_key_action(key_on('Escape', OTHER_BUTTON), {is_armed: false})",
                 "ignore", id="escape-closes-even-before-arming"),
    pytest.param("decide_confirmation_key_action(repeated_key_on('Enter', OTHER_BUTTON), {is_armed: true})",
                 "suppress", id="held-enter"),
    pytest.param("decide_confirmation_key_action(key_on('Space', OTHER_BUTTON), {is_armed: true})",
                 "suppress", id="space"),
    pytest.param("decide_confirmation_key_action(key_on('Enter', OTHER_BUTTON), {is_armed: false})",
                 "suppress", id="enter-before-arming"),
    pytest.param("decide_confirmation_key_action(key_on('Enter', OTHER_BUTTON), {is_armed: true})",
                 "ignore", id="enter-once-armed"),
]

FOCUS_CASES = [
    pytest.param("decide_focus_after_action(action_context({action: 'discard_last'}))", FOCUS_ON_SCAN_BUTTON,
                 id="discard-last-by-keyboard"),
    pytest.param("decide_focus_after_action(action_context({action: 'name_saved'}))", FOCUS_ON_SCAN_BUTTON,
                 id="name-saved"),
    pytest.param("decide_focus_after_action(action_context({action: 'dialog_closed'}))", FOCUS_ON_SCAN_BUTTON,
                 id="dialog-closed"),
    pytest.param("decide_focus_after_action(action_context({action: 'finalized'}))", FOCUS_ON_SCAN_BUTTON,
                 id="finalized"),
    pytest.param("decide_focus_after_action(action_context({action: 'cancelled'}))", FOCUS_ON_SCAN_BUTTON,
                 id="cancelled"),
    pytest.param("decide_focus_after_action(action_context({action: 'drop'}))", FOCUS_ON_SCAN_BUTTON, id="drop"),
    pytest.param("decide_focus_after_action(action_context({is_keyboard_initiated: false}))", FOCUS_ON_SCAN_BUTTON,
                 id="move-by-pointer"),
    pytest.param(
        "decide_focus_after_action(action_context({action: 'delete', is_keyboard_initiated: false}))",
        FOCUS_ON_SCAN_BUTTON,
        id="delete-by-pointer",
    ),
    pytest.param("decide_focus_after_action(action_context({}))", {"target": "same_button", "page_identifier": "b"},
                 id="move-by-keyboard"),
    pytest.param(
        "decide_focus_after_action(action_context({action: 'delete', page_identifiers_after: ['a', 'c']}))",
        {"target": "delete_button", "page_identifier": "c"},
        id="delete-in-the-middle-by-keyboard",
    ),
    pytest.param(
        "decide_focus_after_action(action_context("
        "{action: 'delete', page_identifiers_after: ['a', 'b'], acted_page_identifier: 'c', acted_position: 3}))",
        {"target": "delete_button", "page_identifier": "b"},
        id="delete-the-last-page-by-keyboard",
    ),
    pytest.param(
        "decide_focus_after_action(action_context("
        "{action: 'delete', page_identifiers_after: [], acted_page_identifier: 'a', acted_position: 1}))",
        FOCUS_ON_SCAN_BUTTON,
        id="delete-the-only-page-by-keyboard",
    ),
]

DOCUMENT_EVENT_CASES = [
    pytest.param("next_document_event(null, observation({}), 'page_added')", "none", id="first-observation"),
    pytest.param("next_document_event(observation({}), observation({draft_session: 's2'}), 'edited')", "none",
                 id="other-session"),
    pytest.param("next_document_event(observation({}), observation({capture_mode: 'single'}), 'page_failed')",
                 "edited", id="mode-changed"),
    pytest.param(
        "next_document_event(observation({}), observation({page_count: 3, scans_completed: 6, revision: 4}), 'none')",
        "page_added",
        id="page-added",
    ),
    pytest.param("next_document_event(observation({}), observation({page_count: 3, revision: 4}), 'none')", "edited",
                 id="more-pages-without-a-scan"),
    pytest.param("next_document_event(observation({}), observation({scans_completed: 6}), 'page_added')",
                 "page_added", id="quick-scan-keeps-the-event"),
    pytest.param(
        "next_document_event(observation({}), observation({last_error_code: 'scanner_unreachable'}), 'none')",
        "page_failed",
        id="error-appeared",
    ),
    pytest.param(
        "next_document_event(observation({last_error_code: 'scan_failed'}), "
        "observation({last_error_code: 'scan_failed'}), 'page_failed')",
        "page_failed",
        id="error-still-there",
    ),
    pytest.param("next_document_event(observation({}), observation({revision: 4}), 'page_failed')", "edited",
                 id="revision-changed"),
    pytest.param("next_document_event(observation({}), observation({}), 'page_added')", "page_added",
                 id="nothing-changed"),
]

NAME_CASES = [
    pytest.param("decide_name_field_after_draft_end('finalized')", "clear", id="field-after-finalizing"),
    pytest.param("decide_name_field_after_draft_end('cancelled')", "clear", id="field-after-cancelling"),
    pytest.param("decide_name_field_after_draft_end('last_page_removed_here')", "keep",
                 id="field-after-removing-the-last-page-here"),
    pytest.param("decide_name_field_after_draft_end('ended_elsewhere')", "clear", id="field-after-an-end-elsewhere"),
    pytest.param("decide_name_to_send({typed_name: '  Contrato  ', saved_name: '', document_exists: true})",
                 "Contrato", id="trimmed-new-name"),
    pytest.param("decide_name_to_send({typed_name: 'Contrato ', saved_name: 'Contrato', document_exists: true})",
                 None, id="name-already-saved"),
    pytest.param("decide_name_to_send({typed_name: 'Contrato', saved_name: '', document_exists: false})", None,
                 id="no-document-yet"),
    pytest.param("decide_name_to_send({typed_name: '   ', saved_name: 'Contrato', document_exists: true})", "",
                 id="cleared-name-goes-back-to-automatic"),
    pytest.param("decide_name_to_send({typed_name: '', saved_name: '', document_exists: true})", None,
                 id="empty-and-automatic"),
]

MODE_CASES = [
    pytest.param("should_switch_to_document_mode(mode_switch_check({}))", True, id="resumed-in-single-mode"),
    pytest.param("should_switch_to_document_mode(mode_switch_check({capture_mode: 'document'}))", False,
                 id="already-in-document-mode"),
    pytest.param("should_switch_to_document_mode(mode_switch_check({recovery: null}))", False,
                 id="without-recovery"),
    pytest.param("should_switch_to_document_mode(mode_switch_check({recovery: recovery({outcome: 'pages_lost'})}))",
                 False, id="nothing-resumed"),
    pytest.param("should_switch_to_document_mode(mode_switch_check({switched_draft_session: 's1'}))", False,
                 id="already-switched-for-this-session"),
    pytest.param("should_switch_to_document_mode(mode_switch_check({switched_draft_session: 's0'}))", True,
                 id="switched-for-an-older-session"),
]

WARNING_CASES = [
    pytest.param("should_warn_about_large_document({page_count: 300, estimated_size_in_bytes: 0})", False,
                 id="300-pages"),
    pytest.param("should_warn_about_large_document({page_count: 301, estimated_size_in_bytes: 0})", True,
                 id="301-pages"),
    pytest.param("should_warn_about_large_document({page_count: 2, estimated_size_in_bytes: 1024 ** 3})", False,
                 id="exactly-1-gibibyte"),
    pytest.param("should_warn_about_large_document({page_count: 2, estimated_size_in_bytes: 1024 ** 3 + 1})", True,
                 id="above-1-gibibyte"),
    pytest.param(
        "should_warn_about_draft_storage({free_space_in_bytes: 5, estimated_pages_remaining: 2, available: true})",
        True,
        id="room-for-2-pages",
    ),
    pytest.param(
        "should_warn_about_draft_storage({free_space_in_bytes: 5, estimated_pages_remaining: 3, available: true})",
        False,
        id="room-for-3-pages",
    ),
    pytest.param(
        "should_warn_about_draft_storage({free_space_in_bytes: 0, estimated_pages_remaining: 0, available: false})",
        True,
        id="draft-disk-unavailable",
    ),
    pytest.param("should_reload_document_after_error('invalid_page_order')", True, id="reload-after-stale-order"),
    pytest.param("should_reload_document_after_error('page_not_found')", True, id="reload-after-missing-page"),
    pytest.param("should_reload_document_after_error('no_open_document')", True, id="reload-after-missing-document"),
    pytest.param("should_reload_document_after_error('scan_already_running')", False, id="no-reload-after-conflict"),
]

DURATION_AND_COUNT_CASES = [
    pytest.param("describe_expected_scan_duration('document')", "cerca de 15 s", id="text-preset"),
    pytest.param("describe_expected_scan_duration('document_economy')", "cerca de 15 s", id="economy-preset"),
    pytest.param("describe_expected_scan_duration('photo')", "cerca de 75 s", id="photo-preset"),
    pytest.param("describe_expected_scan_duration('poster')", "cerca de 15 s", id="unknown-preset"),
    pytest.param("describe_page_count(0)", "0 páginas", id="no-pages"),
    pytest.param("describe_page_count(1)", "1 página", id="one-page"),
    pytest.param("describe_page_count(2)", "2 páginas", id="two-pages"),
    pytest.param("describe_page_count(1234)", "1.234 páginas", id="thousands"),
]

STATUS_CASES = [
    pytest.param("describe_document_status('preparing', document_progress({}))", "Preparando a página 3…",
                 id="preparing"),
    pytest.param("describe_document_status('scanning', document_progress({scan_preset: 'photo'}))",
                 "Digitalizando a página 3… (cerca de 75 s)", id="scanning-a-photo"),
    pytest.param("describe_document_status('saving', document_progress({}))", "Guardando a página 3…", id="saving"),
    pytest.param("describe_document_status('idle', document_progress({is_finalizing: true}))",
                 "Finalizando o PDF (2 páginas)…", id="finalizing"),
    pytest.param("describe_document_status('idle', document_progress({page_count: 1, is_finalizing: true}))",
                 "Finalizando o PDF (1 página)…", id="finalizing-one-page"),
    pytest.param(
        "describe_document_status('idle', document_progress({last_event: 'page_failed'}))",
        "A última página não foi adicionada. Coloque a folha de novo e aperte Espaço.",
        id="page-failed",
    ),
    pytest.param("describe_document_status('idle', document_progress({last_event: 'page_added'}))",
                 f"Página 2 adicionada. {NEXT_SHEET_TEXT}", id="page-added"),
    pytest.param("describe_document_status('idle', document_progress({last_event: 'edited'}))",
                 f"2 páginas no documento. {NEXT_SHEET_TEXT}", id="edited"),
    pytest.param("describe_document_status('idle', document_progress({page_count: 1}))",
                 f"1 página no documento. {NEXT_SHEET_TEXT}", id="one-page"),
    pytest.param(
        "describe_document_status('idle', document_progress({page_count: 0}))",
        "Modo Documento: coloque a primeira folha no vidro e aperte Espaço.",
        id="no-pages",
    ),
]

REMOVAL_AND_MOVE_CASES = [
    pytest.param("describe_page_removal({action: 'discard_last', position: 12, remaining_page_count: 11})",
                 "Página 12 descartada. O documento tem 11 páginas.", id="discarded"),
    pytest.param("describe_page_removal({action: 'delete', position: 5, remaining_page_count: 11})",
                 "Página 5 excluída. O documento tem 11 páginas.", id="deleted"),
    pytest.param("describe_page_removal({action: 'delete', position: 2, remaining_page_count: 1})",
                 "Página 2 excluída. O documento tem 1 página.", id="one-page-left"),
    pytest.param("describe_page_removal({action: 'delete', position: 1, remaining_page_count: 0})",
                 "Página 1 excluída. O documento foi encerrado.", id="document-ended"),
    pytest.param("describe_page_move(3, 2)", "Página 3 movida para a posição 2", id="moved"),
]

RECOVERY_CASES = [
    pytest.param("describe_recovery(recovery({}))", "Documento em andamento recuperado: 41 páginas.",
                 id="resumed-without-losses"),
    pytest.param("describe_recovery(recovery({kept_page_count: 1}))", "Documento em andamento recuperado: 1 página.",
                 id="resumed-one-page"),
    pytest.param(
        "describe_recovery(recovery({dropped_page_positions: [37]}))",
        "Documento em andamento recuperado: 41 páginas. A página 37 não pôde ser recuperada; digitalize-a de novo.",
        id="one-page-lost",
    ),
    pytest.param(
        "describe_recovery(recovery({dropped_page_positions: [5, 37]}))",
        "Documento em andamento recuperado: 41 páginas. "
        "As páginas 5 e 37 não puderam ser recuperadas; digitalize-as de novo.",
        id="two-pages-lost",
    ),
    pytest.param(
        "describe_recovery(recovery({dropped_page_positions: [5, 12, 37]}))",
        "Documento em andamento recuperado: 41 páginas. "
        "As páginas 5, 12 e 37 não puderam ser recuperadas; digitalize-as de novo.",
        id="three-pages-lost",
    ),
    pytest.param(
        "describe_recovery(recovery({dropped_page_positions: [37], set_aside_folder: '/set-aside-1'}))",
        "Documento em andamento recuperado: 41 páginas. A página 37 não pôde ser recuperada; digitalize-a de novo. "
        "Os arquivos danificados foram guardados em /set-aside-1.",
        id="resumed-with-files-set-aside",
    ),
    pytest.param(
        "describe_recovery(recovery({outcome: 'pages_lost', kept_page_count: 0, dropped_page_positions: [1, 2]}))",
        "Não consegui recuperar nenhuma página do documento em andamento.",
        id="pages-lost",
    ),
    pytest.param(
        "describe_recovery(recovery({outcome: 'pages_lost', kept_page_count: 0, set_aside_folder: '/set-aside-1'}))",
        "Não consegui recuperar nenhuma página do documento em andamento. "
        "Os arquivos danificados foram guardados em /set-aside-1.",
        id="pages-lost-with-files-set-aside",
    ),
    pytest.param(
        "describe_recovery(recovery({outcome: 'set_aside', kept_page_count: 0, set_aside_folder: '/set-aside-1'}))",
        "Não consegui ler o documento em andamento. As páginas foram guardadas em /set-aside-1.",
        id="set-aside",
    ),
    pytest.param(
        "describe_recovery(recovery({outcome: 'failed', kept_page_count: 0}))",
        "Não consegui abrir o documento em andamento. Nada foi apagado: feche o Digitalizadora e abra de novo. "
        "Detalhes em ~/Library/Logs/Digitalizadora.",
        id="failed",
    ),
    pytest.param("describe_recovery(null)", None, id="no-recovery"),
]

DOCUMENT_TEXT_CASES = [
    pytest.param(
        "describe_possible_previous_save(draft_document({finished_document_path: '/Volumes/Arquivo/Contrato.pdf'}))",
        "Este documento talvez já tenha sido salvo como /Volumes/Arquivo/Contrato.pdf. "
        "Confira antes de finalizar de novo.",
        id="possibly-saved",
    ),
    pytest.param(
        "describe_possible_previous_save(draft_document({finalization_started_at: '2026-10-17T10:05:00-03:00'}))",
        "Uma finalização deste documento foi interrompida às 10:05. "
        "Confira na pasta de saída se o PDF já existe antes de finalizar de novo.",
        id="finalization-interrupted",
    ),
    pytest.param("describe_possible_previous_save(draft_document({}))", None, id="no-marker"),
    pytest.param("describe_possible_previous_save(null)", None, id="no-document"),
    pytest.param("describe_pending_document(3)", "Documento em andamento: 3 páginas", id="pending-pages"),
    pytest.param("describe_pending_document(1)", "Documento em andamento: 1 página", id="pending-page"),
    pytest.param(
        "describe_finished_document({file_name: 'Contrato.pdf', output_folder: '/Volumes/Arquivo', page_count: 3, "
        "size_in_bytes: 2418369, finalized_at: '2026-10-17T10:05:00-03:00'})",
        "Pronto! Salvo como Contrato.pdf (3 páginas)",
        id="finished",
    ),
    pytest.param("describe_finished_document(null)", None, id="nothing-finished"),
]

ALL_CASES = (
    MOVE_CASES
    + DROP_CASES
    + RENDER_CASES
    + ACTIVITY_CASES
    + DOCUMENT_KEY_CASES
    + CONFIRMATION_KEY_CASES
    + FOCUS_CASES
    + DOCUMENT_EVENT_CASES
    + NAME_CASES
    + MODE_CASES
    + WARNING_CASES
    + DURATION_AND_COUNT_CASES
    + STATUS_CASES
    + REMOVAL_AND_MOVE_CASES
    + RECOVERY_CASES
    + DOCUMENT_TEXT_CASES
)


@pytest.fixture(scope="module")
def policy_results() -> dict:
    expressions = [case.values[0] for case in ALL_CASES]
    completed = subprocess.run(
        [NODE_EXECUTABLE, str(HARNESS_PATH)],
        input=json.dumps(expressions),
        capture_output=True,
        text=True,
        timeout=HARNESS_TIMEOUT_SECONDS,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.parametrize(("expression", "expected"), MOVE_CASES)
def test_page_moves(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), DROP_CASES)
def test_drag_and_drop_rules(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), RENDER_CASES)
def test_document_body_render_rule(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), ACTIVITY_CASES)
def test_edit_and_page_availability(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), DOCUMENT_KEY_CASES)
def test_document_key_rules(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), CONFIRMATION_KEY_CASES)
def test_confirmation_key_rules(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), FOCUS_CASES)
def test_focus_after_an_action(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), DOCUMENT_EVENT_CASES)
def test_document_event_rules(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), NAME_CASES)
def test_document_name_rules(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), MODE_CASES)
def test_mode_switch_after_recovery(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), WARNING_CASES)
def test_warnings_and_reloads(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), DURATION_AND_COUNT_CASES)
def test_durations_and_page_counts(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), STATUS_CASES)
def test_document_status_texts(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), REMOVAL_AND_MOVE_CASES)
def test_announcement_texts(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), RECOVERY_CASES)
def test_recovery_texts(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), DOCUMENT_TEXT_CASES)
def test_document_notice_texts(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected
