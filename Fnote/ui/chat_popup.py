"""
Chat Popup for Fnote.
Appears in the bottom-right corner with Ctrl+Alt+N.
Shows note history and allows quick input + screenshot.
"""
import sys
import re
import os
import uuid
import subprocess
import platform
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QScrollArea, QLabel, QFrame, QApplication, QMenu,
    QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QEvent, QBuffer, QIODevice
from PyQt6.QtGui import QKeySequence, QShortcut, QColor, QPainter, QAction, QPixmap

from ui.screenshot import ScreenshotCapture
from core.database import Database


class TagDot(QLabel):
    """Colored dot representing a tag."""
    def __init__(self, color: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.setToolTip(tooltip)
        self.color = QColor(color)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(1, 1, 10, 10)
        painter.end()


class NoteWidget(QFrame):
    """Widget representing a single note in the history."""
    
    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    
    def __init__(self, note_id: int, note_text: str, timestamp: datetime, tags: list, 
                 screenshots: list = None, parent=None):
        super().__init__(parent)
        self.note_id = note_id
        self.note_text = note_text
        self.tags = tags
        self.timestamp = timestamp
        self.screenshots = screenshots or []
        self._editing = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            NoteWidget {
                background-color: #2D2D2D;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                padding: 8px;
                margin: 4px 0px;
            }
            NoteWidget:hover {
                background-color: #333333;
                border-color: #555;
            }
            NoteWidget:focus {
                border-color: #6c8cff;
                background-color: #333344;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 6, 8, 6)
        self.layout.setSpacing(4)
        
        # Top row: time + dots
        self.top_row = QHBoxLayout()
        self.top_row.setSpacing(6)
        
        self.time_label = QLabel(timestamp.strftime("%H:%M"))
        self.time_label.setStyleSheet("color: #888; font-size: 11px;")
        self.top_row.addWidget(self.time_label)
        
        self._build_tag_dots()
        self.top_row.addStretch()
        self.layout.addLayout(self.top_row)
        
        # Text
        if note_text:
            self.text_label = QLabel(note_text)
            self.text_label.setWordWrap(True)
            self.text_label.setStyleSheet("color: #EEE; font-size: 13px;")
            self.layout.addWidget(self.text_label)
        else:
            self.text_label = None
        
        # Screenshot thumbnails
        if self.screenshots:
            self._build_thumbnails()
        
        # Edit area
        self.edit_area = QTextEdit()
        self.edit_area.setPlainText(note_text)
        self.edit_area.setMaximumHeight(120)
        self.edit_area.setStyleSheet("""
            QTextEdit {
                background-color: #3D3D3D;
                color: #EEE;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px;
                font-size: 13px;
            }
        """)
        self.edit_area.hide()
        self.edit_area.installEventFilter(self)
        self.installEventFilter(self)
        self.layout.addWidget(self.edit_area)
    
    def _build_thumbnails(self):
        """Builds screenshot thumbnails."""
        thumb_row = QHBoxLayout()
        thumb_row.setSpacing(4)
        for screenshot in self.screenshots:
            thumb = QLabel()
            pixmap = QPixmap(screenshot.filepath)
            if not pixmap.isNull():
                scaled = pixmap.scaledToHeight(70, Qt.TransformationMode.SmoothTransformation)
                thumb.setPixmap(scaled)
                thumb.setFixedSize(scaled.width(), scaled.height())
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb.setStyleSheet("""
                QLabel {
                    border: 1px solid #555;
                    border-radius: 4px;
                    background-color: transparent;
                }
            """)
            thumb.setToolTip("Click to open | Right-click to copy")
            thumb.mousePressEvent = lambda e, path=screenshot.filepath: self._thumbnail_click(e, path)
            thumb_row.addWidget(thumb)
        thumb_row.addStretch()
        self.layout.addLayout(thumb_row)

    def _thumbnail_click(self, event, filepath):
        """Left click opens the image, right-click copies it."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_image(filepath)
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_thumbnail_menu(event, filepath)

    def _show_thumbnail_menu(self, event, filepath):
        """Shows context menu for a thumbnail."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2D2D2D;
                color: #EEE;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #444;
            }
        """)
        menu.addAction("Open image", lambda: self._open_image(filepath))
        menu.addAction("Copy image", lambda: self._copy_image_to_clipboard(filepath))
        menu.exec(event.globalPosition().toPoint())

    def _copy_image_to_clipboard(self, filepath):
        """Copies an image to the clipboard."""
        pixmap = QPixmap(filepath)
        if not pixmap.isNull():
            QApplication.clipboard().setPixmap(pixmap)

    def _open_image(self, filepath):
        """Opens the image with the system viewer."""
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, ChatPopup):
                parent._dialog_open = True
                break
            parent = parent.parent()
        
        if platform.system() == "Windows":
            os.startfile(filepath)
        elif platform.system() == "Darwin":
            subprocess.run(["open", filepath])
        else:
            subprocess.run(["xdg-open", filepath])
        
        QTimer.singleShot(500, lambda: self._reenable_close())

    def _reenable_close(self):
        """Re-enables chat closing after opening an image."""
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, ChatPopup):
                parent._dialog_open = False
                break
            parent = parent.parent()
    
    def _build_tag_dots(self):
        max_dots = 3
        for i, tag in enumerate(self.tags[:max_dots]):
            dot = TagDot(tag.color, f"Tag: {tag.name}")
            self.top_row.addWidget(dot)
        
        if len(self.tags) > max_dots:
            more_label = QLabel(f"+{len(self.tags) - max_dots}")
            more_label.setStyleSheet("color: #888; font-size: 10px;")
            self.top_row.addWidget(more_label)
    
    def eventFilter(self, obj, event):
        # Ctrl+C when note is selected (not editing)
        if obj == self and not self._editing and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                QApplication.clipboard().setText(self.note_text)
                return True
        if obj == self.edit_area and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._finish_editing()
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self._cancel_editing()
                return True
        return super().eventFilter(obj, event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double-click to start editing."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_editing()
        super().mouseDoubleClickEvent(event)
    
    def _show_context_menu(self, position):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2D2D2D;
                color: #EEE;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #444;
            }
        """)
        
        copy_action = menu.addAction("Copy")
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec(position)
        
        if action == copy_action:
            QApplication.clipboard().setText(self.note_text)
        elif action == edit_action:
            self._start_editing()
        elif action == delete_action:
            self.delete_requested.emit(self.note_id)
    
    def _start_editing(self):
        self._editing = True
        if self.text_label:
            self.text_label.hide()
        
        tag_string = " ".join(f"/{tag.name}" for tag in self.tags)
        if tag_string:
            full_text = f"{tag_string} {self.note_text}"
        else:
            full_text = self.note_text
        
        self.edit_area.setPlainText(full_text)
        self.edit_area.show()
        self.edit_area.setFocus()
        self.edit_area.selectAll()
        self.edit_requested.emit(self.note_id)

    def _finish_editing(self):
        full_text = self.edit_area.toPlainText().strip()
        if full_text:
            self._notify_parent_save(full_text)
        self._exit_editing()

    def _cancel_editing(self):
        self._exit_editing()
    
    def _exit_editing(self):
        self._editing = False
        self.edit_area.hide()
        if self.text_label:
            self.text_label.show()
    
    def _notify_parent_save(self, full_text: str):
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, ChatPopup):
                parent._save_edited_note(self.note_id, full_text)
                break
            parent = parent.parent()

    def is_editing(self) -> bool:
        return self._editing


