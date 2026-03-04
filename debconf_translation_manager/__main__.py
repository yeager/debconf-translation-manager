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
        "--json", action="store_true", help="Output machine-readable JSON"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress non-essential output"
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run in CLI mode (print stats and exit)",
    )

    args = parser.parse_args()

    if args.no_gui:
        return _cli_mode(args)

    return _gui_mode(args)


def _cli_mode(args: argparse.Namespace) -> int:
    """Print translation statistics and exit."""
    from debconf_translation_manager.services.template_parser import get_mock_templates

    templates = get_mock_templates()
    stats = {
        "app": APP_NAME,
        "version": __version__,
        "template_count": len(templates),
        "packages": list({t["package"] for t in templates}),
    }

    if args.json:
        print(json.dumps(stats, indent=2))
    elif not args.quiet:
        print(f"{APP_NAME} v{__version__}")
        print(f"Templates: {stats['template_count']}")
        print(f"Packages:  {len(stats['packages'])}")

    return 0


def _gui_mode(args: argparse.Namespace) -> int:
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
    return app.run(sys.argv[:1])  # pass only program name to GLib


if __name__ == "__main__":
    raise SystemExit(main())
