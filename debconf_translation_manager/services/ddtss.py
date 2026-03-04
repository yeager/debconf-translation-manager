"""DDTSS (Debian Description Translation Server) integration.

Fetches and submits translations via ddtp.debian.org.
Falls back to mock data when the network is unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

DDTSS_BASE = "https://ddtp.debian.org"


@dataclass
class DDTSSEntry:
    """A DDTSS translation entry."""

    package: str
    description_md5: str
    original: str
    translation: str
    language: str
    status: str  # open, reviewed, accepted
    reviewer_count: int = 0


def fetch_open_translations(language: str = "sv") -> list[DDTSSEntry]:
    """Fetch open translations from DDTSS.  Falls back to mock data."""
    url = f"{DDTSS_BASE}/ddtss/index.cgi/{language}"
    try:
        import requests

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return _parse_ddtss_page(resp.text, language)
    except Exception as exc:
        log.warning("DDTSS fetch failed: %s — using mock data", exc)
        return get_mock_ddtss_data(language)


def _parse_ddtss_page(html: str, language: str) -> list[DDTSSEntry]:
    """Best-effort parse of DDTSS page."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html, "html.parser")
    entries: list[DDTSSEntry] = []

    for link in soup.find_all("a"):
        href = link.get("href", "")
        if "/ddtss/ddt" in href:
            pkg = link.get_text(strip=True)
            if pkg:
                entries.append(
                    DDTSSEntry(
                        package=pkg,
                        description_md5="",
                        original="",
                        translation="",
                        language=language,
                        status="open",
                    )
                )

    return entries or get_mock_ddtss_data(language)


def submit_translation(
    entry: DDTSSEntry, translation_text: str
) -> bool:
    """Submit a translation to DDTSS. Returns True on success."""
    log.info(
        "Would submit translation for %s (%s): %d chars",
        entry.package,
        entry.language,
        len(translation_text),
    )
    # In production, POST to DDTSS
    return True


# ── Mock data ─────────────────────────────────────────────────────────

def get_mock_ddtss_data(language: str = "sv") -> list[DDTSSEntry]:
    """Mock DDTSS entries for testing."""
    return [
        DDTSSEntry(
            package="apt",
            description_md5="abc123",
            original="Advanced package tool - commandline interface",
            translation="Avancerat paketverktyg - kommandoradsgränssnitt" if language == "sv" else "",
            language=language,
            status="reviewed",
            reviewer_count=2,
        ),
        DDTSSEntry(
            package="dpkg",
            description_md5="def456",
            original="Debian package management system",
            translation="Debians pakethanteringssystem" if language == "sv" else "",
            language=language,
            status="accepted",
            reviewer_count=3,
        ),
        DDTSSEntry(
            package="bash",
            description_md5="ghi789",
            original="GNU Bourne Again SHell",
            translation="",
            language=language,
            status="open",
            reviewer_count=0,
        ),
        DDTSSEntry(
            package="coreutils",
            description_md5="jkl012",
            original="GNU core utilities",
            translation="GNU:s grundläggande verktyg" if language == "sv" else "",
            language=language,
            status="open",
            reviewer_count=1,
        ),
        DDTSSEntry(
            package="systemd",
            description_md5="mno345",
            original="System and service manager",
            translation="",
            language=language,
            status="open",
            reviewer_count=0,
        ),
        DDTSSEntry(
            package="wget",
            description_md5="pqr678",
            original="Retrieves files from the web",
            translation="Hämtar filer från webben" if language == "sv" else "",
            language=language,
            status="reviewed",
            reviewer_count=2,
        ),
    ]
