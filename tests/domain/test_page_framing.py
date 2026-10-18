import pytest

from digitalizadora.domain.page_crop import WHOLE_PAGE, RectangleCrop
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.page_rotation import PageRotation

SAMPLE_CROP = RectangleCrop(0.1, 0.2, 0.5, 0.9)
ALL_ROTATIONS = list(PageRotation)


def test_an_unframed_page_needs_no_rendering() -> None:
    assert UNFRAMED.needs_rendering is False


def test_a_rotated_page_needs_rendering() -> None:
    assert PageFraming(rotation=PageRotation.CLOCKWISE_90).needs_rendering is True


def test_a_cropped_page_needs_rendering() -> None:
    assert PageFraming(crop=SAMPLE_CROP).needs_rendering is True


def test_turning_clockwise_adds_a_quarter_turn() -> None:
    assert UNFRAMED.turned_clockwise().rotation is PageRotation.CLOCKWISE_90


def test_four_turns_bring_the_rotation_back() -> None:
    framing = UNFRAMED
    for _ in range(4):
        framing = framing.turned_clockwise()

    assert framing.rotation is PageRotation.NONE


def test_turning_without_a_crop_keeps_it_empty() -> None:
    assert UNFRAMED.turned_clockwise().crop is None


def test_turning_clockwise_turns_the_crop_with_the_page() -> None:
    framing = PageFraming(crop=RectangleCrop(0.0, 0.0, 0.5, 1.0)).turned_clockwise()

    assert framing.crop == RectangleCrop(0.0, 0.0, 1.0, 0.5)


def test_four_turns_bring_the_crop_back_exactly() -> None:
    framing = PageFraming(crop=SAMPLE_CROP)
    for _ in range(4):
        framing = framing.turned_clockwise()

    assert framing == PageFraming(crop=SAMPLE_CROP)


def test_with_crop_replaces_the_crop() -> None:
    assert UNFRAMED.with_crop(SAMPLE_CROP).crop == SAMPLE_CROP


def test_with_crop_keeps_the_rotation() -> None:
    framing = PageFraming(rotation=PageRotation.HALF_TURN).with_crop(SAMPLE_CROP)

    assert framing.rotation is PageRotation.HALF_TURN


def test_a_crop_that_covers_the_whole_page_becomes_no_crop() -> None:
    assert PageFraming(crop=SAMPLE_CROP).with_crop(WHOLE_PAGE).crop is None


def test_with_no_crop_removes_the_crop() -> None:
    assert PageFraming(crop=SAMPLE_CROP).with_crop(None).crop is None


def test_without_a_crop_the_master_has_no_crop_either() -> None:
    assert PageFraming(rotation=PageRotation.CLOCKWISE_90).crop_on_master() is None


def test_an_unrotated_page_has_the_same_crop_on_the_master() -> None:
    assert PageFraming(crop=SAMPLE_CROP).crop_on_master() == SAMPLE_CROP


def test_the_crop_of_a_page_turned_a_quarter_goes_back_a_quarter_on_the_master() -> None:
    framing = PageFraming(rotation=PageRotation.CLOCKWISE_90, crop=RectangleCrop(0.0, 0.0, 1.0, 0.5))

    assert framing.crop_on_master() == RectangleCrop(0.0, 0.0, 0.5, 1.0)


def test_the_crop_of_a_half_turned_page_is_mirrored_on_the_master() -> None:
    framing = PageFraming(rotation=PageRotation.HALF_TURN, crop=RectangleCrop(0.0, 0.0, 0.5, 0.25))

    assert framing.crop_on_master() == RectangleCrop(0.5, 0.75, 1.0, 1.0)


@pytest.mark.parametrize("rotation", ALL_ROTATIONS)
def test_a_crop_from_the_master_is_the_inverse_of_the_crop_on_the_master(rotation: PageRotation) -> None:
    framing = PageFraming(rotation=rotation, crop=SAMPLE_CROP)

    assert framing.crop_from_master(framing.crop_on_master()) == SAMPLE_CROP


def test_a_crop_found_on_the_master_of_a_turned_page_is_shown_turned() -> None:
    framing = PageFraming(rotation=PageRotation.CLOCKWISE_90)

    assert framing.crop_from_master(RectangleCrop(0.0, 0.0, 0.5, 1.0)) == RectangleCrop(0.0, 0.0, 1.0, 0.5)


def test_a_crop_found_on_an_unrotated_master_is_shown_as_it_is() -> None:
    assert UNFRAMED.crop_from_master(SAMPLE_CROP) == SAMPLE_CROP
