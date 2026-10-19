from pathlib import Path
import ast
import builtins

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "main.py"


def test_all_route_annotation_names_are_defined_at_module_scope():
    tree = ast.parse(MAIN.read_text())
    known = set(dir(builtins))
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                known.add(alias.asname or alias.name.split(".")[-1])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            known.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    known.add(target.id)

    referenced = set()
    for node in ast.walk(tree):
        annotations = []
        if isinstance(node, ast.arg) and node.annotation is not None:
            annotations.append(node.annotation)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
            annotations.append(node.returns)
        for annotation in annotations:
            for part in ast.walk(annotation):
                if isinstance(part, ast.Name):
                    referenced.add(part.id)

    missing = sorted(referenced - known)
    assert not missing, f"Undefined API annotation names: {missing}"
