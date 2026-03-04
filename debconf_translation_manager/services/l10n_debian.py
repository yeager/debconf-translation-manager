"""Fetch and parse translation coordination data from l10n.debian.org."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class L10nPackageStatus:
    """Status of a package on l10n.debian.org."""

    package: str
    status: str  # translated, untranslated, fuzzy, pending-review, etc.
    language: str
    translator: str = ""
    reviewer: str = ""
    date: str = ""
    deadline: str = ""
    bug_number: str = ""
    score: int = 0


def fetch_status_page(language: str = "sv", by: str = "status") -> str | None:
    """Fetch HTML from l10n.debian.org coordination page.

    Returns None on network error (allows fallback to mock data).
    """
    url = f"https://l10n.debian.org/coordination/{language}/{language}.by_{by}.html"
    try:
        import requests

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        log.warning("Failed to fetch %s: %s", url, exc)
        return None


def parse_status_html(html: str, language: str = "sv") -> list[L10nPackageStatus]:
    """Parse an l10n.debian.org status page HTML into structured data."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup4 not installed, cannot parse HTML")
        return []

    soup = BeautifulSoup(html, "html.parser")
    results: list[L10nPackageStatus] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Try to detect columns from header
        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

        for row in rows[1:]:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 2:
                continue

            pkg = cols[0] if cols else ""
            status = cols[1] if len(cols) > 1 else ""
            translator = cols[2] if len(cols) > 2 else ""
            date = cols[3] if len(cols) > 3 else ""

            if pkg:
                results.append(
                    L10nPackageStatus(
                        package=pkg,
                        status=status,
                        language=language,
                        translator=translator,
                        date=date,
                    )
                )

    return results


def fetch_and_parse(language: str = "sv", by: str = "status") -> list[L10nPackageStatus]:
    """Fetch and parse, falling back to mock data on error."""
    html = fetch_status_page(language, by)
    if html:
        results = parse_status_html(html, language)
        if results:
            return results
    return get_mock_l10n_data(language)


# ── Mock data ─────────────────────────────────────────────────────────

def get_mock_l10n_data(language: str = "sv") -> list[L10nPackageStatus]:
    """Return mock l10n.debian.org data for testing."""
    return [
        L10nPackageStatus(
            package="locales",
            status="translated",
            language=language,
            translator="Anders Jonsson",
            reviewer="Sebastian Rasmussen",
            date="2025-12-01",
            score=100,
        ),
        L10nPackageStatus(
            package="tzdata",
            status="translated",
            language=language,
            translator="Anders Jonsson",
            reviewer="",
            date="2025-11-15",
            score=100,
        ),
        L10nPackageStatus(
            package="keyboard-configuration",
            status="fuzzy",
            language=language,
            translator="Martin Bagge",
            reviewer="",
            date="2025-10-20",
            score=75,
        ),
        L10nPackageStatus(
            package="grub-pc",
            status="pending-review",
            language=language,
            translator="Daniel Nylander",
            reviewer="",
            date="2026-01-10",
            deadline="2026-02-10",
            score=95,
        ),
        L10nPackageStatus(
            package="console-setup",
            status="untranslated",
            language=language,
            translator="",
            reviewer="",
            date="",
            score=0,
        ),
        L10nPackageStatus(
            package="samba-common",
            status="untranslated",
            language=language,
            translator="",
            reviewer="",
            date="",
            score=0,
        ),
        L10nPackageStatus(
            package="popularity-contest",
            status="pending-review",
            language=language,
            translator="Sebastian Rasmussen",
            reviewer="",
            date="2026-01-22",
            deadline="2026-02-22",
            score=90,
        ),
        L10nPackageStatus(
            package="dash",
            status="translated",
            language=language,
            translator="Martin Bagge",
            reviewer="Anders Jonsson",
            date="2025-09-05",
            score=100,
        ),
        L10nPackageStatus(
            package="dictionaries-common",
            status="fuzzy",
            language=language,
            translator="Daniel Nylander",
            reviewer="",
            date="2025-08-12",
            score=60,
        ),
        L10nPackageStatus(
            package="debconf",
            status="translated",
            language=language,
            translator="Martin Bagge",
            reviewer="Daniel Nylander",
            date="2025-11-01",
            score=100,
        ),
        L10nPackageStatus(
            package="wireshark-common",
            status="pending-review",
            language=language,
            translator="Anders Jonsson",
            reviewer="",
            date="2026-02-01",
            deadline="2026-03-01",
            score=85,
        ),
        L10nPackageStatus(
            package="libc6",
            status="fuzzy",
            language=language,
            translator="Daniel Nylander",
            reviewer="",
            date="2025-07-20",
            score=40,
        ),
        L10nPackageStatus(
            package="ca-certificates",
            status="translated",
            language=language,
            translator="Sebastian Rasmussen",
            reviewer="Martin Bagge",
            date="2025-12-15",
            score=100,
        ),
        L10nPackageStatus(
            package="cloud-init",
            status="untranslated",
            language=language,
            translator="",
            reviewer="",
            date="",
            score=0,
        ),
        L10nPackageStatus(
            package="openssh-server",
            status="translated",
            language=language,
            translator="Anders Jonsson",
            reviewer="Sebastian Rasmussen",
            date="2025-10-30",
            score=100,
        ),
    ]
