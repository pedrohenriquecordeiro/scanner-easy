import json
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.document_draft import DocumentDraft, DocumentPage
from digitalizadora.domain.errors import UnreadableDraftError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.repositories.document_manifest_codec import (
    MANIFEST_FORMAT_VERSION,
    decode_manifest,
    encode_manifest,
)
from tests.fakes.document_drafts import DRAFT_CREATED_AT, build_document_draft

FRAMED = PageFraming(PageRotation.CLOCKWISE_90, PageCrop(0.125, 0.115, 0.924, 0.925))
FINALIZATION_STARTED_AT = DRAFT_CREATED_AT + timedelta(minutes=4)
FINALIZED_AT = DRAFT_CREATED_AT + timedelta(minutes=5)
FINISHED_DOCUMENT = ScanResult(
    output_path=Path("/Volumes/Arquivo/Contrato do apartamento.pdf"),
    output_format=OutputFormat.PDF,
    scanned_at=FINALIZED_AT,
    size_in_bytes=1612800,
)
SAMPLE_PAGE = DocumentPage(
    page_identifier="3f9c0a1b2c3d4e5f",
    scanned_at=DRAFT_CREATED_AT,
    dots_per_inch=300,
    color_mode=ColorMode.COLOR,
    size_in_bytes=806123,
)
NAMED_DRAFT = DocumentDraft(name="Contrato do apartamento", created_at=DRAFT_CREATED_AT, pages=(SAMPLE_PAGE,))
EXPECTED_MANIFEST_TEXT = """{
  "format_version": 1,
  "name": "Contrato do apartamento",
  "created_at": "2026-10-17T10:00:00-03:00",
  "pages": [
    {
      "page_identifier": "3f9c0a1b2c3d4e5f",
      "scanned_at": "2026-10-17T10:00:00-03:00",
      "dots_per_inch": 300,
      "color_mode": "color",
      "size_in_bytes": 806123,
      "rotation_degrees": 0,
      "crop": null
    }
  ],
  "finalization_started_at": null,
  "finished_document": null
}"""


def manifest_with_both_markers() -> dict[str, Any]:
    marked_draft = NAMED_DRAFT.with_finalization_started(FINALIZATION_STARTED_AT).marked_finished(FINISHED_DOCUMENT)
    return json.loads(encode_manifest(marked_draft))


def encode_document(document: object) -> bytes:
    return json.dumps(document).encode("utf-8")


def decode_changed_manifest(change: Callable[[dict[str, Any]], object]) -> DocumentDraft:
    document = manifest_with_both_markers()
    change(document)
    return decode_manifest(encode_document(document))


def set_manifest_value(key: str, value: object) -> Callable[[dict[str, Any]], object]:
    return lambda document: document.update({key: value})


def remove_manifest_key(key: str) -> Callable[[dict[str, Any]], object]:
    return lambda document: document.pop(key)


def set_page_value(key: str, value: object) -> Callable[[dict[str, Any]], object]:
    return lambda document: document["pages"][0].update({key: value})


def remove_page_key(key: str) -> Callable[[dict[str, Any]], object]:
    return lambda document: document["pages"][0].pop(key)


def set_finished_document_value(key: str, value: object) -> Callable[[dict[str, Any]], object]:
    return lambda document: document["finished_document"].update({key: value})


def remove_finished_document_key(key: str) -> Callable[[dict[str, Any]], object]:
    return lambda document: document["finished_document"].pop(key)


def repeat_the_first_page(document: dict[str, Any]) -> None:
    document["pages"].append(dict(document["pages"][0]))


def test_format_version_is_one():
    assert MANIFEST_FORMAT_VERSION == 1


def test_encoded_manifest_has_the_documented_keys_order_and_indentation():
    assert encode_manifest(NAMED_DRAFT).decode("utf-8") == EXPECTED_MANIFEST_TEXT


def test_finished_document_is_encoded_with_path_size_and_moment():
    document = json.loads(encode_manifest(NAMED_DRAFT.marked_finished(FINISHED_DOCUMENT)))

    assert document["finished_document"] == {
        "path": "/Volumes/Arquivo/Contrato do apartamento.pdf",
        "size_in_bytes": 1612800,
        "finalized_at": "2026-10-17T10:05:00-03:00",
    }


def test_finalization_marker_is_encoded_as_a_moment_with_time_zone():
    document = json.loads(encode_manifest(NAMED_DRAFT.with_finalization_started(FINALIZATION_STARTED_AT)))

    assert document["finalization_started_at"] == "2026-10-17T10:04:00-03:00"


def test_accented_name_is_written_without_escapes():
    manifest_text = encode_manifest(NAMED_DRAFT.renamed("Recibo de março")).decode("utf-8")

    assert '"name": "Recibo de março"' in manifest_text