class ChatPopup(QWidget):
    """Chat-style popup window in the bottom-right corner."""
    
    def __init__(self, backend, shortcut="Ctrl+Alt+N", parent=None):
        super().__init__(parent)
        self.backend = backend
        self.shortcut_text = shortcut
        self._note_widgets: dict[int, NoteWidget] = {}
        self._dialog_open = False
        self._screenshot_capture = None
        self._just_opened = False
        self._pending_screenshot = None
        
        width, height = (380, 500)
        try:
            width, height = backend.config.get_chat_size()
        except Exception:
            pass
        
        self.setWindowTitle("Fnote - Chat")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(width, height)
        
        self._position_bottom_right()
        self.hide()
        
        self._setup_ui()
        self.installEventFilter(self)
        self._load_history()
        
        self.esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.esc_shortcut.activated.connect(self.hide)
        
        self.setStyleSheet("""
            ChatPopup {
                background-color: #1E1E1E;
                border: 1px solid #3D3D3D;
                border-radius: 10px;
            }
        """)
    
    def _position_bottom_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 20
        y = screen.bottom() - self.height() - 20
        self.move(x, y)
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        container = QFrame(self)
        container.setObjectName("container")
        container.setStyleSheet("""
            #container {
                background-color: #1E1E1E;
                border-radius: 10px;
                border: 1px solid #555;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(6)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Fnote")
        title.setStyleSheet("color: #AAA; font-size: 12px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #FFF;
                background-color: #3D3D3D;
                border-radius: 4px;
            }
        """)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        container_layout.addLayout(header)
        
        # Scrollable area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: #2D2D2D;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        self.history_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_widget)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(4)
        self.history_layout.addStretch()
        
        self.scroll_area.setWidget(self.history_widget)
        container_layout.addWidget(self.scroll_area)
        
        # Preview container with X
        self.preview_container = QWidget()
        self.preview_container.setStyleSheet("background-color: transparent;")
        self.preview_container.hide()
        preview_layout = QHBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 4)
        preview_layout.setSpacing(4)
        
        self.thumbnail_preview = QLabel()
        self.thumbnail_preview.setMaximumHeight(80)
        self.thumbnail_preview.setStyleSheet("""
            QLabel {
                border: 1px solid #555;
                border-radius: 6px;
                background-color: #2D2D2D;
            }
        """)
        preview_layout.addWidget(self.thumbnail_preview)
        
        self.remove_thumbnail_btn = QPushButton("✕")
        self.remove_thumbnail_btn.setFixedSize(20, 20)
        self.remove_thumbnail_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 180);
                color: #FFF;
                border: none;
                border-radius: 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF4444;
            }
        """)
        self.remove_thumbnail_btn.clicked.connect(self._remove_pending_screenshot)
        preview_layout.addWidget(self.remove_thumbnail_btn)
        preview_layout.addStretch()
        
        container_layout.addWidget(self.preview_container)
        
        # Input bar
        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Write a note... (/tag for tags, Ctrl+V for image)")
        self.text_input.setMaximumHeight(80)
        self.text_input.setStyleSheet("""
            QTextEdit {
                background-color: #2D2D2D;
                color: #EEE;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border-color: #555;
            }
        """)
        self.text_input.installEventFilter(self)
        input_row.addWidget(self.text_input)
        
        self.screenshot_btn = QPushButton("📎")
        self.screenshot_btn.setFixedSize(36, 36)
        self.screenshot_btn.setToolTip("Capture screenshot (select an area)")
        self.screenshot_btn.setEnabled(True)
        self.screenshot_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #AAA;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        self.screenshot_btn.clicked.connect(self._start_screenshot)
        input_row.addWidget(self.screenshot_btn)
        
        container_layout.addLayout(input_row)
        main_layout.addWidget(container)
    
    def _remove_pending_screenshot(self):
        """Removes the pending screenshot."""
        self._pending_screenshot = None
        self.preview_container.hide()
    
    def eventFilter(self, obj, event):
        # Delete key to delete selected note
        if event.type() == QEvent.Type.ShortcutOverride and event.key() == Qt.Key.Key_Delete:
            if not self._is_any_editing():
                self._delete_selected_note()
            event.accept()
            return True
        
        # Events on input
        if obj == self.text_input and event.type() == QEvent.Type.KeyPress:
            # Ctrl+V to paste image
            if event.key() == Qt.Key.Key_V and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                clipboard = QApplication.clipboard()
                mime = clipboard.mimeData()
                if mime.hasImage():
                    pixmap = clipboard.pixmap()
                    if not pixmap.isNull():
                        self._pending_screenshot = pixmap
                        self.thumbnail_preview.setPixmap(
                            pixmap.scaledToHeight(80, Qt.TransformationMode.SmoothTransformation)
                        )
                        self.preview_container.show()
                        return True
            
            # Enter → save
            if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._save_current_note()
                return True
        
        return super().eventFilter(obj, event)
    
    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow() and not self._just_opened and not self._dialog_open and not self._is_any_editing():
                self.hide()
        super().changeEvent(event)
    
    def _is_any_editing(self) -> bool:
        return any(w.is_editing() for w in self._note_widgets.values())
    
    def _save_current_note(self):
        text = self.text_input.toPlainText().strip()
        
        if not text and not self._pending_screenshot:
            return
        
        manual_tags = re.findall(r'/(\w+)', text)
        aliases = self.backend.config.get_tag_aliases()
        resolved_tags = []
        for tag in manual_tags:
            resolved_tags.append(aliases.get(tag, tag))
        
        clean_text = re.sub(r'/\w+\s*', '', text).strip()
        if not clean_text and self._pending_screenshot:
            clean_text = "📷 Screenshot"
        
        note = self.backend.add_note(clean_text, resolved_tags if resolved_tags else None)
        
        if self._pending_screenshot:
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            self._pending_screenshot.save(buffer, "PNG")
            image_bytes = buffer.data().data()
            buffer.close()
            self.backend.add_screenshot(note.id, image_bytes, "png")
            self._pending_screenshot = None
            self.preview_container.hide()
        
        self.text_input.clear()
        self._reload_history()
        QTimer.singleShot(50, lambda: self.text_input.setFocus())
        
        print(f"✅ Note saved: {clean_text} | tags: {[t.name for t in note.tags]}")
    
    def _load_history(self):
        notes = self.backend.get_notes(limit=10)
        for note in reversed(notes):
            self._add_note_to_history(note.id, note.content, note.created_at, note.tags, note.screenshots)
    
    def _add_note_to_history(self, note_id: int, content: str, timestamp: datetime, tags: list, screenshots: list = None):
        note_widget = NoteWidget(note_id, content, timestamp, tags, screenshots)
        note_widget.delete_requested.connect(self._delete_note)
        self._note_widgets[note_id] = note_widget
        self.history_layout.insertWidget(self.history_layout.count() - 1, note_widget)
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))
    
    def _save_edited_note(self, note_id: int, full_text: str):
        """Saves an inline-edited note. Keeps existing screenshots."""
        manual_tags = re.findall(r'/(\w+)', full_text)
        aliases = self.backend.config.get_tag_aliases()
        resolved_tags = []
        for tag in manual_tags:
            resolved_tags.append(aliases.get(tag, tag))
        
        clean_text = re.sub(r'/\w+\s*', '', full_text).strip()
        
        existing_screenshots = self.backend.get_screenshots_for_note(note_id)
        saved_images = []
        for screenshot in existing_screenshots:
            old_path = Path(screenshot.filepath)
            if old_path.exists():
                image_bytes = old_path.read_bytes()
                saved_images.append(image_bytes)
        
        self.backend.delete_note(note_id)
        note = self.backend.add_note(clean_text, resolved_tags if resolved_tags else None)
        
        for image_bytes in saved_images:
            self.backend.add_screenshot(note.id, image_bytes, "png")
        
        self._reload_history()
        print(f"✅ Note {note_id} edited: '{clean_text}' | tags: {resolved_tags}")

    def _delete_note(self, note_id: int):
        """Deletes a note, with or without confirmation based on config."""
        if self.backend.config.get_bool("general", "confirm_delete", True):
            self._dialog_open = True
            reply = QMessageBox.question(
                self, "Delete note",
                "Are you sure you want to delete this note?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            self._dialog_open = False
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.backend.delete_note(note_id)
        self._reload_history()
        print(f"🗑️ Note {note_id} deleted")

    def _delete_selected_note(self):
        focused = QApplication.focusWidget()
        while focused is not None:
            if isinstance(focused, NoteWidget):
                self._delete_note(focused.note_id)
                return
            focused = focused.parent()

    def _reload_history(self):
        self._note_widgets.clear()
        while self.history_layout.count() > 1:
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._load_history()

    def _start_screenshot(self):
        self.hide()
        QTimer.singleShot(200, self._launch_capture)
    
    def _launch_capture(self):
        self._screenshot_capture = ScreenshotCapture()
        self._screenshot_capture.screenshot_taken.connect(self._on_screenshot_taken)
        self._screenshot_capture.cancelled.connect(self._on_screenshot_cancelled)
        self._screenshot_capture.show()
    
    def _on_screenshot_taken(self, pixmap):
        self._pending_screenshot = pixmap
        self.thumbnail_preview.setPixmap(
            pixmap.scaledToHeight(80, Qt.TransformationMode.SmoothTransformation)
        )
        self.preview_container.show()
        self.toggle()
        print("📷 Screenshot captured. Write a note and press Enter to save.")
    
    def _on_screenshot_cancelled(self):
        self.toggle()
        print("❌ Screenshot cancelled")
    
    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self._just_opened = True
            self._position_bottom_right()
            self.text_input.setReadOnly(True)
            self.show()
            self.raise_()
            if sys.platform == "win32":
                import ctypes
                hwnd = int(self.winId())
                ctypes.windll.user32.ShowWindow(hwnd, 5)
                ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
            else:
                self.activateWindow()
            QTimer.singleShot(50, lambda: self.text_input.setFocus())
            QTimer.singleShot(100, self._enable_input)
            QTimer.singleShot(200, lambda: setattr(self, '_just_opened', False))

    def _enable_input(self):
        self.text_input.setReadOnly(False)
        self.text_input.setFocus()