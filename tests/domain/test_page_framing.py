import pytest

from digitalizadora.domain.errors import InvalidCropError
from digitalizadora.domain.page_crop import CropCorner
from digitalizadora.domain.page_framing import (
    MAXIMUM_CROPS_PER_PAGE,
    UNFRAMED,
    PageFraming,
    put_in_reading_order,
)
from digitalizadora.domain.page_rotation import PageRotation
from tests.fakes.page_crops import quadrilateral, rectangle

SAMPLE_CROP = rectangle(0.1, 0.2, 0.5, 0.9)
OTHER_CROP = rectangle(0.55, 0.2, 0.95, 0.9)
WHOLE_PAGE = rectangle(0.0, 0.0, 1.0, 1.0)
ALL_ROTATIONS = list(PageRotation)


def test_an_unframed_page_needs_no_rendering() -> None:
    assert UNFRAMED.needs_rendering is False


def test_a_rotated_page_needs_rendering() -> None:
    assert PageFraming(rotation=PageRotation.CLOCKWISE_90).needs_rendering is True


def test_a_cropped_page_needs_rendering() -> None:
    assert PageFraming(crops=(SAMPLE_CROP,)).needs_rendering is True


def test_a_page_without_a_crop_produces_one_output() -> None:
    assert UNFRAMED.output_count == 1


def test_a_page_with_two_crops_produces_two_outputs() -> None:
    assert PageFraming(crops=(SAMPLE_CROP, OTHER_CROP)).output_count == 2


def test_the_limit_is_two_crops_per_page() -> None:
    assert MAXIMUM_CROPS_PER_PAGE == 2


def test_three_crops_are_refused() -> None:
    with pytest.raises(InvalidCropError):
        PageFraming(crops=(SAMPLE_CROP, OTHER_CROP, rectangle(0.1, 0.1, 0.3, 0.3)))


def test_turning_clockwise_adds_a_quarter_turn() -> None:
    assert UNFRAMED.turned_clockwise().rotation is PageRotation.CLOCKWISE_90


def test_four_turns_bring_the_rotation_back() -> None:
    framing = UNFRAMED
    for _ in range(4):
        framing = framing.turned_clockwise()

    assert framing.rotation is PageRotation.NONE


def test_turning_without_crops_keeps_them_empty() -> None:
    assert UNFRAMED.turned_clockwise().crops == ()


def test_turning_clockwise_turns_every_crop_with_the_page() -> None:
    framing = PageFraming(crops=(rectangle(0.0, 0.0, 0.5, 1.0),)).turned_clockwise()

    assert framing.crops == (rectangle(0.0, 0.0, 0.5, 1.0).turned_clockwise(),)


def test_turning_clockwise_keeps_the_crops_in_reading_order() -> None:
    upper = rectangle(0.1, 0.05, 0.9, 0.45)
    lower = rectangle(0.1, 0.55, 0.9, 0.95)
    framing = PageFraming(crops=(upper, lower)).turned_clockwise()

    assert framing.crops == (lower.turned_clockwise(), upper.turned_clockwise())


def test_four_turns_bring_the_crops_back_exactly() -> None:
    framing = PageFraming(crops=(SAMPLE_CROP, OTHER_CROP))
    for _ in range(4):
        framing = framing.turned_clockwise()

    assert framing == PageFraming(crops=(SAMPLE_CROP, OTHER_CROP))


def test_with_crops_replaces_the_crops() -> None:
    assert UNFRAMED.with_crops([SAMPLE_CROP]).crops == (SAMPLE_CROP,)


def test_with_crops_keeps_the_rotation() -> None:
    framing = PageFraming(rotation=PageRotation.HALF_TURN).with_crops([SAMPLE_CROP])

    assert framing.rotation is PageRotation.HALF_TURN


def test_a_crop_that_covers_the_whole_page_is_dropped() -> None:
    assert PageFraming(crops=(SAMPLE_CROP,)).with_crops([WHOLE_PAGE]).crops == ()


def test_the_whole_page_does_not_count_against_the_limit() -> None:
    framing = UNFRAMED.with_crops([SAMPLE_CROP, WHOLE_PAGE, OTHER_CROP])

    assert framing.crops == (SAMPLE_CROP, OTHER_CROP)


def test_with_no_crops_removes_the_crops() -> None:
    assert PageFraming(crops=(SAMPLE_CROP,)).with_crops([]).crops == ()


