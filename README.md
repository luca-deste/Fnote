# Fast Note Taker

**fnote** is a lightweight, high-performance micro-logging utility for Windows, built with AutoHotkey v2. It allows you to capture thoughts, bugs, and links instantly via the command line or a smart GUI.

## Key Features

* **Silent Aliasing:** Use the ultra-short `fn` command.
* **Smart Cross-Filtering:** In the viewer, you can filter using Tags, Dates and Words.
* **Custom BGR Themes:** Color-code your notes based on tags directly via the `.ini` file.
* **Auto-Rotation:** Automatically manages log files to keep your workspace clean.

## Installation

1.  Download Fnote.zip and extract the files.
2.  Run `setup.cmd`. 
3.  The setup will:
    * Copy files to the target directory.
    * Create a silent `fn` shortcut.
    * Add the directory to your **User PATH**.

## Usage

### Command Line Interface
Logging is designed to be as fast as possible, ideally integrated with the use of the shortcut Win+R:

```Win+R
# Add a note with a new tag
fn /work Finished the report

# Add a note with multiple shortcut tags - You can edit the shortcuts inside the .ini file
fn /b /u Fix the database leak

# Open the viewer filtered for today
fn /today

# Search for specific text
fn /find "server error"

# Undo the last entry
fn /undo
