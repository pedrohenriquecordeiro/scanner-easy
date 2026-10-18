from pathlib import Path

ESCL_FIXTURE_FOLDER = Path(__file__).resolve().parent.parent / "fixtures" / "escl"


def read_escl_fixture(file_name: str) -> bytes:
    return (ESCL_FIXTURE_FOLDER / file_name).read_bytes()
