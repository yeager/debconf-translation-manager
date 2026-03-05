# Debconf Translation Manager

A GTK4/libadwaita application for managing translations of Debian debconf templates.

## Features

### Template Browser
Browse and search debconf templates from packages. View original English strings, template type (select, multiselect, string, boolean, note, text, password), priority, default values, choices, and extended descriptions. Filter by type and priority.

### Translation Status Dashboard
Per-language translation coverage dashboard with summary cards showing translated, fuzzy, and untranslated counts. Progress bar for overall coverage. Filter by language, package, and status. Supports 20+ languages.

### PO Editor
Edit po-debconf translation files with source and translation displayed side by side:
- Fuzzy marking toggle
- Copy source to translation
- Format string validation
- Length constraint warnings
- PO header editor with translator credits (name, email, year)
- Encoding validation

### Review Board
Pull translation coordination data from [l10n.debian.org](https://l10n.debian.org/coordination/sv/sv.by_status.html). Shows packages needing review, pending translations, translator and reviewer info, deadlines, and scores.

### Diff View
Side-by-side comparison of old vs new template strings when templates are updated. Character-level diff highlighting with color coding.

### l10n Coordination
Full l10n.debian.org coordination workflow:
**Unclaimed** → **ITT** → **Translating** → **RFR** → **Under Review** → **LCFC** → **Done**

### BTS Bug Filing
Compose l10n bug reports for the Debian Bug Tracking System:
- Auto-generated subject: `[INTL:sv] Swedish debconf translation for PACKAGE`
- Email preview popup with edit/save
- Submission history log
- Configurable severity and tags
- Gmail SMTP preset

### DDTSS Integration
Submit and review translations via the [Debian Description Translation Server](https://ddtp.debian.org).

### Settings
Persistent preferences for translator identity, language (all 95 Debian debconf languages), BTS defaults, and SMTP configuration.

### Statistics
Cairo-drawn charts: status distribution, per-package scores, cross-language coverage, and coverage timeline.

### Progress Dialog
Reusable progress popup with cancel button for long-running operations.

### Standard Features
- Theme toggle (light/dark/system, Ctrl+T)
- Keyboard shortcuts
- CSV/JSON export
- Copy Debug Info
- Welcome dialog
- Desktop notifications for template changes

## Installation

### From Debian repository

```bash
# Add the repository
curl -fsSL https://yeager.github.io/debian-repo/KEY.gpg | sudo gpg --dearmor -o /usr/share/keyrings/yeager-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/yeager-archive-keyring.gpg] https://yeager.github.io/debian-repo ./" | sudo tee /etc/apt/sources.list.d/yeager.list
sudo apt update
sudo apt install debconf-translation-manager
```

### From source

```bash
git clone https://github.com/yeager/debconf-translation-manager.git
cd debconf-translation-manager
pip install .
```

### Requirements
- Python 3.10+
- GTK 4
- libadwaita 1.x
- PyGObject
- requests
- beautifulsoup4

### CLI mode

```bash
debconf-translation-manager --no-gui          # Print stats
debconf-translation-manager --no-gui --json   # JSON output
debconf-translation-manager --no-gui -q       # Quiet mode
```

## i18n

All UI strings use `gettext`. Translate on [Transifex](https://app.transifex.com/danielnylander/debconf-translator/).

Man page translation uses po4a.

## License

GPL-3.0-or-later

## Author

Daniel Nylander <daniel@danielnylander.se>
