import pytest

from tests.web.policy_expression_runner import NODE_EXECUTABLE, evaluate_policy_expressions

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so scan-trigger-policy.js cannot be exercised"
)

IDLE_ACTIVITY = "{scan_phase: 'idle', is_start_request_pending: false}"

ROTATION_CASES = [
    pytest.param(
        f"can_rotate_last_scan({IDLE_ACTIVITY}, {{is_rotation_pending: false}})", True, id="idle-page-rotates"
    ),
    pytest.param(
        "can_rotate_last_scan({scan_phase: 'scanning', is_start_request_pending: false}, {is_rotation_pending: false})",
        False,
        id="not-while-scanning",
    ),
    pytest.param(
        "can_rotate_last_scan({scan_phase: 'saving', is_start_request_pending: false}, {is_rotation_pending: false})",
        False,
        id="not-while-saving",
    ),
    pytest.param(
        "can_rotate_last_scan({scan_phase: 'idle', is_start_request_pending: true}, {is_rotation_pending: false})",
        False,
        id="not-while-a-scan-request-is-pending",
    ),
    pytest.param(
        f"can_rotate_last_scan({IDLE_ACTIVITY}, {{is_rotation_pending: true}})", False, id="not-while-rotating"
    ),
]


@pytest.fixture(scope="module")
def trigger_results() -> dict:
    return evaluate_policy_expressions([case.values[0] for case in ROTATION_CASES])


@pytest.mark.parametrize(("expression", "expected"), ROTATION_CASES)
def test_the_last_scan_can_be_rotated_only_while_nothing_else_runs(
    trigger_results: dict, expression: str, expected: object
) -> None:
    assert trigger_results[expression] is expected
