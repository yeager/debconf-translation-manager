"""Fetch and parse translation coordination data from l10n.debian.org."""

from __future__ import annotations

import gzip
import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
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
    translated: int = 0
    fuzzy: int = 0
    untranslated: int = 0
    po_url: str = ""
    pot_url: str = ""


# ── Coordination page (l10n.debian.org/coordination/) ──────────────────

def fetch_status_page(language: str = "sv", by: str = "status") -> str | None:
    """Fetch HTML from l10n.debian.org coordination page.

    Returns None on network error (allows fallback to mock data).
    """
    url = f"https://l10n.debian.org/coordination/{_lang_to_dir(language)}/{language}.by_{by}.html"
    try:
        import requests

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        log.warning("Failed to fetch %s: %s", url, exc)
        return None


_LANG_DIR_MAP = {
    "sv": "swedish",
    "de": "german",
    "fr": "french",
    "es": "spanish",
    "it": "italian",
    "nl": "dutch",
    "pt_BR": "brazilian",
    "ru": "russian",
    "cs": "czech",
    "da": "danish",
    "ca": "catalan",
    "ar": "arabic",
    "id": "indonesian",
    "ro": "romanian",
    "sk": "slovak",
    "tr": "turkish",
    "gl": "galician",
    "fa": "persian",
}


def _lang_to_dir(lang: str) -> str:
    return _LANG_DIR_MAP.get(lang, lang)


def parse_coordination_html(html: str, language: str = "sv") -> list[L10nPackageStatus]:
    """Parse an l10n.debian.org coordination status page HTML.

    The page has one table with tbody sections per status.
    Each status section starts with an h3 header row, then data rows.
    Columns: Package, Type, File, Translator, Status, Date, Message, Bug
    """
    results: list[L10nPackageStatus] = []
    current_status = ""

    for line in html.splitlines():
        line = line.strip()

        # Detect status section headers: <h3 id="bts">
        h3_match = re.search(r'<h3\s+id="(\w+)">', line)
        if h3_match:
            current_status = h3_match.group(1)
            continue

        # Skip non-data rows
        if not line.startswith("<tr") or 'colspan' in line:
            continue

        # Parse data rows
        cols = re.findall(r'<td[^>]*>(.*?)</td>', line, re.DOTALL)
        if len(cols) < 5:
            continue

        package = re.sub(r'<[^>]+>', '', cols[0]).strip()
        if not package:
            continue

        translator = re.sub(r'<[^>]+>', '', cols[3]).strip()
        date = re.sub(r'<[^>]+>', '', cols[5]).strip() if len(cols) > 5 else ""

        bug_number = ""
        if len(cols) > 7:
            bug_match = re.search(r'#(\d+)', cols[7])
            if bug_match:
                bug_number = bug_match.group(1)

        # Map coordination statuses to display statuses
        display_status = _coordination_status_map(current_status)

        results.append(
            L10nPackageStatus(
                package=package,
                status=display_status,
                language=language,
                translator=translator,
                date=date[:10] if date else "",
                bug_number=bug_number,
            )
        )

    return results


def _coordination_status_map(status: str) -> str:
    """Map l10n coordination pseudo-url status to display status."""
    mapping = {
        "taf": "untranslated",
        "maj": "untranslated",
        "itt": "in-progress",
        "itr": "in-progress",
        "rfr": "pending-review",
        "lcfc": "pending-review",
        "bts": "filed",
        "fix": "translated",
        "done": "translated",
        "wontfix": "wontfix",
        "hold": "hold",
    }
    return mapping.get(status, status)


# ── Debian l10n po-debconf statistics page ─────────────────────────────

def fetch_podebconf_page(language: str = "sv") -> str | None:
    """Fetch the po-debconf statistics page from debian.org."""
    url = f"https://www.debian.org/international/l10n/po-debconf/{language}"
    try:
        import requests

        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        log.warning("Failed to fetch %s: %s", url, exc)
        return None


