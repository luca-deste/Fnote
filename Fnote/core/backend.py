"""
Backend principale di Fnote.
Gestisce tutte le operazioni su note e tag,
usando Database per la persistenza e Config per le impostazioni.
"""

import re
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from core.database import Database, get_data_dir
from core.config import Config
from core.models import Note, Tag, Screenshot


class FnoteBackend:
    """
    Classe principale per interagire con le note.
    
    Uso tipico:
        backend = FnoteBackend()
        backend.add_note("comprare il latte", ["spesa", "oggi"])
        note_di_oggi = backend.get_notes(date.today())
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Inizializza il backend.
        
        Args:
            config: Oggetto Config. Se None, ne crea uno nuovo cercando config.ini.
        """
        self.config = config or Config()
        self.data_dir = get_data_dir()
        self.screenshots_dir = self.data_dir / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)


    # ------------------------------------------------------------------
    # TAG
    # ------------------------------------------------------------------

    def ensure_tag_exists(self, tag_name: str, db: Optional[Database] = None) -> Tag:
        """
        Restituisce il tag con quel nome, creandolo se non esiste.
        Il colore viene preso dal config.ini se definito, altrimenti grigio.
        
        Args:
            tag_name: Nome del tag (senza /)
            db: Connessione al database opzionale. Se fornita, la usa;
                altrimenti ne apre una nuova.
        """
        color = self.config.get_tag_color(tag_name)
        
        if db is not None:
            return self._ensure_tag_exists_with_db(db, tag_name, color)
        else:
            with Database() as new_db:
                return self._ensure_tag_exists_with_db(new_db, tag_name, color)

    def _ensure_tag_exists_with_db(self, db: Database, tag_name: str, color: str) -> Tag:
        """Versione interna che richiede una connessione già aperta."""
        cursor = db.conn.cursor()
        
        row = cursor.execute(
            "SELECT id, name, color FROM tags WHERE name = ?",
            (tag_name,)
        ).fetchone()
        
        if row:
            return Tag(id=row["id"], name=row["name"], color=row["color"])
        
        cursor.execute(
            "INSERT INTO tags (name, color) VALUES (?, ?)",
            (tag_name, color)
        )
        db.conn.commit()
        
        return Tag(id=cursor.lastrowid, name=tag_name, color=color)

    def get_tag_by_name(self, tag_name: str) -> Optional[Tag]:
        """Cerca un tag per nome. Restituisce None se non trovato."""
        with Database() as db:
            row = db.conn.execute(
                "SELECT id, name, color FROM tags WHERE name = ?",
                (tag_name,)
            ).fetchone()
            if row:
                return Tag(id=row["id"], name=row["name"], color=row["color"])
        return None

    def get_all_tags(self) -> list[Tag]:
        """Returns all tags that are used in at least one note."""
        with Database() as db:
            rows = db.conn.execute(
                """SELECT DISTINCT t.id, t.name, t.color 
                FROM tags t 
                INNER JOIN note_tags nt ON t.id = nt.tag_id 
                ORDER BY t.name"""
            ).fetchall()
            return [Tag(id=r["id"], name=r["name"], color=r["color"]) for r in rows]

    # ------------------------------------------------------------------
    # AUTO-TAG
    # ------------------------------------------------------------------

    def find_auto_tags(self, content: str) -> list[str]:
        """
        Analizza il testo e restituisce i nomi dei tag che matchano
        con le regex definite in config.ini [auto_tags].
        
        Args:
            content: Testo della nota
        
        Returns:
            Lista di nomi tag (es. ["urgente", "lavoro"])
        """
        matched = []
        for tag_name, regex in self.config.get_all_auto_tags().items():
            if regex.search(content):
                matched.append(tag_name)
        return matched

    # ------------------------------------------------------------------
    # NOTE
    # ------------------------------------------------------------------

    def add_note(self, content: str, manual_tags: Optional[list[str]] = None) -> Note:
        """
        Crea una nuova nota con i tag specificati + auto-tag da regex.
        
        Args:
            content: Testo della nota
            manual_tags: Lista di nomi tag specificati manualmente (es. ["lavoro"])
        
        Returns:
            La nota creata, con id e timestamp popolati.
        """
        if manual_tags is None:
            manual_tags = []
        
        auto_tags = self.find_auto_tags(content)
        all_tag_names = list(dict.fromkeys(manual_tags + auto_tags))
        
        with Database() as db:
            cursor = db.conn.cursor()
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO notes (content, created_at, updated_at) VALUES (?, ?, ?)",
                (content, now, now)
            )
            note_id = cursor.lastrowid
            
            tags = []
            for tag_name in all_tag_names:
                tag = self.ensure_tag_exists(tag_name, db=db)
                assigned_by = "manual" if tag_name in manual_tags else "auto"
                cursor.execute(
                    "INSERT OR IGNORE INTO note_tags (note_id, tag_id, assigned_by) VALUES (?, ?, ?)",
                    (note_id, tag.id, assigned_by)
                )
                tags.append(tag)
            
            db.conn.commit()
        
        return Note(
            id=note_id,
            content=content,
            created_at=datetime.strptime(now, "%Y-%m-%d %H:%M:%S"),
            updated_at=datetime.strptime(now, "%Y-%m-%d %H:%M:%S"),
            tags=tags,
            screenshots=[]
        )

    def get_notes(
        self,
        filter_date: Optional[date] = None,
        filter_tags: Optional[list[str]] = None,
        search_text: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Note]:
        """
        Recupera le note con filtri opzionali.
        
        Args:
            filter_date: Filtra per data specifica (solo giorno, ignora ora)
            filter_tags: Filtra note che hanno ALMENO UNO di questi tag
            search_text: Cerca nel contenuto (LIKE %testo%)
            limit: Massimo numero di note da restituire
            offset: Offset per paginazione
        
        Returns:
            Lista di Note ordinate dalla più recente.
        """
        query = """
            SELECT DISTINCT n.id, n.content, n.created_at, n.updated_at
            FROM notes n
        """
        params = []
        conditions = []
        
        if filter_tags:
            placeholders = ",".join("?" * len(filter_tags))
            query += f"""
                INNER JOIN note_tags nt ON n.id = nt.note_id
                INNER JOIN tags t ON nt.tag_id = t.id
            """
            conditions.append(f"t.name IN ({placeholders})")
            params.extend(filter_tags)
        
        if filter_date:
            conditions.append("date(n.created_at) = date(?)")
            params.append(filter_date.strftime("%Y-%m-%d"))
        
        if search_text:
            conditions.append("n.content LIKE ?")
            params.append(f"%{search_text}%")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY n.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with Database() as db:
            rows = db.conn.execute(query, params).fetchall()
            
            notes = []
            for row in rows:
                tag_rows = db.conn.execute(
                    """
                    SELECT t.id, t.name, t.color
                    FROM tags t
                    INNER JOIN note_tags nt ON t.id = nt.tag_id
                    WHERE nt.note_id = ?
                    """,
                    (row["id"],)
                ).fetchall()
                
                tags = [Tag(id=t["id"], name=t["name"], color=t["color"]) for t in tag_rows]
                
                scr_rows = db.conn.execute(
                    "SELECT id, filepath, created_at FROM screenshots WHERE note_id = ?",
                    (row["id"],)
                ).fetchall()
                
                screenshots = [
                    Screenshot(
                        id=s["id"],
                        note_id=row["id"],
                        filepath=s["filepath"],
                        created_at=datetime.strptime(s["created_at"], "%Y-%m-%d %H:%M:%S") if s["created_at"] else None
                    )
                    for s in scr_rows
                ]
                
                notes.append(Note(
                    id=row["id"],
                    content=row["content"],
                    created_at=datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S") if row["created_at"] else None,
                    updated_at=datetime.strptime(row["updated_at"], "%Y-%m-%d %H:%M:%S") if row["updated_at"] else None,
                    tags=tags,
                    screenshots=screenshots,
                ))
        
        return notes

    def delete_note(self, note_id: int) -> bool:
        """
        Elimina una nota e i suoi screenshot associati.
        
        Returns:
            True se la nota è stata eliminata, False se non esisteva.
        """
        with Database() as db:
            cursor = db.conn.cursor()
            
            scr_rows = cursor.execute(
                "SELECT filepath FROM screenshots WHERE note_id = ?",
                (note_id,)
            ).fetchall()
            
            for scr in scr_rows:
                filepath = Path(scr["filepath"])
                if filepath.exists():
                    filepath.unlink()
            
            cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            deleted = cursor.rowcount > 0
            db.conn.commit()
        
        return deleted

    # ------------------------------------------------------------------
    # SCREENSHOT
    # ------------------------------------------------------------------

    def add_screenshot(self, note_id: int, image_bytes: bytes, extension: str = "png") -> Screenshot:
        """
        Salva uno screenshot su disco e lo associa a una nota.
        
        Args:
            note_id: ID della nota a cui allegare
            image_bytes: Byte dell'immagine
            extension: Estensione file (png, jpg)
        
        Returns:
            Oggetto Screenshot creato.
        """
        filename = f"{uuid.uuid4().hex}.{extension}"
        filepath = self.screenshots_dir / filename
        
        filepath.write_bytes(image_bytes)
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with Database() as db:
            cursor = db.conn.cursor()
            cursor.execute(
                "INSERT INTO screenshots (note_id, filepath, created_at) VALUES (?, ?, ?)",
                (note_id, str(filepath), now)
            )
            db.conn.commit()
        
        return Screenshot(
            id=cursor.lastrowid,
            note_id=note_id,
            filepath=str(filepath),
            created_at=datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        )

    def get_screenshots_for_note(self, note_id: int) -> list[Screenshot]:
        """Restituisce tutti gli screenshot associati a una nota."""
        with Database() as db:
            rows = db.conn.execute(
                "SELECT id, note_id, filepath, created_at FROM screenshots WHERE note_id = ? ORDER BY created_at",
                (note_id,)
            ).fetchall()
            
            return [
                Screenshot(
                    id=r["id"],
                    note_id=r["note_id"],
                    filepath=r["filepath"],
                    created_at=datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S") if r["created_at"] else None
                )
                for r in rows
            ]


# ------------------------------------------------------------------
# TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("=== TEST BACKEND ===\n")
    
    backend = FnoteBackend()
    
    print("1. Aggiungo una nota con tag manuali...")
    nota1 = backend.add_note("Finire relazione per il cliente", ["lavoro"])
    print(f"   Nota creata: id={nota1.id}, content='{nota1.content}'")
    print(f"   Tag: {[(t.name, t.color) for t in nota1.tags]}")
    
    print("\n2. Aggiungo una nota che dovrebbe triggerare auto-tag 'urgente'...")
    nota2 = backend.add_note("Questa cosa è URGENTE e va fatta ASAP")
    print(f"   Nota creata: id={nota2.id}, content='{nota2.content}'")
    print(f"   Tag: {[(t.name) for t in nota2.tags]}")
    
    print("\n3. Aggiungo una nota con tag manuale + auto-tag...")
    nota3 = backend.add_note("Riunione urgente con cliente", ["personale"])
    print(f"   Nota creata: id={nota3.id}, content='{nota3.content}'")
    print(f"   Tag: {[(t.name) for t in nota3.tags]}")
    
    print("\n4. Recupero tutte le note...")
    tutte = backend.get_notes()
    for n in tutte:
        print(f"   [{n.created_at}] {n.content} — tag: {[t.name for t in n.tags]}")
    
    print("\n5. Filtro per tag 'urgente'...")
    urgenti = backend.get_notes(filter_tags=["urgente"])
    for n in urgenti:
        print(f"   [{n.created_at}] {n.content}")
    
    print("\n6. Filtro per oggi...")
    oggi = backend.get_notes(filter_date=date.today())
    print(f"   Trovate {len(oggi)} note")
    
    print("\n7. Cerco 'relazione'...")
    cercate = backend.get_notes(search_text="relazione")
    for n in cercate:
        print(f"   [{n.created_at}] {n.content}")
    
    print("\n✅ Backend funzionante!")