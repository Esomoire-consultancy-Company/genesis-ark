"""GWIEP R0.6: in-process staging HTTP *contract* adapter.

NO server/socket is started. A deployment must supply TLS termination, a
trusted identity issuer, rate limits, a safe bearer-token delivery mechanism,
origin controls, source keys and an independently authorized ingress layer.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from genesis_control_plane.work_gateway import AdmissionDenied
from genesis_control_plane.work_identity import IdentityDenied
from genesis_control_plane.work_notice import WorkNoticeConsent
from genesis_control_plane.work_r05 import WorkEvidenceStaging
from genesis_control_plane.work_review import WardenReviewQueue

_ID = r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}"
_PROGRESS = re.compile(r"^/v1/work/(" + _ID + r")/progress$")
_APPROVE = re.compile(r"^/v1/admin/reviews/(" + _ID + r")/approve$")
_REVIEW = re.compile(r"^/v1/admin/reviews/(" + _ID + r")$")
MAX_BYTES = 16384


@dataclass(frozen=True)
class ApiRequest:
    method: str
    path: str
    headers: Mapping[str, str]
    body: bytes = b""


@dataclass(frozen=True)
class ApiResponse:
    status: int
    headers: dict[str, str]
    body: dict[str, Any]


class WorkStagingAPI:
    """Pure request handler; never infer identity from a client header.

    This is a reference integration contract, not a live HTTP application.
    """

    def __init__(
        self, *, staging: WorkEvidenceStaging, notices: WorkNoticeConsent,
        reviews: WardenReviewQueue, allowed_origins: frozenset[str],
    ):
        self.staging, self.notices, self.reviews = staging, notices, reviews
        self.allowed_origins = allowed_origins

    @staticmethod
    def _response(status: int, content: dict[str, Any]) -> ApiResponse:
        return ApiResponse(status, {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }, content)

    @staticmethod
    def _parse(data: bytes) -> dict:
        if not isinstance(data, bytes) or len(data) > MAX_BYTES:
            raise AdmissionDenied("R06_REQUEST_TOO_LARGE")
        def unique(pairs):
            fields = {}
            for key, value in pairs:
                if key in fields:
                    raise AdmissionDenied("R06_DUPLICATE_JSON_KEY")
                fields[key] = value
            return fields
        try:
            document = json.loads(data.decode("utf-8"), object_pairs_hook=unique)
        except (ValueError, UnicodeError) as exc:
            if isinstance(exc, AdmissionDenied):
                raise
            raise AdmissionDenied("R06_INVALID_JSON") from exc
        if not isinstance(document, dict):
            raise AdmissionDenied("R06_OBJECT_REQUIRED")
        return document

    @staticmethod
    def _body_exact(doc: dict, fields: frozenset[str]) -> None:
        if set(doc) != fields:
            raise AdmissionDenied("R06_BODY_SCHEMA_DENIED")

    @staticmethod
    def _date(value: object) -> datetime:
        if not isinstance(value, str) or len(value) > 60:
            raise AdmissionDenied("R06_DATE_INVALID")
        try:
            result = datetime.fromisoformat(value)
            if result.tzinfo is None:
                raise ValueError("naive")
            return result.astimezone(timezone.utc)
        except (ValueError, OverflowError) as exc:
            raise AdmissionDenied("R06_DATE_INVALID") from exc

    @staticmethod
    def _auth(headers: Mapping[str, str]) -> str:
        credential = headers.get("authorization")
        if (not isinstance(credential, str) or
            not credential.startswith("Bearer ") or
            len(credential) > 8200 or
            len(credential.split()) != 2):
            raise AdmissionDenied("R06_BEARER_REQUIRED")
        return credential[7:]

    def handle(self, request: ApiRequest, *, now: datetime | None = None) -> ApiResponse:
        """Transport-neutral wrapper for synthetic test requests.

        Error responses contain stable reason codes, never bearer credentials,
        original prompts, source packets or private exceptions.
        """
        now = now or datetime.now(timezone.utc)
        try:
            if request.method not in {"GET", "POST"}:
                return self._response(405, {"error": "R06_METHOD_DENIED"})
            if not isinstance(request.path, str) or len(request.path) > 256:
                raise AdmissionDenied("R06_PATH_INVALID")
            if any(ch in request.path for ch in ("?", "#", "%", "\\")):
                raise AdmissionDenied("R06_PATH_INVALID")
            if not isinstance(request.headers, Mapping):
                raise AdmissionDenied("R06_HEADERS_INVALID")
            if len(request.headers) > 30:
                raise AdmissionDenied("R06_HEADERS_INVALID")
            headers = {k.lower(): v for k, v in request.headers.items() if isinstance(k, str)}
            if len(headers) != len(request.headers):
                raise AdmissionDenied("R06_DUPLICATE_HEADERS")
            if "cookie" in headers:
                raise AdmissionDenied("R06_COOKIES_DENIED")
            origin = headers.get("origin")
            if origin is not None and origin not in self.allowed_origins:
                raise AdmissionDenied("R06_ORIGIN_DENIED")

            if request.method == "GET" and request.path == "/v1/work/notice":
                return self._response(200, self.notices.notice())
            token = self._auth(headers)
            if request.method == "GET":
                if request.body:
                    raise AdmissionDenied("R06_GET_BODY_DENIED")
                matched = _PROGRESS.fullmatch(request.path)
                if matched:
                    result = self.staging.private_progress(
                        access_token=token, work_id=matched.group(1), now=now)
                    return self._response(200, result)
                matched = _REVIEW.fullmatch(request.path)
                if matched:
                    result = self.reviews.status(
                        access_token=token, proposal_id=matched.group(1), now=now)
                    return self._response(200, result)
                return self._response(404, {"error": "R06_ROUTE_NOT_FOUND"})

            if headers.get("content-type") != "application/json":
                raise AdmissionDenied("R06_JSON_CONTENT_TYPE_REQUIRED")
            payload = self._parse(request.body)
            if request.path == "/v1/work/consent":
                self._body_exact(payload, frozenset({
                    "work_id", "expires_at", "notice_version", "affirmative"}))
                result = self.notices.opt_in(
                    access_token=token, work_id=payload["work_id"],
                    expires_at=self._date(payload["expires_at"]),
                    notice_version=payload["notice_version"],
                    affirmative=payload["affirmative"], now=now)
                return self._response(201, result)
            if request.path == "/v1/work/withdraw":
                self._body_exact(payload, frozenset({"work_id"}))
                result = self.staging.withdraw(
                    access_token=token, work_id=payload["work_id"], now=now)
                return self._response(200, result)
            if request.path == "/v1/work/capture":
                self._body_exact(payload, frozenset({"packet"}))
                result = self.staging.admit(
                    access_token=token, packet=payload["packet"], now=now)
                return self._response(202, result)
            if request.path == "/v1/admin/reviews":
                self._body_exact(payload, frozenset({
                    "target_id", "source", "work_id", "channels", "kinds", "expires_at"}))
                result = self.reviews.propose(
                    access_token=token, target_id=payload["target_id"],
                    source=payload["source"], work_id=payload["work_id"],
                    channels=payload["channels"], kinds=payload["kinds"],
                    expires_at=self._date(payload["expires_at"]), now=now)
                return self._response(202, result)
            matched = _APPROVE.fullmatch(request.path)
            if matched:
                self._body_exact(payload, frozenset())
                result = self.reviews.approve(
                    access_token=token, proposal_id=matched.group(1), now=now)
                return self._response(200, result)
            return self._response(404, {"error": "R06_ROUTE_NOT_FOUND"})
        except IdentityDenied:
            return self._response(401, {"error": "R06_IDENTITY_DENIED"})
        except (AdmissionDenied, ValueError, TypeError, KeyError) as exc:
            # Never reflect caller-controlled string values. All exposed
            # reason codes are generated by the trusted local modules.
            code = str(exc)
            if not re.fullmatch(r"[A-Z0-9_]{3,90}", code):
                code = "R06_REQUEST_DENIED"
            return self._response(403, {"error": code})
