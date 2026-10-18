import pytest

from tests.web.policy_expression_runner import NODE_EXECUTABLE, evaluate_policy_expressions

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so scan-trigger-policy.js cannot be exercised"
)

IDLE_ACTIVITY = "{scan_phase: 'idle', is_start_request_pending: false}"
EDITABLE_STATE = "{is_editable: true, is_edit_pending: false}"

EDIT_CASES = [
    pytest.param(f"can_edit_last_scan({IDLE_ACTIVITY}, {EDITABLE_STATE})", True, id="idle-page-edits"),
    pytest.param(
        f"can_edit_last_scan({{scan_phase: 'scanning', is_start_request_pending: false}}, {EDITABLE_STATE})",
        False,
        id="not-while-scanning",
    ),
    pytest.param(
        f"can_edit_last_scan({{scan_phase: 'saving', is_start_request_pending: false}}, {EDITABLE_STATE})",
        False,
        id="not-while-saving",
    ),
    pytest.param(
        f"can_edit_last_scan({{scan_phase: 'idle', is_start_request_pending: true}}, {EDITABLE_STATE})",
        False,
        id="not-while-a-scan-request-is-pending",
    ),
    pytest.param(
        f"can_edit_last_scan({IDLE_ACTIVITY}, {{is_editable: true, is_edit_pending: true}})",
        False,
        id="not-while-another-adjustment-runs",
    ),
    pytest.param(
        f"can_edit_last_scan({IDLE_ACTIVITY}, {{is_editable: false, is_edit_pending: false}})",
        False,
        id="not-when-the-original-was-not-kept",
    ),
]

CAPTURE_CASES = [
    pytest.param(
        "can_start_capture({scan_phase: 'idle', is_start_request_pending: false, is_edit_request_pending: false})",
        True,
        id="idle-page-scans",
    ),
    pytest.param(
        "can_start_capture({scan_phase: 'idle', is_start_request_pending: false, is_edit_request_pending: true})",
        False,
        id="not-while-an-adjustment-runs",
    ),
    pytest.param(
        "can_start_capture({scan_phase: 'scanning', is_start_request_pending: false, is_edit_request_pending: false})",
        False,
        id="not-while-scanning",
    ),
]

ALL_CASES = EDIT_CASES + CAPTURE_CASES


@pytest.fixture(scope="module")
def trigger_results() -> dict:
    return evaluate_policy_expressions([case.values[0] for case in ALL_CASES])


@pytest.mark.parametrize(("expression", "expected"), EDIT_CASES)
def test_the_last_scan_can_be_adjusted_only_while_nothing_else_runs(
    trigger_results: dict, expression: str, expected: object
) -> None:
    assert trigger_results[expression] is expected


@pytest.mark.parametrize(("expression", "expected"), CAPTURE_CASES)
def test_a_scan_waits_for_the_adjustments(trigger_results: dict, expression: str, expected: object) -> None:
    assert trigger_results[expression] is expected
