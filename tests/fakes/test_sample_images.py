import io

from PIL import Image

from tests.fakes.sample_images import build_sample_jpeg

JPEG_START_OF_IMAGE = b"\xff\xd8"


def open_image(content: bytes) -> Image.Image:
    return Image.open(io.BytesIO(content))


def test_sample_is_a_decodable_jpeg_with_the_default_size() -> None:
    content = build_sample_jpeg()

    assert content.startswith(JPEG_START_OF_IMAGE)
    assert open_image(content).size == (64, 48)


def test_sample_uses_the_requested_size() -> None:
    assert open_image(build_sample_jpeg(width_pixels=10, height_pixels=20)).size == (10, 20)


def test_sample_with_a_single_pixel_is_valid() -> None:
    assert open_image(build_sample_jpeg(width_pixels=1, height_pixels=1)).size == (1, 1)


def test_sample_writes_the_requested_density() -> None:
    image = open_image(build_sample_jpeg(dots_per_inch=300))

    assert image.info["dpi"] == (300, 300)


def test_sample_without_density_has_no_dots_per_inch() -> None:
    assert "dpi" not in open_image(build_sample_jpeg()).info


def test_sample_is_not_a_flat_color() -> None:
    image = open_image(build_sample_jpeg()).convert("RGB")

    assert image.getpixel((0, 0)) != image.getpixel((63, 47))
