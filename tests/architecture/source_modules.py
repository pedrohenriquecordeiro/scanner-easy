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


def build_import_graph(modules: list[SourceModule]) -> dict[str, set[str]]:
    """Module dotted name -> dotted names of the project modules it imports."""
    known_module_names = frozenset(module.dotted_name for module in modules)
    return {
        module.dotted_name: read_project_imports(module, known_module_names) & known_module_names for module in modules
    }


def package_of(dotted_name: str) -> str | None:
    """The layer and feature package of a module, or None for the modules that sit directly in a layer or at the top."""
    parts = dotted_name.split(".")
    return ".".join(parts[:3]) if len(parts) > 3 else None


def collapse_to_packages(import_graph: dict[str, set[str]]) -> dict[str, set[str]]:
    """Import graph between feature packages; modules at the layer root (such as domain.ports) are left out."""
    package_graph: dict[str, set[str]] = {}
    for importer_name, imported_names in import_graph.items():
        importer_package = package_of(importer_name)
        if importer_package is None:
            continue
        package_graph.setdefault(importer_package, set())
        for imported_name in imported_names:
            imported_package = package_of(imported_name)
            if imported_package is not None and imported_package != importer_package:
                package_graph[importer_package].add(imported_package)
                package_graph.setdefault(imported_package, set())
    return package_graph


def find_import_cycles(import_graph: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components with more than one node (Tarjan), each one a set of mutually dependent names."""
    next_index = 0
    node_indexes: dict[str, int] = {}
    lowest_reachable: dict[str, int] = {}
    open_nodes: list[str] = []
    is_open: set[str] = set()
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal next_index
        node_indexes[node] = lowest_reachable[node] = next_index
        next_index += 1
        open_nodes.append(node)
        is_open.add(node)
        for neighbour in import_graph.get(node, ()):
            if neighbour not in node_indexes:
                visit(neighbour)
                lowest_reachable[node] = min(lowest_reachable[node], lowest_reachable[neighbour])
            elif neighbour in is_open:
                lowest_reachable[node] = min(lowest_reachable[node], node_indexes[neighbour])
        if lowest_reachable[node] == node_indexes[node]:
            component = []
            while True:
                member = open_nodes.pop()
                is_open.discard(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                cycles.append(sorted(component))

    for node in sorted(import_graph):
        if node not in node_indexes:
            visit(node)
    return sorted(cycles)