ROUND_TRIP_DRAFTS = [
    pytest.param(NAMED_DRAFT, id="without-markers"),
    pytest.param(NAMED_DRAFT.with_finalization_started(FINALIZATION_STARTED_AT), id="finalization-started"),
    pytest.param(NAMED_DRAFT.marked_finished(FINISHED_DOCUMENT), id="finished"),
    pytest.param(
        NAMED_DRAFT.with_finalization_started(FINALIZATION_STARTED_AT).marked_finished(FINISHED_DOCUMENT),
        id="both-markers",
    ),
    pytest.param(build_document_draft(3), id="three-pages-automatic-name"),
    pytest.param(build_document_draft(0), id="no-pages"),
    pytest.param(
        DocumentDraft(
            name="Moldura",
            created_at=DRAFT_CREATED_AT,
            pages=(replace(SAMPLE_PAGE, framing=FRAMED),),
        ),
        id="rotated-and-cropped-page",
    ),
    pytest.param(
        DocumentDraft(
            name="Foto",
            created_at=DRAFT_CREATED_AT,
            pages=(DocumentPage("0123456789abcdef", FINALIZED_AT, 200, ColorMode.GRAYSCALE, 1),),
        ),
        id="grayscale-page",
    ),
]


@pytest.mark.parametrize("draft", ROUND_TRIP_DRAFTS)
def test_decoding_the_encoded_manifest_gives_the_same_draft(draft):
    assert decode_manifest(encode_manifest(draft)) == draft


def test_manifest_without_the_marker_keys_reads_them_as_null():
    document = json.loads(encode_manifest(NAMED_DRAFT))
    del document["finalization_started_at"]
    del document["finished_document"]

    assert decode_manifest(encode_document(document)) == NAMED_DRAFT


def test_unknown_keys_are_ignored():
    document = json.loads(encode_manifest(NAMED_DRAFT))
    document["added_by_a_newer_version"] = {"anything": [1, 2]}
    document["pages"][0]["rotation_in_degrees"] = 90

    assert decode_manifest(encode_document(document)) == NAMED_DRAFT


def test_the_rotation_and_the_crop_are_encoded_on_the_page():
    document = json.loads(encode_manifest(replace(NAMED_DRAFT, pages=(replace(SAMPLE_PAGE, framing=FRAMED),))))

    assert (document["pages"][0]["rotation_degrees"], document["pages"][0]["crop"]) == (
        90,
        {"left": 0.125, "top": 0.115, "right": 0.924, "bottom": 0.925},
    )


def test_a_manifest_from_before_the_framing_reads_pages_without_rotation_or_crop():
    document = json.loads(encode_manifest(NAMED_DRAFT))
    del document["pages"][0]["rotation_degrees"]
    del document["pages"][0]["crop"]

    assert decode_manifest(encode_document(document)).pages[0].framing == UNFRAMED


@pytest.mark.parametrize("rotation", [45, "90", 90.0, True, None, [90]])
def test_an_invalid_rotation_is_read_as_no_rotation(rotation):
    draft = decode_changed_manifest(set_page_value("rotation_degrees", rotation))

    assert draft.pages[0].framing.rotation is PageRotation.NONE


INVALID_CROPS = [
    pytest.param({"left": 0.5, "top": 0, "right": 0.4, "bottom": 1}, id="edges-reversed"),
    pytest.param({"left": -0.1, "top": 0, "right": 1, "bottom": 1}, id="outside-the-page"),
    pytest.param({"left": 0, "top": 0, "right": 1}, id="edge-missing"),
    pytest.param({"left": "0", "top": 0, "right": 1, "bottom": 1}, id="edge-as-text"),
    pytest.param({"left": 0, "top": 0, "right": 1, "bottom": 10**400}, id="integer-too-large-for-a-float"),
    pytest.param([0, 0, 1, 1], id="not-an-object"),
    pytest.param("whole", id="text"),
]


@pytest.mark.parametrize("crop", INVALID_CROPS)
def test_an_invalid_crop_is_read_as_no_crop(crop):
    draft = decode_changed_manifest(set_page_value("crop", crop))

    assert draft.pages[0].framing.crop is None


def test_an_invalid_crop_does_not_make_the_manifest_unreadable():
    draft = decode_changed_manifest(set_page_value("crop", "whole"))

    assert draft.name == NAMED_DRAFT.name


def test_an_invalid_rotation_keeps_the_crop_of_the_page():
    document = manifest_with_both_markers()
    document["pages"][0].update({"rotation_degrees": 45, "crop": {"left": 0, "top": 0, "right": 0.5, "bottom": 0.5}})

    framing = decode_manifest(encode_document(document)).pages[0].framing

    assert framing == PageFraming(PageRotation.NONE, PageCrop(0.0, 0.0, 0.5, 0.5))


def test_a_crop_of_the_whole_page_is_read_as_no_crop():
    whole_page = {"left": 0, "top": 0, "right": 1, "bottom": 1}

    assert decode_changed_manifest(set_page_value("crop", whole_page)).pages[0].framing.crop is None


def test_an_invalid_framing_value_is_reported_in_the_log(caplog):
    with caplog.at_level(logging.WARNING):
        decode_changed_manifest(set_page_value("rotation_degrees", 45))

    assert "invalid rotation" in caplog.text


