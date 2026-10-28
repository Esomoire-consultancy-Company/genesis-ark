"""Regression checks for the static Genesis gateway validator.

Tests use isolated temporary folders and synthetic HTML/JS fixtures: no network
access and no repository credentials.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import re
import unittest

from check import ROOT, check


BASE_HTML = """<!doctype html>
<html lang="en">
<head><title>Valid Gateway</title><link rel="stylesheet" href="styles.css"></head>
<body>
<a href="#main">Skip to content</a>
<main id="main" tabindex="-1"><button type="button">Explore</button></main>
<script src="portal.js"></script>
</body></html>
"""


class GatewayValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.html = BASE_HTML
        self.js = "setText('main', 'ok');"
        (self.root / "styles.css").write_text(".example {}", encoding="utf-8")
        self.write()

    def write(self) -> None:
        (self.root / "index.html").write_text(self.html, encoding="utf-8")
        (self.root / "portal.js").write_text(self.js, encoding="utf-8")

    def errors(self) -> list[str]:
        self.write()
        return check(self.root)

    def assert_error(self, marker: str) -> None:
        self.assertTrue(
            any(marker in error for error in self.errors()),
            msg="Expected {!r} in validator errors: {!r}".format(marker, self.errors()),
        )

    def test_valid_minimal_document(self) -> None:
        self.assertEqual(self.errors(), [])

    def test_reject_blank_language(self) -> None:
        self.html = self.html.replace('lang="en"', 'lang="  "')
        self.assert_error("non-blank lang")

    def test_reject_empty_title(self) -> None:
        self.html = self.html.replace("Valid Gateway", "")
        self.assert_error("non-blank title")

    def test_reject_whitespace_title(self) -> None:
        self.html = self.html.replace("Valid Gateway", "  \n \t ")
        self.assert_error("non-blank title")

    def test_accept_title_split_across_data_nodes(self) -> None:
        self.html = self.html.replace("Valid Gateway", "Valid &amp; accessible")
        self.assertEqual(self.errors(), [])

    def test_skip_target_must_be_focusable(self) -> None:
        self.html = self.html.replace(' id="main" tabindex="-1"', ' id="main"')
        self.assert_error("tabindex=-1")

    def test_reject_missing_image_even_with_alt(self) -> None:
        self.html = self.html.replace("</main>", '<img src="absent.png" alt="image"></main>')
        self.assert_error("Missing or unsafe local asset: absent.png")

    def test_reject_missing_audio_and_media_sources(self) -> None:
        self.html = self.html.replace(
            "</main>",
            '<audio src="missing.mp3"></audio>'
            '<video poster="missing-poster.png"><source src="missing.webm"></video>'
            '<track src="missing.vtt"><embed src="missing.svg">'
            '<iframe src="missing.html"></iframe>'
            '<object data="missing.pdf"></object></main>',
        )
        errors = self.errors()
        for asset in (
            "missing.mp3", "missing-poster.png", "missing.webm",
            "missing.vtt", "missing.svg", "missing.html", "missing.pdf",
        ):
            self.assertTrue(any(asset in error for error in errors), asset)

    def test_srcset_requires_every_file(self) -> None:
        (self.root / "photo.png").write_bytes(b"fixture")
        self.html = self.html.replace(
            "</main>",
            '<picture><source srcset="photo.png 1x, missing2.png 2x">'
            '<img src="photo.png" alt="photo"></picture></main>',
        )
        self.assert_error("missing2.png")

    def test_accept_existing_media_resources(self) -> None:
        for name in ("photo.png", "poster.png", "video.mp4", "clip.mp4"):
            (self.root / name).write_bytes(b"fixture")
        self.html = self.html.replace(
            "</main>",
            '<img src="photo.png" alt="photo">'
            '<video src="video.mp4" poster="poster.png"></video>'
            '<source src="clip.mp4"></main>',
        )
        self.assertEqual(self.errors(), [])

    def test_reject_broken_fragment(self) -> None:
        self.html = self.html.replace('href="#main"', 'href="#missing"')
        self.assert_error("Broken page anchor")

    def test_reject_broken_same_document_path_fragment(self) -> None:
        for href in ("index.html#missing", "./index.html#missing", "index.html?view=all#missing"):
            with self.subTest(href=href):
                self.html = BASE_HTML.replace('href="#main"', 'href="' + href + '"')
                self.assert_error("Broken page anchor")

    def test_accept_valid_same_document_path_fragment(self) -> None:
        self.html = self.html.replace('href="#main"', 'href="./index.html#main"')
        self.assertEqual(self.errors(), [])

    def test_reject_malformed_https_host(self) -> None:
        for href in ("https://", "https:///no-host", "https://["):
            with self.subTest(href=href):
                self.html = BASE_HTML.replace('href="#main"', 'href="' + href + '"')
                errors = self.errors()
                self.assertTrue(
                    any("missing host" in x or "Malformed URL" in x for x in errors),
                    errors,
                )

    def test_reject_blank_mailto(self) -> None:
        for href in ("mailto:", "mailto:?subject=Hello", "mailto:not-an-address"):
            with self.subTest(href=href):
                self.html = BASE_HTML.replace('href="#main"', 'href="' + href + '"')
                self.assert_error("Mailto URL missing recipient")

    def test_reject_protocol_relative_link(self) -> None:
        self.html = self.html.replace('href="#main"', 'href="//untrusted.example/path"')
        self.assert_error("Unexpected URL protocol")

    def test_reject_directory_escape(self) -> None:
        self.html = self.html.replace('href="#main"', 'href="../secret.txt"')
        self.assert_error("Missing or unsafe local asset")

    def test_reject_double_quoted_js_dom_target(self) -> None:
        self.js = 'setText("not-present", "value");'
        self.assert_error("JS refers to missing DOM id: not-present")

    def test_reject_single_quoted_js_dom_target(self) -> None:
        self.js = "setText('not-present', 'value');"
        self.assert_error("JS refers to missing DOM id: not-present")

    def test_reject_forbidden_runtime_fetch(self) -> None:
        self.js = "fetch('https://example.com');"
        self.assert_error("Forbidden feature")

    def test_reject_missing_css(self) -> None:
        (self.root / "styles.css").unlink()
        self.assert_error("Missing or unsafe local asset: styles.css")

    def test_reject_empty_src(self) -> None:
        self.html = self.html.replace("</main>", '<img src="" alt="image"></main>')
        self.assert_error("Empty img src URL")

    def test_actual_portal_uses_locale_independent_lowercasing(self) -> None:
        script = (ROOT / "portal.js").read_text(encoding="utf-8")
        self.assertIn(".toLowerCase()", script)
        self.assertNotIn(".toLocaleLowerCase()", script)

    def test_placeholder_contrast_meets_wcag_aa(self) -> None:
        styles = (ROOT / "styles.css").read_text(encoding="utf-8")
        match = re.search(
            r"\.searchbox input::placeholder\{color:(#[0-9a-fA-F]{6})",
            styles,
        )
        self.assertIsNotNone(match, "Search placeholder color not found")
        fg = match.group(1)
        bg = "#101d2b"

        def luminance(hex_color: str) -> float:
            channels = [int(hex_color[index:index + 2], 16) / 255
                        for index in (1, 3, 5)]
            linear = [channel / 12.92 if channel <= 0.04045
                      else ((channel + 0.055) / 1.055) ** 2.4
                      for channel in channels]
            return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))

        light, dark = sorted((luminance(fg), luminance(bg)), reverse=True)
        self.assertGreaterEqual((light + 0.05) / (dark + 0.05), 4.5)

    def test_ci_checkout_has_no_persisted_token_or_mutable_actions(self) -> None:
        workflow = (ROOT.parent / ".github" / "workflows" / "gateway-static.yml").read_text(encoding="utf-8")
        self.assertIn("permissions: {}", workflow)
        self.assertIn("persist-credentials: false", workflow)
        used_actions = re.findall(r"\buses: (actions/[\w-]+)@([^\s]+)", workflow)
        self.assertEqual(
            {name for name, _ in used_actions},
            {"actions/checkout", "actions/setup-python", "actions/setup-node",
             "actions/upload-artifact"},
        )
        for name, ref in used_actions:
            with self.subTest(name=name):
                self.assertRegex(ref, r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
