"""
Dataclass per rappresentare Note, Tag e Screenshot nel codice.
Separati dal database per tenere pulita la logica.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Tag:
    """Un tag con nome e colore."""
    id: Optional[int] = None
    name: str = ""
    color: str = "#CCCCCC"


@dataclass
class NoteTag:
    """Associazione tra nota e tag, con info su come è stato assegnato."""
    note_id: int
    tag_id: int
    assigned_by: str = "manual"  # "manual" o "auto"


@dataclass
class Screenshot:
    """Screenshot allegato a una nota."""
    id: Optional[int] = None
    note_id: int = 0
    filepath: str = ""
    created_at: Optional[datetime] = None


@dataclass
class Note:
    """Una nota completa, con testo, timestamp e tag."""
    id: Optional[int] = None
    content: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: list[Tag] = field(default_factory=list)
    screenshots: list[Screenshot] = field(default_factory=list)