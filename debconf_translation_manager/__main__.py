"""Entry point for debconf-translation-manager."""

from __future__ import annotations

import argparse
import json
import sys

from debconf_translation_manager import __version__, APP_NAME


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="debconf-translation-manager",
        description="Manage translations of Debian debconf templates",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run in CLI mode (print stats and exit)",
    )

    args = parser.parse_args()

    if args.no_gui:
        return _cli_mode()

    return _gui_mode()


def _cli_mode() -> int:
    """Print translation statistics and exit."""
    from debconf_translation_manager.services.l10n_debian import fetch_and_parse

    results = fetch_and_parse()
    total = len(results)
    done = sum(1 for r in results if r.score == 100)
    print(f"{APP_NAME} v{__version__}")
    print(f"Packages: {total}, Translated: {done}, Remaining: {total - done}")
    return 0


def _gui_mode() -> int:
    """Launch the GTK4 GUI."""
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
    except (ImportError, ValueError) as exc:
        print(f"Error: GTK4/libadwaita not available: {exc}", file=sys.stderr)
        return 1

    from debconf_translation_manager.app import DebconfTranslationManagerApp

    app = DebconfTranslationManagerApp()
    return app.run(sys.argv[:1])


if __name__ == "__main__":
    raise SystemExit(main())
