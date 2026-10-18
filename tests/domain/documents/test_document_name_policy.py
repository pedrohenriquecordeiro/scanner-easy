import unicodedata

import pytest

from digitalizadora.domain.documents.document_name_policy import build_document_file_name, clean_document_name
from digitalizadora.domain.errors import InvalidDocumentNameError

ACCENTED_NAME_IN_NFD = unicodedata.normalize("NFD", "Ação")
DOCUMENTED_NAMES = [
    ("Contrato do apartamento", "Contrato do apartamento", "Contrato do apartamento.pdf"),
    ("  Notas fiscais 2026/10  ", "Notas fiscais 2026-10", "Notas fiscais 2026-10.pdf"),
    ("Recibo: março", "Recibo- março", "Recibo- março.pdf"),
    ("Linha 1\nLinha   2", "Linha 1 Linha 2", "Linha 1 Linha 2.pdf"),
    (".oculto", "oculto", "oculto.pdf"),
    ("Relatório.PDF", "Relatório", "Relatório.pdf"),
    ("Pergunta?", "Pergunta-", "Pergunta-.pdf"),
    ("abc\u202efdp.exe", "abcfdp.exe", "abcfdp.exe.pdf"),
    (ACCENTED_NAME_IN_NFD, "Ação", "Ação.pdf"),
]
DOCUMENTED_NAME_IDENTIFIERS = [
    "plain",
    "slash-and-edge-spaces",
    "colon",
    "line-break-and-repeated-spaces",
    "leading-dot",
    "typed-pdf-suffix",
    "question-mark",
    "bidirectional-override",
    "decomposed-accents",
]


CLEAN_NAME_CASES = [(raw_name, clean_name) for raw_name, clean_name, _ in DOCUMENTED_NAMES]
FILE_NAME_CASES = [(raw_name, file_name) for raw_name, _, file_name in DOCUMENTED_NAMES]


@pytest.mark.parametrize(("raw_name", "expected_name"), CLEAN_NAME_CASES, ids=DOCUMENTED_NAME_IDENTIFIERS)
def test_clean_document_name_follows_the_documented_table(raw_name: str, expected_name: str) -> None:
    assert clean_document_name(raw_name) == expected_name


@pytest.mark.parametrize(("raw_name", "expected_file_name"), FILE_NAME_CASES, ids=DOCUMENTED_NAME_IDENTIFIERS)
def test_first_file_name_follows_the_documented_table(raw_name: str, expected_file_name: str) -> None:
    assert build_document_file_name(clean_document_name(raw_name), 1) == expected_file_name


def test_decomposed_accents_become_composed() -> None:
    assert clean_document_name(ACCENTED_NAME_IN_NFD) == unicodedata.normalize("NFC", ACCENTED_NAME_IN_NFD)


@pytest.mark.parametrize("raw_name", ["", "   ", "\t\n"], ids=["empty", "spaces", "tab-and-line-break"])
def test_blank_name_means_the_automatic_name(raw_name: str) -> None:
    assert clean_document_name(raw_name) == ""


@pytest.mark.parametrize(
    "raw_name",
    ["...", ".pdf", " . . ", "\u200b", "\u202e"],
    ids=["dots", "only-suffix", "dots-and-spaces", "zero-width", "bidirectional-mark"],
)
def test_name_without_visible_characters_is_refused(raw_name: str) -> None:
    with pytest.raises(InvalidDocumentNameError):
        clean_document_name(raw_name)


@pytest.mark.parametrize(
    ("raw_name", "expected_name"),
    [
        ("a\u00a0b", "a b"),
        ("a\u2028b", "a b"),
        ("a\u00adb", "ab"),
        ("a\x07b", "ab"),
        ("x*y<z>|w\\v\"u", "x-y-z--w-v-u"),
        ("Relatório.pdf.", "Relatório.pdf"),
        ("Relatório .pdf", "Relatório"),
        ("Relatório.pdf.pdf", "Relatório.pdf"),
    ],
    ids=[
        "no-break-space",
        "line-separator",
        "soft-hyphen",
        "bell",
        "other-forbidden-characters",
        "trailing-dot-after-suffix",
        "space-before-suffix",
        "suffix-removed-once",
    ],
)
def test_clean_document_name_handles_each_character_rule(raw_name: str, expected_name: str) -> None:
    assert clean_document_name(raw_name) == expected_name


def test_name_with_exactly_120_characters_is_accepted() -> None:
    assert clean_document_name("a" * 120) == "a" * 120


def test_name_with_121_characters_is_refused() -> None:
    with pytest.raises(InvalidDocumentNameError):
        clean_document_name("a" * 121)


def test_name_with_exactly_200_bytes_is_accepted() -> None:
    assert clean_document_name("é" * 100) == "é" * 100


def test_name_with_201_bytes_is_refused() -> None:
    with pytest.raises(InvalidDocumentNameError):
        clean_document_name("é" * 100 + "a")


def test_name_with_60_emojis_is_refused() -> None:
    with pytest.raises(InvalidDocumentNameError):
        clean_document_name("\U0001f4c4" * 60)


def test_long_name_is_measured_after_cleaning() -> None:
    assert clean_document_name("  " + "a" * 120 + "  ") == "a" * 120


@pytest.mark.parametrize(
    ("attempt_number", "expected_file_name"),
    [
        (1, "Contrato do apartamento.pdf"),
        (2, "Contrato do apartamento (2).pdf"),
        (3, "Contrato do apartamento (3).pdf"),
        (1000, "Contrato do apartamento (1000).pdf"),
    ],
)
def test_build_document_file_name_numbers_the_later_attempts(attempt_number: int, expected_file_name: str) -> None:
    assert build_document_file_name("Contrato do apartamento", attempt_number) == expected_file_name


def test_longest_name_with_the_last_attempt_fits_in_255_bytes() -> None:
    file_name = build_document_file_name("é" * 100, 1000)

    assert len(file_name.encode("utf-8")) <= 255
