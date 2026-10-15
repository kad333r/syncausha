"""Page Émissions : liste des émissions (dossier, mots-clés), carte de l'émission, mots-clés et leur éditeur."""
import copy

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QMessageBox

from syncausha import i18n
from syncausha.ausha_client import Playlist, Show
from syncausha.config import Config, KeywordRule, ShowFolder, load_config
from syncausha.i18n import tr
from syncausha.journal import Journal
from syncausha.ui import controller as controller_module
from syncausha.ui import shows_page as shows_page_module
from syncausha.ui.controller import AppController
from syncausha.ui.shows_page import ShowsPage

RLM, FSI, PDI = "‏", "⁨", "⁩"
MARS, SILICON = Show(1, "Mars Attack"), Show(2, "Silicon Talk")
CATALOG = {MARS: [Playlist(7, "Saison 3"), Playlist(8, "Bonus")], SILICON: [Playlist(9, "Débrief")]}


@pytest.fixture
def controller(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(controller_module, "get_token", lambda: None)
    journal = Journal(tmp_path / "journal.db")
    controller = AppController(tmp_path / "config.json", journal)
    yield controller
    controller.shutdown()
    journal.close()


@pytest.fixture
def syncs(controller, monkeypatch):
    calls = []
    monkeypatch.setattr(controller, "sync_now", lambda: calls.append(True))
    return calls


@pytest.fixture(autouse=True)
def wide_list_text(monkeypatch):
    """Textes de la liste comparés en entier : sans police réelle (offscreen), tout serait coupé. La coupe des
    textes trop longs a son propre test."""
    monkeypatch.setattr(shows_page_module, "LIST_TEXT_WIDTH", 10_000)


@pytest.fixture
def answers(monkeypatch):
    """Réponses données aux confirmations (Oui par défaut) ; les questions posées sont relevées."""
    state = {"answer": QMessageBox.StandardButton.Yes, "asked": []}

    def question(parent, title, text):
        state["asked"].append((title, text))
        return state["answer"]

    monkeypatch.setattr(shows_page_module.QMessageBox, "question", question)
    return state


def make_page(controller, *shows, catalog=CATALOG):
    if shows:
        assert controller.update_config(Config(shows=list(shows)))
    page = ShowsPage(controller)
    if catalog is not None:
        page._on_catalog(catalog)
    return page


def mars(folder=r"D:\Mars", rules=None, baseline=None):
    return ShowFolder(1, "Mars Attack", folder, folder if baseline is None else baseline, list(rules or []))


def silicon(folder=r"E:\Silicon", rules=None):
    return ShowFolder(2, "Silicon Talk", folder, folder, list(rules or []))


def items(widget):
    return [widget.item(i).text() for i in range(widget.count())]


def combo_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def choose(combo, data):
    index = combo.findData(data)
    assert index >= 0, (data, combo_items(combo))
    combo.setCurrentIndex(index)


def drag(widget, source, target):
    """Comme un glisser-déposer interne de Qt : la ligne source passe à la position target (la ligne courante
    suit l'élément déplacé), puis « reordered »."""
    destination = target if target < source else target + 1
    assert widget.model().moveRow(QModelIndex(), source, QModelIndex(), destination)
    assert widget.item(target).data(Qt.ItemDataRole.UserRole) == source
    widget.reordered.emit()


class Snapshot:
    """Réglages courants copiés : la page ne doit jamais les modifier en place."""

    def __init__(self, controller):
        self.config = controller.config
        self.copy = copy.deepcopy(controller.config)

    def untouched(self):
        return self.config == self.copy


def test_show_list_shows_name_folder_and_keyword_count(controller, french):
    page = make_page(
        controller,
        mars(rules=[KeywordRule("MARS ATTACK"), KeywordRule("BONUS")]),
        silicon(),
        ShowFolder(3, "", ""),
    )
    assert items(page.show_list) == [
        "Mars Attack\nMots-clés : 2 · D:\\Mars",
        "Silicon Talk\nMots-clés : 0 · E:\\Silicon",
        "Émission 3\nMots-clés : 0 · Aucun dossier choisi",
    ]


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_long_names_and_paths_are_cut_without_losing_the_keyword_count(controller, monkeypatch, lang):
    i18n.set_language(lang)
    long_path = r"C:\Users\frmje\Documents\Podcasts\Enregistrements\2026\Mars"
    page = make_page(controller, ShowFolder(1, "Mars Attack, l'émission des passionnés d'espace", long_path))
    monkeypatch.setattr(shows_page_module, "LIST_TEXT_WIDTH", 480)
    page._render_shows()
    name, details = page.show_list.item(0).text().split("\n")
    count = tr("shows_keyword_count", n=0)
    assert "…" in name and "Mars Attack" in name
    assert details.lstrip(RLM).startswith(count + " · ")
    path = details.lstrip(RLM)[len(count + " · "):].strip(FSI + PDI)
    assert path.startswith("C:\\") and "…" in path and path.endswith("\\Mars")
    assert details.count(FSI) == details.count(PDI) == (1 if lang == "ar" else 0)
    assert page.show_list.item(0).toolTip() == long_path


def test_first_show_is_selected_when_the_page_opens(controller):
    page = make_page(controller, mars(), silicon())
    assert page.show_list.currentRow() == 0
    assert page.show_combo.currentData() == 1
    assert page.folder.text() == r"D:\Mars"


def test_adding_a_show_saves_it_with_its_folder_still_to_inventory(controller, syncs, tmp_path, french):
    page = make_page(controller)
    page.add_show_button.click()
    assert page.show_list.currentRow() == -1
    assert page.show_combo.currentIndex() == -1  # aucune émission choisie d'office
    assert not page.keywords_box.isEnabled()  # mots-clés après l'enregistrement de l'émission
    page._save_show()
    assert page.show_error.text() == "Choisissez une émission."
    choose(page.show_combo, 2)
    page._save_show()
    assert page.show_error.text() == "Choisissez un dossier."
    assert controller.config.shows == [] and syncs == []
    page._set_folder(str(tmp_path / "silicon") + "/")
    page._save_show()
    expected = [ShowFolder(2, "Silicon Talk", str(tmp_path / "silicon"), "", [])]
    assert controller.config.shows == expected
    assert load_config(controller.config_path).shows == expected
    assert page.show_error.text() == ""
    assert page.show_list.currentRow() == 0
    assert page.keywords_box.isEnabled()
    assert syncs == [True]


def test_changing_the_folder_of_a_show_takes_a_new_baseline(controller, syncs):
    page = make_page(controller, mars(rules=[KeywordRule("MARS ATTACK")]))
    snapshot = Snapshot(controller)
    page._set_folder(r"E:\Nouveau")
    page._save_show()
    assert controller.config.shows == [ShowFolder(1, "Mars Attack", r"E:\Nouveau", "", [KeywordRule("MARS ATTACK")])]
    assert snapshot.untouched()
    assert syncs == [True]


def test_same_folder_written_differently_keeps_the_baseline(controller, syncs):
    page = make_page(controller, mars())
    page._set_folder("d:/mars/")
    page._save_show()
    assert controller.config.shows == [mars()]


def test_changing_the_show_keeps_the_keywords_but_not_the_playlists_of_the_old_show(controller, syncs):
    page = make_page(controller, mars(rules=[KeywordRule("MARS ATTACK", 7, "Saison 3", "cover.png", "Texte")]))
    choose(page.show_combo, 2)
    page._save_show()
    show = controller.config.shows[0]
    assert (show.show_id, show.show_name, show.folder, show.baseline_folder) == (2, "Silicon Talk", r"D:\Mars", r"D:\Mars")
    assert show.rules == [KeywordRule("MARS ATTACK", None, "", "cover.png", "Texte")]


def test_show_not_saved_is_reported(controller, syncs, monkeypatch, french):
    page = make_page(controller, mars())

    def full_disk(config, path):
        raise OSError(28, "Espace disque insuffisant")

    monkeypatch.setattr(controller_module, "save_config", full_disk)
    page._set_folder(r"E:\Nouveau")
    page._save_show()
    assert page.show_error.text() == "Émission non enregistrée."
    assert controller.config.shows == [mars()]
    assert syncs == []


def test_keywords_are_added_edited_reordered_and_deleted(controller, syncs, answers):
    page = make_page(controller, mars(), silicon())
    page.select_show(1)
    page.add_rule_button.click()
    page.keyword.setText("  DEBRIEF ")
    choose(page.playlist_combo, 9)
    snapshot = Snapshot(controller)
    page._save_rule()
    assert snapshot.untouched()
    assert controller.config.shows[1].rules == [KeywordRule("DEBRIEF", 9, "Débrief")]
    assert controller.config.shows[0].rules == []
    page.add_rule_button.click()
    page.keyword.setText("INTERVIEW")
    page._save_rule()
    assert [rule.keyword for rule in controller.config.shows[1].rules] == ["DEBRIEF", "INTERVIEW"]
    assert page.rule_list.currentRow() == 1
    assert items(page.rule_list) == ["DEBRIEF\nDébrief", "INTERVIEW\nNo playlist"]
    assert items(page.show_list)[1] == "Silicon Talk\nKeywords: 2 · E:\\Silicon"

    page.rule_list.setCurrentRow(0)
    assert page.keyword.text() == "DEBRIEF"
    assert page.playlist_combo.currentData() == 9
    page.description.setPlainText("Le débrief de la semaine")
    page._save_rule()
    assert controller.config.shows[1].rules[0] == KeywordRule("DEBRIEF", 9, "Débrief", "", "Le débrief de la semaine")

    drag(page.rule_list, 1, 0)
    assert [rule.keyword for rule in controller.config.shows[1].rules] == ["INTERVIEW", "DEBRIEF"]
    assert page.rule_list.currentRow() == 1 and page.keyword.text() == "DEBRIEF"  # toujours en cours d'édition

    page.rule_list.setCurrentRow(0)
    page._delete_rule()
    assert answers["asked"] == [("Delete keyword", "Delete the keyword “INTERVIEW”?")]
    assert [rule.keyword for rule in controller.config.shows[1].rules] == ["DEBRIEF"]
    assert page.rule_list.currentRow() == -1 and page.keyword.text() == ""
    assert syncs == [True] * 5


def test_keyword_is_required_and_its_image_must_be_valid(controller, syncs, tmp_path, french):
    page = make_page(controller, mars())
    page._save_rule()
    assert page.form_error.text() == "Indiquez un mot-clé."
    page.keyword.setText("MARS ATTACK")
    page._set_image(str(tmp_path / "absente.png"))
    page._save_rule()
    assert page.form_error.text() == "Corrigez l'image avant d'enregistrer."
    assert controller.config.shows[0].rules == [] and syncs == []


def test_playlists_are_those_of_the_selected_show(controller):
    page = make_page(controller, mars(), silicon(rules=[KeywordRule("DEBRIEF", 42, "Ancienne")]))
    assert combo_items(page.playlist_combo) == ["No playlist", "Bonus", "Saison 3"]
    page.select_show(1)
    assert combo_items(page.playlist_combo) == ["No playlist", "Débrief"]
    page.rule_list.setCurrentRow(0)  # playlist disparue d'Ausha : gardée et nommée
    assert combo_items(page.playlist_combo) == ["No playlist", "Débrief", "Ancienne"]
    assert page.playlist_combo.currentData() == 42


def test_reordering_shows_changes_their_priority(controller, syncs):
    third = ShowFolder(3, "Le Debrief", r"F:\Debrief", r"F:\Debrief")
    page = make_page(controller, mars(), silicon(), third)
    page.select_show(2)
    drag(page.show_list, 2, 0)
    assert [show.show_id for show in controller.config.shows] == [3, 1, 2]
    assert page.show_list.currentRow() == 0 and page.show_combo.currentData() == 3
    assert syncs == [True]


def test_deleting_a_show_asks_first(controller, syncs, answers, french):
    page = make_page(controller, mars(), silicon())
    answers["answer"] = QMessageBox.StandardButton.No
    page._delete_show()
    assert len(controller.config.shows) == 2
    answers["answer"] = QMessageBox.StandardButton.Yes
    page._delete_show()
    assert answers["asked"][0] == (
        "Supprimer l'émission",
        "Supprimer l'émission « Mars Attack » et ses mots-clés ? Rien n'est supprimé dans son dossier ni sur Ausha.",
    )
    assert controller.config.shows == [silicon()]
    assert page.show_list.currentRow() == 0 and page.show_combo.currentData() == 2
    page._delete_show()
    assert controller.config.shows == []
    assert page.show_list.currentRow() == -1 and not page.delete_show_button.isVisibleTo(page)
    assert syncs == [True, True]


def test_new_rule_opens_the_first_show_of_the_file_folder(controller):
    other = ShowFolder(3, "Le Debrief", r"D:\Podcasts", r"D:\Podcasts")
    page = make_page(controller, mars(), silicon(r"D:\Podcasts"), other)
    page.start_new_rule("d:/podcasts", "interview_brut")
    assert page.show_list.currentRow() == 1
    assert page.show_combo.currentData() == 2
    assert page.keyword.text() == "interview_brut"
    assert page.rule_list.currentRow() == -1  # nouveau mot-clé


def test_new_rule_without_a_show_for_the_folder_prefills_a_new_show(controller, syncs):
    page = make_page(controller, mars())
    page.start_new_rule(r"F:\Nouveau", "interview_brut")
    assert page.show_list.currentRow() == -1
    assert page.folder.text() == r"F:\Nouveau"
    assert page.keyword.text() == "interview_brut"
    choose(page.show_combo, 2)
    page._save_show()
    assert page.keyword.text() == "interview_brut"  # le mot-clé proposé attend toujours
    page._save_rule()
    assert controller.config.shows[1] == ShowFolder(2, "Silicon Talk", r"F:\Nouveau", "", [KeywordRule("interview_brut")])


def test_select_show(controller):
    page = make_page(controller, mars(rules=[KeywordRule("MARS ATTACK")]), silicon())
    page.select_show(1)
    assert page.show_list.currentRow() == 1
    assert (page.show_combo.currentData(), page.folder.text()) == (2, r"E:\Silicon")
    assert page.rule_list.count() == 0
    page.select_show(0)
    assert items(page.rule_list) == ["MARS ATTACK\nNo playlist"]


def test_show_stays_selected_while_the_catalog_is_unavailable(controller):
    page = make_page(controller, mars(), ShowFolder(5, "", r"G:\Autre"), catalog=None)
    assert page.show_combo.currentText() == "Mars Attack"
    page.select_show(1)
    assert page.show_combo.currentText() == "Show 5"
    page._on_catalog_failed(Exception("jeton refusé"))
    assert page.catalog_status.text() == "Can't load Ausha shows: jeton refusé"


def test_catalog_arriving_keeps_a_show_being_chosen(controller):
    page = make_page(controller, mars(), catalog={MARS: []})
    page.add_show_button.click()
    choose(page.show_combo, 1)
    page._on_catalog(CATALOG)
    assert page.show_combo.currentData() == 1
    assert combo_items(page.show_combo) == ["Mars Attack", "Silicon Talk"]


def test_saving_runs_a_sync_unless_paused(controller, syncs):
    page = make_page(controller, mars())
    controller.update_config(Config(paused=True, shows=[mars()]))
    page.keyword.setText("MARS ATTACK")
    page._save_rule()
    assert controller.config.shows[0].rules == [KeywordRule("MARS ATTACK")]
    assert syncs == []  # en pause : rien n'est lancé


def test_show_list_items_keep_their_position(controller):
    page = make_page(controller, mars(), silicon())
    assert [page.show_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(2)] == [0, 1]
