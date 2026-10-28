#!/usr/bin/env python3
"""Run browser-based UX acceptance against the local, static Genesis Gateway.

Uses the Chromium/ChromeDriver binaries preinstalled on the GitHub-hosted
Ubuntu 24.04 runner. No Python packages, backend or external site are required.

This is a browser interaction smoke test, not an accessibility certification.
"""
from __future__ import annotations

import base64
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from threading import Thread
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT.parent / "gateway-qa" / "screenshots"
ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"
VIEWPORTS = ((320, 720), (390, 844), (768, 1024), (1440, 900))


def assert_ok(condition: bool, description: str) -> None:
    if not condition:
        raise AssertionError(description)


class QuietServer(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *_args) -> None:
        return


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def webdriver_binary() -> str:
    env = os.environ.get("CHROMEWEBDRIVER", "")
    choices = [
        shutil.which("chromedriver"),
        env,
        str(Path(env) / "chromedriver") if env else "",
        "/usr/local/share/chromedriver-linux64/chromedriver",
    ]
    for path in choices:
        if path and Path(path).is_file() and os.access(path, os.X_OK):
            return path
    raise RuntimeError("ChromeDriver not installed; expected Ubuntu 24.04 runner image")


class Driver:
    def __init__(self, port: int) -> None:
        self.base = f"http://127.0.0.1:{port}"
        self.process = subprocess.Popen(
            [webdriver_binary(), f"--port={port}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.session = ""
        for _ in range(80):
            if self.process.poll() is not None:
                raise RuntimeError("ChromeDriver terminated unexpectedly")
            try:
                self.call("GET", "/status")
                break
            except (URLError, ConnectionError, RuntimeError):
                time.sleep(.1)
        else:
            raise RuntimeError("ChromeDriver did not become ready")

    def call(self, method: str, path: str, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            self.base + path, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=20) as response:
                output = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"WebDriver {method} {path}: {error.read()[:500]!r}") from error
        if isinstance(output.get("value"), dict) and output["value"].get("error"):
            raise RuntimeError(f"WebDriver error: {output['value']}")
        return output.get("value", output)

    def open(self, url: str, width: int, height: int) -> None:
        options = {
            "capabilities": {"alwaysMatch": {
                "browserName": "chrome",
                "goog:chromeOptions": {
                    "args": [
                        "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
                        "--disable-gpu", "--disable-background-networking",
                        "--no-first-run", "--window-size=1440,900",
                    ],
                },
                "goog:loggingPrefs": {"browser": "ALL"},
            }}
        }
        response = self.call("POST", "/session", options)
        self.session = response.get("sessionId", "")
        assert_ok(bool(self.session), "Chrome session was not created")
        # Use device metrics rather than the window geometry, which Chrome may
        # clamp on small mobile viewports.
        self.call("POST", self.endpoint("goog/cdp/execute"), {
            "cmd": "Emulation.setDeviceMetricsOverride",
            "params": {
                "width": width, "height": height,
                "deviceScaleFactor": 1, "mobile": width <= 600,
            },
        })
        self.navigate(url)

    def endpoint(self, suffix: str) -> str:
        return f"/session/{self.session}/{suffix}"

    def navigate(self, url: str) -> None:
        self.call("POST", self.endpoint("url"), {"url": url})

    def js(self, script: str):
        return self.call("POST", self.endpoint("execute/sync"), {
            "script": script, "args": [],
        })

    def element(self, selector: str) -> str:
        element = self.call("POST", self.endpoint("element"), {
            "using": "css selector", "value": selector,
        })
        return element[ELEMENT_KEY]

    def click(self, selector: str) -> None:
        # WebDriver scroll-to-click races with the site's smooth-scrolling CSS
        # on long pages. Use an instant, deterministic scroll before real click.
        self.js("document.documentElement.style.scrollBehavior = 'auto';"
                "document.querySelector(" + json.dumps(selector) +
                ").scrollIntoView({block:'center',behavior:'instant'});")
        element_id = self.element(selector)
        self.call("POST", self.endpoint(f"element/{element_id}/click"), {})

    def key(self, selector: str, text: str) -> None:
        element_id = self.element(selector)
        self.call("POST", self.endpoint(f"element/{element_id}/value"), {
            "text": text, "value": list(text),
        })

    def screenshot(self, filename: str) -> None:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        image = self.call("GET", self.endpoint("screenshot"))
        (ARTIFACTS / filename).write_bytes(base64.b64decode(image))

    def errors(self):
        return self.call("POST", self.endpoint("log"), {"type": "browser"})

    def close(self):
        if self.session:
            try:
                self.call("DELETE", f"/session/{self.session}")
            except Exception:
                pass
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)


