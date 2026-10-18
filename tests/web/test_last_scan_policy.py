import pytest

from tests.web.policy_expression_runner import NODE_EXECUTABLE, evaluate_policy_expressions

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so last-scan-policy.js cannot be exercised"
)

ONE_FILE = "['2026_10_18__16_14_03_000000006.pdf']"
TWO_FILES = "['2026_10_18__16_14_03_000000006.pdf', '2026_10_18__16_14_03_000000007.pdf']"
NEW_FILE = "['2026_10_18__16_14_04_000000001.pdf']"
TWO_NEW_FILES = "['2026_10_18__16_14_04_000000001.pdf', '2026_10_18__16_14_04_000000002.pdf']"
ONE_CROP = "[{}]"


def edit(action: str, previous: str, answer: str) -> str:
    return f"describe_last_scan_edit({{action: '{action}', previous_file_names: {previous}, answer: {answer}}})"


def answer(file_names: str, crops: str = "[]", extra: str = "") -> str:
    return f"{{last_result: {{file_names: {file_names}, crops: {crops}}}{extra}}}"


ADDRESS_CASES = [
    pytest.param("LAST_SCAN_ROTATION_PATH", "/api/scans/last/rotation", id="rotation"),
    pytest.param("LAST_SCAN_CROPS_PATH", "/api/scans/last/crops", id="crops"),
    pytest.param("LAST_SCAN_CROPS_DETECTION_PATH", "/api/scans/last/crops/detect", id="detection"),
    pytest.param(
        "build_last_scan_thumbnail_address(7)", "/api/scans/last/thumbnail?version=7", id="thumbnail-by-version"
    ),
    pytest.param(
        "build_last_scan_preview_address('9f3c', 90)",
        "/api/scans/last/preview?scan_identifier=9f3c&rotation_degrees=90",
        id="enlarged-view-of-a-scan",
    ),
]

STATUS_CASES = [
    pytest.param(
        f"describe_saved_scan_status({{file_names: {ONE_FILE}}})",
        "Pronto! Salvo como 2026_10_18__16_14_03_000000006.pdf",
        id="one-file",
    ),
    pytest.param(
        f"describe_saved_scan_status({{file_names: {TWO_FILES}}})",
        "Pronto! 2 arquivos salvos: 2026_10_18__16_14_03_000000006.pdf e 2026_10_18__16_14_03_000000007.pdf",
        id="two-files",
    ),
    pytest.param(
        f"describe_last_scan_thumbnail_label({ONE_FILE})", "Miniatura da última digitalização", id="thumbnail-of-one"
    ),
    pytest.param(
        f"describe_last_scan_thumbnail_label({TWO_FILES})",
        "Miniatura da última digitalização (2 fotos)",
        id="thumbnail-of-two",
    ),
]

EDIT_CASES = [
    pytest.param(
        edit("rotate", ONE_FILE, answer(NEW_FILE)),
        "Última digitalização girada 90° para a direita. "
        "1 arquivo novo salvo: 2026_10_18__16_14_04_000000001.pdf. O arquivo anterior foi mantido.",
        id="rotated",
    ),
    pytest.param(
        edit("set_crops", ONE_FILE, answer(TWO_NEW_FILES, "[{}, {}]")),
        "Moldura aplicada. 2 arquivos novos salvos: "
        "2026_10_18__16_14_04_000000001.pdf e 2026_10_18__16_14_04_000000002.pdf. O arquivo anterior foi mantido.",
        id="a-second-frame-writes-two-new-files",
    ),
    pytest.param(
        edit("set_crops", ONE_FILE, answer(NEW_FILE, ONE_CROP)),
        "Moldura aplicada. 1 arquivo novo salvo: 2026_10_18__16_14_04_000000001.pdf. O arquivo anterior foi mantido.",
        id="one-frame-applied",
    ),
    pytest.param(
        edit("set_crops", ONE_FILE, answer(NEW_FILE)),
        "Corte removido. 1 arquivo novo salvo: 2026_10_18__16_14_04_000000001.pdf. O arquivo anterior foi mantido.",
        id="crop-removed",
    ),
    pytest.param(
        edit("set_crops", TWO_FILES, answer(NEW_FILE, ONE_CROP)),
        "Moldura aplicada. 1 arquivo novo salvo: 2026_10_18__16_14_04_000000001.pdf. "
        "Os arquivos anteriores foram mantidos.",
        id="a-removed-frame-keeps-both-earlier-files",
    ),
    pytest.param(
        edit("detect_crops", ONE_FILE, answer(TWO_NEW_FILES, "[{}, {}]", extra=", crops_detected: true")),
        "Molduras detectadas. 2 arquivos novos salvos: "
        "2026_10_18__16_14_04_000000001.pdf e 2026_10_18__16_14_04_000000002.pdf. O arquivo anterior foi mantido.",
        id="detection-found-two-photos",
    ),
    pytest.param(
        edit("detect_crops", ONE_FILE, answer(ONE_FILE, extra=", crops_detected: false")),
        "Não achei uma borda confiável nesta digitalização. As molduras não mudaram.",
        id="detection-found-nothing",
    ),
    pytest.param(
        "describe_last_scan_rotation_for_dialog(180, 0)",
        "Última digitalização girada 90° para a direita (total: 180°).",
        id="dialog-rotation-without-frames",
    ),
    pytest.param(
        "describe_last_scan_rotation_for_dialog(90, 1)",
        "Última digitalização girada 90° para a direita (total: 90°). A moldura acompanhou o giro.",
        id="dialog-rotation-with-a-frame",
    ),
    pytest.param(
        "describe_last_scan_rotation_for_dialog(0, 2)",
        "Última digitalização girada 90° para a direita (de volta à posição original). "
        "As molduras acompanharam o giro.",
        id="dialog-rotation-back-with-two-frames",
    ),
]

