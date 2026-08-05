from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from .errors import ForbiddenError, NotFoundError, StateConflictError
from .models import BrowserActionRequest, BrowserActionType, BrowserPolicy, BrowserSession


class CredentialProvider(Protocol):
    def resolve(self, credential_reference: str) -> dict[str, str]: ...


class DenyCredentialProvider:
    def resolve(self, credential_reference: str) -> dict[str, str]:
        raise ForbiddenError(
            "No credential provider is configured",
            reason_codes=["CREDENTIAL_PROVIDER_UNAVAILABLE"],
        )


class BrowserExecutor(Protocol):
    def supports(self, action_type: BrowserActionType) -> bool: ...
    def start_session(self, session: BrowserSession, policy: BrowserPolicy) -> None: ...
    def execute(
        self,
        session: BrowserSession,
        action: BrowserActionRequest,
        policy: BrowserPolicy,
    ) -> dict[str, Any]: ...
    def pause_session(self, session: BrowserSession) -> None: ...
    def terminate_session(self, session: BrowserSession) -> None: ...
    def close(self) -> None: ...


class DeterministicBrowserExecutor:
    """Non-network executor for tests and environments without Chromium."""

    def supports(self, action_type: BrowserActionType) -> bool:
        return True

    def start_session(self, session: BrowserSession, policy: BrowserPolicy) -> None:
        return None

    def execute(
        self,
        session: BrowserSession,
        action: BrowserActionRequest,
        policy: BrowserPolicy,
    ) -> dict[str, Any]:
        return {
            "executor": "DETERMINISTIC_BROKER",
            "browser_session_id": session.browser_session_id,
            "action_type": action.action_type,
            "target_url": str(action.target_url) if action.target_url else None,
            "executed": True,
        }

    def pause_session(self, session: BrowserSession) -> None:
        return None

    def terminate_session(self, session: BrowserSession) -> None:
        return None

    def close(self) -> None:
        return None


@dataclass(slots=True)
class _FixtureResponse:
    status: int


@dataclass(slots=True)
class _RuntimeSession:
    context: Any
    page: Any
    policy: BrowserPolicy


class PlaywrightChromiumExecutor:
    """Single-worker isolated Chromium runtime.

    Playwright objects remain on one dedicated worker thread. Each governed browser
    session receives a fresh non-persistent BrowserContext with service workers
    blocked and a context-wide network allowlist.
    """

    SUPPORTED = {
        BrowserActionType.NAVIGATE,
        BrowserActionType.READ_PAGE,
        BrowserActionType.FILL_FORM,
        BrowserActionType.SUBMIT_FORM,
        BrowserActionType.UPLOAD_FILE,
        BrowserActionType.DOWNLOAD_FILE,
        BrowserActionType.USE_CREDENTIAL,
        BrowserActionType.CAPTURE_SCREEN,
    }

    def __init__(
        self,
        *,
        chromium_executable: str | None = None,
        headless: bool = True,
        quarantine_root: str | Path = "/tmp/genesis-cloudbrowser",
        credential_provider: CredentialProvider | None = None,
        timeout_seconds: float = 30.0,
        route_fulfiller: Callable[[str, dict[str, str]], tuple[int, dict[str, str], bytes] | None] | None = None,
    ) -> None:
        self.chromium_executable = chromium_executable
        self.headless = headless
        self.quarantine_root = Path(quarantine_root).resolve()
        self.quarantine_root.mkdir(parents=True, exist_ok=True)
        self.quarantine_root.chmod(0o700)
        self.credential_provider = credential_provider or DenyCredentialProvider()
        self.timeout_seconds = timeout_seconds
        self.route_fulfiller = route_fulfiller
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cloudbrowser")
        self._playwright = None
        self._browser = None
        self._sessions: dict[str, _RuntimeSession] = {}
        self._closed = False

    def supports(self, action_type: BrowserActionType) -> bool:
        return action_type in self.SUPPORTED

    def _call(self, function, *args):
        if self._closed:
            raise StateConflictError("Chromium executor is closed")
        return self._worker.submit(function, *args).result(timeout=self.timeout_seconds)

    def _ensure_browser(self):
        if self._browser is not None:
            return self._browser
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise StateConflictError(
                "Playwright is not installed; install the chromium runtime extra"
            ) from exc
        self._playwright = sync_playwright().start()
        launch_args: dict[str, Any] = {"headless": self.headless}
        if self.chromium_executable:
            launch_args["executable_path"] = self.chromium_executable
        self._browser = self._playwright.chromium.launch(**launch_args)
        return self._browser

    @staticmethod
    def _domain_allowed(url: str, rules: list[str]) -> bool:
        parsed = urlparse(url)
        if parsed.scheme in {"about", "data", "blob"}:
            return True
        hostname = (parsed.hostname or "").lower()
        for rule in rules:
            normalized = rule.lower().strip()
            if normalized.startswith("*."):
                suffix = normalized[2:]
                if hostname.endswith(f".{suffix}") and hostname != suffix:
                    return True
            elif hostname == normalized:
                return True
        return False

    def start_session(self, session: BrowserSession, policy: BrowserPolicy) -> None:
        self._call(self._start_session, session, policy)

    def _start_session(self, session: BrowserSession, policy: BrowserPolicy) -> None:
        if session.browser_session_id in self._sessions:
            raise StateConflictError("Chromium session already exists")
        browser = self._ensure_browser()
        context = browser.new_context(
            accept_downloads=policy.allow_downloads,
            service_workers="block",
            permissions=[],
        )
        context.set_default_timeout(self.timeout_seconds * 1000)
        context.set_default_navigation_timeout(self.timeout_seconds * 1000)

        def route_handler(route, request) -> None:
            if not self._domain_allowed(request.url, policy.allowed_domains):
                route.abort("blockedbyclient")
                return
            if self.route_fulfiller is not None:
                fixture = self.route_fulfiller(request.url, request.headers)
                if fixture is not None:
                    status, headers, body = fixture
                    route.fulfill(status=status, headers=headers, body=body)
                    return
            route.continue_()

        context.route("**/*", route_handler)
        page = context.new_page()
        self._sessions[session.browser_session_id] = _RuntimeSession(
            context=context,
            page=page,
            policy=policy,
        )

    def execute(
        self,
        session: BrowserSession,
        action: BrowserActionRequest,
        policy: BrowserPolicy,
    ) -> dict[str, Any]:
        if not self.supports(action.action_type):
            raise ForbiddenError(
                "The isolated Chromium adapter does not support this action",
                reason_codes=["EXECUTOR_ACTION_UNSUPPORTED"],
            )
        try:
            return self._call(self._execute, session, action, policy)
        except (ForbiddenError, NotFoundError, StateConflictError):
            raise
        except Exception as exc:
            raise StateConflictError(
                "Isolated Chromium execution failed",
                reason_codes=["CHROMIUM_EXECUTION_FAILED"],
            ) from exc

    def _runtime(self, session_id: str) -> _RuntimeSession:
        runtime = self._sessions.get(session_id)
        if runtime is None:
            raise StateConflictError("Chromium context is not active for this session")
        return runtime

    def _navigate_if_needed(
        self,
        page,
        action: BrowserActionRequest,
        policy: BrowserPolicy,
    ) -> Any:
        if action.target_url is None:
            return None
        target = str(action.target_url)
        if not self._domain_allowed(target, policy.allowed_domains):
            raise ForbiddenError(
                "Chromium network request is outside the browser allowlist",
                reason_codes=["NETWORK_DOMAIN_BLOCKED"],
            )
        if self.route_fulfiller is not None:
            cookie_values = page.context.cookies([target])
            headers: dict[str, str] = {}
            if cookie_values:
                headers["cookie"] = "; ".join(
                    f"{item['name']}={item['value']}" for item in cookie_values
                )
            fixture = self.route_fulfiller(target, headers)
            if fixture is not None:
                status, response_headers, body = fixture
                set_cookie = next(
                    (value for key, value in response_headers.items() if key.lower() == "set-cookie"),
                    None,
                )
                if set_cookie:
                    pair = set_cookie.split(";", 1)[0]
                    name, value = pair.split("=", 1)
                    page.context.add_cookies(
                        [{"name": name, "value": value, "url": target}]
                    )
                page.set_content(body.decode("utf-8", errors="replace"))
                return _FixtureResponse(status=status)
        if page.url != target:
            return page.goto(target, wait_until="domcontentloaded")
        return None

    @staticmethod
    def _fill(page, fields: dict[str, Any]) -> None:
        for selector, value in fields.items():
            page.locator(selector).fill(str(value))

    def _session_directory(self, session_id: str) -> Path:
        directory = (self.quarantine_root / session_id).resolve()
        try:
            directory.relative_to(self.quarantine_root)
        except ValueError as exc:
            raise ForbiddenError(
                "Invalid browser session quarantine directory",
                reason_codes=["INVALID_QUARANTINE_SESSION"],
            ) from exc
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)
        return directory

    def _safe_file(self, raw_path: str, max_bytes: int) -> Path:
        path = Path(raw_path).expanduser().resolve()
        try:
            path.relative_to(self.quarantine_root)
        except ValueError as exc:
            raise ForbiddenError(
                "Files must remain inside the CloudBrowser quarantine root",
                reason_codes=["FILE_OUTSIDE_QUARANTINE"],
            ) from exc
        if not path.is_file():
            raise NotFoundError(f"Quarantined file {path.name} does not exist")
        if path.stat().st_size > max_bytes:
            raise ForbiddenError(
                "Quarantined file exceeds browser policy size",
                reason_codes=["FILE_SIZE_EXCEEDED"],
            )
        return path

    def _execute(
        self,
        session: BrowserSession,
        action: BrowserActionRequest,
        policy: BrowserPolicy,
    ) -> dict[str, Any]:
        runtime = self._runtime(session.browser_session_id)
        if runtime.policy.policy_id != policy.policy_id:
            raise StateConflictError("Runtime browser policy does not match session policy")
        page = runtime.page
        response = self._navigate_if_needed(page, action, policy)
        action_type = action.action_type

        if action_type == BrowserActionType.NAVIGATE:
            return {
                "executor": "PLAYWRIGHT_CHROMIUM",
                "url": page.url,
                "title": page.title(),
                "http_status": response.status if response else None,
            }
        if action_type == BrowserActionType.READ_PAGE:
            return {
                "executor": "PLAYWRIGHT_CHROMIUM",
                "url": page.url,
                "title": page.title(),
                "text": page.locator("body").inner_text()[:50_000],
            }
        if action_type == BrowserActionType.FILL_FORM:
            fields = action.payload.get("fields", {})
            if not isinstance(fields, dict) or not fields:
                raise StateConflictError("FILL_FORM requires a non-empty fields object")
            self._fill(page, fields)
            return {"executor": "PLAYWRIGHT_CHROMIUM", "filled_fields": len(fields)}
        if action_type == BrowserActionType.SUBMIT_FORM:
            fields = action.payload.get("fields", {})
            if fields:
                if not isinstance(fields, dict):
                    raise StateConflictError("SUBMIT_FORM fields must be an object")
                self._fill(page, fields)
            selector = action.payload.get("submit_selector")
            if not selector:
                raise StateConflictError("SUBMIT_FORM requires submit_selector")
            page.locator(str(selector)).click()
            page.wait_for_load_state("domcontentloaded")
            return {
                "executor": "PLAYWRIGHT_CHROMIUM",
                "url": page.url,
                "title": page.title(),
                "submitted": True,
            }
        if action_type == BrowserActionType.UPLOAD_FILE:
            selector = action.payload.get("selector")
            raw_path = action.payload.get("file_path")
            if not selector or not raw_path:
                raise StateConflictError("UPLOAD_FILE requires selector and file_path")
            path = self._safe_file(str(raw_path), policy.max_file_bytes)
            page.locator(str(selector)).set_input_files(str(path))
            return {
                "executor": "PLAYWRIGHT_CHROMIUM",
                "file_name": path.name,
                "file_bytes": path.stat().st_size,
                "sha256": sha256(path.read_bytes()).hexdigest(),
            }
        if action_type == BrowserActionType.DOWNLOAD_FILE:
            selector = action.payload.get("trigger_selector")
            if not selector:
                raise StateConflictError("DOWNLOAD_FILE requires trigger_selector")
            session_dir = self._session_directory(session.browser_session_id)
            with page.expect_download() as download_info:
                page.locator(str(selector)).click()
            download = download_info.value
            suggested = Path(download.suggested_filename).name
            destination = (session_dir / suggested).resolve()
            download.save_as(str(destination))
            if destination.stat().st_size > policy.max_file_bytes:
                destination.unlink(missing_ok=True)
                raise ForbiddenError(
                    "Downloaded file exceeds browser policy size",
                    reason_codes=["DOWNLOAD_SIZE_EXCEEDED"],
                )
            return {
                "executor": "PLAYWRIGHT_CHROMIUM",
                "file_name": destination.name,
                "file_bytes": destination.stat().st_size,
                "sha256": sha256(destination.read_bytes()).hexdigest(),
            }
        if action_type == BrowserActionType.CAPTURE_SCREEN:
            session_dir = self._session_directory(session.browser_session_id)
            name = Path(str(action.payload.get("file_name", f"{action.action_id}.png"))).name
            destination = (session_dir / name).with_suffix(".png")
            page.screenshot(path=str(destination), full_page=True)
            return {
                "executor": "PLAYWRIGHT_CHROMIUM",
                "file_name": destination.name,
                "file_bytes": destination.stat().st_size,
                "sha256": sha256(destination.read_bytes()).hexdigest(),
            }
        if action_type == BrowserActionType.USE_CREDENTIAL:
            reference = str(action.payload.get("credential_reference", ""))
            selectors = action.payload.get("selectors", {})
            if not reference or not isinstance(selectors, dict) or not selectors:
                raise StateConflictError(
                    "USE_CREDENTIAL requires credential_reference and selectors"
                )
            secret_values = self.credential_provider.resolve(reference)
            filled = 0
            for field_name, selector in selectors.items():
                if field_name not in secret_values:
                    raise StateConflictError(
                        f"Credential reference does not provide field {field_name}"
                    )
                page.locator(str(selector)).fill(secret_values[field_name])
                filled += 1
            return {
                "executor": "PLAYWRIGHT_CHROMIUM",
                "credential_reference": reference,
                "filled_fields": filled,
                "raw_secret_returned": False,
            }
        raise ForbiddenError(
            "The isolated Chromium adapter does not support this action",
            reason_codes=["EXECUTOR_ACTION_UNSUPPORTED"],
        )

    def pause_session(self, session: BrowserSession) -> None:
        self._call(self._close_session, session.browser_session_id)

    def terminate_session(self, session: BrowserSession) -> None:
        self._call(self._close_session, session.browser_session_id)

    def _close_session(self, session_id: str) -> None:
        runtime = self._sessions.pop(session_id, None)
        if runtime is not None:
            runtime.context.close()

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._worker.submit(self._close_all).result(timeout=self.timeout_seconds)
        finally:
            self._closed = True
            self._worker.shutdown(wait=True, cancel_futures=True)

    def _close_all(self) -> None:
        for runtime in list(self._sessions.values()):
            runtime.context.close()
        self._sessions.clear()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._browser = None
        self._playwright = None