def layout(driver: Driver, width: int) -> None:
    measures = driver.js("""
      return {
        viewport: window.innerWidth,
        body: document.body.scrollWidth,
        html: document.documentElement.scrollWidth,
        title: document.title,
        main: document.querySelector('main') !== null,
        hero: document.querySelector('#hero-title')?.getBoundingClientRect().width,
        clickable: [...document.querySelectorAll('button')].every(
          x => x.getBoundingClientRect().width >= 24 &&
               x.getBoundingClientRect().height >= 24
        )
      };
    """)
    print("LAYOUT", width, json.dumps(measures), flush=True)
    assert_ok(measures["main"] and measures["title"], f"{width}px: missing main or title")
    assert_ok(measures["viewport"] == width, f"{width}px: unexpected viewport")
    assert_ok(measures["html"] <= width + 2, f"{width}px: horizontal overflow in document")
    assert_ok(measures["body"] <= width + 2, f"{width}px: horizontal overflow in body")
    assert_ok(measures["clickable"], f"{width}px: interactive button below 24px")
    assert_ok(measures["hero"] > 100, f"{width}px: invisible hero")
    if width <= 520:
        # Mobile hero metrics must remain a single aligned row, not wrap 2+1.
        stats = driver.js("""
          return [...document.querySelectorAll('.hero-facts > div')].map(el => {
            const box = el.getBoundingClientRect();
            return {top: box.top, left: box.left, right: box.right,
                    width: box.width};
          });
        """)
        assert_ok(len(stats) == 3, f"{width}px: expected three metrics")
        assert_ok(
            max(s["top"] for s in stats) - min(s["top"] for s in stats) <= 2,
            f"{width}px: hero metrics wrap onto multiple rows: {stats}"
        )
        assert_ok(
            all(s["width"] >= 60 for s in stats)
            and all(s["right"] <= width + 2 for s in stats),
            f"{width}px: hero metrics clipped: {stats}"
        )


def interactions(driver: Driver, width: int, origin: str) -> None:
    driver.click('[data-role="member"]')
    assert_ok(driver.js("return document.querySelector('#role-title').textContent.includes('Discover')"),
              f"{width}px: member entrance not updated")
    driver.click('[data-role="auditor"]')
    assert_ok(driver.js("return document.querySelector('#role-title').textContent.includes('evidence')"),
              f"{width}px: auditor entrance not updated")

    driver.click('[data-node="warden"]')
    assert_ok(driver.js("return document.querySelector('#node-title').textContent === 'Warden'"),
              f"{width}px: architecture selection not working")
    driver.click('[data-node="river"]')
    assert_ok(driver.js("return document.querySelector('#node-title').textContent === 'RiverOS'"),
              f"{width}px: RiverOS selection not working")

    driver.click('[data-filter="implementation"]')
    count = driver.js("return [...document.querySelectorAll('.cap-card')].filter(x=>!x.hidden).length")
    assert_ok(count == 2, f"{width}px: implementation filter expected 2, got {count}")
    driver.key("#capability-search", "SMART")
    count = driver.js("return [...document.querySelectorAll('.cap-card')].filter(x=>!x.hidden).length")
    assert_ok(count == 1, f"{width}px: case-insensitive search expected 1, got {count}")
    driver.js("""
      const input = document.querySelector('#capability-search');
      input.value = 'nonexistent-capability';
      input.dispatchEvent(new Event('input',{bubbles:true}));
    """)
    assert_ok(driver.js("return !document.querySelector('#capability-empty').hidden"),
              f"{width}px: empty-search state not shown")

    driver.click('[data-method="ocm"]')
    driver.click('[data-step="1"]')
    assert_ok(driver.js("return document.querySelector('#method-label').textContent === 'OCM'"),
              f"{width}px: method toggle not updated")
    assert_ok(driver.js("return document.querySelector('#method-title').textContent.includes('Correct')"),
              f"{width}px: method step not updated")

    # Anchor activation with a real Enter key must move keyboard focus to main.
    driver.navigate(origin)
    driver.js("document.querySelector('.skip').focus()")
    driver.key("a.skip", "\ue007")  # WebDriver Keys.ENTER
    focus = driver.js("return {id:document.activeElement.id, hash:location.hash}")
    assert_ok(focus["id"] == "main", f"{width}px: skip link didn't focus main: {focus}")

    # A focused role button must be activatable from a keyboard, not only mouse.
    driver.js("document.querySelector('[data-role=\"operator\"]').focus()")
    driver.key('[data-role="operator"]', "\ue007")
    assert_ok(driver.js("return document.querySelector('#role-title').textContent.includes('governed')"),
              f"{width}px: keyboard activation didn't update role")

    requests = driver.js("""
      return performance.getEntriesByType('resource')
        .map(x=>x.name).filter(x=>!x.startsWith(location.origin));
    """)
    assert_ok(not requests, f"{width}px: unexpected external requests: {requests}")
    logs = driver.errors()
    severe = [entry for entry in logs if entry.get("level") == "SEVERE"]
    assert_ok(not severe, f"{width}px: Chrome console errors: {severe}")


def main() -> int:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietServer)
    Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_port
    driver: Driver | None = None
    failures = []
    try:
        driver = Driver(available_port())
        for width, height in VIEWPORTS:
            label = f"{width}x{height}"
            try:
                driver.open(f"http://127.0.0.1:{port}/index.html", width, height)
                layout(driver, width)
                driver.screenshot(label + "-landing.png")
                interactions(driver, width, f"http://127.0.0.1:{port}/index.html")
                driver.screenshot(label + "-interaction.png")
                print("PASS", label, "layout, roles, atlas, search, method, keyboard, console", flush=True)
            except Exception as error:
                failures.append(f"{label}: {error}")
                print("FAIL", label, repr(error), file=sys.stderr, flush=True)
                try:
                    driver.screenshot(label + "-failure.png")
                except Exception:
                    pass
            finally:
                if driver:
                    driver.close()
                driver = Driver(available_port()) if (width, height) != VIEWPORTS[-1] else None
    finally:
        if driver:
            driver.close()
        httpd.shutdown()
        httpd.server_close()
    if failures:
        for failure in failures:
            print("ERROR:", failure, file=sys.stderr)
        return 1
    print("PASS: Chromium Gateway smoke suite across four viewports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
