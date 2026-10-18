import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import UnreadableQuickScanError
from digitalizadora.domain.last_scan import LastScan, QuickScanSlot, SavedScanFile
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.repositories.quick_scan_manifest_codec import (
    MANIFEST_FORMAT_VERSION,
    decode_quick_scan_manifest,
    encode_quick_scan_manifest,
)
from tests.fakes.page_crops import quadrilateral, rectangle

MOMENT = datetime(2026, 10, 18, 12, 41, 3, tzinfo=timezone(timedelta(hours=-3)))
UPPER_CROP = quadrilateral((0.039, 0.28), (0.65, 0.019), (0.894, 0.321), (0.282, 0.582))
LOWER_CROP = quadrilateral((0.171, 0.604), (0.878, 0.584), (0.896, 0.931), (0.189, 0.951))
FIRST_FILE = SavedScanFile("2026-10-18_16-14-03-000000006.pdf", 211873, 1760802063123456789)
SECOND_FILE = SavedScanFile("2026-10-18_16-14-03-000000007.pdf", 98211, 1760802063223456789)
ONE_RECTANGLE = PageFraming().with_crops([rectangle((0.1, 0.2, 0.5, 0.9))])
SLOT = QuickScanSlot(
    last_scan=LastScan(
        scan_identifier="9f3c1a2b4d5e6f70",
        scanned_at=MOMENT,
        output_folder=Path("/Users/pedro/Pictures/Digitalizadora"),
        output_format=OutputFormat.PDF,
        saved_files=(FIRST_FILE,),
    ),
    dots_per_inch=300,
    color_mode=ColorMode.COLOR,
)
TWO_PHOTOS_SLOT = replace(
    SLOT,
    last_scan=replace(
        SLOT.last_scan,
        saved_files=(FIRST_FILE, SECOND_FILE),
        framing=PageFraming(PageRotation.CLOCKWISE_90).with_crops([UPPER_CROP, LOWER_CROP]),
    ),
    render_pending=True,
)


def encoded_document(slot: QuickScanSlot = TWO_PHOTOS_SLOT) -> dict[str, Any]:
    return json.loads(encode_quick_scan_manifest(slot))


def decode_document(document: object) -> QuickScanSlot:
    return decode_quick_scan_manifest(json.dumps(document).encode("utf-8"))


def test_the_format_version_is_one():
    assert MANIFEST_FORMAT_VERSION == 1


@pytest.mark.parametrize(
    "slot",
    [
        pytest.param(SLOT, id="one-file-without-crops"),
        pytest.param(TWO_PHOTOS_SLOT, id="two-files-two-crops-rotated-and-pending"),
        pytest.param(
            replace(SLOT, last_scan=replace(SLOT.last_scan, output_format=OutputFormat.JPEG)),
            id="jpg",
        ),
        pytest.param(
            replace(SLOT, last_scan=replace(SLOT.last_scan, framing=ONE_RECTANGLE)),
            id="one-rectangle",
        ),
    ],
)
def test_decoding_the_encoded_manifest_gives_the_same_slot(slot):
    assert decode_quick_scan_manifest(encode_quick_scan_manifest(slot)) == slot


def test_the_encoded_manifest_has_the_documented_keys_in_order():
    assert list(encoded_document()) == [
        "format_version",
        "scan_identifier",
        "scanned_at",
        "dots_per_inch",
        "color_mode",
        "output_folder",
        "output_format",
        "rotation_degrees",
        "crops",
        "saved_files",
        "render_pending",
    ]


def test_the_crops_are_written_with_their_four_corners():
    assert encoded_document()["crops"][0] == {
        "top_left": {"x": 0.039, "y": 0.28},
        "top_right": {"x": 0.65, "y": 0.019},
        "bottom_right": {"x": 0.894, "y": 0.321},
        "bottom_left": {"x": 0.282, "y": 0.582},
    }


def test_a_saved_file_is_written_with_its_size_and_modification_time():
    assert encoded_document()["saved_files"][0] == {
        "file_name": "2026-10-18_16-14-03-000000006.pdf",
        "size_in_bytes": 211873,
        "modified_at_nanoseconds": 1760802063123456789,
    }


