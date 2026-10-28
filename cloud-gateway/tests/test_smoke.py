"""Offline unit tests of internal smoke-runner redirect and failure handling."""

from io import BytesIO

import pytest
from urllib import error

from genesis_gateway import smoke


@pytest.mark.parametrize("status", [302, 307])
def test_smoke_rejects_redirect_instead_of_forwarding_bearer(monkeypatch, status):
    def build_opener(*handlers):
        assert any(
            isinstance(handler, smoke.request.HTTPRedirectHandler)
            and type(handler) is not smoke.request.HTTPRedirectHandler
            for handler in handlers
        )
        class FakeOpener:
            def open(self, req, timeout):
                assert req.get_header("Authorization") == "Bearer fixture-only"
                raise error.HTTPError(
                    req.full_url, status, "Redirect", {"Location": "https://invalid.example/"},
                    BytesIO(b"{}"),
                )
        return FakeOpener()

    monkeypatch.setattr(smoke.request, "build_opener", build_opener)
    with pytest.raises(RuntimeError, match="SMOKE_REDIRECT_REJECTED"):
        smoke._send("http://gateway.railway.internal/healthz", token="fixture-only")


def test_smoke_check_failure_never_optimized_away():
    with pytest.raises(RuntimeError, match="SMOKE_CHECK_FAILED:TEST"):
        smoke.check(False, "TEST")
