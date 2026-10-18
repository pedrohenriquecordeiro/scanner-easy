import io

from PIL import Image

JPEG_QUALITY = 85
CHANNEL_MAXIMUM = 255


def build_sample_jpeg(
    width_pixels: int = 64,
    height_pixels: int = 48,
    dots_per_inch: int | None = None,
) -> bytes:
    size = (width_pixels, height_pixels)
    horizontal_ramp = [
        round(column * CHANNEL_MAXIMUM / max(width_pixels - 1, 1)) for column in range(width_pixels)
    ]
    vertical_ramp = [
        round(row * CHANNEL_MAXIMUM / max(height_pixels - 1, 1)) for row in range(height_pixels)
    ]
    red_channel = Image.frombytes("L", size, bytes(horizontal_ramp) * height_pixels)
    green_channel = Image.frombytes(
        "L", size, b"".join(bytes([level]) * width_pixels for level in vertical_ramp)
    )
    blue_channel = Image.new("L", size, CHANNEL_MAXIMUM // 2)
    image = Image.merge("RGB", (red_channel, green_channel, blue_channel))
    save_options: dict[str, object] = {"quality": JPEG_QUALITY}
    if dots_per_inch is not None:
        save_options["dpi"] = (dots_per_inch, dots_per_inch)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", **save_options)
    return buffer.getvalue()