def test_the_moment_is_written_with_its_time_zone():
    assert encoded_document()["scanned_at"] == "2026-10-18T12:41:03-03:00"


def test_a_manifest_that_is_not_json_is_unreadable():
    with pytest.raises(UnreadableQuickScanError):
        decode_quick_scan_manifest(b"{not json")


def test_a_manifest_that_is_not_utf8_is_unreadable():
    with pytest.raises(UnreadableQuickScanError):
        decode_quick_scan_manifest(b"\xff\xfe\x00")


@pytest.mark.parametrize("document", [[], "text", 3, None])
def test_a_manifest_that_is_not_an_object_is_unreadable(document):
    with pytest.raises(UnreadableQuickScanError):
        decode_document(document)


def change(key: str, value: object):
    return lambda document: document.update({key: value})


def remove(key: str):
    return lambda document: document.pop(key)


def saved_file(file_name: str, size_in_bytes: int = 1) -> dict[str, object]:
    return {"file_name": file_name, "size_in_bytes": size_in_bytes, "modified_at_nanoseconds": 1}


UNREADABLE_CHANGES = [
    pytest.param(change("format_version", 2), id="other-version"),
    pytest.param(change("format_version", True), id="version-as-boolean"),
    pytest.param(remove("format_version"), id="no-version"),
    pytest.param(change("scan_identifier", "xyz"), id="short-identifier"),
    pytest.param(change("scan_identifier", "G" * 16), id="identifier-not-hexadecimal"),
    pytest.param(change("scan_identifier", 12), id="identifier-not-text"),
    pytest.param(change("scanned_at", "yesterday"), id="moment-not-iso"),
    pytest.param(change("scanned_at", "2026-10-18T12:41:03"), id="moment-without-zone"),
    pytest.param(change("dots_per_inch", 0), id="no-resolution"),
    pytest.param(change("dots_per_inch", "300"), id="resolution-as-text"),
    pytest.param(change("color_mode", "sepia"), id="unknown-colour"),
    pytest.param(change("output_folder", "relative/folder"), id="relative-folder"),
    pytest.param(change("output_format", "tiff"), id="unknown-format"),
    pytest.param(change("rotation_degrees", 45), id="odd-rotation"),
    pytest.param(change("rotation_degrees", None), id="no-rotation"),
    pytest.param(change("crops", "none"), id="crops-not-a-list"),
    pytest.param(change("crops", [{}]), id="empty-crop"),
    pytest.param(change("crops", [UPPER_CROP.top_left.x] * 3), id="crops-as-numbers"),
    pytest.param(change("saved_files", []), id="no-files"),
    pytest.param(change("saved_files", "file.pdf"), id="files-as-text"),
    pytest.param(change("saved_files", [saved_file("a/b.pdf")]), id="folder-in-the-name"),
    pytest.param(change("saved_files", [saved_file("a.pdf", size_in_bytes=-1)]), id="negative-size"),
    pytest.param(change("saved_files", [{"file_name": "a.pdf", "size_in_bytes": 1}]), id="no-modification-time"),
    pytest.param(change("render_pending", "yes"), id="pending-as-text"),
    pytest.param(remove("render_pending"), id="no-pending-flag"),
    pytest.param(remove("saved_files"), id="no-files-key"),
]


@pytest.mark.parametrize("modification", UNREADABLE_CHANGES)
def test_a_manifest_outside_the_format_is_unreadable(modification):
    document = encoded_document()
    modification(document)

    with pytest.raises(UnreadableQuickScanError):
        decode_document(document)


def test_a_third_crop_makes_the_manifest_unreadable():
    document = encoded_document()
    document["crops"] = [document["crops"][0]] * 3

    with pytest.raises(UnreadableQuickScanError):
        decode_document(document)


def test_the_same_file_twice_makes_the_manifest_unreadable():
    document = encoded_document()
    document["saved_files"] = [document["saved_files"][0]] * 2

    with pytest.raises(UnreadableQuickScanError):
        decode_document(document)


def test_unknown_keys_are_ignored():
    document = encoded_document(SLOT)
    document["added_by_a_newer_version"] = [1, 2]

    assert decode_document(document) == SLOT
