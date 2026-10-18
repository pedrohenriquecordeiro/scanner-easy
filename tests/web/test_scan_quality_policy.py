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

ALL_CASES = DURATION_CASES + WARNING_CASES


@pytest.fixture(scope="module")
def policy_results() -> dict:
    return evaluate_policy_expressions([case.values[0] for case in ALL_CASES])


@pytest.mark.parametrize(("expression", "expected"), DURATION_CASES)
def test_expected_scan_duration_text(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), WARNING_CASES)
def test_resolution_warning_text(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected

