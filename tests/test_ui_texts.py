"""Garde-fou : aucun texte visible écrit en dur dans syncausha/ui (tout passe par tr())."""
import ast
from pathlib import Path

import pytest

UI_DIR = Path(__file__).resolve().parent.parent / "syncausha" / "ui"
# fonction/méthode → positions des arguments qui sont des textes visibles
SINKS = {
    "QLabel": (0,), "QPushButton": (0,), "QCheckBox": (0,), "QMenu": (0,),
    "setText": (0,), "setToolTip": (0,), "setWindowTitle": (0,), "setPlaceholderText": (0,),
    "addAction": (0,), "addItem": (0,), "addItems": (0,), "addRow": (0,), "setSuffix": (0,),
    "showMessage": (0, 1), "make_label": (0,), "section_label": (0,), "pill": (0,), "Row": (0, 1),
    "question": (1, 2), "information": (1, 2), "warning": (1, 2), "critical": (1, 2),
    "getOpenFileName": (1, 3), "getExistingDirectory": (1,),
}
LOGGERS = {"log", "logging", "logger"}
FRENCH_CHARS = set("éèêëàâçîïôûùœÉÈÀÇ")


def _is_text(node):
    if isinstance(node, ast.JoinedStr):
        return True
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and any(c.isalpha() for c in node.value)


def _call_name(func):
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name) and func.value.id in LOGGERS:
            return ""
        return func.attr
    return func.id if isinstance(func, ast.Name) else ""


def _docstrings(tree):
    nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                nodes.add(id(first.value))
    return nodes


def _log_args(tree):
    nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id in LOGGERS:
            for sub in ast.walk(node):
                nodes.add(id(sub))
    return nodes


@pytest.mark.xfail(reason="UI en cours de traduction (Task 5)", strict=True)
def test_no_hardcoded_text_passed_to_widgets():
    offenders = []
    for path in sorted(UI_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            positions = SINKS.get(_call_name(node.func))
            if not positions:
                continue
            for index in positions:
                if index >= len(node.args):
                    continue
                arg = node.args[index]
                items = arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]
                offenders += [f"{path.name}:{node.lineno}: {ast.unparse(item)[:70]}" for item in items if _is_text(item)]
    assert offenders == []


@pytest.mark.xfail(reason="UI en cours de traduction (Task 5)", strict=True)
def test_no_french_text_left_in_ui_modules():
    offenders = []
    for path in sorted(UI_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = _docstrings(tree) | _log_args(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
                if FRENCH_CHARS & set(node.value):
                    offenders.append(f"{path.name}:{node.lineno}: {node.value[:70]!r}")
    assert offenders == []
