import ast
from dataclasses import dataclass
from pathlib import Path

PACKAGE_NAME = "digitalizadora"
SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
PACKAGE_ROOT = SOURCE_ROOT / PACKAGE_NAME


def layer_of(dotted_name: str) -> str:
    """The first folder under the package, or the module name itself for the top-level modules."""
    parts = dotted_name.split(".")[1:]
    return parts[0] if parts else PACKAGE_NAME


@dataclass(frozen=True)
class SourceModule:
    dotted_name: str
    file_path: Path

    @property
    def layer(self) -> str:
        return layer_of(self.dotted_name)


def find_source_modules() -> list[SourceModule]:
    modules = []
    for file_path in sorted(PACKAGE_ROOT.rglob("*.py")):
        relative_parts = file_path.relative_to(SOURCE_ROOT).with_suffix("").parts
        if relative_parts[-1] == "__init__":
            relative_parts = relative_parts[:-1]
        modules.append(SourceModule(".".join(relative_parts), file_path))
    return modules


def read_project_imports(module: SourceModule, known_module_names: frozenset[str]) -> set[str]:
    """Dotted names of the project modules imported anywhere in the file, even lazily or under TYPE_CHECKING."""
    imported_names: set[str] = set()
    for node in ast.walk(ast.parse(module.file_path.read_text())):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                raise AssertionError(f"{module.dotted_name} uses a relative import; use absolute imports")
            for alias in node.names:
                submodule_name = f"{node.module}.{alias.name}"
                imported_names.add(submodule_name if submodule_name in known_module_names else node.module)
    return {name for name in imported_names if name == PACKAGE_NAME or name.startswith(f"{PACKAGE_NAME}.")}