def parse_podebconf_html(html: str, language: str = "sv") -> list[L10nPackageStatus]:
    """Parse the Debian po-debconf statistics page.

    This page has:
    - "Packages to do" section: packages with no translation yet
    - "Packages underway/done": tables with score, .po download links, translator
    """
    results: list[L10nPackageStatus] = []

    # Parse "to do" packages (need new translation)
    todo_section = re.search(
        r'<h2[^>]*>.*?[Tt]o do.*?</h2>(.*?)(?=<h2|$)', html, re.DOTALL
    )
    if todo_section:
        todo_text = todo_section.group(1)
        # Pattern: pot#PACKAGE ... (N) — may have &nbsp; between link and count
        todo_entries = re.findall(r'pot#([^"]+)"[^>]*>[^<]*</a>[&nbsp;\s]*\((\d+)\)', todo_text)
        for pkg, count in todo_entries:
            results.append(
                L10nPackageStatus(
                    package=pkg,
                    status="untranslated",
                    language=language,
                    score=0,
                    translated=0,
                    fuzzy=0,
                    untranslated=int(count),
                )
            )

    # Parse table rows with .po.gz links (underway + done)
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        if '.po.gz' not in row:
            continue

        pkg_match = re.search(r'data=([^"&]+)[^>]*>([^<]+)</a>', row)
        score_match = re.search(r'(\d+)%\s*\((\d+)t;(\d+)f;(\d+)u\)', row)
        po_match = re.search(r'href="(https://i18n\.debian\.org/[^"]+\.po\.gz)"', row)

        if not pkg_match or not score_match:
            continue

        pkg = pkg_match.group(2).strip()
        score = int(score_match.group(1))
        translated = int(score_match.group(2))
        fuzzy_count = int(score_match.group(3))
        untranslated = int(score_match.group(4))
        po_url = po_match.group(1) if po_match else ""

        # Extract translator (first non-score td after the po link)
        tds = re.findall(r'<td>([^<]*)</td>', row)
        translator = ""
        for td in tds:
            td = td.strip()
            if td and '%' not in td and 'http' not in td:
                translator = td
                break

        if score == 100:
            status = "translated"
        elif fuzzy_count > 0 and untranslated == 0:
            status = "fuzzy"
        elif untranslated > 0:
            status = "untranslated"
        else:
            status = "translated"

        results.append(
            L10nPackageStatus(
                package=pkg,
                status=status,
                language=language,
                translator=translator,
                score=score,
                translated=translated,
                fuzzy=fuzzy_count,
                untranslated=untranslated,
                po_url=po_url,
            )
        )

    return results


# ── Download .po files ─────────────────────────────────────────────────

def download_po_file(url: str, dest_dir: str | None = None) -> str | None:
    """Download a .po or .po.gz file and return the local path.

    If url ends in .gz, decompress automatically.
    Returns the path to the saved .po file, or None on error.
    """
    try:
        import requests

        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        log.error("Failed to download %s: %s", url, exc)
        return None

    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix="debconf-l10n-")

    # Determine filename from URL
    filename = url.rsplit("/", 1)[-1]
    if filename.endswith(".gz"):
        filename = filename[:-3]

    dest_path = str(Path(dest_dir) / filename)

    try:
        if url.endswith(".gz"):
            content = gzip.decompress(resp.content)
            with open(dest_path, "wb") as f:
                f.write(content)
        else:
            with open(dest_path, "wb") as f:
                f.write(resp.content)
    except Exception as exc:
        log.error("Failed to save %s: %s", dest_path, exc)
        return None

    log.info("Downloaded PO file to %s", dest_path)
    return dest_path


# ── Combined fetch & parse ─────────────────────────────────────────────

def fetch_and_parse(language: str = "sv", by: str = "status") -> list[L10nPackageStatus]:
    """Fetch and parse real data, falling back to mock data on error."""
    # Try the po-debconf stats page first (has .po download links)
    html = fetch_podebconf_page(language)
    if html:
        results = parse_podebconf_html(html, language)
        if results:
            return results

    # Fall back to coordination page
    html = fetch_status_page(language, by)
    if html:
        results = parse_coordination_html(html, language)
        if results:
            return results

    return get_mock_l10n_data(language)


def fetch_coordination_data(language: str = "sv") -> list[L10nPackageStatus]:
    """Fetch coordination page data (ITT/RFR/BTS workflow status)."""
    html = fetch_status_page(language, "status")
    if html:
        results = parse_coordination_html(html, language)
        if results:
            return results
    return []


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
            translated=10,
        ),
        L10nPackageStatus(
            package="tzdata",
            status="translated",
            language=language,
            translator="Anders Jonsson",
            reviewer="",
            date="2025-11-15",
            score=100,
            translated=8,
        ),
        L10nPackageStatus(
            package="keyboard-configuration",
            status="fuzzy",
            language=language,
            translator="Martin Bagge",
            reviewer="",
            date="2025-10-20",
            score=75,
            translated=6,
            fuzzy=2,
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
            translated=19,
            fuzzy=1,
        ),
        L10nPackageStatus(
            package="console-setup",
            status="untranslated",
            language=language,
            translator="",
            reviewer="",
            date="",
            score=0,
            untranslated=5,
        ),
        L10nPackageStatus(
            package="samba-common",
            status="untranslated",
            language=language,
            translator="",
            reviewer="",
            date="",
            score=0,
            untranslated=3,
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
            translated=9,
            fuzzy=1,
        ),
        L10nPackageStatus(
            package="dash",
            status="translated",
            language=language,
            translator="Martin Bagge",
            reviewer="Anders Jonsson",
            date="2025-09-05",
            score=100,
            translated=5,
        ),
        L10nPackageStatus(
            package="dictionaries-common",
            status="fuzzy",
            language=language,
            translator="Daniel Nylander",
            reviewer="",
            date="2025-08-12",
            score=60,
            translated=3,
            fuzzy=2,
        ),
        L10nPackageStatus(
            package="debconf",
            status="translated",
            language=language,
            translator="Martin Bagge",
            reviewer="Daniel Nylander",
            date="2025-11-01",
            score=100,
            translated=12,
        ),
    ]
