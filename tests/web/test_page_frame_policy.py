import pytest

from tests.web.policy_expression_runner import NODE_EXECUTABLE, evaluate_policy_expressions

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so document-page-policy.js cannot be exercised"
)

FRAME_CROP = "{left: 0.13, top: 0.12, right: 0.91, bottom: 0.91}"
FRAME_OF_THE_PAGE = "{left: 0.13, top: 0.115, right: 0.914, bottom: 0.915}"

ADDRESS_CASES = [
    pytest.param("build_page_path('abc')", "/api/document/pages/abc", id="page"),
    pytest.param("build_page_rotation_path('abc')", "/api/document/pages/abc/rotation", id="rotation"),
    pytest.param("build_page_crop_path('abc')", "/api/document/pages/abc/crop", id="crop"),
    pytest.param("build_page_crop_detection_path('abc')", "/api/document/pages/abc/crop/detect", id="crop-detection"),
    pytest.param(
        "build_page_thumbnail_address('abc', 0)",
        "/api/document/pages/abc/thumbnail?rotation_degrees=0",
        id="thumbnail-without-rotation",
    ),
    pytest.param(
        "build_page_thumbnail_address('abc', 270)",
        "/api/document/pages/abc/thumbnail?rotation_degrees=270",
        id="thumbnail-turned",
    ),
    pytest.param(
        "build_page_preview_address('abc', 90)",
        "/api/document/pages/abc/preview?rotation_degrees=90",
        id="enlarged-view-turned",
    ),
]

LABEL_CASES = [
    pytest.param(
        "describe_tile_label({position: 2, page_count: 3, crop: null})", "Página 2 de 3", id="tile-without-a-frame"
    ),
    pytest.param(
        f"describe_tile_label({{position: 2, page_count: 3, crop: {FRAME_CROP}}})",
        "Página 2 de 3, com moldura de corte",
        id="tile-with-a-frame",
    ),
    pytest.param(
        "describe_enlarge_label(2)",
        "Ampliar a página 2 e ajustar a moldura de corte",
        id="enlarge-button",
    ),
    pytest.param(
        "describe_frame_dialog_title({position: 2, page_count: 3})",
        "Página 2 de 3: moldura de corte",
        id="dialog-title",
    ),
]

ANNOUNCEMENT_CASES = [
    pytest.param(
        "describe_page_rotation_result({position: 2, rotation_degrees: 90, crop: null})",
        "Página 2 girada 90° para a direita (total: 90°).",
        id="rotation-without-a-frame",
    ),
    pytest.param(
        f"describe_page_rotation_result({{position: 2, rotation_degrees: 180, crop: {FRAME_CROP}}})",
        "Página 2 girada 90° para a direita (total: 180°). A moldura acompanhou o giro.",
        id="rotation-with-a-frame",
    ),
    pytest.param(
        f"describe_detected_frame({FRAME_OF_THE_PAGE})",
        "Moldura detectada e salva. Moldura: esquerda 13%, topo 12%, direita 91%, base 92%.",
        id="frame-detected",
    ),
    pytest.param(
        "NO_FRAME_DETECTED_TEXT",
        "Não achei uma borda confiável nesta página. A moldura não mudou.",
        id="frame-not-detected",
    ),
    pytest.param("describe_frame_applied(2)", "Moldura aplicada à página 2.", id="frame-applied"),
    pytest.param("describe_frame_removed(2)", "Corte removido da página 2.", id="frame-removed"),
    pytest.param(
        f"describe_crop_application({{position: 2, crop: {FRAME_CROP}}})",
        "Moldura aplicada à página 2.",
        id="a-crop-was-applied",
    ),
    pytest.param(
        "describe_crop_application({position: 2, crop: null})",
        "Corte removido da página 2.",
        id="no-crop-removes-the-crop",
    ),
    pytest.param("FRAME_CHANGES_DISCARDED_TEXT", "Alterações da moldura descartadas.", id="changes-discarded"),
    pytest.param(
        "FRAME_IMAGE_FAILED_TEXT",
        "Não consegui carregar a imagem ampliada desta página.",
        id="enlarged-view-failed",
    ),
    pytest.param("FRAME_PAGE_GONE_TEXT", "Essa página não está mais no documento.", id="page-gone"),
]

KEY_CASES = [
    pytest.param("should_hide_key_from_page_shortcuts(key_on('Space', PAGE_BODY))", True, id="space"),
    pytest.param("should_hide_key_from_page_shortcuts(key_on('Backspace', PAGE_BODY))", True, id="backspace"),
    pytest.param("should_hide_key_from_page_shortcuts(key_on('ArrowLeft', OTHER_BUTTON))", False, id="arrow"),
    pytest.param("should_hide_key_from_page_shortcuts(key_on('Enter', OTHER_BUTTON))", False, id="enter"),
]

FOCUS_CASES = [
    pytest.param(
        "decide_focus_after_action(action_context({action: 'frame_closed'}))",
        {"target": "enlarge_button", "page_identifier": "b"},
        id="closing-the-editor-opened-by-keyboard",
    ),
    pytest.param(
        "decide_focus_after_action(action_context({action: 'frame_closed', is_keyboard_initiated: false}))",
        {"target": "scan_button", "page_identifier": None},
        id="closing-the-editor-opened-by-pointer",
    ),
]

ALL_CASES = ADDRESS_CASES + LABEL_CASES + ANNOUNCEMENT_CASES + KEY_CASES + FOCUS_CASES


@pytest.fixture(scope="module")
def policy_results() -> dict:
    return evaluate_policy_expressions([case.values[0] for case in ALL_CASES])


@pytest.mark.parametrize(("expression", "expected"), ADDRESS_CASES)
def test_page_addresses(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), LABEL_CASES)
def test_page_labels(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), ANNOUNCEMENT_CASES)
def test_frame_texts(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), KEY_CASES)
def test_keys_the_frame_dialog_keeps_from_the_page(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] is expected


@pytest.mark.parametrize(("expression", "expected"), FOCUS_CASES)
def test_focus_after_the_frame_dialog(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected
