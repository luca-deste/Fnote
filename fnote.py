"""
Fnote - Applicazione per prendere note veloci.
Entry point principale.
"""

import sys, os
import threading
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, pyqtSignal, QObject

import keyboard

from core.backend import FnoteBackend
from core.config import Config
from ui.chat_popup import ChatPopup
from ui.viewer import ViewerWindow

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class HotkeyBridge(QObject):
    """Ponte tra il thread di keyboard e il thread principale di Qt."""
    activated = pyqtSignal()
    screenshot = pyqtSignal()
    viewer = pyqtSignal()
    quit_app = pyqtSignal()

    def trigger(self):
        self.activated.emit()
    
    def screenshot_trigger(self):
        self.screenshot.emit()
    
    def viewer_trigger(self):
        self.viewer.emit()
    
    def quit_trigger(self):
        self.quit_app.emit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Fnote")
    app.setQuitOnLastWindowClosed(False)

    # Tray icon
    tray_icon = QSystemTrayIcon()
    tray_icon.setIcon(QIcon(resource_path('fnote.ico')))
    #tray_icon.setIcon(QIcon.fromTheme("edit-undo"))  # icona di default
    tray_icon.setToolTip("Fnote - Premi Ctrl+Alt+N")

    tray_menu = QMenu()
    quit_action = tray_menu.addAction("Esci")
    quit_action.triggered.connect(app.quit)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    config = Config()
    shortcut_chat = config.get_shortcut("shortcut_chat")
    shortcut_screenshot = config.get_shortcut("shortcut_screenshot")
    shortcut_viewer = config.get_shortcut("shortcut_viewer")

    backend = FnoteBackend(config=config)
    popup = ChatPopup(backend, shortcut=shortcut_chat)
    viewer = ViewerWindow(backend)
    
    # Callback per aggiornare la chat quando il viewer fa modifiche
    viewer.set_refresh_callback(lambda: popup._reload_history())

    bridge = HotkeyBridge()
    bridge.activated.connect(popup.toggle)
    bridge.screenshot.connect(popup._start_screenshot)
    bridge.viewer.connect(viewer.toggle)
    bridge.quit_app.connect(app.quit)

    def start_hotkey():
        keyboard.add_hotkey(shortcut_chat, bridge.trigger)
        keyboard.add_hotkey(shortcut_screenshot, bridge.screenshot_trigger)
        keyboard.add_hotkey(shortcut_viewer, bridge.viewer_trigger)
        keyboard.add_hotkey("Ctrl+Alt+Q", bridge.quit_trigger)
        keyboard.wait()

    thread = threading.Thread(target=start_hotkey, daemon=True)
    thread.start()

    print("✅ Fnote avviato in background.")
    print(f"   Premi {shortcut_chat} per aprire la chat popup.")
    print(f"   Premi {shortcut_screenshot} per catturare uno screenshot.")
    print(f"   Premi {shortcut_viewer} per aprire il viewer.")
    print("   Premi Ctrl+Alt+Q per uscire.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()