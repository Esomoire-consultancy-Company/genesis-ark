#!/usr/bin/env python3
"""Read-only static link, accessibility and asset verifier for Gateway R0.1."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
RESOURCE_ATTRIBUTES = {
    "a": ("href",),
    "area": ("href",),
    "link": ("href",),
    "script": ("src",),
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "audio": ("src",),
    "video": ("src", "poster"),
    "track": ("src",),
    "embed": ("src",),
    "iframe": ("src",),
    "object": ("data",),
    "input": ("src",),
}


class Inspector(HTMLParser):
    """Collect document targets and resource attributes without running scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[tuple[str, str, str]] = []
        self.images_without_alt: list[str] = []
        self.buttons_without_names: list[str] = []
        self._button_stack: list[dict[str, str | bool]] = []
        self._in_title = False
        self._title_parts: list[str] = []
        self.has_title_element = False
        self.lang = False
        self.main_is_focusable = False

    @property
    def page_title(self) -> bool:
        return self.has_title_element and bool("".join(self._title_parts).strip())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "html":
            self.lang = bool((attributes.get("lang") or "").strip())
        if tag == "title":
            self.has_title_element = True
            self._in_title = True
        if attributes.get("id"):
            self.ids.append(str(attributes["id"]))
        if tag == "main" and attributes.get("id") == "main":
            self.main_is_focusable = (attributes.get("tabindex") or "").strip() == "-1"
        for attribute in RESOURCE_ATTRIBUTES.get(tag, ()):
            if attribute in attributes:
                value = attributes[attribute] or ""
                if attribute == "srcset":
                    # Static image preview srcset; no embedded data URI support.
                    candidates = value.split(",")
                    for candidate in candidates:
                        parts = candidate.strip().split()
                        self.links.append((tag, attribute, parts[0] if parts else ""))
                else:
                    self.links.append((tag, attribute, value))
        if tag == "img" and "alt" not in attributes:
            self.images_without_alt.append(str(attributes.get("src") or "?"))
        if tag == "button":
            self._button_stack.append(
                {"label": str(attributes.get("aria-label") or "").strip(),
                 "has_content": False}
            )

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        if data.strip() and self._button_stack:
            self._button_stack[-1]["has_content"] = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "button" and self._button_stack:
            button = self._button_stack.pop()
            if not button["label"] and not button["has_content"]:
                self.buttons_without_names.append("Unnamed button")


def inspect_url(
    tag: str, attribute: str, link: str, root: Path, ids: set[str]
) -> list[str]:
    errors: list[str] = []
    if not link.strip():
        return [f"Empty {tag} {attribute} URL"]
    try:
        parsed = urlsplit(link)
        hostname = parsed.hostname  # also validates bracket syntax
    except ValueError:
        return [f"Malformed URL in {tag} {attribute}: {link}"]

    if parsed.scheme == "https":
        if not hostname:
            errors.append(f"HTTPS URL missing host: {link}")
        return errors
    if parsed.scheme == "mailto":
        # Require an actual recipient, not just the mailto: scheme.
        if not parsed.path.strip() or "@" not in parsed.path:
            errors.append(f"Mailto URL missing recipient: {link}")
        return errors
    if parsed.scheme or parsed.netloc:
        return [f"Unexpected URL protocol or network path: {link}"]

    # Resolve local files against the gateway root (never escape it).
    relative_path = unquote(parsed.path)
    if relative_path:
        target = (root / relative_path).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            errors.append(f"Missing or unsafe local asset: {link}")
    else:
        target = root / "index.html"

    # Check same-document fragments for both #id and index.html#id.
    if parsed.fragment and target.resolve() == (root / "index.html").resolve():
        fragment = unquote(parsed.fragment)
        if fragment not in ids:
            errors.append(f"Broken page anchor: {link}")
    return errors


def check(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    html = (root / "index.html").read_text(encoding="utf-8")
    parser = Inspector()
    parser.feed(html)
    if not parser.page_title:
        errors.append("HTML page has no non-blank title")
    if not parser.lang:
        errors.append("HTML element lacks a non-blank lang")
    ids: set[str] = set()
    for element_id in parser.ids:
        if element_id in ids:
            errors.append("Duplicate element id: " + element_id)
        ids.add(element_id)
    if "main" in ids and not parser.main_is_focusable:
        errors.append("Main skip-link target must have tabindex=-1")
    for tag, attribute, link in parser.links:
        errors.extend(inspect_url(tag, attribute, link, root, ids))
    errors.extend("Image missing alt: " + value for value in parser.images_without_alt)
    errors.extend(parser.buttons_without_names)

    js = (root / "portal.js").read_text(encoding="utf-8")
    # Recognise either quote style; the closing quote must match the opening.
    for match in re.finditer(r"""setText\(\s*(['"])([^'"]+)\1""", js):
        selector = match.group(2)
        if selector not in ids:
            errors.append("JS refers to missing DOM id: " + selector)
    for token in (
        "eval(", "document.write(", "innerHTML", "localStorage",
        "fetch(", "XMLHttpRequest",
    ):
        if token in js:
            errors.append("Forbidden feature in static prototype: " + token)
    return errors


if __name__ == "__main__":
    failures = check()
    if failures:
        for failure in failures:
            print("FAIL:", failure, file=sys.stderr)
        raise SystemExit(1)
    print("PASS: Gateway links, resources, HTML metadata and static guardrails")
