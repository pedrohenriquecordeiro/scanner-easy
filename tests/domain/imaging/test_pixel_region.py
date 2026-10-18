from digitalizadora.domain.imaging.pixel_region import PixelRegion

REGION = PixelRegion(left=10, top=20, right=110, bottom=70)


def test_width_is_the_horizontal_extent() -> None:
    assert REGION.width == 100


def test_height_is_the_vertical_extent() -> None:
    assert REGION.height == 50


def test_area_is_width_times_height() -> None:
    assert REGION.area == 5000


def test_as_box_follows_the_order_of_pillow() -> None:
    assert REGION.as_box() == (10, 20, 110, 70)


def test_scaled_multiplies_by_the_size_ratio() -> None:
    assert REGION.scaled((200, 100), (400, 300)) == PixelRegion(20, 60, 220, 210)


def test_scaled_rounds_the_origin_down_and_the_far_edge_up() -> None:
    region = PixelRegion(left=1, top=1, right=2, bottom=2)

    assert region.scaled((3, 3), (10, 10)) == PixelRegion(left=3, top=3, right=7, bottom=7)


def test_grown_within_adds_the_margin_on_every_side() -> None:
    assert REGION.grown_within(5, (200, 200)) == PixelRegion(5, 15, 115, 75)


def test_grown_within_stops_at_the_limits_of_the_image() -> None:
    assert REGION.grown_within(50, (120, 80)) == PixelRegion(0, 0, 120, 80)
