"""
Fnote Viewer.
Window to browse, search and filter all notes.
Opens with Ctrl+Alt+V.
"""

from datetime import datetime, date
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QScrollArea, QLabel, QFrame, QApplication, QComboBox,
    QSplitter, QMenu, QMessageBox, QCalendarWidget, QDialog, QTextEdit,
    QStyledItemDelegate, QStyle
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDate, QPoint, QEvent
from PyQt6.QtGui import QKeySequence, QShortcut, QPixmap, QColor, QPainter


TAG_COLOR_ROLE = Qt.ItemDataRole.UserRole + 1


class TagDelegate(QStyledItemDelegate):
    """Delegate to show colored tags in the QComboBox."""
    
    def paint(self, painter, option, index):
        painter.save()
        
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#444"))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor("#3A3A4A"))
        else:
            painter.fillRect(option.rect, QColor("#2D2D2D"))
        
        text = index.data(Qt.ItemDataRole.DisplayRole)
        color = index.data(TAG_COLOR_ROLE)
        
        if color and isinstance(color, QColor):
            painter.setPen(color)
        else:
            painter.setPen(QColor("#EEE"))
        
        r = option.rect.adjusted(8, 0, -8, 0)
        painter.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        painter.restore()


class CalendarButton(QPushButton):
    """Button that shows a date and opens a calendar dialog."""
    
    dateChanged = pyqtSignal(QDate)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._date = QDate(2000, 1, 1)
        self.updateText()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D; color: #EEE;
                border: 1px solid #3D3D3D; border-radius: 6px;
                padding: 8px; font-size: 12px; min-width: 110px;
                text-align: left;
            }
            QPushButton:hover { border-color: #555; }
        """)
        self.clicked.connect(self._show_calendar)
    
    def updateText(self):
        if self._date.year() <= 2000:
            self.setText("All dates")
        else:
            self.setText(self._date.toString("dd/MM/yyyy"))
    
    def _show_calendar(self):
        dialog = QDialog(self.window())
        dialog.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        dialog.setStyleSheet("background-color: #2D2D2D;")
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        
        cal = QCalendarWidget()
        cal.setSelectedDate(self._date if self._date.year() > 2000 else QDate.currentDate())
        cal.setStyleSheet("""
            QCalendarWidget {
                background-color: #2D2D2D; color: #EEE; font-size: 13px;
                min-width: 280px; min-height: 240px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #3D3D3D; padding: 6px;
            }
            QCalendarWidget QToolButton {
                color: #EEE; background-color: transparent; border: none;
                border-radius: 4px; padding: 6px 10px; font-size: 13px; margin: 2px;
            }
            QCalendarWidget QToolButton:hover { background-color: #555; }
            QCalendarWidget QToolButton::menu-indicator { image: none; }
            QCalendarWidget QMenu { background-color: #2D2D2D; color: #EEE; }
            QCalendarWidget QSpinBox {
                background-color: #3D3D3D; color: #EEE; border: 1px solid #555;
                border-radius: 4px; padding: 4px 8px; font-size: 13px;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #EEE; background-color: #252530;
                selection-background-color: #555; selection-color: #FFF; padding: 4px;
            }
        """)
        cal.clicked.connect(lambda d: self._date_selected(d, dialog))
        layout.addWidget(cal)
        
        all_btn = QPushButton("Show all dates")
        all_btn.setStyleSheet("""
            QPushButton {
                background-color: #3D3D3D; color: #CCC;
                border: none; padding: 8px; font-size: 12px;
            }
            QPushButton:hover { background-color: #555; color: #FFF; }
        """)
        all_btn.clicked.connect(lambda: self._date_selected(QDate(2000, 1, 1), dialog))
        layout.addWidget(all_btn)
        
        pos = self.mapToGlobal(QPoint(0, self.height()))
        dialog.move(pos)
        dialog.exec()
    
    def _date_selected(self, date, dialog):
        self._date = date
        self.updateText()
        dialog.accept()
        self.dateChanged.emit(date)
    
    def date(self):
        return self._date
    
    def setDate(self, date):
        self._date = date
        self.updateText()


class NoteDetailWidget(QFrame):
    """Panel showing a single note in detail."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)
        
        self._show_placeholder()
        self._current_note = None
        self._viewer = None
    
    def _show_placeholder(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.setStyleSheet("""
            NoteDetailWidget {
                background-color: transparent;
                border: none;
            }
        """)
        
        placeholder = QLabel("Select a note to view details")
        placeholder.setStyleSheet("color: #666; font-size: 14px;")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(placeholder)
    
    def _make_text_editable(self, label, note):
        """Transforms a QLabel into an editable QTextEdit."""
        text = label.text()
        label.hide()
        
        edit = QTextEdit()
        edit.setPlainText(text)
        edit.setStyleSheet("""
            QTextEdit {
                background-color: #3D3D3D; color: #EEE;
                border: 1px solid #555; border-radius: 4px;
                padding: 8px; font-size: 14px;
            }
        """)
        edit.setMaximumHeight(200)
        
        idx = self._layout.indexOf(label)
        if idx < 0:
            idx = self._layout.count() - 1
        self._layout.insertWidget(idx, edit)
        
        edit._label = label
        edit._note = note
        edit._detail_widget = self
        
        def on_key(e):
            if e.key() == Qt.Key.Key_Return and not e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._finish_edit(edit)
            elif e.key() == Qt.Key.Key_Escape:
                self._cancel_edit(edit)
            else:
                QTextEdit.keyPressEvent(edit, e)
        
        edit.keyPressEvent = on_key
        edit.setFocus()
        edit.selectAll()
    
    def _finish_edit(self, edit):
        """Saves changes."""
        new_text = edit.toPlainText().strip()
        label = edit._label
        note = edit._note
        
        if new_text and self._viewer:
            import re
            manual_tags = re.findall(r'/(\w+)', new_text)
            aliases = self._viewer.backend.config.get_tag_aliases()
            resolved = [aliases.get(t, t) for t in manual_tags]
            clean = re.sub(r'/\w+\s*', '', new_text).strip()
            
            existing = self._viewer.backend.get_screenshots_for_note(note.id)
            saved = []
            for s in existing:
                p = Path(s.filepath)
                if p.exists():
                    saved.append(p.read_bytes())
            
            self._viewer.backend.delete_note(note.id)
            new_note = self._viewer.backend.add_note(clean, resolved if resolved else None)
            for img in saved:
                self._viewer.backend.add_screenshot(new_note.id, img, "png")
            
            # Ricarica la nota completa (con screenshot) dal database
            reloaded_notes = self._viewer.backend.get_notes(limit=1)
            for n in reloaded_notes:
                if n.id == new_note.id:
                    new_note = n
                    break
            
            self._viewer._load_notes(
                search_text=self._viewer.search_input.text().strip() or None,
                filter_tag=self._viewer.tag_filter.currentData(),
                filter_date=self._viewer._get_date_filter()
            )
            self._viewer._show_note_detail(new_note)
        
        edit.deleteLater()
        label.show()
    
    def _cancel_edit(self, edit):
        """Cancels editing."""
        edit._label.show()
        edit.deleteLater()
    
    def show_note(self, note, viewer=None):
        if note is None:
            self._current_note = None
            self._show_placeholder()
            return
        
        self._current_note = note
        self._viewer = viewer
        
        self.setStyleSheet("""
            NoteDetailWidget {
                background-color: #252530;
                border-radius: 8px;
            }
        """)
        
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        header = QHBoxLayout()
        
        if note.created_at:
            date_label = QLabel(note.created_at.strftime("%d/%m/%Y %H:%M"))
            date_label.setStyleSheet("color: #888; font-size: 11px;")
            header.addWidget(date_label)
        
        header.addStretch()
        
        edit_btn = QPushButton("Edit")
        edit_btn.setFixedHeight(24)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3D3D3D; color: #CCC;
                border: none; border-radius: 4px;
                padding: 4px 8px; font-size: 10px;
            }
            QPushButton:hover { background-color: #555; }
        """)
        edit_btn.clicked.connect(lambda: self._start_edit_current())
        header.addWidget(edit_btn)
        
        copy_btn = QPushButton("Copy text")
        copy_btn.setFixedHeight(24)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #3D3D3D; color: #CCC;
                border: none; border-radius: 4px;
                padding: 4px 8px; font-size: 10px;
            }
            QPushButton:hover { background-color: #555; }
        """)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(note.content or ""))
        header.addWidget(copy_btn)
        
        del_btn = QPushButton("Delete")
        del_btn.setFixedHeight(24)
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: #3D3D3D; color: #CCC;
                border: none; border-radius: 4px;
                padding: 4px 8px; font-size: 10px;
            }
            QPushButton:hover { background-color: #FF4444; color: #FFF; }
        """)
        del_btn.clicked.connect(self._delete_current_note)
        header.addWidget(del_btn)
        
        self._layout.addLayout(header)
        
        if note.tags:
            tags_text = "  ".join([f"<span style='color:{t.color};'>● {t.name}</span>" for t in note.tags])
            tag_label = QLabel(tags_text)
            tag_label.setStyleSheet("font-size: 12px;")
            tag_label.setTextFormat(Qt.TextFormat.RichText)
            self._layout.addWidget(tag_label)
        
        if note.content:
            self._text_label = QLabel(note.content)
            self._text_label.setWordWrap(True)
            self._text_label.setStyleSheet("color: #EEE; font-size: 14px;")
            self._text_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self._text_label.customContextMenuRequested.connect(
                lambda pos: self._show_text_context_menu(pos, note.content)
            )
            self._layout.addWidget(self._text_label)
        else:
            self._text_label = None
        
        if note.screenshots:
            for screenshot in note.screenshots:
                pixmap = QPixmap(screenshot.filepath)
                if not pixmap.isNull():
                    img_container = QFrame()
                    img_container.setStyleSheet("border: 1px solid #555; border-radius: 6px;")
                    img_container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    img_container.customContextMenuRequested.connect(
                        lambda pos, p=screenshot.filepath: self._show_image_context_menu(pos, p)
                    )
                    img_layout = QVBoxLayout(img_container)
                    img_layout.setContentsMargins(0, 0, 0, 0)
                    
                    img_label = QLabel()
                    scaled = pixmap.scaledToWidth(400, Qt.TransformationMode.SmoothTransformation)
                    img_label.setPixmap(scaled)
                    img_label.setCursor(Qt.CursorShape.PointingHandCursor)
                    img_label.mousePressEvent = lambda e, p=screenshot.filepath: self._image_click(e, p)
                    img_layout.addWidget(img_label)
                    
                    self._layout.addWidget(img_container)
        
        self._layout.addStretch()
    
    def _start_edit_current(self):
        """Starts editing the current note's text."""
        if self._text_label and self._current_note:
            self._make_text_editable(self._text_label, self._current_note)
    
    def _image_click(self, event, filepath):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_image(filepath)
    
    def _show_text_context_menu(self, position, text):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2D2D2D; color: #EEE; border: 1px solid #555; }
            QMenu::item { padding: 6px 16px; }
            QMenu::item:selected { background-color: #444; }
        """)
        menu.addAction("Copy text", lambda: QApplication.clipboard().setText(text))
        menu.addAction("Edit", lambda: self._start_edit_current())
        menu.exec(self.mapToGlobal(position))
    
    def _show_image_context_menu(self, position, filepath):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2D2D2D; color: #EEE; border: 1px solid #555; }
            QMenu::item { padding: 6px 16px; }
            QMenu::item:selected { background-color: #444; }
        """)
        menu.addAction("Copy image", lambda: self._copy_image(filepath))
        menu.addAction("Open image", lambda: self._open_image(filepath))
        menu.exec(self.mapToGlobal(position))
    
    def _copy_image(self, filepath):
        pixmap = QPixmap(filepath)
        if not pixmap.isNull():
            QApplication.clipboard().setPixmap(pixmap)
    
    def _open_image(self, filepath):
        import os, subprocess, platform
        if platform.system() == "Windows":
            os.startfile(filepath)
        elif platform.system() == "Darwin":
            subprocess.run(["open", filepath])
        else:
            subprocess.run(["xdg-open", filepath])
    
    def _delete_current_note(self):
        if not self._current_note or not self._viewer:
            return
        self._viewer._delete_note_with_confirm(self._current_note)


class NoteListItem(QFrame):
    """Single note item in the left panel list."""
    
    clicked = pyqtSignal(object)
    delete_requested = pyqtSignal(object)
    
    def __init__(self, note, parent=None):
        super().__init__(parent)
        self.note = note
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        self.setStyleSheet("""
            NoteListItem {
                background-color: #2D2D2D;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                padding: 8px;
                margin: 2px 0;
            }
            NoteListItem:hover { background-color: #3A3A4A; border-color: #555; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        top = QHBoxLayout()
        if note.created_at:
            time_label = QLabel(note.created_at.strftime("%d/%m %H:%M"))
            time_label.setStyleSheet("color: #888; font-size: 10px;")
            top.addWidget(time_label)
        top.addStretch()
        if note.screenshots:
            icon_label = QLabel("📷")
            icon_label.setStyleSheet("font-size: 12px;")
            top.addWidget(icon_label)
        layout.addLayout(top)
        
        text = note.content or ""
        if not text and note.screenshots:
            text = "Screenshot"
        if len(text) > 80:
            text = text[:77] + "..."
        content_label = QLabel(text)
        content_label.setStyleSheet("color: #CCC; font-size: 12px;")
        content_label.setWordWrap(True)
        layout.addWidget(content_label)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.note)
        super().mousePressEvent(event)
    
    def _show_context_menu(self, position):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2D2D2D; color: #EEE; border: 1px solid #555; }
            QMenu::item { padding: 6px 16px; }
            QMenu::item:selected { background-color: #444; }
        """)
        menu.addAction("Copy text", lambda: QApplication.clipboard().setText(self.note.content or ""))
        if self.note.screenshots:
            menu.addAction("Copy image", lambda: self._copy_first_image())
        menu.addSeparator()
        menu.addAction("Delete", lambda: self.delete_requested.emit(self.note))
        menu.exec(self.mapToGlobal(position))
        self.update()
        # Notifica il genitore di aggiornare tutti gli item
        parent = self.parent()
        if parent:
            parent.update()

    
    def _copy_first_image(self):
        pixmap = QPixmap(self.note.screenshots[0].filepath)
        if not pixmap.isNull():
            QApplication.clipboard().setPixmap(pixmap)


class ViewerWindow(QWidget):
    """Main viewer window."""
    
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self._current_detail_note = None
        self._refresh_callback = None
        
        self.setWindowTitle("Fnote - Viewer")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(850, 580)
        
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        
        self._setup_ui()
        self._load_notes()
        
        self.esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.esc_shortcut.activated.connect(self.hide)
        
        self.del_shortcut = QShortcut(QKeySequence("Delete"), self)
        self.del_shortcut.activated.connect(self._delete_current_detail_note)
        self.del_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        
        self.setStyleSheet("ViewerWindow { background-color: #1E1E1E; }")
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        
        title = QLabel("Fnote - All notes")
        title.setStyleSheet("color: #AAA; font-size: 14px; font-weight: bold; padding: 0px; margin: 0px;")
        title.setFixedHeight(20)
        main_layout.addWidget(title)
        
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search notes...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #2D2D2D; color: #EEE;
                border: 1px solid #3D3D3D; border-radius: 6px;
                padding: 8px; font-size: 13px;
            }
            QLineEdit:focus { border-color: #555; }
        """)
        self.search_input.textChanged.connect(self._on_search)
        filter_row.addWidget(self.search_input)
        
        self.tag_filter = QComboBox()
        self.tag_filter.setMinimumWidth(150)
        self.tag_filter.setItemDelegate(TagDelegate(self.tag_filter))
        self.tag_filter.setStyleSheet("""
            QComboBox {
                background-color: #2D2D2D; color: #EEE;
                border: 1px solid #3D3D3D; border-radius: 6px;
                padding: 8px; font-size: 12px; min-width: 140px;
            }
            QComboBox:hover { border-color: #555; }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox QAbstractItemView {
                background-color: #2D2D2D; color: #EEE;
                border: 1px solid #555; selection-background-color: #444; outline: none;
            }
        """)
        self._reload_tag_filter()
        self.tag_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.tag_filter)
        
        self.date_filter = CalendarButton()
        self.date_filter.setDate(QDate(2000, 1, 1))
        self.date_filter.dateChanged.connect(self._on_date_changed)
        filter_row.addWidget(self.date_filter)
        
        reset_btn = QPushButton("Reset")
        reset_btn.setFixedHeight(36)
        reset_btn.setToolTip("Reset filters to default")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #3D3D3D; color: #CCC;
                border: none; border-radius: 6px;
                padding: 8px 12px; font-size: 11px;
            }
            QPushButton:hover { background-color: #555; color: #FFF; }
        """)
        reset_btn.clicked.connect(self._reset_filters)
        filter_row.addWidget(reset_btn)
        
        filter_row.addStretch()
        main_layout.addLayout(filter_row)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_widget = QFrame()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.note_list_area = QScrollArea()
        self.note_list_area.setWidgetResizable(True)
        self.note_list_area.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { background: #2D2D2D; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #555; border-radius: 3px; }
        """)
        
        self.note_list_widget = QWidget()
        self.note_list_layout = QVBoxLayout(self.note_list_widget)
        self.note_list_layout.setContentsMargins(0, 0, 0, 0)
        self.note_list_layout.setSpacing(2)
        self.note_list_layout.addStretch()
        
        self.note_list_area.setWidget(self.note_list_widget)
        left_layout.addWidget(self.note_list_area)
        
        splitter.addWidget(left_widget)
        
        self.detail_widget = NoteDetailWidget()
        splitter.addWidget(self.detail_widget)
        
        splitter.setSizes([300, 550])
        main_layout.addWidget(splitter)
    
    def set_refresh_callback(self, callback):
        self._refresh_callback = callback
    
    def _reload_tag_filter(self):
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("All tags", None)
        self.tag_filter.addItem("No tags", "__no_tags__")
        used_tags = self.backend.get_all_tags()
        for tag in used_tags:
            color = QColor(tag.color)
            self.tag_filter.addItem(f"● {tag.name}", tag.name)
            idx = self.tag_filter.count() - 1
            self.tag_filter.setItemData(idx, color, TAG_COLOR_ROLE)
        self.tag_filter.blockSignals(False)
        self._update_tag_filter_color()

    def _update_tag_filter_color(self):
        idx = self.tag_filter.currentIndex()
        if idx > 1:
            color = self.tag_filter.itemData(idx, TAG_COLOR_ROLE)
            if color and isinstance(color, QColor):
                self.tag_filter.setStyleSheet(f"""
                    QComboBox {{
                        background-color: #2D2D2D;
                        border: 1px solid #3D3D3D;
                        border-radius: 6px;
                        padding: 8px;
                        font-size: 12px;
                        min-width: 140px;
                        color: {color.name()};
                    }}
                    QComboBox:hover {{ border-color: #555; }}
                    QComboBox::drop-down {{ border: none; width: 24px; }}
                    QComboBox QAbstractItemView {{
                        background-color: #2D2D2D;
                        border: 1px solid #555;
                        selection-background-color: #444;
                        outline: none;
                    }}
                """)
                return
        self._reset_tag_filter_style()
    
    def _reset_tag_filter_style(self):
        self.tag_filter.setStyleSheet("""
            QComboBox {
                background-color: #2D2D2D; color: #EEE;
                border: 1px solid #3D3D3D; border-radius: 6px;
                padding: 8px; font-size: 12px; min-width: 140px;
            }
            QComboBox:hover { border-color: #555; }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox QAbstractItemView {
                background-color: #2D2D2D; color: #EEE;
                border: 1px solid #555; selection-background-color: #444; outline: none;
            }
        """)
    
    def _get_date_filter(self):
        qdate = self.date_filter.date()
        return None if qdate.year() <= 2000 else qdate.toPyDate()
    
    def _reset_filters(self):
        self.search_input.clear()
        self.tag_filter.setCurrentIndex(0)
        self.date_filter.setDate(QDate(2000, 1, 1))
        self._load_notes()
        self._update_tag_filter_color()
    
    def _load_notes(self, search_text=None, filter_tag=None, filter_date=None):
        while self.note_list_layout.count() > 1:
            item = self.note_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if filter_tag == "__no_tags__":
            all_notes = self.backend.get_notes(
                search_text=search_text if search_text else None,
                filter_tags=None,
                filter_date=filter_date,
                limit=500
            )
            notes = [n for n in all_notes if not n.tags][:100]
        else:
            tag_list = [filter_tag] if filter_tag is not None else None
            notes = self.backend.get_notes(
                search_text=search_text if search_text else None,
                filter_tags=tag_list,
                filter_date=filter_date,
                limit=100
            )

        if self._current_detail_note:
            found = any(n.id == self._current_detail_note.id for n in notes)
            if not found:
                self._current_detail_note = None
                self.detail_widget.show_note(None)
        
        for note in notes:
            item = NoteListItem(note)
            item.clicked.connect(self._show_note_detail)
            item.delete_requested.connect(self._delete_note_with_confirm)
            self.note_list_layout.insertWidget(self.note_list_layout.count() - 1, item)
    
    def _show_note_detail(self, note):
        self._current_detail_note = note
        self.detail_widget.show_note(note, viewer=self)
    
    def _delete_current_detail_note(self):
        if self._current_detail_note:
            self._delete_note_with_confirm(self._current_detail_note)
    
    def _delete_note_with_confirm(self, note):
        if self.backend.config.get_bool("general", "confirm_delete", True):
            reply = QMessageBox.question(
                self, "Delete note",
                "Are you sure you want to delete this note?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.backend.delete_note(note.id)
        self._current_detail_note = None
        self._load_notes(
            search_text=self.search_input.text().strip() or None,
            filter_tag=self.tag_filter.currentData(),
            filter_date=self._get_date_filter()
        )
        self._reload_tag_filter()
        self.detail_widget.show_note(None)
        if self._refresh_callback:
            self._refresh_callback()
    
    def _on_search(self, text):
        text = text.strip()
        tag = self.tag_filter.currentData()
        self._load_notes(search_text=text if text else None, filter_tag=tag, filter_date=self._get_date_filter())
    
    def _on_filter_changed(self):
        tag = self.tag_filter.currentData()
        text = self.search_input.text().strip()
        self._load_notes(search_text=text if text else None, filter_tag=tag, filter_date=self._get_date_filter())
        self._update_tag_filter_color()
    
    def _on_date_changed(self, qdate):
        tag = self.tag_filter.currentData()
        text = self.search_input.text().strip()
        self._load_notes(search_text=text if text else None, filter_tag=tag, filter_date=self._get_date_filter())
    
    def toggle(self):
        if self.isVisible():
            self.hide()
            if self._refresh_callback:
                self._refresh_callback()
        else:
            self._reload_tag_filter()
            self._load_notes()
            self.show()
            self.raise_()
            self.activateWindow()