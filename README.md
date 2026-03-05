# Debconf Translation Manager

A GTK4/libadwaita application for managing translations of Debian debconf templates. Part of the [Daniel Nylander](https://github.com/yeager/).

## Features

### Template Browser
Browse and search debconf templates from packages. View original English strings, template type (select, multiselect, string, boolean, note, text, password), priority, default values, choices, and extended descriptions. Filter by type and priority.

### Translation Status Dashboard
Per-language translation coverage dashboard with summary cards showing translated, fuzzy, and untranslated counts. Progress bar for overall coverage. Filter by language, package, and status. Supports 20+ languages.

### PO Editor
Edit po-debconf translation files with source and translation displayed side by side. Features include:
- Fuzzy marking toggle
- Copy source to translation
- Format string validation (checks `%s`, `%d`, etc. match between source and translation)
- Length constraint warnings
- Encoding validation
- Translator comments

### Review Board
Pull translation coordination data from [l10n.debian.org](https://l10n.debian.org/coordination/sv/sv.by_status.html). Shows packages needing review, pending translations, translator and reviewer info, deadlines, and scores. Live refresh from the web with fallback to offline mock data.

### Diff View
Side-by-side comparison of old vs new template strings when templates are updated. Character-level diff highlighting with color coding: removed text in red with strikethrough, added text in green. Tracks modified, added, and removed template strings.

### l10n Coordination
Full l10n.debian.org coordination workflow tracking the lifecycle:
- **Unclaimed** → **ITT** (Intent To Translate) → **Translating** → **RFR** (Request For Review) → **Under Review** → **LCFC** (Last Chance For Comments) → **Done**

Claim packages, submit for review, and track progress through the pipeline with a visual lifecycle progress bar.

### BTS Bug Filing
Compose l10n bug reports for the Debian Bug Tracking System:
- Auto-generated subject: `[INTL:sv] Swedish debconf translation for PACKAGE`
- Pre-filled body template with translator/reviewer credits
- Attach .po files
- Configurable severity and tags
- Preview, copy to clipboard, or open in mail client
- Track filed bugs with status

### DDTSS Integration
Submit and review translations via the [Debian Description Translation Server](https://ddtp.debian.org):
- View open translations needing work
- Submit new translations
- Review queue with approve/reject workflow
- Simulated login for testing

### Statistics
Charts and graphs drawn with Cairo:
- **Status distribution** — donut chart showing translated/fuzzy/untranslated/pending-review proportions
- **Per-package score** — horizontal bar chart with color-coded scores
- **Cross-language coverage** — vertical bar chart comparing coverage across 8+ languages
- **Coverage timeline** — line chart showing translation progress over time

### Change Notifications
Background polling detects when debconf templates change (new/modified/removed strings). Shows an in-app notification bar and sends desktop notifications listing affected packages.

### Standard L10n Suite Features
- **Theme toggle** — cycle between light, dark, and system themes (Ctrl+T)
- **Keyboard shortcuts** — Ctrl+F search, Ctrl+S save, Ctrl+Q quit, and more
- **Status bar** with timestamps
- **CSV/JSON export** of data from any view (Ctrl+Shift+E / Ctrl+Shift+J)
- **Copy Debug Info** button — copies app version, GTK version, OS info
- **Welcome dialog** on first launch
- **About dialog** using `Adw.AboutDialog` with `present(parent)`

## Installation

### Requirements
- Python 3.10+
- GTK 4
- libadwaita 1.x
- PyGObject
- requests
- beautifulsoup4

### Install from source

```bash
pip install .
```

### Run without installing

```bash
python -m debconf_translation_manager
```

### CLI mode

```bash
# Print stats and exit
debconf-translation-manager --no-gui

# JSON output
debconf-translation-manager --no-gui --json

# Quiet mode
debconf-translation-manager --no-gui -q
```

## Development

```bash
# Clone the repository
git clone https://github.com/yeager/debconf-translation-manager.git
cd debconf-translation-manager

# Install in development mode
pip install -e .

# Run
python -m debconf_translation_manager
```

The application includes comprehensive mock data for all views, so it can be fully tested without network access or a Debian system.

## File Structure

```
debconf_translation_manager/
├── __init__.py              # Version, APP_ID
├── __main__.py              # Entry point, CLI flags
├── app.py                   # Adw.Application, theme, shortcuts, about/welcome
├── window.py                # Main window, sidebar navigation, export, notifications
├── views/
│   ├── template_browser.py  # Browse/search debconf templates
│   ├── translation_status.py # Per-language coverage dashboard
│   ├── po_editor.py         # Side-by-side PO editor with validation
│   ├── review_board.py      # l10n.debian.org review board
│   ├── diff_view.py         # Side-by-side template diff
│   ├── coordination.py      # l10n coordination workflow (ITT/RFR/LCFC)
│   ├── bts_workflow.py      # BTS bug filing
│   ├── ddtss_workflow.py    # DDTSS submit/review workflow
│   └── statistics.py        # Cairo-drawn charts and graphs
├── services/
│   ├── template_parser.py   # Parse debconf templates and PO files
│   ├── l10n_debian.py       # Fetch/parse l10n.debian.org data
│   ├── ddtss.py             # DDTSS integration
│   ├── apt_service.py       # Package lookup
│   └── notifier.py          # Change detection and desktop notifications
├── widgets/
│   ├── diff_widget.py       # Side-by-side diff with character highlighting
│   ├── status_badge.py      # Colored status pill widget
│   └── filter_bar.py        # Reusable search + dropdown filter bar
└── data/
    └── *.desktop             # Desktop entry file
```

## i18n

All UI strings are in English and wrapped with `gettext._()` for translation. Swedish translations are provided in `po/sv.po`.

## License

GPL-3.0-or-later
