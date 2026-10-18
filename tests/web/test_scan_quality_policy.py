import pytest

from tests.web.policy_expression_runner import NODE_EXECUTABLE, evaluate_policy_expressions

SLOW_SCAN_WARNING = "600 dpi leva cerca de 75 s por página e gera arquivos grandes."
VERY_SLOW_SCAN_WARNING = "1200 dpi pode levar vários minutos e gerar arquivos muito grandes."

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so scan-quality-policy.js cannot be exercised"
)

DURATION_CASES = [
    pytest.param("describe_expected_scan_duration(75)", "cerca de 15 s", id="75-dpi"),
    pytest.param("describe_expected_scan_duration(200)", "cerca de 15 s", id="200-dpi"),
    pytest.param("describe_expected_scan_duration(300)", "cerca de 15 s", id="300-dpi"),
    pytest.param("describe_expected_scan_duration(400)", "cerca de 30 s", id="400-dpi"),
    pytest.param("describe_expected_scan_duration(600)", "cerca de 75 s", id="600-dpi"),
    pytest.param("describe_expected_scan_duration(1200)", "vários minutos", id="1200-dpi"),
    pytest.param("describe_expected_scan_duration(undefined)", "cerca de 15 s", id="server-without-resolution"),
]

WARNING_CASES = [
    pytest.param("describe_resolution_warning(75)", None, id="75-dpi"),
    pytest.param("describe_resolution_warning(300)", None, id="300-dpi"),
    pytest.param("describe_resolution_warning(400)", None, id="400-dpi"),
    pytest.param("describe_resolution_warning(600)", SLOW_SCAN_WARNING, id="600-dpi"),
    pytest.param("describe_resolution_warning(1200)", VERY_SLOW_SCAN_WARNING, id="1200-dpi"),
    pytest.param("describe_resolution_warning(undefined)", None, id="server-without-resolution"),
]

PRESET_CASES = [
    pytest.param("choose_preset_option({scan_preset: 'photo'})", "photo", id="named-preset"),
    pytest.param("choose_preset_option({scan_preset: null})", "custom", id="custom-combination"),
    pytest.param("choose_preset_option({})", "custom", id="no-preset-field"),
    pytest.param(
        "build_preset_changes('photo')",
        {"scan_preset": "photo", "dots_per_inch": None, "color_mode": None},
        id="preset-changes-clear-the-pair",
    ),
]

ROTATION_CASES = [
    pytest.param("parse_rotation_degrees('0')", 0, id="no-rotation"),
    pytest.param("parse_rotation_degrees('90')", 90, id="quarter-turn-right"),
    pytest.param("parse_rotation_degrees('180')", 180, id="half-turn"),
    pytest.param("parse_rotation_degrees('270')", 270, id="quarter-turn-left"),
    pytest.param("parse_rotation_degrees('45')", 0, id="unknown-angle"),
    pytest.param("parse_rotation_degrees('')", 0, id="empty-value"),
    pytest.param("parse_rotation_degrees('abc')", 0, id="not-a-number"),
]

ALL_CASES = DURATION_CASES + WARNING_CASES + PRESET_CASES + ROTATION_CASES


@pytest.fixture(scope="module")
def policy_results() -> dict:
    return evaluate_policy_expressions([case.values[0] for case in ALL_CASES])


@pytest.mark.parametrize(("expression", "expected"), DURATION_CASES)
def test_expected_scan_duration_text(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), WARNING_CASES)
def test_resolution_warning_text(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), PRESET_CASES)
def test_preset_choice_rules(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), ROTATION_CASES)
def test_rotation_choice_rules(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected
