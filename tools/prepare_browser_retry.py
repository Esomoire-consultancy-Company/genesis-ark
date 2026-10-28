#!/usr/bin/env python3
"""Optional, review-before-apply patch to tame transient browser CI timeouts.

This script does not change a repository unless --apply is explicitly passed.
It looks for the original single-attempt gateway/browser_smoke.py `main` block
and rewrites only that block. No assertions are relaxed or ignored.
"""
from pathlib import Path
import argparse
import difflib

OLD = '''    driver: Driver | None = None
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
'''

NEW = '''    failures = []
    try:
        for width, height in VIEWPORTS:
            label = f"{width}x{height}"
            # Only HTTP/driver transport timeouts may be retried. Assertions,
            # auth decisions, content failures and JavaScript errors are final.
            for attempt in range(1, 3):
                driver: Driver | None = None
                try:
                    driver = Driver(available_port())
                    driver.open(f"http://127.0.0.1:{port}/index.html", width, height)
                    layout(driver, width)
                    driver.screenshot(label + "-landing.png")
                    interactions(driver, width, f"http://127.0.0.1:{port}/index.html")
                    driver.screenshot(label + "-interaction.png")
                    print("PASS", label, "layout, roles, atlas, search, method, keyboard, console", flush=True)
                    break
                except (TimeoutError, ConnectionError, URLError) as error:
                    print("TRANSIENT", label, f"attempt {attempt}/2", type(error).__name__,
                          file=sys.stderr, flush=True)
                    if attempt == 1:
                        continue
                    failures.append(f"{label}: transport timeout after retry: {error}")
                except Exception as error:
                    failures.append(f"{label}: {error}")
                    print("FAIL", label, repr(error), file=sys.stderr, flush=True)
                    if driver is not None:
                        try:
                            driver.screenshot(label + "-failure.png")
                        except Exception:
                            pass
                    break
                finally:
                    if driver is not None:
                        driver.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
'''


def transform(text: str) -> str:
    if text.count(OLD) != 1:
        raise ValueError("expected exact original browser smoke main block; manual review required")
    return text.replace(OLD, NEW)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default="gateway/browser_smoke.py")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = Path(args.source)
    original = target.read_text(encoding="utf-8")
    updated = transform(original)
    if args.apply:
        target.write_text(updated, encoding="utf-8")
        print("Applied bounded transport-only retry. Review diff and run browser CI.")
    else:
        print("".join(difflib.unified_diff(original.splitlines(True),
                       updated.splitlines(True), fromfile="a/" + str(target),
                       tofile="b/" + str(target))))


if __name__ == "__main__":
    main()
