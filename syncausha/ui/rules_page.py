"""Page Règles : liste réordonnable + éditeur (mot-clé, émission, playlist, image, description)."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
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
    QVBoxLayout,
    QWidget,
)

from syncausha.config import Rule
from syncausha.rules import validate_image
from syncausha.ui.controller import AppController, Catalog
from syncausha.ui.style import palette
from syncausha.ui.widgets import make_label

NO_PLAYLIST = "Aucune playlist"
PREVIEW_SIZE = 110
THUMBNAIL_SIZE = 36


class ReorderableList(QListWidget):
    reordered = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        self.reordered.emit()


class RulesPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.catalog: Catalog = {}
        self._editing_index: int | None = None
        self._editing = Rule(keyword="", show_id=0)
        self._image_path = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        header = QHBoxLayout()
        header.addWidget(make_label("Règles", "pageTitle"))
        header.addStretch(1)
        add_button = QPushButton("Ajouter")
        add_button.clicked.connect(lambda _=False: self.start_new_rule(""))
        header.addWidget(add_button)
        layout.addLayout(header)
        layout.addWidget(make_label(
            "La première règle dont le mot-clé apparaît dans le nom du fichier s'applique. "
            "Glissez les règles pour changer l'ordre.", "muted", wrap=True))
        self.catalog_status = make_label(object_name="muted", wrap=True)
        layout.addWidget(self.catalog_status)

        self.list = ReorderableList()
        self.list.setObjectName("rules")
        self.list.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        self.list.currentRowChanged.connect(self._on_row_changed)
        self.list.reordered.connect(self._on_reordered)
        layout.addWidget(self.list, 1)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(16)
        form = QFormLayout()
        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("MARS ATTACK")
        form.addRow("Le nom du fichier contient", self.keyword)
        self.show_combo = QComboBox()
        self.show_combo.currentIndexChanged.connect(lambda _i: self._fill_playlists())
        form.addRow("Émission", self.show_combo)
        self.playlist_combo = QComboBox()
        form.addRow("Playlist", self.playlist_combo)
        self.description = QPlainTextEdit()
        self.description.setPlaceholderText("Nouvel épisode de Mars Attack. Retrouvez-nous sur…")
        self.description.setFixedHeight(90)
        form.addRow("Description", self.description)
        card_layout.addLayout(form, 1)

        image_column = QVBoxLayout()
        image_column.addWidget(make_label("Image", "muted"))
        self.image_preview = QLabel("Aucune image")
        self.image_preview.setObjectName("imagePreview")
        self.image_preview.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_column.addWidget(self.image_preview)
        choose_button = QPushButton("Choisir…")
        choose_button.clicked.connect(self._choose_image)
        remove_button = QPushButton("Retirer")
        remove_button.clicked.connect(lambda _=False: self._set_image(""))
        image_column.addWidget(choose_button)
        image_column.addWidget(remove_button)
        self.image_error = make_label(object_name="error", wrap=True)
        self.image_error.setFixedWidth(PREVIEW_SIZE + 40)
        image_column.addWidget(self.image_error)
        image_column.addStretch(1)
        card_layout.addLayout(image_column)
        layout.addWidget(card)

        actions = QHBoxLayout()
        self.form_error = make_label(object_name="error")
        actions.addWidget(self.form_error, 1)
        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self._delete)
        actions.addWidget(self.delete_button)
        save_button = QPushButton("Enregistrer")
        save_button.setObjectName("primary")
        save_button.clicked.connect(self._save)
        actions.addWidget(save_button)
        layout.addLayout(actions)

        self._render_list()
        self.start_new_rule("")

    # --- Catalogue Ausha -----------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reload_catalog()

    def reload_catalog(self) -> None:
        self.catalog_status.setText("Chargement des émissions Ausha…")
        self.controller.fetch_catalog(self._on_catalog, self._on_catalog_failed)

    def _on_catalog(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.catalog_status.clear()
        self._fill_shows()

    def _on_catalog_failed(self, error: Exception) -> None:
        self.catalog_status.setText(f"Impossible de charger les émissions Ausha : {error}")

    # --- Liste ---------------------------------------------------------------

    def _render_list(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for index, rule in enumerate(self.controller.config.rules):
            target = rule.show_name or f"Émission {rule.show_id}"
            if rule.playlist_name:
                target += f" → {rule.playlist_name}"
            item = QListWidgetItem(_thumbnail(rule.image_path), f"{rule.keyword}\n{target}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.list.addItem(item)
        self.list.blockSignals(False)

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self.controller.config.rules):
            self._load_into_editor(row, self.controller.config.rules[row])

    def _on_reordered(self) -> None:
        old = self.controller.config.rules
        order = [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())]
        self.controller.update_config(replace(self.controller.config, rules=[old[i] for i in order]))
        self._render_list()
        self.start_new_rule("")

    # --- Éditeur -------------------------------------------------------------

    def start_new_rule(self, keyword: str) -> None:
        self.list.blockSignals(True)
        self.list.setCurrentRow(-1)
        self.list.blockSignals(False)
        self._load_into_editor(None, Rule(keyword=keyword, show_id=0))

    def _load_into_editor(self, index: int | None, rule: Rule) -> None:
        self._editing_index, self._editing = index, rule
        self.keyword.setText(rule.keyword)
        self.description.setPlainText(rule.description_template)
        self._set_image(rule.image_path)
        self.delete_button.setVisible(index is not None)
        self.form_error.clear()
        self._fill_shows()

    def _fill_shows(self) -> None:
        rule = self._editing
        items = [(show.name, show.id) for show in sorted(self.catalog, key=lambda s: s.name.casefold())]
        if rule.show_id and rule.show_id not in {show.id for show in self.catalog}:
            items.insert(0, (rule.show_name or f"Émission {rule.show_id}", rule.show_id))
        _set_combo_items(self.show_combo, items, rule.show_id or None)
        self._fill_playlists()

    def _fill_playlists(self) -> None:
        show_id = self.show_combo.currentData()
        playlists = next((pls for show, pls in self.catalog.items() if show.id == show_id), [])
        items: list[tuple[str, int | None]] = [(NO_PLAYLIST, None)]
        items += [(p.name, p.id) for p in sorted(playlists, key=lambda p: p.name.casefold())]
        rule = self._editing
        selected = rule.playlist_id if rule.show_id == show_id else None
        if selected is not None and selected not in {p.id for p in playlists}:
            items.append((rule.playlist_name or f"Playlist {selected}", selected))
        _set_combo_items(self.playlist_combo, items, selected)

    def _set_image(self, path: str) -> None:
        self._image_path = path
        pixmap = QPixmap(path) if path else QPixmap()
        if pixmap.isNull():
            self.image_preview.setPixmap(QPixmap())
            self.image_preview.setText("Aucune image")
        else:
            self.image_preview.setPixmap(pixmap.scaled(
                PREVIEW_SIZE, PREVIEW_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.image_error.setText((validate_image(path) or "") if path else "")

    def _choose_image(self) -> None:
        start = str(Path(self._image_path).parent) if self._image_path else ""
        path, _filter = QFileDialog.getOpenFileName(self, "Choisir l'image", start, "Images (*.png *.jpg *.jpeg)")
        if path:
            self._set_image(path)

    def _save(self) -> None:
        keyword = self.keyword.text().strip()
        show_id = self.show_combo.currentData()
        if not keyword:
            self.form_error.setText("Indiquez un mot-clé.")
            return
        if not show_id:
            self.form_error.setText("Choisissez une émission.")
            return
        if self._image_path and validate_image(self._image_path):
            self.form_error.setText("Corrigez l'image avant d'enregistrer.")
            return
        playlist_id = self.playlist_combo.currentData()
        rule = Rule(
            keyword=keyword,
            show_id=int(show_id),
            show_name=self.show_combo.currentText(),
            playlist_id=playlist_id,
            playlist_name=self.playlist_combo.currentText() if playlist_id is not None else "",
            image_path=self._image_path,
            description_template=self.description.toPlainText().strip(),
        )
        rules = list(self.controller.config.rules)
        if self._editing_index is None:
            rules.append(rule)
            index = len(rules) - 1
        else:
            rules[self._editing_index] = rule
            index = self._editing_index
        self.controller.update_config(replace(self.controller.config, rules=rules))
        self._render_list()
        self.list.setCurrentRow(index)

    def _delete(self) -> None:
        if self._editing_index is None:
            return
        answer = QMessageBox.question(self, "Supprimer la règle", f"Supprimer la règle « {self._editing.keyword} » ?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        rules = list(self.controller.config.rules)
        del rules[self._editing_index]
        self.controller.update_config(replace(self.controller.config, rules=rules))
        self._render_list()
        self.start_new_rule("")


def _thumbnail(path: str) -> QIcon:
    """Carré arrondi : l'image recadrée, ou une case neutre qui garde les textes alignés."""
    size = THUMBNAIL_SIZE * 2  # nette sur les écrans haute densité
    image = QPixmap(path) if path else QPixmap()
    if image.isNull():
        brush = QBrush(QColor(palette()["hover"]))
    else:
        image = image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        brush = QBrush(image.copy((image.width() - size) // 2, (image.height() - size) // 2, size, size))
    thumbnail = QPixmap(size, size)
    thumbnail.fill(Qt.GlobalColor.transparent)
    painter = QPainter(thumbnail)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(brush)
    painter.drawRoundedRect(thumbnail.rect(), 12, 12)
    painter.end()
    return QIcon(thumbnail)


def _set_combo_items(combo: QComboBox, items: list[tuple[str, object]], selected: object) -> None:
    combo.blockSignals(True)
    combo.clear()
    for text, data in items:
        combo.addItem(text, data)
    index = combo.findData(selected) if selected is not None else 0
    combo.setCurrentIndex(max(index, 0))
    combo.blockSignals(False)
