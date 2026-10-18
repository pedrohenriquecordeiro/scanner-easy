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

JPEG_QUALITY_CASES = [
    pytest.param("parse_jpeg_quality('75')", 75, id="a-quality-in-the-range"),
    pytest.param("parse_jpeg_quality(75)", 75, id="a-number-in-the-range"),
    pytest.param("parse_jpeg_quality('50')", 50, id="the-lowest-quality"),
    pytest.param("parse_jpeg_quality('100')", 100, id="the-highest-quality"),
    pytest.param("parse_jpeg_quality('49')", 90, id="below-the-range-gives-the-default"),
    pytest.param("parse_jpeg_quality('101')", 90, id="above-the-range-gives-the-default"),
    pytest.param("parse_jpeg_quality('abc')", 90, id="text-gives-the-default"),
    pytest.param("parse_jpeg_quality('')", 90, id="empty-gives-the-default"),
    pytest.param("parse_jpeg_quality('75.5')", 90, id="a-fraction-gives-the-default"),
    pytest.param("parse_jpeg_quality(undefined)", 90, id="a-server-without-the-setting-gives-the-default"),
    pytest.param("parse_jpeg_quality(null)", 90, id="null-gives-the-default"),
    pytest.param("[MINIMUM_JPEG_QUALITY, DEFAULT_JPEG_QUALITY, MAXIMUM_JPEG_QUALITY]", [50, 90, 100], id="limits"),
]

ALL_CASES = DURATION_CASES + WARNING_CASES + JPEG_QUALITY_CASES


@pytest.fixture(scope="module")
def policy_results() -> dict:
    return evaluate_policy_expressions([case.values[0] for case in ALL_CASES])


@pytest.mark.parametrize(("expression", "expected"), DURATION_CASES)
def test_expected_scan_duration_text(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), WARNING_CASES)
def test_resolution_warning_text(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), JPEG_QUALITY_CASES)
def test_the_jpeg_quality_is_read_within_its_range(policy_results: dict, expression: str, expected: object) -> None:
    assert policy_results[expression] == expected
