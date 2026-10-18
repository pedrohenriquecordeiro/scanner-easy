import pytest

from tests.web.policy_expression_runner import NODE_EXECUTABLE, evaluate_policy_expressions

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so frame-dialog-policy.js cannot be exercised"
)

TEXT_CASES = [
    pytest.param("describe_frame_label(2)", "Moldura 2", id="frame-label"),
    pytest.param("describe_selected_frame(1, 2)", "Moldura 1 de 2 selecionada.", id="frame-selected"),
    pytest.param("describe_select_frame_label(2)", "Selecionar moldura 2", id="select-button"),
    pytest.param("describe_frame_added(2)", "Moldura 2 adicionada.", id="frame-added"),
    pytest.param("FRAME_LIMIT_TEXT", "Só dá para ter 2 molduras.", id="frame-limit"),
    pytest.param("describe_frame_removed(2)", "Moldura 2 removida.", id="frame-removed"),
    pytest.param(
        "describe_frame_output_turned(1)", "Moldura 1 girada: o lado de cima da foto mudou.", id="frame-turned"
    ),
    pytest.param(
        "describe_rotate_frame_label(1)",
        "Girar a moldura 1 em 90 graus para a direita: muda o lado de cima da foto recortada",
        id="rotate-frame-button",
    ),
    pytest.param("FRAME_REWRITING_TEXT", "Regravando…", id="rewriting"),
    pytest.param("FRAME_CHANGES_DISCARDED_TEXT", "Alterações da moldura descartadas.", id="changes-discarded"),
    pytest.param(
        "INVALID_FRAME_MOVE_TEXT",
        "Esse movimento deixaria a moldura torta demais. Ela ficou como estava.",
        id="invalid-move",
    ),
    pytest.param(
        "describe_frame_image_failed('nesta página')",
        "Não consegui carregar a imagem ampliada nesta página.",
        id="enlarged-view-failed",
    ),
    pytest.param(
        "describe_no_frame_detected('nesta digitalização')",
        "Não achei uma borda confiável nesta digitalização. As molduras não mudaram.",
        id="nothing-detected",
    ),
]

DETECTION_CASES = [
    pytest.param(
        "describe_detected_frames({frame_count: 1, ignored_region_count: 0})",
        "Achei 1 moldura e salvei.",
        id="one-frame",
    ),
    pytest.param(
        "describe_detected_frames({frame_count: 2, ignored_region_count: 0})",
        "Achei 2 molduras e salvei.",
        id="two-frames",
    ),
    pytest.param(
        "describe_detected_frames({frame_count: 2, ignored_region_count: 1})",
        "Achei 2 molduras e salvei. Achei mais de 2 fotos; usei as 2 maiores.",
        id="more-than-two-photos",
    ),
]

LABEL_CASES = [
    pytest.param(
        "describe_handle_label('Canto superior esquerdo', {frame_number: 1, frame_count: 1})",
        "Canto superior esquerdo",
        id="one-frame-needs-no-number",
    ),
    pytest.param(
        "describe_handle_label('Canto superior esquerdo', {frame_number: 2, frame_count: 2})",
        "Canto superior esquerdo da moldura 2",
        id="two-frames-name-the-selected-one",
    ),
    pytest.param(
        "describe_grip_label(MOVE_HANDLE_LABEL, {frame_number: 1, frame_count: 1})",
        "Mover a moldura",
        id="one-frame-grip-needs-no-number",
    ),
    pytest.param(
        "describe_grip_label(ROTATE_HANDLE_LABEL, {frame_number: 2, frame_count: 2})",
        "Girar a moldura 2",
        id="two-frames-grip-gets-the-number",
    ),
    pytest.param("[MOVE_HANDLE_LABEL, ROTATE_HANDLE_LABEL]", ["Mover a moldura", "Girar a moldura"], id="grips"),
]

ALL_CASES = TEXT_CASES + DETECTION_CASES + LABEL_CASES


@pytest.fixture(scope="module")
def policy_results() -> dict:
    return evaluate_policy_expressions([case.values[0] for case in ALL_CASES])


@pytest.mark.parametrize(("expression", "expected"), TEXT_CASES)
def test_dialog_texts_are_in_portuguese(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), DETECTION_CASES)
def test_detection_results_are_announced(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), LABEL_CASES)
def test_handles_name_the_frame_they_belong_to(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected
