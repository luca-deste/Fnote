"""
Gestione del database SQLite per Fnote.
Fornisce connessione, creazione tabelle e migrazioni.
"""

import sqlite3
import os
from pathlib import Path


def get_data_dir() -> Path:
    """Restituisce il Path della cartella data/, la crea se non esiste."""
    # Se siamo dentro un exe PyInstaller, usa la cartella dell'exe
    import sys
    if getattr(sys, 'frozen', False):
        # PyInstaller crea sys._MEIPASS come temp dir
        # Noi vogliamo la cartella dove sta l'exe
        exe_dir = Path(sys.executable).parent
    else:
        # Sviluppo normale
        exe_dir = Path(__file__).parent.parent
    
    data_dir = exe_dir / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    """Restituisce il percorso completo del file .db"""
    return get_data_dir() / "fnote.db"


class Database:
    """
    Gestisce la connessione al database SQLite.
    Si usa come context manager:

        with Database() as db:
            cursor = db.conn.cursor()
            cursor.execute(...)
    """

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = get_db_path()
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def __enter__(self):
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # per accedere alle colonne per nome
        self.conn.execute("PRAGMA journal_mode=WAL")  # scritture più veloci
        self.conn.execute("PRAGMA foreign_keys=ON")   # abilita chiavi esterne
        self._create_tables()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
        return False  # non sopprime le eccezioni

    def _create_tables(self):
        """Crea le tabelle se non esistono già."""
        cursor = self.conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT NOT NULL DEFAULT '#CCCCCC'
            );

            CREATE TABLE IF NOT EXISTS note_tags (
                note_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                assigned_by TEXT NOT NULL DEFAULT 'manual',
                PRIMARY KEY (note_id, tag_id),
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                filepath TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
            );

            -- Indici per ricerche veloci
            CREATE INDEX IF NOT EXISTS idx_notes_created_at
                ON notes(created_at);

            CREATE INDEX IF NOT EXISTS idx_notes_content
                ON notes(content);

            CREATE INDEX IF NOT EXISTS idx_note_tags_tag_id
                ON note_tags(tag_id);
        """)