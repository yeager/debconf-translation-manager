# Debconf Translation Manager

A GTK4/libadwaita application for managing translations of Debian debconf
templates. Built for translators who work with the Debian l10n infrastructure.

## Features

- **Package List**: Browse all packages needing translation, sorted and filtered
  by name, percentage, or untranslated count. Color-coded status indicators.
- **Package Detail**: View translation stats, download PO files, run l10n-lint,
  and submit translations — all from one view.
- **Built-in PO Editor**: Side-by-side source/translation editor with fuzzy
  highlighting, search, and copy-source-to-target.
- **One-click Submit**: Pre-filled email with standard Debian l10n format,
  SMTP sending with attachment.
- **Statistics**: Track progress over time, compare language rankings,
  view submission history. Data cached in SQLite.
- **Preferences**: Language selection, SMTP configuration with Gmail preset,
  translator identity settings.

## Requirements

- Python 3.10+
- GTK4 and libadwaita
- Python packages: PyGObject, requests, beautifulsoup4, polib

### Ubuntu/Debian

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-requests python3-bs4 python3-polib
```

## Installation

```bash
# From source
pip install -e .

# Or build
python -m build
pip install dist/debconf_translation_manager-*.whl
```

## Usage

```bash
# Launch GUI
debconf-translation-manager

# CLI mode (stats only)
debconf-translation-manager --no-gui
```

## Workflow

1. **Browse** — App fetches data from debian.org and shows packages needing
   translation for your language
2. **Select** — Click a package to see details and download the PO file
3. **Translate** — Use the built-in PO editor to translate strings
4. **Submit** — Send the translation via email with one click

## Data Source

Translation data is fetched from:
- `https://www.debian.org/international/l10n/po-debconf/{lang_code}`
- PO files downloaded from `i18n.debian.org`

## Configuration

Settings are stored in `~/.config/debconf-translation-manager/settings.json`.
Submission history is cached in `~/.cache/debconf-translation-manager/submissions.db`.

## License

GPL-3.0-or-later

## Author

Daniel Nylander <daniel@danielnylander.se>
