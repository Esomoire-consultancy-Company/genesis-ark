from genesis_control_plane.cli import build_parser, main


def test_missing_hmac_key_returns_nonzero_with_safe_message(capsys):
    code = main(
        ["restart", "--resource", "RES-RIVER-WORKER-001", "--timeout", "30"],
        environ={},
    )
    captured = capsys.readouterr()
    assert code != 0
    assert "GENESIS_WARDEN_HMAC_KEY is required" in captured.err


def test_restart_requires_explicit_resource():
    parser = build_parser()
    try:
        parser.parse_args(["restart"])
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("--resource must be required")


def test_only_restart_subcommand_is_supported():
    parser = build_parser()
    try:
        parser.parse_args(["shell", "--resource", "RES-RIVER-WORKER-001"])
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("free-form shell subcommand must not exist")


def test_cli_exit_code_requires_verified_outcome():
    from types import SimpleNamespace
    from genesis_control_plane.contracts import DecisionResult, VerificationState
    from genesis_control_plane.cli import outcome_exit_code

    failed = SimpleNamespace(
        decision=SimpleNamespace(result=DecisionResult.PERMIT),
        verification=SimpleNamespace(state=VerificationState.NOT_VERIFIED),
    )
    verified = SimpleNamespace(
        decision=SimpleNamespace(result=DecisionResult.PERMIT),
        verification=SimpleNamespace(state=VerificationState.VERIFIED),
    )
    denied = SimpleNamespace(
        decision=SimpleNamespace(result=DecisionResult.DENY),
        verification=None,
    )
    assert outcome_exit_code(failed) != 0
    assert outcome_exit_code(denied) != 0
    assert outcome_exit_code(verified) == 0
