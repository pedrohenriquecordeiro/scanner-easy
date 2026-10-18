import os

import pytest

HARDWARE_TESTS_VARIABLE = "DIGITALIZADORA_HARDWARE_TESTS"
HARDWARE_TESTS_ENABLED_VALUE = "1"
HARDWARE_MARKER_NAME = "hardware"
HARDWARE_SKIP_REASON = (
    f"hardware test: set {HARDWARE_TESTS_VARIABLE}={HARDWARE_TESTS_ENABLED_VALUE} to run it"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.environ.get(HARDWARE_TESTS_VARIABLE) == HARDWARE_TESTS_ENABLED_VALUE:
        return
    skip_hardware = pytest.mark.skip(reason=HARDWARE_SKIP_REASON)
    for item in items:
        if item.get_closest_marker(HARDWARE_MARKER_NAME) is not None:
            item.add_marker(skip_hardware)