TEXT_CASES = [
    pytest.param(
        "LAST_SCAN_HINT_TEXT", "Cada ajuste salva arquivos novos e mantém os anteriores.", id="hint"
    ),
    pytest.param(
        "LAST_SCAN_NOT_EDITABLE_HINT_TEXT",
        "O original desta digitalização não foi guardado; os arquivos foram salvos normalmente.",
        id="original-not-kept",
    ),
    pytest.param("LAST_SCAN_GONE_TEXT", "Essa digitalização foi substituída por outra.", id="scan-replaced"),
    pytest.param(
        "LAST_SCAN_RELOAD_ERROR_CODES.includes('no_last_scan')", True, id="a-missing-scan-reloads-the-state"
    ),
    pytest.param(
        "LAST_SCAN_RELOAD_ERROR_CODES.includes('last_scan_replaced')", True, id="a-replaced-scan-reloads-the-state"
    ),
    pytest.param(
        "LAST_SCAN_RELOAD_ERROR_CODES.includes('invalid_crop')", False, id="an-invalid-crop-does-not-reload"
    ),
]

CLASSIFICATION_CASES = [
    pytest.param("classify_last_scan_edit({method: 'POST', path: LAST_SCAN_ROTATION_PATH})", "rotate", id="rotation"),
    pytest.param(
        "classify_last_scan_edit({method: 'PUT', path: LAST_SCAN_CROPS_PATH, body: {crops: []}})",
        "set_crops",
        id="crops",
    ),
    pytest.param(
        "classify_last_scan_edit({method: 'POST', path: LAST_SCAN_CROPS_DETECTION_PATH})",
        "detect_crops",
        id="detection",
    ),
    pytest.param(
        "choose_last_scan_thumbnail_version({revision: 4, edit_serial: 0})", "4", id="thumbnail-as-the-server-says"
    ),
    pytest.param(
        "choose_last_scan_thumbnail_version({revision: 4, edit_serial: 2})",
        "4-2",
        id="thumbnail-after-adjustments-made-here",
    ),
]

ALL_CASES = ADDRESS_CASES + STATUS_CASES + EDIT_CASES + TEXT_CASES + CLASSIFICATION_CASES


@pytest.fixture(scope="module")
def policy_results() -> dict:
    return evaluate_policy_expressions([case.values[0] for case in ALL_CASES])


@pytest.mark.parametrize(("expression", "expected"), ADDRESS_CASES)
def test_the_addresses_of_the_last_scan(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), STATUS_CASES)
def test_the_status_of_the_last_scan(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), EDIT_CASES)
def test_an_adjustment_says_what_it_did_to_the_files(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), TEXT_CASES)
def test_the_fixed_texts_of_the_last_scan(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), CLASSIFICATION_CASES)
def test_edits_and_thumbnails_are_told_apart(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected
