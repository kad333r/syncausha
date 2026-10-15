"""Page Émissions : en haut, la liste réordonnable des émissions (chacune avec son dossier) et la carte de
l'émission choisie (émission Ausha, dossier) ; en bas, ses mots-clés réordonnables et leur éditeur (playlist,
image, description). Les listes à gauche, les cartes à droite, tout visible sans défiler."""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from syncausha.config import KeywordRule, ShowFolder, same_folder
from syncausha.i18n import render, tr
from syncausha.rules import validate_image
from syncausha.ui.controller import AppController, Catalog
from syncausha.ui.style import palette
from syncausha.ui.widgets import isolate, joined, leading_alignment, make_label, section_label

PREVIEW_SIZE = 110
THUMBNAIL_SIZE = 36
DESCRIPTION_HEIGHT = 80
LIST_WIDTH = 220  # listes des émissions et des mots-clés, alignées l'une sur l'autre
# Largeur d'une ligne de texte de la liste : sans bordure, retraits (liste, ligne) ni barre de défilement.
LIST_TEXT_WIDTH = LIST_WIDTH - 40
COLUMN_SPACING = 16


class ReorderableList(QListWidget):
    reordered = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("items")
        self.setFixedWidth(LIST_WIDTH)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        # Texte trop long : coupé (voir ShowsPage._render_shows), jamais de barre de défilement horizontale.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        self.reordered.emit()


class ShowsPage(QWidget):
    """Chaque modification est enregistrée par controller.update_config avec de nouvelles listes (jamais les
    réglages courants modifiés en place), puis une synchronisation est lancée."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.catalog: Catalog = {}
        self._show_index: int | None = None  # émission affichée (position dans les réglages) ; None : nouvelle
        self._show = ShowFolder(show_id=0)  # telle qu'enregistrée
        self._folder = ""  # dossier choisi, enregistré avec l'émission
        self._rule_index: int | None = None  # mot-clé affiché (position dans l'émission) ; None : nouveau
        self._rule = KeywordRule(keyword="")
        self._image_path = ""

        # Tout tient dans la fenêtre à sa taille par défaut ; plus petite, la page défile au lieu de se tasser.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        header = QHBoxLayout()
        header.addWidget(make_label(tr("shows_title"), "pageTitle"))
        header.addStretch(1)
        self.add_show_button = QPushButton(tr("shows_add"))
        self.add_show_button.clicked.connect(lambda _=False: self.start_new_show())
        header.addWidget(self.add_show_button)
        layout.addLayout(header)
        layout.addWidget(make_label(tr("shows_help"), "muted", wrap=True))
        self.catalog_status = make_label(object_name="muted", wrap=True)
        self.catalog_status.hide()  # affiché seulement pendant le chargement ou après un échec
        layout.addWidget(self.catalog_status)

        shows_row = QHBoxLayout()
        shows_row.setSpacing(COLUMN_SPACING)
        self.show_list = ReorderableList()
        # Aussi haute que la carte de l'émission, à côté.
        self.show_list.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Ignored)
        self.show_list.currentRowChanged.connect(self._on_show_row_changed)
        self.show_list.reordered.connect(self._on_shows_reordered)
        shows_row.addWidget(self.show_list)
        shows_row.addWidget(self._build_show_card(), 1)
        layout.addLayout(shows_row)
        self.keywords_box = self._build_keywords()
        layout.addWidget(self.keywords_box, 1)

        self._render_shows()
        if self.controller.config.shows:
            self._load_show(0)
        else:
            self.start_new_show()

    def _build_show_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        self.show_combo = QComboBox()
        self.show_combo.setPlaceholderText(tr("shows_show_placeholder"))
        self.show_combo.setItemDelegate(QStyledItemDelegate(self.show_combo))  # stylée par la feuille de style
        form.addRow(tr("shows_field_show"), self.show_combo)
        self.folder = QLineEdit()
        self.folder.setAlignment(leading_alignment() | Qt.AlignmentFlag.AlignVCenter)  # chemin latin à droite en arabe
        self.folder.setReadOnly(True)
        self.folder.setPlaceholderText(tr("shows_no_folder"))
        folder_button = QPushButton(tr("common_choose"))
        folder_button.clicked.connect(self._choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(folder_button)
        form.addRow(tr("shows_field_folder"), folder_row)
        actions = QHBoxLayout()
        self.show_error = make_label(object_name="error", wrap=True)
        actions.addWidget(self.show_error, 1)
        self.delete_show_button = QPushButton(tr("shows_delete"))
        self.delete_show_button.setObjectName("danger")
        self.delete_show_button.clicked.connect(self._delete_show)
        actions.addWidget(self.delete_show_button)
        save_button = QPushButton(tr("common_save"))
        save_button.setObjectName("primary")
        save_button.clicked.connect(self._save_show)
        actions.addWidget(save_button)
        form.addRow(actions)
        return card

    def _build_keywords(self) -> QWidget:
        """Mots-clés de l'émission : titre, liste (sous celle des émissions) et éditeur (sous la carte)."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        header.addWidget(section_label(tr("shows_keywords")))
        self.keywords_hint = make_label(tr("shows_save_show_first"), "section")
        header.addWidget(self.keywords_hint)
        header.addStretch(1)
        self.add_rule_button = QPushButton(tr("shows_add_keyword"))
        self.add_rule_button.clicked.connect(lambda _=False: self.start_new_keyword())
        header.addWidget(self.add_rule_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(header)
        row = QHBoxLayout()
        row.setSpacing(COLUMN_SPACING)
        self.rule_list = ReorderableList()
        self.rule_list.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        self.rule_list.currentRowChanged.connect(self._on_rule_row_changed)
        self.rule_list.reordered.connect(self._on_rules_reordered)
        row.addWidget(self.rule_list)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(16)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)  # libellés au-dessus : la carte tient à côté
        self.keyword = QLineEdit()
        self.keyword.setAlignment(leading_alignment() | Qt.AlignmentFlag.AlignVCenter)
        self.keyword.setPlaceholderText(tr("rules_keyword_placeholder"))
        form.addRow(tr("rules_field_keyword"), self.keyword)
        self.playlist_combo = QComboBox()
        self.playlist_combo.setItemDelegate(QStyledItemDelegate(self.playlist_combo))
        form.addRow(tr("rules_field_playlist"), self.playlist_combo)
        self.description = QPlainTextEdit()
        self.description.setPlaceholderText(tr("rules_description_placeholder"))
        self.description.setFixedHeight(DESCRIPTION_HEIGHT)
        form.addRow(tr("rules_field_description"), self.description)
        card_layout.addLayout(form, 1)

        image_column = QVBoxLayout()
        image_column.addWidget(make_label(tr("rules_image"), "muted"))
        self.image_preview = QLabel(tr("rules_no_image"))
        self.image_preview.setObjectName("imagePreview")
        self.image_preview.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_column.addWidget(self.image_preview)
        choose_button = QPushButton(tr("common_choose"))
        choose_button.clicked.connect(self._choose_image)
        remove_button = QPushButton(tr("rules_remove_image"))
        remove_button.clicked.connect(lambda _=False: self._set_image(""))
        image_column.addWidget(choose_button)
        image_column.addWidget(remove_button)
        self.image_error = make_label(object_name="error", wrap=True)
        self.image_error.setFixedWidth(PREVIEW_SIZE + 40)
        image_column.addWidget(self.image_error)
        image_column.addStretch(1)
        card_layout.addLayout(image_column)
        row.addWidget(card, 1)
        layout.addLayout(row, 1)

        actions = QHBoxLayout()
        self.form_error = make_label(object_name="error")
        actions.addWidget(self.form_error, 1)
        self.delete_button = QPushButton(tr("common_delete"))
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self._delete_rule)
        actions.addWidget(self.delete_button)
        save_button = QPushButton(tr("common_save"))
        save_button.setObjectName("primary")
        save_button.clicked.connect(self._save_rule)
        actions.addWidget(save_button)
        layout.addLayout(actions)
        return box

    # --- Catalogue Ausha -----------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reload_catalog()

    def reload_catalog(self) -> None:
        self._set_catalog_status(tr("rules_loading_shows"))
        self.controller.fetch_catalog(self._on_catalog, self._on_catalog_failed)

    def _on_catalog(self, catalog: Catalog) -> None:
        """Listes remplies à nouveau ; une émission ou une playlist en cours de choix le reste."""
        self.catalog = catalog
        self._set_catalog_status("")
        self._fill_shows(self.show_combo.currentData())
        self._fill_playlists(self.playlist_combo.currentData() if self.playlist_combo.count() else self._rule.playlist_id)

    def _on_catalog_failed(self, error: Exception) -> None:
        self._set_catalog_status(tr("rules_shows_failed", detail=render(str(error))))

    def _set_catalog_status(self, text: str) -> None:
        self.catalog_status.setText(text)
        self.catalog_status.setVisible(bool(text))

    def _catalog_name(self, show_id: int) -> str | None:
        return next((show.name for show in self.catalog if show.id == show_id), None)

    # --- Émissions -------------------------------------------------------------

    def select_show(self, index: int) -> None:
        """Affiche l'émission à cette position des réglages (« Modifier l'émission » de l'Activité)."""
        if 0 <= index < len(self.controller.config.shows):
            self._load_show(index)

    def start_new_show(self, folder: str = "", keyword: str = "") -> None:
        """Nouvelle émission, pas encore enregistrée ; folder et keyword pré-remplis (« Créer une règle »)."""
        self._show_index, self._show = None, ShowFolder(show_id=0)
        _set_current_row(self.show_list, -1)
        self._set_folder(folder)
        self.show_error.clear()
        self.delete_show_button.setVisible(False)
        self._fill_shows(None)
        self._enable_keywords(False)
        self._render_rules()
        self.start_new_keyword(keyword)

    def start_new_rule(self, folder: str, keyword: str) -> None:
        """« Créer une règle » sur un fichier sans règle : la première émission de son dossier avec ce mot-clé
        proposé, ou une nouvelle émission pour ce dossier."""
        shows = self.controller.config.shows
        index = next((i for i, show in enumerate(shows) if same_folder(show.folder, folder)), None)
        if index is None:
            self.start_new_show(folder, keyword)
        else:
            self._load_show(index)
            self.start_new_keyword(keyword)

    def _load_show(self, index: int) -> None:
        show = self.controller.config.shows[index]
        self._show_index, self._show = index, show
        _set_current_row(self.show_list, index)
        self._set_folder(show.folder)
        self.show_error.clear()
        self.delete_show_button.setVisible(True)
        self._fill_shows(show.show_id)
        self._enable_keywords(True)
        self._rule_index = None
        self._render_rules()
        self.start_new_keyword()

    def _enable_keywords(self, enabled: bool) -> None:
        """Les mots-clés d'une nouvelle émission s'ajoutent une fois l'émission enregistrée."""
        self.keywords_box.setEnabled(enabled)
        self.keywords_hint.setVisible(not enabled)

    def _render_shows(self) -> None:
        """Deux lignes par émission : son nom, puis « mots-clés · dossier ».

        Le nom et le chemin trop longs sont coupés ici, avant d'être isolés : Qt couperait sinon la ligne
        entière en son milieu logique, et en arabe le nombre de mots-clés ou une marque d'isolat sauterait."""
        self.show_list.ensurePolished()  # police de la feuille de style
        metrics = self.show_list.fontMetrics()
        self.show_list.blockSignals(True)
        self.show_list.clear()
        for index, show in enumerate(self.controller.config.shows):
            name = metrics.elidedText(_show_name(show), Qt.TextElideMode.ElideRight, LIST_TEXT_WIDTH)
            count = tr("shows_keyword_count", n=len(show.rules))
            folder = tr("shows_no_folder")
            if show.folder:
                room = LIST_TEXT_WIDTH - metrics.horizontalAdvance(f"{count} · ")
                folder = isolate(metrics.elidedText(show.folder, Qt.TextElideMode.ElideMiddle, room))
            item = QListWidgetItem(f"{isolate(name)}\n{joined([count, folder])}")
            item.setToolTip(show.folder)  # chemin complet
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.show_list.addItem(item)
        self.show_list.setCurrentRow(-1 if self._show_index is None else self._show_index)
        self.show_list.blockSignals(False)

    def _on_show_row_changed(self, row: int) -> None:
        item = self.show_list.item(row)
        if item is not None:  # position d'avant un éventuel glisser-déposer : celle des réglages
            self._load_show(item.data(Qt.ItemDataRole.UserRole))

    def _on_shows_reordered(self) -> None:
        config = self.controller.config
        order = [self.show_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.show_list.count())]
        if self.controller.update_config(replace(config, shows=[config.shows[i] for i in order])):
            if self._show_index is not None:
                self._show_index = order.index(self._show_index)
            self._sync_now()
        self._render_shows()

    def _fill_shows(self, selected: int | None) -> None:
        """Émissions Ausha ; l'émission enregistrée reste proposée si Ausha ne la renvoie pas (catalogue
        indisponible, accès retiré). Aucune n'est choisie d'office pour une nouvelle émission."""
        items = [(show.name, show.id) for show in sorted(self.catalog, key=lambda s: s.name.casefold())]
        show = self._show
        if show.show_id and self._catalog_name(show.show_id) is None:
            items.insert(0, (_show_name(show), show.show_id))
        _set_combo_items(self.show_combo, items, selected, fallback=-1)

    def _set_folder(self, path: str) -> None:
        self._folder = os.path.normpath(path) if path else ""
        self.folder.setText(self._folder)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("dialog_choose_show_folder"), self._folder)
        if folder:
            self._set_folder(folder)

    def _save_show(self) -> None:
        show_id = self.show_combo.currentData()
        if not show_id:
            self.show_error.setText(tr("rules_err_show"))
            return
        if not self._folder:
            self.show_error.setText(tr("shows_err_folder"))
            return
        show_id = int(show_id)
        config = self.controller.config
        shows = list(config.shows)
        old = None if self._show_index is None else shows[self._show_index]
        name = self._catalog_name(show_id)
        if old is None:
            show = ShowFolder(show_id=show_id, show_name=name or "", folder=self._folder)
            shows.append(show)
            index = len(shows) - 1
        else:
            if name is None:
                name = old.show_name if old.show_id == show_id else ""
            unchanged = same_folder(self._folder, old.folder)  # même dossier écrit autrement : rien à refaire
            rules = list(old.rules)
            if show_id != old.show_id:  # les playlists de l'ancienne émission n'existent pas dans la nouvelle
                rules = [replace(rule, playlist_id=None, playlist_name="") for rule in rules]
            show = replace(
                old,
                show_id=show_id,
                show_name=name,
                folder=old.folder if unchanged else self._folder,
                # Nouveau dossier : ses fichiers déjà présents seront ignorés (état des lieux à refaire).
                baseline_folder=old.baseline_folder if unchanged else "",
                rules=rules,
            )
            index = self._show_index
            shows[index] = show
        if not self.controller.update_config(replace(config, shows=shows)):
            self.show_error.setText(tr("shows_not_saved"))
            return
        if old is None or old.show_id != show_id:
            pending = self.keyword.text() if old is None else ""  # mot-clé proposé par « Créer une règle »
            self._show_index = index
            self._render_shows()
            self._load_show(index)
            if pending:
                self.start_new_keyword(pending)
        else:  # même émission Ausha : le mot-clé en cours d'édition est gardé
            self._show = show
            self._render_shows()
            self._set_folder(show.folder)
            self.show_error.clear()
        self._sync_now()

    def _delete_show(self) -> None:
        if self._show_index is None:
            return
        config = self.controller.config
        name = _show_name(config.shows[self._show_index])
        answer = QMessageBox.question(self, tr("dialog_delete_show"), tr("dialog_delete_show_question", show=name))
        if answer != QMessageBox.StandardButton.Yes:
            return
        shows = list(config.shows)
        del shows[self._show_index]
        if not self.controller.update_config(replace(config, shows=shows)):
            self.show_error.setText(tr("shows_not_saved"))
            return
        index = min(self._show_index, len(shows) - 1)
        self._show_index = None
        self._render_shows()
        if shows:
            self._load_show(index)
        else:
            self.start_new_show()
        self._sync_now()

    # --- Mots-clés de l'émission -----------------------------------------------

    def start_new_keyword(self, keyword: str = "") -> None:
        _set_current_row(self.rule_list, -1)
        self._load_rule(None, KeywordRule(keyword=keyword))

    def _render_rules(self) -> None:
        self.rule_list.blockSignals(True)
        self.rule_list.clear()
        rules = self._show.rules if self._show_index is not None else []
        for index, rule in enumerate(rules):
            # Une ligne par valeur brute, isolée : en arabe, un nom qui commence par des chiffres garde son ordre.
            item = QListWidgetItem(_thumbnail(rule.image_path), f"{isolate(rule.keyword)}\n{_playlist_label(rule)}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.rule_list.addItem(item)
        self.rule_list.setCurrentRow(-1 if self._rule_index is None else self._rule_index)
        self.rule_list.blockSignals(False)

    def _on_rule_row_changed(self, row: int) -> None:
        item = self.rule_list.item(row)
        if item is not None and self._show_index is not None:
            index = item.data(Qt.ItemDataRole.UserRole)
            self._load_rule(index, self._show.rules[index])

    def _on_rules_reordered(self) -> None:
        if self._show_index is None:
            return
        show = self.controller.config.shows[self._show_index]
        order = [self.rule_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.rule_list.count())]
        if self._replace_show(replace(show, rules=[show.rules[i] for i in order])):
            if self._rule_index is not None:
                self._rule_index = order.index(self._rule_index)
            self._sync_now()
        self._render_rules()

    def _load_rule(self, index: int | None, rule: KeywordRule) -> None:
        self._rule_index, self._rule = index, rule
        self.keyword.setText(rule.keyword)
        self.description.setPlainText(rule.description_template)
        self._set_image(rule.image_path)
        self.delete_button.setVisible(index is not None)
        self.form_error.clear()
        self._fill_playlists(rule.playlist_id)

    def _show_playlists(self) -> list:
        """Playlists de l'émission affichée (enregistrée), d'après le catalogue."""
        show_id = self._show.show_id if self._show_index is not None else None
        return next((playlists for show, playlists in self.catalog.items() if show.id == show_id), [])

    def _fill_playlists(self, selected: int | None) -> None:
        playlists = self._show_playlists()
        items: list[tuple[str, int | None]] = [(tr("rules_no_playlist"), None)]
        items += [(p.name, p.id) for p in sorted(playlists, key=lambda p: p.name.casefold())]
        if selected is not None and selected not in {p.id for p in playlists}:  # disparue d'Ausha : gardée
            items.append((self._known_playlist_name(selected) or tr("rules_playlist_fallback", id=selected), selected))
        _set_combo_items(self.playlist_combo, items, selected)

    def _known_playlist_name(self, playlist_id: int) -> str:
        """Nom d'une playlist : celui d'Ausha, sinon celui enregistré avec le mot-clé."""
        name = next((p.name for p in self._show_playlists() if p.id == playlist_id), "")
        return name or (self._rule.playlist_name if playlist_id == self._rule.playlist_id else "")

    def _set_image(self, path: str) -> None:
        self._image_path = path
        pixmap = QPixmap(path) if path else QPixmap()
        if pixmap.isNull():
            self.image_preview.setPixmap(QPixmap())
            self.image_preview.setText(tr("rules_no_image"))
        else:
            self.image_preview.setPixmap(pixmap.scaled(
                PREVIEW_SIZE, PREVIEW_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.image_error.setText(render(validate_image(path) or "") if path else "")

    def _choose_image(self) -> None:
        start = str(Path(self._image_path).parent) if self._image_path else ""
        path, _filter = QFileDialog.getOpenFileName(self, tr("dialog_choose_image"), start, tr("rules_image_filter"))
        if path:
            self._set_image(path)

    def _save_rule(self) -> None:
        if self._show_index is None:
            return
        keyword = self.keyword.text().strip()
        if not keyword:
            self.form_error.setText(tr("rules_err_keyword"))
            return
        if self._image_path and validate_image(self._image_path):
            self.form_error.setText(tr("rules_err_image"))
            return
        playlist_id = self.playlist_combo.currentData()
        rule = KeywordRule(
            keyword=keyword,
            playlist_id=playlist_id,
            playlist_name=self._known_playlist_name(playlist_id) if playlist_id is not None else "",
            image_path=self._image_path,
            description_template=self.description.toPlainText().strip(),
        )
        show = self.controller.config.shows[self._show_index]
        rules = list(show.rules)
        if self._rule_index is None:
            rules.append(rule)
            index = len(rules) - 1
        else:
            rules[self._rule_index] = rule
            index = self._rule_index
        if not self._replace_show(replace(show, rules=rules)):
            self.form_error.setText(tr("rules_not_saved"))
            return
        self._render_rules_and_select(index)
        self._sync_now()

    def _render_rules_and_select(self, index: int) -> None:
        self._rule_index = index
        self._render_rules()
        self._load_rule(index, self._show.rules[index])

    def _delete_rule(self) -> None:
        if self._show_index is None or self._rule_index is None:
            return
        answer = QMessageBox.question(
            self, tr("dialog_delete_keyword"), tr("dialog_delete_keyword_question", keyword=self._rule.keyword))
        if answer != QMessageBox.StandardButton.Yes:
            return
        show = self.controller.config.shows[self._show_index]
        rules = list(show.rules)
        del rules[self._rule_index]
        if not self._replace_show(replace(show, rules=rules)):
            self.form_error.setText(tr("rules_not_saved"))
            return
        self._rule_index = None
        self._render_rules()
        self.start_new_keyword()
        self._sync_now()

    def _replace_show(self, show: ShowFolder) -> bool:
        """Enregistre l'émission affichée modifiée (nouvelles listes, rien de muté en place)."""
        config = self.controller.config
        shows = list(config.shows)
        shows[self._show_index] = show
        if not self.controller.update_config(replace(config, shows=shows)):
            return False
        self._show = show
        self._render_shows()  # nombre de mots-clés
        return True

    def _sync_now(self) -> None:
        """Applique tout de suite les émissions modifiées (un fichier « sans règle » part sans attendre)."""
        if not self.controller.config.paused:
            self.controller.sync_now()


def _show_name(show: ShowFolder) -> str:
    return show.show_name or tr("rules_show_fallback", id=show.show_id)


def _playlist_label(rule: KeywordRule) -> str:
    if rule.playlist_name:
        return isolate(rule.playlist_name)
    if rule.playlist_id is not None:
        return tr("rules_playlist_fallback", id=rule.playlist_id)
    return tr("rules_no_playlist")


def _set_current_row(widget: QListWidget, row: int) -> None:
    widget.blockSignals(True)
    widget.setCurrentRow(row)
    widget.blockSignals(False)


def _thumbnail(path: str) -> QIcon:
    """Carré arrondi : l'image recadrée, ou une case neutre qui garde les textes alignés."""
    size = THUMBNAIL_SIZE * 2  # nette sur les écrans haute densité
    image = QPixmap(path) if path else QPixmap()
    colors = palette()
    if image.isNull():
        brush, pen = QBrush(QColor(colors["hover"])), QPen(QColor(colors["border"]), 2)
    else:
        image = image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        brush = QBrush(image.copy((image.width() - size) // 2, (image.height() - size) // 2, size, size))
        pen = QPen(Qt.PenStyle.NoPen)
    thumbnail = QPixmap(size, size)
    thumbnail.fill(Qt.GlobalColor.transparent)
    painter = QPainter(thumbnail)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(pen)
    painter.setBrush(brush)
    painter.drawRoundedRect(thumbnail.rect().adjusted(1, 1, -1, -1), 12, 12)
    painter.end()
    icon = QIcon()
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Selected):  # sans la teinte bleue de la ligne sélectionnée
        icon.addPixmap(thumbnail, mode)
    return icon


def _set_combo_items(combo: QComboBox, items: list[tuple[str, object]], selected: object, fallback: int = 0) -> None:
    """Remplit la liste et choisit selected ; sinon la ligne fallback (-1 : aucune, le texte d'invite s'affiche)."""
    combo.blockSignals(True)
    combo.clear()
    for text, data in items:
        combo.addItem(text, data)
    index = combo.findData(selected) if selected is not None else -1
    combo.setCurrentIndex(index if index >= 0 else fallback)
    combo.blockSignals(False)