def test_with_crops_puts_them_in_reading_order() -> None:
    assert UNFRAMED.with_crops([OTHER_CROP, SAMPLE_CROP]).crops == (SAMPLE_CROP, OTHER_CROP)


def test_with_crops_refuses_more_than_two() -> None:
    with pytest.raises(InvalidCropError):
        UNFRAMED.with_crops([SAMPLE_CROP, OTHER_CROP, rectangle(0.1, 0.1, 0.3, 0.3)])


def test_side_by_side_crops_come_left_first() -> None:
    assert put_in_reading_order([OTHER_CROP, SAMPLE_CROP]) == (SAMPLE_CROP, OTHER_CROP)


def test_stacked_crops_come_upper_first() -> None:
    upper = rectangle(0.1, 0.05, 0.9, 0.45)
    lower = rectangle(0.1, 0.55, 0.9, 0.95)

    assert put_in_reading_order([lower, upper]) == (upper, lower)


def test_crops_that_only_touch_in_height_come_upper_first() -> None:
    upper = quadrilateral((0.04, 0.28), (0.65, 0.02), (0.89, 0.32), (0.28, 0.58))
    lower = quadrilateral((0.17, 0.58), (0.88, 0.58), (0.9, 0.93), (0.19, 0.95))

    assert put_in_reading_order([lower, upper]) == (upper, lower)


def test_crops_overlapping_by_more_than_half_in_height_come_left_first() -> None:
    left = rectangle(0.05, 0.1, 0.45, 0.6)
    right = rectangle(0.55, 0.3, 0.95, 0.9)

    assert put_in_reading_order([right, left]) == (left, right)


def test_crops_overlapping_by_less_than_half_in_height_come_upper_first() -> None:
    left_lower = rectangle(0.05, 0.5, 0.45, 0.95)
    right_upper = rectangle(0.55, 0.05, 0.95, 0.6)

    assert put_in_reading_order([left_lower, right_upper]) == (right_upper, left_lower)


def test_crops_with_the_same_centre_keep_their_arrival_order() -> None:
    first = rectangle(0.1, 0.1, 0.9, 0.9)
    second = rectangle(0.2, 0.2, 0.8, 0.8)

    assert put_in_reading_order([first, second]) == (first, second)


def test_one_crop_is_in_order_already() -> None:
    assert put_in_reading_order([SAMPLE_CROP]) == (SAMPLE_CROP,)


def test_without_crops_the_master_has_none_either() -> None:
    assert PageFraming(rotation=PageRotation.CLOCKWISE_90).crops_on_master() == ()


def test_an_unrotated_page_has_the_same_crops_on_the_master() -> None:
    assert PageFraming(crops=(SAMPLE_CROP,)).crops_on_master() == (SAMPLE_CROP,)


def test_the_crop_of_a_page_turned_a_quarter_goes_back_a_quarter_on_the_master() -> None:
    framing = PageFraming(rotation=PageRotation.CLOCKWISE_90, crops=(rectangle(0.0, 0.0, 1.0, 0.5),))

    assert framing.crops_on_master()[0].bounding_edges.right == 0.5


def test_the_crop_on_the_master_keeps_the_roles_of_the_displayed_crop() -> None:
    framing = PageFraming(rotation=PageRotation.CLOCKWISE_90, crops=(rectangle(0.0, 0.0, 1.0, 0.5),))

    assert framing.crops_on_master()[0].top_left == CropCorner(0.0, 1.0)


@pytest.mark.parametrize("rotation", ALL_ROTATIONS)
def test_crops_from_the_master_put_the_points_back_where_they_are_displayed(rotation: PageRotation) -> None:
    framing = PageFraming(rotation=rotation, crops=(SAMPLE_CROP, OTHER_CROP))

    shown = framing.crops_from_master(framing.crops_on_master())

    assert [set(crop.corners) for crop in shown] == [set(crop.corners) for crop in framing.crops]


def test_a_crop_found_on_the_master_of_a_turned_page_is_shown_turned() -> None:
    framing = PageFraming(rotation=PageRotation.CLOCKWISE_90)
    found = rectangle(0.0, 0.0, 0.5, 1.0)

    assert framing.crops_from_master([found]) == (found.turned_clockwise(),)


def test_a_crop_found_on_an_unrotated_master_is_shown_as_it_is() -> None:
    assert UNFRAMED.crops_from_master([SAMPLE_CROP]) == (SAMPLE_CROP,)
