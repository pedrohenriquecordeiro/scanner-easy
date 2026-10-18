import pytest

from tests.conftest import (
    HARDWARE_MARKER_NAME,
    HARDWARE_TESTS_VARIABLE,
    pytest_collection_modifyitems,
)


class FakeTestItem:
    def __init__(self, marker_names: set[str]) -> None:
        self.marker_names = marker_names
        self.added_markers: list[object] = []

    def get_closest_marker(self, name: str) -> object | None:
        return object() if name in self.marker_names else None

    def add_marker(self, marker: object) -> None:
        self.added_markers.append(marker)


def apply_hook(items: list[FakeTestItem]) -> None:
    pytest_collection_modifyitems(items=items)


def test_hardware_tests_are_skipped_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HARDWARE_TESTS_VARIABLE, raising=False)
    hardware_item = FakeTestItem({HARDWARE_MARKER_NAME})

    apply_hook([hardware_item])

    assert len(hardware_item.added_markers) == 1


def test_regular_tests_are_never_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HARDWARE_TESTS_VARIABLE, raising=False)
    regular_item = FakeTestItem(set())

    apply_hook([regular_item])

    assert regular_item.added_markers == []


def test_hardware_tests_run_when_the_variable_is_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(HARDWARE_TESTS_VARIABLE, "1")
    hardware_item = FakeTestItem({HARDWARE_MARKER_NAME})

    apply_hook([hardware_item])

    assert hardware_item.added_markers == []


@pytest.mark.parametrize("value", ["0", "", "true"])
def test_hardware_tests_stay_skipped_for_any_other_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(HARDWARE_TESTS_VARIABLE, value)
    hardware_item = FakeTestItem({HARDWARE_MARKER_NAME})

    apply_hook([hardware_item])

    assert len(hardware_item.added_markers) == 1
