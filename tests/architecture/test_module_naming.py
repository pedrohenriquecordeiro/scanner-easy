import re

import pytest

from tests.architecture.source_modules import PACKAGE_ROOT, SOURCE_ROOT, SourceModule, find_source_modules

SNAKE_CASE_NAME = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
DUNDER_NAMES = {"__init__", "__main__"}
SOURCE_MODULES = find_source_modules()


@pytest.mark.parametrize("module", SOURCE_MODULES, ids=lambda module: module.dotted_name)
def test_module_file_name_is_snake_case(module: SourceModule) -> None:
    file_stem = module.file_path.stem

    assert file_stem in DUNDER_NAMES or SNAKE_CASE_NAME.match(file_stem), f"{module.file_path} is not snake_case"


def test_package_folder_names_are_snake_case() -> None:
    folder_names = {
        folder.relative_to(SOURCE_ROOT)
        for folder in PACKAGE_ROOT.rglob("*")
        if folder.is_dir() and folder.name != "__pycache__" and any(folder.glob("*.py"))
    }

    offending_folders = sorted(str(folder) for folder in folder_names if not SNAKE_CASE_NAME.match(folder.name))

    assert offending_folders == []
