"""Parse debconf templates and PO files.

Provides both real parsing and mock data for testing without network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DebconfTemplate:
    """A single debconf template entry."""

    package: str
    template_name: str
    template_type: str  # select, multiselect, string, boolean, note, text, password
    priority: str  # low, medium, high, critical
    default: str = ""
    description: str = ""
    extended_description: str = ""
    choices: list[str] = field(default_factory=list)


@dataclass
class POEntry:
    """A single PO file entry."""

    msgid: str
    msgstr: str = ""
    msgid_plural: str = ""
    msgstr_plural: dict[int, str] = field(default_factory=dict)
    context: str = ""
    comment: str = ""
    translator_comment: str = ""
    flags: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    obsolete: bool = False

    @property
    def is_translated(self) -> bool:
        return bool(self.msgstr.strip())

    @property
    def is_fuzzy(self) -> bool:
        return "fuzzy" in self.flags


def parse_templates_file(content: str) -> list[DebconfTemplate]:
    """Parse a Debian debconf templates file."""
    templates: list[DebconfTemplate] = []
    current: dict[str, Any] = {}

    for line in content.splitlines():
        line_stripped = line.rstrip()

        if not line_stripped:
            if current:
                templates.append(_dict_to_template(current))
                current = {}
            continue

        if line_stripped.startswith(" "):
            # Continuation line
            if "extended_description" not in current:
                current["extended_description"] = ""
            text = line_stripped.strip()
            if text == ".":
                current["extended_description"] += "\n\n"
            else:
                current["extended_description"] += text + " "
            continue

        if ":" in line_stripped:
            key, sep, value = line_stripped.partition(":")
            key = key.strip().lower().replace("-", "_")
            value = value.strip()

            if key == "template":
                current["template_name"] = value
            elif key == "type":
                current["template_type"] = value
            elif key == "default":
                current["default"] = value
            elif key == "description":
                current["description"] = value
            elif key == "choices":
                current["choices"] = [c.strip() for c in value.split(",")]
            elif key == "priority":
                current["priority"] = value

    if current:
        templates.append(_dict_to_template(current))

    return templates


def _dict_to_template(d: dict[str, Any]) -> DebconfTemplate:
    name = d.get("template_name", "unknown")
    pkg = name.split("/")[0] if "/" in name else "unknown"
    return DebconfTemplate(
        package=pkg,
        template_name=name,
        template_type=d.get("template_type", "string"),
        priority=d.get("priority", "medium"),
        default=d.get("default", ""),
        description=d.get("description", ""),
        extended_description=d.get("extended_description", "").strip(),
        choices=d.get("choices", []),
    )


def parse_po_file(content: str) -> list[POEntry]:
    """Parse a PO file into a list of POEntry objects."""
    entries: list[POEntry] = []
    current_entry: dict[str, Any] = {}
    current_field: str = ""

    for raw_line in content.splitlines():
        line = raw_line.rstrip()

        # Translator comment
        if line.startswith("# "):
            current_entry.setdefault("translator_comment", "")
            current_entry["translator_comment"] += line[2:] + "\n"
            continue

        # Extracted / reference comments
        if line.startswith("#. "):
            current_entry.setdefault("comment", "")
            current_entry["comment"] += line[3:] + "\n"
            continue

        if line.startswith("#: "):
            current_entry.setdefault("references", [])
            current_entry["references"].extend(line[3:].split())
            continue

        if line.startswith("#, "):
            current_entry.setdefault("flags", [])
            current_entry["flags"].extend(
                f.strip() for f in line[3:].split(",")
            )
            continue

        if line.startswith("#~ "):
            current_entry["obsolete"] = True
            line = line[3:]

        # msgid
        match = re.match(r'^msgid\s+"(.*)"$', line)
        if match:
            if current_entry.get("msgid") is not None and current_entry["msgid"] != "":
                entries.append(_dict_to_po_entry(current_entry))
                current_entry = {}
            current_entry["msgid"] = _unescape(match.group(1))
            current_field = "msgid"
            continue

        # msgid_plural
        match = re.match(r'^msgid_plural\s+"(.*)"$', line)
        if match:
            current_entry["msgid_plural"] = _unescape(match.group(1))
            current_field = "msgid_plural"
            continue

        # msgstr
        match = re.match(r'^msgstr\s+"(.*)"$', line)
        if match:
            current_entry["msgstr"] = _unescape(match.group(1))
            current_field = "msgstr"
            continue

        # msgstr[n]
        match = re.match(r'^msgstr\[(\d+)\]\s+"(.*)"$', line)
        if match:
            idx = int(match.group(1))
            current_entry.setdefault("msgstr_plural", {})[idx] = _unescape(
                match.group(2)
            )
            current_field = f"msgstr_plural_{idx}"
            continue

        # Continuation string
        match = re.match(r'^"(.*)"$', line)
        if match:
            text = _unescape(match.group(1))
            if current_field == "msgid":
                current_entry["msgid"] = current_entry.get("msgid", "") + text
            elif current_field == "msgstr":
                current_entry["msgstr"] = current_entry.get("msgstr", "") + text
            elif current_field == "msgid_plural":
                current_entry["msgid_plural"] = (
                    current_entry.get("msgid_plural", "") + text
                )
            elif current_field.startswith("msgstr_plural_"):
                idx = int(current_field.split("_")[-1])
                current_entry.setdefault("msgstr_plural", {})[idx] = (
                    current_entry.get("msgstr_plural", {}).get(idx, "") + text
                )
            continue

        # Blank line — end of entry
        if not line.strip():
            if current_entry.get("msgid") is not None:
                entries.append(_dict_to_po_entry(current_entry))
                current_entry = {}
                current_field = ""

    if current_entry.get("msgid") is not None:
        entries.append(_dict_to_po_entry(current_entry))

    return entries


def _dict_to_po_entry(d: dict[str, Any]) -> POEntry:
    return POEntry(
        msgid=d.get("msgid", ""),
        msgstr=d.get("msgstr", ""),
        msgid_plural=d.get("msgid_plural", ""),
        msgstr_plural=d.get("msgstr_plural", {}),
        context=d.get("context", ""),
        comment=d.get("comment", "").strip(),
        translator_comment=d.get("translator_comment", "").strip(),
        flags=d.get("flags", []),
        references=d.get("references", []),
        obsolete=d.get("obsolete", False),
    )


def _unescape(s: str) -> str:
    return s.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def po_entry_to_string(entry: POEntry) -> str:
    """Serialize a POEntry back to PO format."""
    lines: list[str] = []
    if entry.translator_comment:
        for cl in entry.translator_comment.splitlines():
            lines.append(f"# {cl}")
    if entry.comment:
        for cl in entry.comment.splitlines():
            lines.append(f"#. {cl}")
    for ref in entry.references:
        lines.append(f"#: {ref}")
    if entry.flags:
        lines.append(f"#, {', '.join(entry.flags)}")
    lines.append(f'msgid "{_escape(entry.msgid)}"')
    if entry.msgid_plural:
        lines.append(f'msgid_plural "{_escape(entry.msgid_plural)}"')
        for idx in sorted(entry.msgstr_plural.keys()):
            lines.append(f'msgstr[{idx}] "{_escape(entry.msgstr_plural[idx])}"')
    else:
        lines.append(f'msgstr "{_escape(entry.msgstr)}"')
    return "\n".join(lines)


# ── Mock/sample data ──────────────────────────────────────────────────

def get_mock_templates() -> list[dict[str, Any]]:
    """Return mock debconf template data for testing."""
    return [
        {
            "package": "locales",
            "template_name": "locales/locales_to_be_generated",
            "template_type": "multiselect",
            "priority": "high",
            "default": "en_US.UTF-8 UTF-8",
            "description": "Locales to be generated",
            "extended_description": (
                "Select the locales you want to be generated. The selection "
                "will be saved to '/etc/locale.gen'. The selected locales will "
                "be generated when you finish configuring locales."
            ),
            "choices": ["All locales", "aa_DJ ISO-8859-1", "en_US.UTF-8 UTF-8", "sv_SE.UTF-8 UTF-8"],
        },
        {
            "package": "locales",
            "template_name": "locales/default_environment_locale",
            "template_type": "select",
            "priority": "high",
            "default": "None",
            "description": "Default locale for the system environment",
            "extended_description": (
                "Select the default locale for the system environment. This "
                "will be the default language/locale for all programs and "
                "services, unless overridden individually."
            ),
            "choices": ["None", "C.UTF-8", "en_US.UTF-8", "sv_SE.UTF-8"],
        },
        {
            "package": "tzdata",
            "template_name": "tzdata/Areas",
            "template_type": "select",
            "priority": "high",
            "default": "Etc",
            "description": "Geographic area",
            "extended_description": (
                "Please select the geographic area in which you live. "
                "Subsequent configuration questions will narrow this down "
                "by presenting a list of cities, representing the time "
                "zones in which they are located."
            ),
            "choices": ["Africa", "America", "Asia", "Europe", "Pacific"],
        },
        {
            "package": "tzdata",
            "template_name": "tzdata/Zones/Europe",
            "template_type": "select",
            "priority": "high",
            "default": "London",
            "description": "Time zone",
            "extended_description": "Please select the city or region corresponding to your time zone.",
            "choices": ["Amsterdam", "Berlin", "London", "Paris", "Stockholm"],
        },
        {
            "package": "keyboard-configuration",
            "template_name": "keyboard-configuration/model",
            "template_type": "select",
            "priority": "medium",
            "default": "pc105",
            "description": "Keyboard model",
            "extended_description": (
                "Please select the model of the keyboard of this machine."
            ),
            "choices": ["pc104", "pc105", "macintosh"],
        },
        {
            "package": "keyboard-configuration",
            "template_name": "keyboard-configuration/layout",
            "template_type": "select",
            "priority": "high",
            "default": "us",
            "description": "Keyboard layout",
            "extended_description": (
                "Please select the layout matching the keyboard for this machine."
            ),
            "choices": ["English (US)", "Swedish", "German", "French"],
        },
        {
            "package": "console-setup",
            "template_name": "console-setup/charmap47",
            "template_type": "select",
            "priority": "low",
            "default": "UTF-8",
            "description": "Character set to support",
            "extended_description": (
                "Choose the character set to use for the console."
            ),
            "choices": ["UTF-8", "ISO-8859-1", "ISO-8859-15"],
        },
        {
            "package": "grub-pc",
            "template_name": "grub-pc/install_devices",
            "template_type": "multiselect",
            "priority": "critical",
            "default": "",
            "description": "GRUB install devices",
            "extended_description": (
                "The grub-pc package is being upgraded. This menu allows you "
                "to select which devices you'd like grub-install to be "
                "automatically run for, if any."
            ),
            "choices": [],
        },
        {
            "package": "grub-pc",
            "template_name": "grub-pc/install_devices_empty",
            "template_type": "boolean",
            "priority": "critical",
            "default": "false",
            "description": "Continue without installing GRUB?",
            "extended_description": (
                "You chose not to install GRUB to any devices. If you "
                "continue, the boot loader may not be properly configured."
            ),
            "choices": [],
        },
        {
            "package": "dash",
            "template_name": "dash/sh",
            "template_type": "boolean",
            "priority": "high",
            "default": "true",
            "description": "Use dash as the default system shell (/bin/sh)?",
            "extended_description": (
                "The system shell is the default command interpreter for "
                "shell scripts. Using dash as the system shell will improve "
                "the system's overall performance."
            ),
            "choices": [],
        },
        {
            "package": "popularity-contest",
            "template_name": "popularity-contest/participate",
            "template_type": "boolean",
            "priority": "medium",
            "default": "false",
            "description": "Participate in the package usage survey?",
            "extended_description": (
                "The system may anonymously supply statistics about the most "
                "used packages. This information helps Debian improve future "
                "releases and prioritize porting efforts."
            ),
            "choices": [],
        },
        {
            "package": "dictionaries-common",
            "template_name": "dictionaries-common/default-wordlist",
            "template_type": "select",
            "priority": "medium",
            "default": "",
            "description": "System default wordlist",
            "extended_description": (
                "Please indicate the default wordlist for the system."
            ),
            "choices": ["american (American English)", "swedish (Swedish)"],
        },
        {
            "package": "debconf",
            "template_name": "debconf/frontend",
            "template_type": "select",
            "priority": "medium",
            "default": "Dialog",
            "description": "Interface to use for configuring packages",
            "extended_description": (
                "Packages that use debconf for configuration share a common "
                "look and feel. You can select the type of user interface "
                "they use."
            ),
            "choices": ["Dialog", "Readline", "Gnome", "Kde", "Editor", "Noninteractive"],
        },
        {
            "package": "debconf",
            "template_name": "debconf/priority",
            "template_type": "select",
            "priority": "medium",
            "default": "high",
            "description": "Ignore questions with a priority less than...",
            "extended_description": (
                "Debconf prioritizes the questions it asks. Only questions "
                "with a certain priority or higher are actually shown to you."
            ),
            "choices": ["critical", "high", "medium", "low"],
        },
        {
            "package": "samba-common",
            "template_name": "samba-common/workgroup",
            "template_type": "string",
            "priority": "high",
            "default": "WORKGROUP",
            "description": "Workgroup/Domain Name",
            "extended_description": (
                "Please specify the workgroup you want this server to appear to be in."
            ),
            "choices": [],
        },
        {
            "package": "wireshark-common",
            "template_name": "wireshark-common/install-setuid",
            "template_type": "boolean",
            "priority": "high",
            "default": "false",
            "description": "Should non-superusers be able to capture packets?",
            "extended_description": (
                "Dumpcap can be installed in a way that allows members of the "
                '"wireshark" system group to capture packets.'
            ),
            "choices": [],
        },
        {
            "package": "libc6",
            "template_name": "glibc/upgrade",
            "template_type": "note",
            "priority": "critical",
            "default": "",
            "description": "Restart services during package upgrades without asking?",
            "extended_description": (
                "There are services installed on your system which need to be "
                "restarted when certain libraries are upgraded. Since these "
                "restarts may cause interruptions, you can choose to be "
                "prompted on each upgrade."
            ),
            "choices": [],
        },
        {
            "package": "ca-certificates",
            "template_name": "ca-certificates/trust_new_crts",
            "template_type": "select",
            "priority": "medium",
            "default": "yes",
            "description": "Trust new certificates from certificate authorities?",
            "extended_description": (
                "New CA certificates added by the package maintainer can be "
                "automatically trusted."
            ),
            "choices": ["yes", "no", "ask"],
        },
    ]


def get_mock_po_entries(lang: str = "sv") -> list[dict[str, str]]:
    """Return mock PO entries for testing the editor."""
    entries = [
        {
            "msgid": "Locales to be generated",
            "msgstr": "Lokalanpassningar att generera" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: multiselect\nDescription",
            "reference": "locales/locales_to_be_generated",
        },
        {
            "msgid": "Default locale for the system environment",
            "msgstr": "Standardlokal för systemmiljön" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: select\nDescription",
            "reference": "locales/default_environment_locale",
        },
        {
            "msgid": "Geographic area",
            "msgstr": "Geografiskt område" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: select\nDescription",
            "reference": "tzdata/Areas",
        },
        {
            "msgid": "Time zone",
            "msgstr": "Tidszon" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: select\nDescription",
            "reference": "tzdata/Zones/Europe",
        },
        {
            "msgid": "Keyboard model",
            "msgstr": "",
            "flags": "fuzzy",
            "comment": "Type: select\nDescription",
            "reference": "keyboard-configuration/model",
        },
        {
            "msgid": "Keyboard layout",
            "msgstr": "Tangentbordslayout" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: select\nDescription",
            "reference": "keyboard-configuration/layout",
        },
        {
            "msgid": "Character set to support",
            "msgstr": "",
            "flags": "",
            "comment": "Type: select\nDescription",
            "reference": "console-setup/charmap47",
        },
        {
            "msgid": "GRUB install devices",
            "msgstr": "Installationsenheter för GRUB" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: multiselect\nDescription",
            "reference": "grub-pc/install_devices",
        },
        {
            "msgid": "Continue without installing GRUB?",
            "msgstr": "Fortsätt utan att installera GRUB?" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: boolean\nDescription",
            "reference": "grub-pc/install_devices_empty",
        },
        {
            "msgid": "Use dash as the default system shell (/bin/sh)?",
            "msgstr": "Använd dash som standardsystemskal (/bin/sh)?" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: boolean\nDescription",
            "reference": "dash/sh",
        },
        {
            "msgid": "Participate in the package usage survey?",
            "msgstr": "",
            "flags": "",
            "comment": "Type: boolean\nDescription",
            "reference": "popularity-contest/participate",
        },
        {
            "msgid": "System default wordlist",
            "msgstr": "Systemets standardordlista" if lang == "sv" else "",
            "flags": "fuzzy",
            "comment": "Type: select\nDescription",
            "reference": "dictionaries-common/default-wordlist",
        },
        {
            "msgid": "Interface to use for configuring packages",
            "msgstr": "Gränssnitt att använda för paketkonfiguration" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: select\nDescription",
            "reference": "debconf/frontend",
        },
        {
            "msgid": (
                "Packages that use debconf for configuration share a common "
                "look and feel. You can select the type of user interface "
                "they use."
            ),
            "msgstr": (
                "Paket som använder debconf för konfiguration delar ett gemensamt "
                "utseende. Du kan välja vilken typ av användargränssnitt de "
                "använder."
            ) if lang == "sv" else "",
            "flags": "",
            "comment": "Type: select\nExtended description",
            "reference": "debconf/frontend",
        },
        {
            "msgid": "Ignore questions with a priority less than...",
            "msgstr": "Ignorera frågor med lägre prioritet än..." if lang == "sv" else "",
            "flags": "",
            "comment": "Type: select\nDescription",
            "reference": "debconf/priority",
        },
        {
            "msgid": "Workgroup/Domain Name",
            "msgstr": "",
            "flags": "",
            "comment": "Type: string\nDescription",
            "reference": "samba-common/workgroup",
        },
        {
            "msgid": "Should non-superusers be able to capture packets?",
            "msgstr": "Ska icke-rootanvändare kunna fånga paket?" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: boolean\nDescription",
            "reference": "wireshark-common/install-setuid",
        },
        {
            "msgid": "Restart services during package upgrades without asking?",
            "msgstr": "",
            "flags": "fuzzy",
            "comment": "Type: note\nDescription",
            "reference": "glibc/upgrade",
        },
        {
            "msgid": "Trust new certificates from certificate authorities?",
            "msgstr": "Lita på nya certifikat från certifikatutfärdare?" if lang == "sv" else "",
            "flags": "",
            "comment": "Type: select\nDescription",
            "reference": "ca-certificates/trust_new_crts",
        },
        {
            "msgid": (
                "Please select the geographic area in which you live. "
                "Subsequent configuration questions will narrow this down "
                "by presenting a list of cities, representing the time "
                "zones in which they are located."
            ),
            "msgstr": (
                "Välj det geografiska området där du bor. Efterföljande "
                "konfigurationsfrågor kommer att begränsa detta genom att "
                "visa en lista med städer som representerar de tidszoner "
                "de befinner sig i."
            ) if lang == "sv" else "",
            "flags": "",
            "comment": "Type: select\nExtended description",
            "reference": "tzdata/Areas",
        },
    ]
    return entries


def get_mock_diff_data() -> list[dict[str, str]]:
    """Return mock diff data for the diff view."""
    return [
        {
            "package": "grub-pc",
            "template": "grub-pc/install_devices",
            "field": "Description",
            "old": "GRUB install devices:",
            "new": "GRUB install devices",
            "change_type": "modified",
        },
        {
            "package": "locales",
            "template": "locales/locales_to_be_generated",
            "field": "Extended description",
            "old": (
                "Select the locales you want to generate. The selection "
                "will be saved to '/etc/locale.gen'."
            ),
            "new": (
                "Select the locales you want to be generated. The selection "
                "will be saved to '/etc/locale.gen'. The selected locales will "
                "be generated when you finish configuring locales."
            ),
            "change_type": "modified",
        },
        {
            "package": "samba-common",
            "template": "samba-common/workgroup",
            "field": "Description",
            "old": "Workgroup/Domain Name?",
            "new": "Workgroup/Domain Name",
            "change_type": "modified",
        },
        {
            "package": "cloud-init",
            "template": "cloud-init/datasources",
            "field": "Description",
            "old": "",
            "new": "Which cloud datasources should be read?",
            "change_type": "added",
        },
        {
            "package": "openssh-server",
            "template": "openssh-server/permit-root-login",
            "field": "Description",
            "old": "Permit root login via SSH?",
            "new": "",
            "change_type": "removed",
        },
        {
            "package": "keyboard-configuration",
            "template": "keyboard-configuration/model",
            "field": "Extended description",
            "old": "Please select the model of keyboard of this machine.",
            "new": "Please select the model of the keyboard of this machine.",
            "change_type": "modified",
        },
    ]