@pytest.mark.parametrize("dots_per_inch", [1, 65535])
def test_dots_per_inch_at_the_limits_is_accepted(dots_per_inch):
    draft = decode_changed_manifest(set_page_value("dots_per_inch", dots_per_inch))

    assert draft.pages[0].dots_per_inch == dots_per_inch


def test_page_of_one_byte_is_accepted():
    draft = decode_changed_manifest(set_page_value("size_in_bytes", 1))

    assert draft.pages[0].size_in_bytes == 1


UNREADABLE_CHANGES = [
    pytest.param(set_manifest_value("format_version", 2), id="newer-version"),
    pytest.param(remove_manifest_key("format_version"), id="version-missing"),
    pytest.param(set_manifest_value("format_version", True), id="version-true"),
    pytest.param(set_manifest_value("format_version", "1"), id="version-as-text"),
    pytest.param(set_manifest_value("format_version", 1.0), id="version-as-fraction"),
    pytest.param(remove_manifest_key("name"), id="name-missing"),
    pytest.param(set_manifest_value("name", 5), id="name-not-text"),
    pytest.param(set_manifest_value("created_at", "2026-10-17T10:00:00"), id="created-at-without-time-zone"),
    pytest.param(set_manifest_value("created_at", "yesterday"), id="created-at-not-a-moment"),
    pytest.param(set_manifest_value("created_at", 1760706000), id="created-at-not-text"),
    pytest.param(remove_manifest_key("created_at"), id="created-at-missing"),
    pytest.param(remove_manifest_key("pages"), id="pages-missing"),
    pytest.param(set_manifest_value("pages", {"page": 1}), id="pages-not-a-list"),
    pytest.param(set_manifest_value("pages", ["page"]), id="page-not-an-object"),
    pytest.param(set_page_value("page_identifier", "LAST3F9C0A1B2C3D"), id="identifier-uppercase"),
    pytest.param(set_page_value("page_identifier", "../manifest.json"), id="identifier-path"),
    pytest.param(set_page_value("page_identifier", 3), id="identifier-not-text"),
    pytest.param(remove_page_key("page_identifier"), id="identifier-missing"),
    pytest.param(repeat_the_first_page, id="identifier-repeated"),
    pytest.param(set_page_value("scanned_at", "2026-10-17T10:00:00"), id="scanned-at-without-time-zone"),
    pytest.param(set_page_value("dots_per_inch", 0), id="dots-per-inch-zero"),
    pytest.param(set_page_value("dots_per_inch", 65536), id="dots-per-inch-too-large"),
    pytest.param(set_page_value("dots_per_inch", True), id="dots-per-inch-true"),
    pytest.param(set_page_value("dots_per_inch", "300"), id="dots-per-inch-as-text"),
    pytest.param(set_page_value("color_mode", "sepia"), id="unknown-color-mode"),
    pytest.param(remove_page_key("color_mode"), id="color-mode-missing"),
    pytest.param(set_page_value("size_in_bytes", 0), id="size-zero"),
    pytest.param(set_page_value("size_in_bytes", "806123"), id="size-as-text"),
    pytest.param(remove_page_key("size_in_bytes"), id="size-missing"),
    pytest.param(set_manifest_value("finalization_started_at", "2026-10-17T10:04:00"), id="intent-without-zone"),
    pytest.param(set_manifest_value("finalization_started_at", 5), id="intent-not-text"),
    pytest.param(set_manifest_value("finished_document", "done"), id="finished-not-an-object"),
    pytest.param(set_finished_document_value("path", "Contrato do apartamento.pdf"), id="finished-relative-path"),
    pytest.param(set_finished_document_value("path", 7), id="finished-path-not-text"),
    pytest.param(remove_finished_document_key("finalized_at"), id="finished-without-finalized-at"),
    pytest.param(set_finished_document_value("finalized_at", "2026-10-17T10:05:00"), id="finished-without-zone"),
    pytest.param(set_finished_document_value("size_in_bytes", 0), id="finished-size-zero"),
]


@pytest.mark.parametrize("change", UNREADABLE_CHANGES)
def test_manifest_that_breaks_a_reading_rule_is_unreadable(change):
    with pytest.raises(UnreadableDraftError):
        decode_changed_manifest(change)


UNREADABLE_CONTENTS = [
    pytest.param(b'{"format_version": 1, "name": "Contr', id="cut-json"),
    pytest.param(b"", id="empty-file"),
    pytest.param(b"[]", id="list-instead-of-object"),
    pytest.param(b"\xff\xfe{}", id="not-utf-8"),
]


@pytest.mark.parametrize("content", UNREADABLE_CONTENTS)
def test_content_that_is_not_a_json_object_is_unreadable(content):
    with pytest.raises(UnreadableDraftError):
        decode_manifest(content)


def test_moment_with_time_zone_keeps_its_offset():
    draft = decode_changed_manifest(set_manifest_value("created_at", "2026-10-17T13:00:00+00:00"))

    assert draft.created_at == datetime.fromisoformat("2026-10-17T10:00:00-03:00")
