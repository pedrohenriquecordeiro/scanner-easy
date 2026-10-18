from importlib.metadata import version

import digitalizadora


def test_package_exposes_its_version() -> None:
    assert digitalizadora.__version__ == "0.1.0"


def test_package_version_matches_the_installed_metadata() -> None:
    assert version("digitalizadora") == digitalizadora.__version__
