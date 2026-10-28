#!/usr/bin/env python3
"""Static link, accessibility-anchor and asset checks for Gateway R0.1."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


class Inspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[str] = []
        self.images_without_alt: list[str] = []
        self.buttons_without_names: list[str] = []
        self._button_stack: list[dict[str, str | bool]] = []
        self.page_title = False
        self.lang = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "html":
            self.lang = bool(attrs_dict.get("lang"))
        if tag == "title":
            self.page_title = True
        if attrs_dict.get("id"):
            self.ids.append(str(attrs_dict["id"]))
        if tag in ("a", "link", "script"):
            attribute = "href" if tag in ("a", "link") else "src"
            if attrs_dict.get(attribute):
                self.links.append(str(attrs_dict[attribute]))
        if tag == "img" and "alt" not in attrs_dict:
            self.images_without_alt.append(str(attrs_dict.get("src", "?")))
        if tag == "button":
            self._button_stack.append(
                {"label": str(attrs_dict.get("aria-label") or ""), "has_content": False}
            )

    def handle_data(self, data: str) -> None:
        if data.strip() and self._button_stack:
            self._button_stack[-1]["has_content"] = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._button_stack:
            button = self._button_stack.pop()
            if not button["label"] and not button["has_content"]:
                self.buttons_without_names.append("unnamed button")


def check() -> list[str]:
    errors: list[str] = []
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    parser = Inspector()
    parser.feed(html)
    if not parser.page_title:
        errors.append("HTML page has no title")
    if not parser.lang:
        errors.append("HTML element lacks lang")
    seen: set[str] = set()
    for element_id in parser.ids:
        if element_id in seen:
            errors.append("Duplicate element id: " + element_id)
        seen.add(element_id)
    for link in parser.links:
        parsed = urlsplit(link)
        if link.startswith("#"):
            if link[1:] not in seen:
                errors.append("Broken page anchor: " + link)
        elif not parsed.scheme and not parsed.netloc and parsed.path:
            asset = (ROOT / parsed.path).resolve()
            if not asset.is_relative_to(ROOT.resolve()) or not asset.is_file():
                errors.append("Missing or unsafe local asset: " + link)
        elif parsed.scheme not in ("https", "mailto"):
            errors.append("Unexpected link protocol: " + link)
    errors.extend("Image missing alt: " + value for value in parser.images_without_alt)
    errors.extend(parser.buttons_without_names)
    js = (ROOT / "portal.js").read_text(encoding="utf-8")
    for selector in re.findall(r"setText\('([^']+)'", js):
        if selector not in seen:
            errors.append("JS refers to missing DOM id: " + selector)
    for token in ("eval(", "document.write(", "innerHTML", "localStorage", "fetch(", "XMLHttpRequest"):
        if token in js:
            errors.append("Forbidden feature in static prototype: " + token)
    return errors


if __name__ == "__main__":
    failures = check()
    if failures:
        for failure in failures:
            print("FAIL:", failure, file=sys.stderr)
        raise SystemExit(1)
    print("PASS: Gateway assets, document links and static guardrail checks")
