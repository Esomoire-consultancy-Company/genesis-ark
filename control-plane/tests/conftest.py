from pathlib import Path

import pytest

from genesis_control_plane.evidence import EvidenceJournal
from genesis_control_plane.registry import AlphaRegistry
from genesis_control_plane.tokens import TokenIssuer
from genesis_control_plane.weg import ConsumedTokenLedger, WardenExecutionGateway
from genesis_control_plane.warden import Warden, WardenPolicy


@pytest.fixture
def registry():
    path = Path(__file__).parents[1] / "registry" / "alpha-registry.json"
    return AlphaRegistry.load(path)


@pytest.fixture
def token_issuer():
    return TokenIssuer(b"test-secret-not-production", "KEY-TEST-001", "WEG-GES-ALPHA-001")


@pytest.fixture
def warden(registry):
    return Warden(registry, WardenPolicy())


@pytest.fixture
def weg(tmp_path, registry, token_issuer):
    return WardenExecutionGateway(
        registry,
        token_issuer,
        ConsumedTokenLedger(tmp_path / "tokens.sqlite3"),
    )


@pytest.fixture
def evidence(tmp_path):
    return EvidenceJournal(tmp_path / "river.jsonl")
