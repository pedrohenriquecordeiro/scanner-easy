#!/usr/bin/env python3
"""Static quality gate for an implementation plan written in Markdown.

Usage: python3 -I check-plan-code.py <plan-or-part.md> [--quiet]

Checks (exit code 1 when any ERROR is found):
  ERROR   a fenced ```python block does not parse (ast.parse)
  ERROR   a function or method has more than 3 parameters (self/cls excluded)       -- Clean Code F1
  ERROR   a defined name (function, class, parameter, variable, field) uses a banned abbreviation
  ERROR   placeholder text (TBD, TODO, FIXME, "implement later", "similar to task")
  ERROR   a Python module path under src/ or tests/ is not snake_case                -- documented exception D6
  ERROR   a boolean flag parameter without a default is used (F3 hint: bool-annotated parameters)
  WARN    a function body that is only "..." outside a Protocol class
  WARN    a non-Python file path in "Create:" lines is not kebab-case (Makefile/README/LICENSE excepted)
  WARN    a "### Task" section lacks Files / Interfaces / checkbox steps
"""
import ast
import re
import sys
from pathlib import Path

BANNED_TOKENS = {
    "id", "url", "uuid", "dpi", "cfg", "conf", "config", "repo", "msg", "img", "tmp",
    "num", "idx", "req", "res", "resp", "cb", "fn", "func", "ctx", "dir", "mgr", "svc",
    "btn", "lbl", "addr", "attr", "val", "var", "obj", "arr", "str", "int", "len", "cnt",
}
ALLOWED_IDENTIFIERS = {"tmp_path", "tmp_path_factory", "id", "len", "str", "int"}
PLACEHOLDER_PATTERN = re.compile(r"\b(TBD|TODO|FIXME|XXX)\b|implement later|similar to task|fill in details", re.IGNORECASE)
PATH_PATTERN = re.compile(r"^\s*-\s*(Create|Modify|Test):\s*`([^`]+)`")
FENCE_PATTERN = re.compile(r"^(\s*)```(\w*)\s*$")
SNAKE_CASE_MODULE = re.compile(r"^[a-z0-9_]+\.py$")
KEBAB_CASE_FILE = re.compile(r"^[a-z0-9.]+(-[a-z0-9.]+)*$")
SPECIAL_FILES = {"Makefile", "README.md", "LICENSE", "__init__.py", "__main__.py", ".gitignore", ".gitkeep"}


def split_words(identifier: str) -> list:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", identifier)
    return [word.lower() for word in spaced.split("_") if word]


def banned_words_in(identifier: str) -> list:
    if identifier in ALLOWED_IDENTIFIERS or identifier.startswith("__"):
        return []
    return [word for word in split_words(identifier) if word in BANNED_TOKENS]


def extract_python_blocks(lines: list) -> list:
    blocks, current, start, language = [], None, 0, ""
    for number, line in enumerate(lines, 1):
        match = FENCE_PATTERN.match(line)
        if match and current is None:
            current, start, language = [], number + 1, match.group(2)
        elif match and current is not None:
            if language == "python":
                blocks.append((start, "\n".join(current)))
            current = None
        elif current is not None:
            current.append(line)
    return blocks


