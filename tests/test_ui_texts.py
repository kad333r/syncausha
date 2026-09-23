"""Garde-fous : aucun texte visible écrit en dur dans syncausha/ui (tout passe par tr()), et chaque appel
tr("clé", …) / msg("clé", …) du code vise une clé du catalogue avec exactement ses variables."""
import ast
import string
from pathlib import Path

from syncausha.translations import CATALOG

SOURCE_DIR = Path(__file__).resolve().parent.parent / "syncausha"
UI_DIR = SOURCE_DIR / "ui"
# fonction/méthode → positions des arguments qui sont des textes visibles
SINKS = {
    "QLabel": (0,), "QPushButton": (0,), "QCheckBox": (0,), "QMenu": (0,),
    "QListWidgetItem": (0, 1), "QAction": (0, 1),  # (texte, …) ou (icône, texte, …)
    "setText": (0,), "setToolTip": (0,), "setWindowTitle": (0,), "setPlaceholderText": (0,),
    "setStatusTip": (0,), "setAccessibleName": (0,), "setItemText": (1,),
    "addAction": (0,), "addItem": (0,), "addItems": (0,), "addRow": (0,), "setSuffix": (0,),
    "showMessage": (0, 1), "make_label": (0,), "section_label": (0,), "pill": (0,), "Row": (0, 1),
    "question": (1, 2), "information": (1, 2), "warning": (1, 2), "critical": (1, 2),
    "getOpenFileName": (1, 3), "getExistingDirectory": (1,),
}
LOGGERS = {"log", "logging", "logger"}
FRENCH_CHARS = set("éèêëàâçîïôûùœÉÈÀÇ")
TRANSLATORS = {"tr", "msg"}


def _is_text(node):
    if isinstance(node, ast.JoinedStr):  # f-string : texte si une de ses parties écrites en dur a une lettre
        return any(_is_text(part) for part in node.values if isinstance(part, ast.Constant))
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


def _hardcoded_texts(source, name):
    """Textes écrits en dur passés à un widget (SINKS)."""
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        for index in SINKS.get(_call_name(node.func), ()):
            if index >= len(node.args):
                continue
            arg = node.args[index]
            items = arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]
            offenders += [f"{name}:{node.lineno}: {ast.unparse(item)[:70]}" for item in items if _is_text(item)]
    return offenders


def test_no_hardcoded_text_passed_to_widgets():
    offenders = []
    for path in sorted(UI_DIR.glob("*.py")):
        offenders += _hardcoded_texts(path.read_text(encoding="utf-8"), path.name)
    assert offenders == []


def test_the_widget_guard_sees_every_kind_of_text():
    snippet = "\n".join([
        'item = QListWidgetItem(icon, "Mars Attack")',
        'other = QListWidgetItem("Silicon Talk")',
        'action = QAction("Quit", window)',
        'combo.setItemText(0, "First")',
        'button.setStatusTip("Starts a sync")',
        'button.setAccessibleName("Sync")',
        'label.setText(f"Next sync in {minutes} min")',
        'item = QListWidgetItem(icon, f"{rule.keyword}\\n{target}")',  # que des variables : pas un texte
        'log.warning("Jeton refusé : %s", detail)',  # journal : en français, non traduit
    ])
    assert [line.split(":")[1] for line in _hardcoded_texts(snippet, "x.py")] == ["1", "2", "3", "4", "5", "6", "7"]


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


def _placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def _translator(func):
    """« tr » ou « msg » pour tr(…), msg(…), i18n.tr(…), i18n.msg(…) ; sinon None."""
    if isinstance(func, ast.Name) and func.id in TRANSLATORS:
        return func.id
    if isinstance(func, ast.Attribute) and func.attr in TRANSLATORS:
        if isinstance(func.value, ast.Name) and func.value.id == "i18n":
            return func.attr
    return None


def _translation_problems(source, name):
    """(appels vérifiés, problèmes) : clé absente du catalogue, variables en trop ou manquantes. Les appels
    dont la clé n'est pas écrite en dur, ou qui passent **variables, ne peuvent pas être vérifiés ici."""
    checked, problems = 0, []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not (kind := _translator(node.func)):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        if any(keyword.arg is None for keyword in node.keywords):
            continue
        checked += 1
        key, where = node.args[0].value, f"{name}:{node.lineno}"
        if key not in CATALOG:
            problems.append(f"{where}: clé inconnue {key!r}")
            continue
        given = {keyword.arg for keyword in node.keywords} - ({"lang"} if kind == "tr" else set())
        expected = _placeholders(CATALOG[key]["en"])
        if given != expected:
            problems.append(f"{where}: {key} reçoit {sorted(given)}, attend {sorted(expected)}")
    return checked, problems


def test_translation_calls_match_the_catalog():
    checked, problems = 0, []
    for path in sorted(SOURCE_DIR.rglob("*.py")):
        count, found = _translation_problems(path.read_text(encoding="utf-8"), path.relative_to(SOURCE_DIR).as_posix())
        checked, problems = checked + count, problems + found
    assert problems == []
    assert checked > 100  # l'analyse trouve bien les appels


def test_the_translation_guard_reports_bad_calls():
    snippet = "\n".join([
        'tr("does_not_exist")',
        'msg("dry_line", title=t)',  # detail manquant
        'i18n.tr("activity_uploading", percent=1, extra=2)',  # variable en trop
        'msg("dry_would_publish", show=s, lang="fr")',  # msg n'a pas de paramètre lang
        'tr("activity_uploading", lang="ar", percent=1)',  # correct
        'tr(key, n=1)',  # clé calculée : non vérifiable
        'msg("dry_line", **values)',  # variables calculées : non vérifiables
    ])
    checked, problems = _translation_problems(snippet, "x.py")
    assert checked == 5
    assert [problem.split(":")[1] for problem in problems] == ["1", "2", "3", "4"]
