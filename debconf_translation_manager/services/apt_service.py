"""Apt/package lookup service.

Query apt-cache or download templates from packages.debian.org.
Falls back to mock data on non-Debian systems.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

PACKAGES_DEBIAN_BASE = "https://packages.debian.org"


@dataclass
class PackageInfo:
    """Basic package information."""

    name: str
    version: str
    section: str
    priority: str
    description: str
    homepage: str = ""
    maintainer: str = ""
    has_debconf: bool = False


def apt_cache_show(package: str) -> PackageInfo | None:
    """Query apt-cache for package info."""
    try:
        result = subprocess.run(
            ["apt-cache", "show", package],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        return _parse_apt_show(result.stdout, package)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        log.debug("apt-cache unavailable: %s", exc)
        return None


def _parse_apt_show(output: str, package: str) -> PackageInfo:
    fields: dict[str, str] = {}
    for line in output.splitlines():
        if ":" in line and not line.startswith(" "):
            key, sep, val = line.partition(":")
            fields[key.strip()] = val.strip()
    return PackageInfo(
        name=fields.get("Package", package),
        version=fields.get("Version", ""),
        section=fields.get("Section", ""),
        priority=fields.get("Priority", ""),
        description=fields.get("Description", ""),
        homepage=fields.get("Homepage", ""),
        maintainer=fields.get("Maintainer", ""),
    )


def fetch_templates_from_packages_debian(
    package: str, suite: str = "bookworm"
) -> str | None:
    """Download debconf templates from packages.debian.org."""
    url = (
        f"{PACKAGES_DEBIAN_BASE}/{suite}/all/{package}/"
        f"filelist#debconf-templates"
    )
    try:
        import requests

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        # In a real implementation, we'd parse the file list and
        # download the actual templates file.
        return resp.text
    except Exception as exc:
        log.warning("Could not fetch templates for %s: %s", package, exc)
        return None


def lookup_package(package: str) -> PackageInfo:
    """Look up a package, trying apt-cache first, then mock data."""
    info = apt_cache_show(package)
    if info is not None:
        return info
    # Fall back to mock
    return _get_mock_package(package)


def search_packages(query: str) -> list[PackageInfo]:
    """Search for packages matching a query."""
    mock = get_mock_packages()
    q = query.lower()
    return [p for p in mock if q in p.name.lower() or q in p.description.lower()]


# ── Mock data ─────────────────────────────────────────────────────────

def _get_mock_package(name: str) -> PackageInfo:
    for pkg in get_mock_packages():
        if pkg.name == name:
            return pkg
    return PackageInfo(
        name=name,
        version="unknown",
        section="misc",
        priority="optional",
        description=f"Package {name}",
        has_debconf=False,
    )


def get_mock_packages() -> list[PackageInfo]:
    return [
        PackageInfo("locales", "2.36-9", "libs", "required",
                     "GNU C Library: National Language (locale) data", has_debconf=True),
        PackageInfo("tzdata", "2024a-4", "libs", "required",
                     "time zone and daylight-saving time data", has_debconf=True),
        PackageInfo("keyboard-configuration", "1.221", "utils", "optional",
                     "system-wide keyboard preferences", has_debconf=True),
        PackageInfo("console-setup", "1.221", "utils", "optional",
                     "console font and keymap setup program", has_debconf=True),
        PackageInfo("grub-pc", "2.06-13", "admin", "optional",
                     "GRand Unified Bootloader, version 2 (PC/BIOS)", has_debconf=True),
        PackageInfo("dash", "0.5.12-6", "shells", "required",
                     "POSIX-compliant shell", has_debconf=True),
        PackageInfo("popularity-contest", "1.73", "misc", "optional",
                     "Vote for your favourite packages automatically", has_debconf=True),
        PackageInfo("dictionaries-common", "1.28.14", "text", "optional",
                     "Common utilities for spelling dictionary tools", has_debconf=True),
        PackageInfo("debconf", "1.5.82", "admin", "required",
                     "Debian configuration management system", has_debconf=True),
        PackageInfo("samba-common", "4.17.12", "net", "optional",
                     "common files used by both the Samba server and client", has_debconf=True),
        PackageInfo("wireshark-common", "4.0.11-1", "net", "optional",
                     "network traffic analyzer - common files", has_debconf=True),
        PackageInfo("libc6", "2.36-9", "libs", "required",
                     "GNU C Library: Shared libraries", has_debconf=True),
        PackageInfo("ca-certificates", "20230311", "misc", "optional",
                     "Common CA certificates", has_debconf=True),
        PackageInfo("cloud-init", "23.3.1-1", "admin", "optional",
                     "initialization and customization tool for cloud instances", has_debconf=True),
        PackageInfo("openssh-server", "9.2p1-2", "net", "optional",
                     "secure shell (SSH) server", has_debconf=True),
    ]
