"""
Config.ini file reading and management.
"""

import configparser
import re, sys
from pathlib import Path
from typing import Optional


class Config:
    """
    Loads and exposes settings from config.ini.
    
    Usage:
        config = Config()
        color = config.get_tag_color("work")  # -> "#FF5733"
        regex = config.get_auto_tag_regex("urgent")  # -> compiled regex
        auto_tags = config.get_all_auto_tags()  # -> {tag_name: compiled_regex, ...}
    """

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            # Se è un exe PyInstaller, usa la cartella dell'exe
            if getattr(sys, 'frozen', False):
                base_dir = Path(sys.executable).parent
            else:
                base_dir = Path(__file__).parent.parent
            config_path = base_dir / "config.ini"
        
        self.config_path = config_path
        self.parser = configparser.ConfigParser()
        self._auto_tag_regexes: dict[str, re.Pattern] = {}
        
        if not self.config_path.exists():
            self._create_default_config()
        
        self.parser.read(str(self.config_path), encoding="utf-8")
        self._compile_auto_tags()

    def _create_default_config(self):
        """Creates a default config.ini file with preset tags and settings."""
        default_config = """[general]
shortcut_chat = Ctrl+Alt+N
shortcut_screenshot = Ctrl+Alt+M
shortcut_viewer = Ctrl+Alt+V
chat_history = 10
chat_size = medium
confirm_delete = false

[tags]
work = #FF5733
personal = #33A8FF
urgent = #FF0000
idea = #FFD700

[tag_aliases]
i = personal
w = work
u = urgent

[auto_tags]
urgent = \\burgent\\b|\\bASAP\\b|\\bdeadline\\b
work = \\bclient\\b|\\bmeeting\\b|\\bproject\\b|\\boffice\\b
personal = \\bhome\\b|\\bfamily\\b|\\bpersonal\\b
"""
        self.config_path.write_text(default_config, encoding="utf-8")
        print(f"✅ Created default config.ini at {self.config_path}")

    def _compile_auto_tags(self):
        """
        Compiles regex patterns defined in the [auto_tags] section.
        Each key is a tag name, the value is the regex pattern.
        
        Example from config.ini:
            [auto_tags]
            urgent = \\burgent\\b|\\bASAP\\b
            work = \\bclient\\b|\\bmeeting\\b
        
        Becomes:
            self._auto_tag_regexes = {
                "urgent": re.compile(r"\\burgent\\b|\\bASAP\\b", re.IGNORECASE),
                "work": re.compile(r"\\bclient\\b|\\bmeeting\\b", re.IGNORECASE),
            }
        """
        if not self.parser.has_section("auto_tags"):
            return
        
        for tag_name, pattern in self.parser.items("auto_tags"):
            try:
                self._auto_tag_regexes[tag_name] = re.compile(
                    pattern.strip(), re.IGNORECASE
                )
            except re.error as e:
                print(f"⚠️ Invalid regex for tag '{tag_name}': {e}")

    def get_tag_color(self, tag_name: str) -> str:
        """
        Returns the color of a tag from config.ini.
        If the tag is not defined, returns light gray.
        """
        if self.parser.has_option("tags", tag_name):
            return self.parser.get("tags", tag_name).strip()
        return "#CCCCCC"

    def get_tag_names(self) -> list[str]:
        """Returns the list of all tag names defined in [tags]."""
        if self.parser.has_section("tags"):
            return [name for name, _ in self.parser.items("tags")]
        return []

    def get_auto_tag_regex(self, tag_name: str) -> Optional[re.Pattern]:
        """Returns the compiled regex for a tag, or None."""
        return self._auto_tag_regexes.get(tag_name)

    def get_all_auto_tags(self) -> dict[str, re.Pattern]:
        """
        Returns a dict {tag_name: compiled_regex}
        for all tags with auto-tag defined.
        """
        return dict(self._auto_tag_regexes)

    def get_shortcut(self, name: str) -> str:
        """
        Returns a shortcut from the [general] section.
        Example: config.get_shortcut("shortcut_chat") -> "Ctrl+Alt+N"
        """
        if self.parser.has_option("general", name):
            return self.parser.get("general", name).strip()
        # Fallback defaults
        defaults = {
            "shortcut_chat": "Ctrl+Alt+N",
            "shortcut_viewer": "Ctrl+Alt+V",
            "shortcut_screenshot": "Ctrl+Alt+M",
            "chat_history": "10",
        }
        return defaults.get(name, "")

    def get_int(self, section: str, option: str, default: int = 0) -> int:
        """Returns an integer value from config, with fallback."""
        try:
            return self.parser.getint(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default

    def get_chat_size(self) -> tuple[int, int]:
        """
        Returns chat width and height based on configuration.
        """
        size_name = "medium"
        if self.parser.has_option("general", "chat_size"):
            size_name = self.parser.get("general", "chat_size").strip().lower()
        
        sizes = {
            "small": (300, 400),
            "medium": (380, 500),
            "large": (480, 650),
        }
        return sizes.get(size_name, sizes["medium"])

    def get_tag_aliases(self) -> dict[str, str]:
        """
        Returns the tag aliases dictionary.
        Example: {"i": "personal", "w": "work"}
        """
        if self.parser.has_section("tag_aliases"):
            return dict(self.parser.items("tag_aliases"))
        return {}
    
    def get_bool(self, section: str, option: str, default: bool = False) -> bool:
        """Reads a boolean value from config."""
        try:
            if self.parser.has_option(section, option):
                raw = self.parser.get(section, option).strip().lower()
                if raw in ("true", "yes", "1", "on"):
                    return True
                elif raw in ("false", "no", "0", "off"):
                    return False
            return default
        except Exception as e:
            print(f"get_bool error: {e}")
            return default


# Quick test when run directly
if __name__ == "__main__":
    config = Config()
    print("Tags defined:", config.get_tag_names())
    print("Color 'work':", config.get_tag_color("work"))
    print("Color 'urgent':", config.get_tag_color("urgent"))
    print("Auto-tag regexes:", {k: v.pattern for k, v in config.get_all_auto_tags().items()})
    print("Shortcut chat:", config.get_shortcut("shortcut_chat"))
    print("✅ Config working!")