class DefinitionChecker(ast.NodeVisitor):
    def __init__(self, block_start: int) -> None:
        self.block_start = block_start
        self.problems = []
        self.class_stack = []

    def report(self, node: ast.AST, severity: str, message: str) -> None:
        self.problems.append((severity, self.block_start + getattr(node, "lineno", 1) - 1, message))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for word in banned_words_in(node.name):
            self.report(node, "ERROR", f"class name '{node.name}' uses banned abbreviation '{word}'")
        self.class_stack.append(node)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.check_function(node)
        self.generic_visit(node)

    def check_function(self, node) -> None:
        arguments = node.args
        parameters = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
        if arguments.vararg:
            parameters.append(arguments.vararg)
        if arguments.kwarg:
            parameters.append(arguments.kwarg)
        parameters = [parameter for parameter in parameters if parameter.arg not in {"self", "cls"}]
        is_fixture_test = node.name.startswith("test_")
        if len(parameters) > 3:
            self.report(node, "ERROR", f"function '{node.name}' has {len(parameters)} parameters (maximum 3)")
        for word in banned_words_in(node.name):
            self.report(node, "ERROR", f"function name '{node.name}' uses banned abbreviation '{word}'")
        for parameter in parameters:
            for word in banned_words_in(parameter.arg):
                self.report(node, "ERROR", f"parameter '{parameter.arg}' of '{node.name}' uses banned abbreviation '{word}'")
            annotation = ast.unparse(parameter.annotation) if parameter.annotation else ""
            if annotation == "bool" and not is_fixture_test:
                self.report(node, "ERROR", f"flag parameter '{parameter.arg}: bool' in '{node.name}' (split the function)")
        body = [statement for statement in node.body if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str))]
        only_ellipsis = len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and body[0].value.value is Ellipsis
        in_protocol = any("Protocol" in ast.unparse(base) for owner in self.class_stack for base in owner.bases)
        if only_ellipsis and not in_protocol:
            self.report(node, "WARN", f"function '{node.name}' body is only '...' outside a Protocol (placeholder?)")

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            for name_node in ast.walk(target):
                if isinstance(name_node, ast.Name):
                    for word in banned_words_in(name_node.id):
                        self.report(node, "ERROR", f"variable '{name_node.id}' uses banned abbreviation '{word}'")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            for word in banned_words_in(node.target.id):
                self.report(node, "ERROR", f"field/variable '{node.target.id}' uses banned abbreviation '{word}'")
        self.generic_visit(node)


def check_paths(lines: list) -> list:
    problems = []
    for number, line in enumerate(lines, 1):
        match = PATH_PATTERN.match(line)
        if not match:
            continue
        path = Path(match.group(2).split(":")[0].strip())
        name = path.name
        if name in SPECIAL_FILES:
            continue
        in_code_tree = path.parts and path.parts[0] in {"src", "tests"}
        if name.endswith(".py") and in_code_tree:
            if not SNAKE_CASE_MODULE.match(name):
                problems.append(("ERROR", number, f"Python module '{path}' must be snake_case (decision D6)"))
        elif not name.endswith(".py") and not KEBAB_CASE_FILE.match(name):
            problems.append(("WARN", number, f"file '{path}' is not kebab-case"))
    return problems


def check_task_sections(lines: list) -> list:
    problems, sections, current = [], [], None
    for number, line in enumerate(lines, 1):
        if line.startswith("### Task"):
            current = [number, line, []]
            sections.append(current)
        elif line.startswith("## ") and current is not None:
            current = None
        elif current is not None:
            current[2].append(line)
    for number, title, body in sections:
        text = "\n".join(body)
        if "**Files:**" not in text:
            problems.append(("WARN", number, f"'{title.strip()}' lacks **Files:**"))
        if "**Interfaces:**" not in text and "Task 0" not in title and "Gate 0" not in title:
            problems.append(("WARN", number, f"'{title.strip()}' lacks **Interfaces:**"))
        if "- [ ]" not in text:
            problems.append(("WARN", number, f"'{title.strip()}' has no checkbox steps"))
    return problems


def main() -> int:
    arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
    quiet = "--quiet" in sys.argv
    if not arguments:
        print(__doc__)
        return 2
    path = Path(arguments[0])
    lines = path.read_text(encoding="utf-8").splitlines()
    problems = []
    blocks = extract_python_blocks(lines)
    for start, source in blocks:
        try:
            tree = ast.parse(source)
        except SyntaxError as error:
            problems.append(("ERROR", start + (error.lineno or 1) - 1, f"python block does not parse: {error.msg}"))
            continue
        checker = DefinitionChecker(start)
        checker.visit(tree)
        problems.extend(checker.problems)
    for number, line in enumerate(lines, 1):
        if PLACEHOLDER_PATTERN.search(line):
            problems.append(("ERROR", number, f"placeholder text: {line.strip()[:80]}"))
    problems.extend(check_paths(lines))
    problems.extend(check_task_sections(lines))
    errors = [problem for problem in problems if problem[0] == "ERROR"]
    warnings = [problem for problem in problems if problem[0] == "WARN"]
    for severity, number, message in sorted(problems, key=lambda problem: (problem[1], problem[0])):
        if quiet and severity == "WARN":
            continue
        print(f"{path.name}:{number}: {severity}: {message}")
    print(f"-- {len(blocks)} python blocks, {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
