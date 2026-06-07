# Fnote

> Ultra-fast note-taking app for Windows. Hotkey-powered, tag-based, with screenshot capture.

**Fnote** is a lightweight, keyboard-driven note-taking app that lives in your Windows system tray. It's designed for speed: press a hotkey, type a note, and get back to work. No browser, no loading screens, no accounts — just notes.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Auto-tagging with Regex](#auto-tagging-with-regex)
- [Shortcuts](#shortcuts)
- [File Structure](#file-structure)
- [Building from Source](#building-from-source)
- [Tech Stack](#tech-stack)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)

---

## Features

- **Instant Notes** — `Ctrl+Alt+N` opens a chat-like popup in the bottom-right corner. Type and press Enter to save.
- **Tags** — Add tags inline with `/tag` syntax (e.g., `/work Buy groceries`). Aliases let you type `/w` instead of `/work`.
- **Auto-tagging** — Define regex patterns in `config.ini`. Notes matching a pattern are automatically tagged (e.g., any note containing "ASAP" or "urgent" gets the `urgent` tag).
- **Screenshots** — `Ctrl+Alt+M` lets you select an area of the screen to capture. The image is attached to the current note. You can also paste images from clipboard with `Ctrl+V`.
- **Inline Editing** — Right-click any note in the chat history or viewer to edit it in place. Press Enter to save, Esc to cancel.
- **Viewer** — `Ctrl+Alt+V` opens a full window to browse all notes. Search by text, filter by tag or date, view full-size screenshots, copy text or images, and edit or delete notes.
- **Local Storage** — Everything is stored in a single SQLite database file. No cloud, no accounts, no internet required.
- **Portable** — Single `.exe` file. Configuration is auto-generated on first run. The database and screenshots are saved next to the executable.
- **System Tray** — Fnote runs in the background. Right-click the tray icon to quit.

---

## Installation

### Download (Windows)

1. Go to the [Releases](https://github.com/lucadeste/fnote/releases) page
2. Download `Fnote.exe`
3. Run it — no installation required

On first launch, Fnote creates:
- `config.ini` — your settings
- `data/` — database and screenshots folder

Everything is saved next to the executable, so you can put Fnote on a USB stick and take it anywhere.

### From Source (Windows, macOS, Linux)

```bash
# Clone the repository
git clone https://github.com/lucadeste/fnote.git
cd fnote

# Install dependencies
pip install -r requirements.txt

# Run
python fnote.py
```

---

## Usage

### Taking a Note

1. Press `Ctrl+Alt+N`
2. Type your note. Use `/tag` for tags (e.g., `/work Finish the report`)
3. Press Enter

Your note is saved instantly and appears in the chat history with colored tag dots.

### Taking a Screenshot

1. Press `Ctrl+Alt+M` (or click the 📎 button in the chat)
2. Click and drag to select an area
3. Release — the screenshot appears as a preview in the chat
4. Type an optional note and press Enter to save

### Pasting an Image

1. Copy an image to your clipboard
2. Open the chat (`Ctrl+Alt+N`)
3. Press `Ctrl+V`
4. Type an optional note and press Enter

### Browsing Notes

1. Press `Ctrl+Alt+V` to open the viewer
2. Search by keyword in the top bar
3. Filter by tag or date
4. Click a note to see its details on the right
5. Right-click for options: copy text, copy image, delete
6. Click "Edit" or right-click → Edit to modify a note inline

---

## Configuration

The `config.ini` file is created automatically on first run. Here's a complete example:

```ini
[general]
# Global keyboard shortcuts
shortcut_chat = Ctrl+Alt+N
shortcut_screenshot = Ctrl+Alt+M
shortcut_viewer = Ctrl+Alt+V

# Chat popup dimensions: small, medium, large
chat_size = medium

# Ask for confirmation before deleting notes. default false
confirm_delete = false

[tags]
# Define your tags and their colors (hex color codes)
work = #FF5733
personal = #33A8FF
urgent = #FF0000
idea = #FFD700
shopping = #FF69B4

[tag_aliases]
# Shortcuts for tags
w = work
p = personal
u = urgent
i = idea

[auto_tags]
# Regex patterns for automatic tagging (case-insensitive)
urgent = \burgent\b|\bASAP\b|\bdeadline\b|\btoday\b
work = \bclient\b|\bmeeting\b|\bproject\b|\boffice\b|\bboss\b
personal = \bhome\b|\bfamily\b|\bgym\b|\bdinner\b
shopping = \bbuy\b|\bshop\b|\bamazon\b|\border\b|\bgrocery\b
```

### Chat Sizes

| Size | Width × Height |
|------|----------------|
| `small` | 300 × 400 |
| `medium` | 380 × 500 |
| `large` | 480 × 650 |

---

## Auto-tagging with Regex

Fnote compiles your regex patterns with `re.IGNORECASE`. Any Python regex is valid.

**Simple word matching:**
```ini
urgent = \burgent\b|\bASAP\b
```

**Dates (matches "15/03" or "03-15"):**
```ini
deadline = \b\d{1,2}[/-]\d{1,2}\b
```

**Amounts (matches "$50", "100 euro", "20 dollars"):**
```ini
expense = \$\d+|\d+\s?(?:euro|dollars)\b
```

**Email or phone:**
```ini
contact = \b[\w.-]+@[\w.-]+\.\w{2,}\b|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b
```

---

## Shortcuts

| Shortcut | Context | Action |
|----------|---------|--------|
| `Ctrl+Alt+N` | Global | Open/close chat popup |
| `Ctrl+Alt+M` | Global | Start screenshot capture |
| `Ctrl+Alt+V` | Global | Open viewer |
| `Ctrl+Alt+Q` | Global | Quit application |
| `Enter` | Chat input | Save current note |
| `Shift+Enter` | Chat input | New line in note |
| `Esc` | Chat/Viewer | Close window |
| `Delete` | Chat/Viewer | Delete selected note |
| `Ctrl+C` | Chat (note selected) | Copy note text |
| `Ctrl+V` | Chat input | Paste image from clipboard |
| Right-click | Note thumbnail | Copy or open image |
| Right-click | Note text | Edit or copy |

---

## File Structure

```
Fnote/
├── fnote.py              # Entry point, hotkey handling
├── fnote.ico             # Application icon
├── config.ini            # User configuration (auto-generated)
├── requirements.txt      # Python dependencies
├── core/
│   ├── backend.py        # Note CRUD, screenshot handling
│   ├── config.py         # Config file parser
│   ├── database.py       # SQLite connection manager
│   └── models.py         # Data classes
├── ui/
│   ├── chat_popup.py     # Chat popup interface
│   ├── viewer.py         # Note viewer/browser
│   └── screenshot.py     # Screenshot capture overlay
└── data/                 # Created at runtime
    ├── fnote.db          # SQLite database
    └── screenshots/      # Captured images
```

---

## Building from Source

### Requirements

- Python 3.10 or later
- PyQt6 ≥ 6.5.0
- keyboard ≥ 0.13.5
- PyInstaller (for building .exe)

### Development

```bash
git clone https://github.com/lucadeste/fnote.git
cd fnote
pip install -r requirements.txt
python fnote.py
```

### Building the Windows Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build
python -m PyInstaller fnote.spec
```

The executable will be in `dist/Fnote/Fnote.exe`.

To distribute, copy `Fnote.exe`. `config.ini` and `data/` are created on first run.

### Creating an Icon

Place an `fnote.ico` file in the project root. It should contain 16×16, 32×32, 48×48, and 256×256 resolutions. The `.spec` file includes it automatically.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| GUI | PyQt6 |
| Database | SQLite |
| Hotkeys | keyboard (global hotkey library) |
| Screenshots | PyQt6 screen capture |
| Build | PyInstaller |

---

## Roadmap

- [ ] Tag management from viewer
- [ ] Note pinning
- [ ] Dark/light theme switcher
- [ ] Startup with Windows option

---

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you'd like to change.

### Development Setup

```bash
git clone https://github.com/lucadeste/fnote.git
cd fnote
pip install -r requirements.txt
python fnote.py
```

### Before Submitting

- Test your changes on Windows
- Ensure the `.exe` build still works
- Update the README if you add new features

---

## License

This project is licensed under the **GNU General Public License v3.0**.

See [LICENSE](LICENSE) for the full text.

You are free to:
- Use the software for any purpose
- Modify the source code
- Distribute copies

Under the terms:
- You must disclose the source code when distributing
- You must use the same license
- You must state changes made to the code

---

## Author

**Luca D'Este**

- Blog: [lucadeste.it](https://blog.lucadeste.it)
- GitHub: [@lucadeste](https://github.com/luca-deste)
- Project: [fnote.lucadeste.it](https://fnote.lucadeste.it)

---
