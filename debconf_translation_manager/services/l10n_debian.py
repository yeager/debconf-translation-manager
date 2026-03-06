"""Fetch and parse translation data from www.debian.org/international/l10n/po-debconf."""

from __future__ import annotations

import gzip
import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class L10nPackageStatus:
    """Status of a single package's translation."""

    package: str
    language: str
    score: int = 0
    translated: int = 0
    fuzzy: int = 0
    untranslated: int = 0
    total: int = 0
    po_url: str = ""
    translator: str = ""
    bug_number: str = ""
    status: str = ""  # translated, fuzzy, untranslated

    def __post_init__(self) -> None:
        if self.total == 0:
            self.total = self.translated + self.fuzzy + self.untranslated


# ── Fetch page ─────────────────────────────────────────────────────────

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


# ── Parse page ─────────────────────────────────────────────────────────

def parse_podebconf_html(html: str, language: str = "sv") -> list[L10nPackageStatus]:
    """Parse the Debian po-debconf statistics page.

    Extracts:
    - "To do" section: packages with no translation
    - Table rows with score (Nt;Nf;Nu): packages with partial/full translations
    """
    results: list[L10nPackageStatus] = []

    # Parse "to do" packages
    todo_section = re.search(
        r'<h2[^>]*>.*?[Tt]o do.*?</h2>(.*?)(?=<h2|$)', html, re.DOTALL
    )
    if todo_section:
        todo_text = todo_section.group(1)
        todo_entries = re.findall(
            r'pot#([^"]+)"[^>]*>[^<]*</a>(?:&nbsp;|\s)*\((\d+)\)', todo_text
        )
        for pkg, count in todo_entries:
            results.append(
                L10nPackageStatus(
                    package=pkg,
                    language=language,
                    score=0,
                    translated=0,
                    fuzzy=0,
                    untranslated=int(count),
                    status="untranslated",
                )
            )

    # Parse table rows with scores
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        score_match = re.search(r'(\d+)%\s*\((\d+)t;(\d+)f;(\d+)u\)', row)
        if not score_match:
            continue

        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if not tds:
            continue

        pkg = re.sub(r'<[^>]+>', '', tds[0])
        pkg = pkg.replace('&nbsp;', ' ').replace('!', '').strip()
        if not pkg:
            continue

        score = int(score_match.group(1))
        translated = int(score_match.group(2))
        fuzzy_count = int(score_match.group(3))
        untranslated = int(score_match.group(4))

        po_match = re.search(r'href="(https://i18n\.debian\.org/[^"]+\.po\.gz)"', row)
        po_url = po_match.group(1) if po_match else ""

        translator = ""
        if len(tds) >= 4:
            translator = re.sub(r'<[^>]+>', '', tds[3]).strip()

        bug_number = ""
        bug_match = re.search(r'bugs\.debian\.org/(\d+)', row)
        if bug_match:
            bug_number = bug_match.group(1)

        if score == 100:
            status = "translated"
        elif fuzzy_count > 0 and untranslated == 0:
            status = "fuzzy"
        else:
            status = "untranslated"

        results.append(
            L10nPackageStatus(
                package=pkg,
                language=language,
                score=score,
                translated=translated,
                fuzzy=fuzzy_count,
                untranslated=untranslated,
                po_url=po_url,
                translator=translator,
                bug_number=bug_number,
                status=status,
            )
        )

    return results


# ── Download .po files ─────────────────────────────────────────────────

def download_po_file(url: str, dest_dir: str | None = None) -> str | None:
    """Download a .po or .po.gz file and return the local path."""
    try:
        import requests
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        log.error("Failed to download %s: %s", url, exc)
        return None

    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix="debconf-l10n-")

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

def fetch_and_parse(language: str = "sv") -> list[L10nPackageStatus]:
    """Fetch and parse data, returning list of package statuses."""
    html = fetch_podebconf_page(language)
    if html:
        results = parse_podebconf_html(html, language)
        if results:
            return results
    return []


# ── Ranking page for comparisons ───────────────────────────────────────

def fetch_ranking_page() -> str | None:
    """Fetch the po-debconf ranking page."""
    url = "https://www.debian.org/international/l10n/po-debconf/rank"
    try:
        import requests
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        log.warning("Failed to fetch ranking: %s", exc)
        return None


def parse_ranking_html(html: str) -> list[dict]:
    """Parse ranking page, return list of {rank, language, score}."""
    results = []
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(tds) >= 3:
            rank_text = re.sub(r'<[^>]+>', '', tds[0]).strip()
            lang_match = re.search(r'po-debconf/([^"]+)"', tds[1])
            score_text = re.sub(r'<[^>]+>', '', tds[2]).strip()
            if rank_text.isdigit() and lang_match:
                results.append({
                    "rank": int(rank_text),
                    "language": lang_match.group(1),
                    "score": score_text,
                })
    return results
