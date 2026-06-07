"""
Screenshot capture overlay with selection rectangle.
Fullscreen semi-transparent overlay, click & drag to select area,
shows pixel dimensions during selection.
Right-click or Esc to cancel.
Emits screenshot_taken(QPixmap) or cancelled() signal.
"""

from PyQt6.QtWidgets import QWidget, QApplication, QLabel
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal, QBuffer, QIODevice
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QFont, QPixmap


class ScreenshotCapture(QWidget):
    """Overlay a schermo intero per catturare un'area con il mouse."""
    
    screenshot_taken = pyqtSignal(QPixmap)
    cancelled = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        self._full_screenshot = self._grab_all_screens()
        
        self._start_point = QPoint()
        self._end_point = QPoint()
        self._selecting = False
        self._selection_rect = QRect()
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        total_rect = QRect()
        for screen in QApplication.screens():
            total_rect = total_rect.united(screen.geometry())
        self.setGeometry(total_rect)
        
        self._size_label = QLabel(self)
        self._size_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-family: monospace;
            }
        """)
        self._size_label.hide()
        
        self._done = False
    
    def _grab_all_screens(self) -> QPixmap:
        """Cattura tutti gli schermi in un unico pixmap."""
        total_rect = QRect()
        for screen in QApplication.screens():
            total_rect = total_rect.united(screen.geometry())
        
        pixmap = QPixmap(total_rect.size())
        pixmap.fill(Qt.GlobalColor.black)
        
        painter = QPainter(pixmap)
        for screen in QApplication.screens():
            screen_pixmap = screen.grabWindow(0)
            offset = screen.geometry().topLeft() - total_rect.topLeft()
            painter.drawPixmap(offset, screen_pixmap)
        painter.end()
        
        return pixmap
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # Disegna lo screenshot originale
        painter.drawPixmap(self.rect(), self._full_screenshot)
        
        # Overlay semi-trasparente
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if self._selecting and not self._selection_rect.isNull():
            # Ritaglia l'area selezionata (mostra originale senza overlay)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self._selection_rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            
            # Bordo blu
            pen = QPen(QColor("#4A9EFF"), 2)
            painter.setPen(pen)
            painter.drawRect(self._selection_rect)
        
        painter.end()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_point = event.pos()
            self._end_point = event.pos()
            self._selecting = True
            self._selection_rect = QRect()
            self._size_label.hide()
        elif event.button() == Qt.MouseButton.RightButton:
            self._cancel()
    
    def mouseMoveEvent(self, event):
        if self._selecting:
            self._end_point = event.pos()
            self._selection_rect = QRect(self._start_point, self._end_point).normalized()
            
            w = self._selection_rect.width()
            h = self._selection_rect.height()
            self._size_label.setText(f"{w} × {h} px")
            
            label_x = self._selection_rect.right() + 8
            label_y = self._selection_rect.bottom() + 4
            
            self._size_label.adjustSize()
            if label_x + self._size_label.width() > self.width():
                label_x = self._selection_rect.left() - self._size_label.width() - 8
            if label_y + self._size_label.height() > self.height():
                label_y = self._selection_rect.top() - self._size_label.height() - 4
            
            self._size_label.move(max(0, label_x), max(0, label_y))
            self._size_label.show()
            
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._selecting:
            self._selecting = False
            self._size_label.hide()
            
            if self._selection_rect.width() < 5 or self._selection_rect.height() < 5:
                return
            
            self._capture_selection()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
    
    def _capture_selection(self):
        """Cattura l'area selezionata ed emette il segnale."""
        if self._done:
            return
        self._done = True
        
        cropped = self._full_screenshot.copy(self._selection_rect)
        self.hide()
        self.screenshot_taken.emit(cropped)
        self.deleteLater()
    
    def _cancel(self):
        """Annulla la cattura."""
        if self._done:
            return
        self._done = True
        self.hide()
        self.cancelled.emit()
        self.deleteLater()