import pytest

from tests.architecture.source_modules import (
    PACKAGE_NAME,
    SourceModule,
    find_source_modules,
    layer_of,
    read_project_imports,
)

SOURCE_MODULES = find_source_modules()
KNOWN_MODULE_NAMES = frozenset(module.dotted_name for module in SOURCE_MODULES)

# Layer -> layers it may import (always including itself). The top-level modules of the package are layers of their
# own, named after the module. "simulator" is a development tool that answers like the printer, so it may reuse the
# eSCL protocol of the infrastructure.
ALLOWED_LAYERS = {
    "domain": {"domain"},
    "services": {"domain", "services"},
    "repositories": {"domain", "repositories"},
    "controllers": {"domain", "services", "controllers"},
    "infrastructure": {"domain", "infrastructure"},
    "simulator": {"domain", "infrastructure", "simulator"},
    "application_factory": {"domain", "controllers", "application_factory"},
    "configuration": {"configuration"},
    "composition_root": {
        "domain",
        "services",
        "repositories",
        "controllers",
        "infrastructure",
        "application_factory",
        "configuration",
        "composition_root",
    },
    "__main__": {"domain", "controllers", "application_factory", "configuration", "composition_root", "__main__"},
    PACKAGE_NAME: {PACKAGE_NAME},
}
# Only the entry point may build the object graph; every other module receives its collaborators.
COMPOSITION_ROOT_NAME = f"{PACKAGE_NAME}.composition_root"
COMPOSITION_ROOT_USERS = {COMPOSITION_ROOT_NAME, f"{PACKAGE_NAME}.__main__"}
MODULES_WITHOUT_COMPOSITION_ACCESS = [
    module for module in SOURCE_MODULES if module.dotted_name not in COMPOSITION_ROOT_USERS
]


@pytest.mark.parametrize("module", SOURCE_MODULES, ids=lambda module: module.dotted_name)
def test_module_imports_only_layers_it_may_depend_on(module: SourceModule) -> None:
    allowed_layers = ALLOWED_LAYERS[module.layer]

    forbidden_imports = sorted(
        imported_name
        for imported_name in read_project_imports(module, KNOWN_MODULE_NAMES)
        if layer_of(imported_name) not in allowed_layers
    )

    assert forbidden_imports == [], f"{module.dotted_name} ({module.layer}) must not import {forbidden_imports}"


@pytest.mark.parametrize("module", MODULES_WITHOUT_COMPOSITION_ACCESS, ids=lambda module: module.dotted_name)
def test_only_the_entry_point_imports_the_composition_root(module: SourceModule) -> None:
    imported_names = read_project_imports(module, KNOWN_MODULE_NAMES)

    assert COMPOSITION_ROOT_NAME not in imported_names


def test_every_source_module_belongs_to_a_known_layer() -> None:
    unknown_layers = sorted({module.layer for module in SOURCE_MODULES} - ALLOWED_LAYERS.keys())

    assert unknown_layers == [], f"classify these new top-level packages or modules in ALLOWED_LAYERS: {unknown_layers}"
