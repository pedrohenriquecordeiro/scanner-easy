import pytest

from digitalizadora.domain.page_rotation import PageRotation


@pytest.mark.parametrize(
    ("rotation", "expected_rotation"),
    [
        (PageRotation.NONE, PageRotation.CLOCKWISE_90),
        (PageRotation.CLOCKWISE_90, PageRotation.HALF_TURN),
        (PageRotation.HALF_TURN, PageRotation.COUNTERCLOCKWISE_90),
        (PageRotation.COUNTERCLOCKWISE_90, PageRotation.NONE),
    ],
)
def test_turned_clockwise_goes_round_the_four_quarters(
    rotation: PageRotation, expected_rotation: PageRotation
) -> None:
    assert rotation.turned_clockwise() is expected_rotation


def test_rotation_is_created_from_its_degrees() -> None:
    assert PageRotation(270) is PageRotation.COUNTERCLOCKWISE_90


def test_a_diagonal_angle_is_not_a_rotation() -> None:
    with pytest.raises(ValueError):
        PageRotation(45)
