from tests.architecture.source_modules import (
    build_import_graph,
    collapse_to_packages,
    find_import_cycles,
    find_source_modules,
)

IMPORT_GRAPH = build_import_graph(find_source_modules())


def test_no_two_modules_import_each_other_directly_or_through_others() -> None:
    assert find_import_cycles(IMPORT_GRAPH) == []


def test_no_two_feature_packages_depend_on_each_other() -> None:
    assert find_import_cycles(collapse_to_packages(IMPORT_GRAPH)) == []


def test_the_cycle_finder_reports_a_cycle_through_three_modules() -> None:
    graph = {"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"a"}}

    assert find_import_cycles(graph) == [["a", "b", "c"]]


def test_the_cycle_finder_accepts_a_graph_without_cycles() -> None:
    graph = {"a": {"b", "c"}, "b": {"c"}, "c": set()}

    assert find_import_cycles(graph) == []


def test_the_package_graph_ignores_modules_at_the_layer_root() -> None:
    graph = {
        "digitalizadora.domain.ports": {"digitalizadora.domain.output.encoded_scan"},
        "digitalizadora.domain.output.policy": {"digitalizadora.domain.ports"},
        "digitalizadora.domain.output.encoded_scan": set(),
    }

    assert collapse_to_packages(graph) == {"digitalizadora.domain.output": set()}
