from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

from .config import Settings
from .errors import ForbiddenError, NotFoundError, StateConflictError
from .evidence import build_event, new_id, utcnow
from .executor import BrowserExecutor
from .models import (
    ActionDecision,
    BrowserAction,
    BrowserActionRequest,
    BrowserActionType,
    BrowserApproval,
    BrowserApprovalRequest,
    BrowserPolicy,
    BrowserSession,
    BrowserSessionRequest,
    SessionPauseRequest,
    SessionStatus,
    SessionTerminateRequest,
    UsageRecord,
)
from .repository import CloudBrowserRepository
from .warden_client import WardenClient

RAW_SECRET_KEYS = {
    "password",
    "passphrase",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "raw_credential",
}

EGRESS_ACTIONS = {
    BrowserActionType.FILL_FORM,
    BrowserActionType.SUBMIT_FORM,
    BrowserActionType.UPLOAD_FILE,
    BrowserActionType.OPEN_CONNECTOR,
    BrowserActionType.USE_CREDENTIAL,
    BrowserActionType.SEND_MESSAGE,
    BrowserActionType.PLACE_ORDER,
    BrowserActionType.ACCEPT_TERMS,
    BrowserActionType.CHANGE_ACCOUNT,
    BrowserActionType.PUBLISH_CONTENT,
    BrowserActionType.INITIATE_PAYMENT,
    BrowserActionType.DELETE_RECORD,
    BrowserActionType.TRANSFER_ASSET,
}


class CloudBrowserEngine:
    def __init__(
        self,
        repository: CloudBrowserRepository,
        warden: WardenClient,
        executor: BrowserExecutor,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.warden = warden
        self.executor = executor
        self.settings = settings

    def create_session(self, request: BrowserSessionRequest) -> BrowserSession:
        now = utcnow()
        policy = self.repository.get_policy(request.policy_id)
        if policy is None:
            raise NotFoundError(f"Browser policy {request.policy_id} does not exist")

        ttl = min(
            request.requested_duration_seconds,
            self.settings.max_session_ttl_seconds,
        )
        decision = self.warden.evaluate(
            {
                "request_id": request.request_id,
                "requested_at": now.isoformat(),
                "box_id": request.box_id,
                "runtime_id": request.runtime_id,
                "subject_id": request.digitalme_id,
                "agent_id": request.agent_id,
                "context_id": request.context_id,
                "resource_id": request.workspace_id,
                "requested_action": "BROWSER_SESSION_START",
                "purpose": request.purpose,
                "data_classes": request.data_classes,
                "source_zone": "ORGANISATION",
                "destination_zone": "ORGANISATION",
                "requested_duration_seconds": ttl,
                "human_approval_present": True,
            }
        )
        if decision["outcome"] not in {"ALLOW", "RESTRICT"}:
            raise ForbiddenError(
                "Warden denied the CloudBrowser session",
                reason_codes=decision.get("reason_codes", []),
            )
        capability = self.warden.issue(
            decision["policy_decision_id"],
            request.digitalme_id,
        )
        expires_at = min(
            now + timedelta(seconds=ttl),
            self._parse_time(capability["expires_at"]),
        )
        session = BrowserSession(
            browser_session_id=new_id("BROWSER-SESSION"),
            box_id=request.box_id,
            digitalme_id=request.digitalme_id,
            runtime_id=request.runtime_id,
            context_id=request.context_id,
            workspace_id=request.workspace_id,
            licence_id=request.licence_id,
            agent_id=request.agent_id,
            policy_id=policy.policy_id,
            policy_decision_id=decision["policy_decision_id"],
            capability_id=capability["capability_id"],
            session_status=SessionStatus.ACTIVE,
            isolation_profile="EPHEMERAL_PARTITION_NO_SHARED_COOKIES",
            started_at=now,
            expires_at=expires_at,
            evidence_stream_id=new_id("BROWSER-RIVER"),
            compute_meter_id=new_id("COMPUTE-METER"),
        )
        usage = UsageRecord(
            compute_meter_id=session.compute_meter_id,
            browser_session_id=session.browser_session_id,
            runtime_seconds=0,
            action_count=0,
            approval_count=0,
            connector_calls=0,
            uploaded_bytes=0,
            downloaded_bytes=0,
            network_bytes=0,
            compute_units=0,
            updated_at=now,
        )
        event = self._build_event(
            session=session,
            event_type="BROWSER_SESSION_STARTED",
            actor_id=request.digitalme_id,
            action_reference=session.browser_session_id,
            payload={
                "policy_id": policy.policy_id,
                "capability_id": session.capability_id,
                "expires_at": expires_at.isoformat(),
            },
        )
        try:
            self.executor.start_session(session, policy)
            self.repository.create_session(session, usage, event)
        except Exception:
            try:
                self.executor.terminate_session(session)
            finally:
                try:
                    self.warden.revoke(
                        session.capability_id,
                        reason="CloudBrowser runtime startup failed",
                        revoked_by=request.digitalme_id,
                        policy_reference="CLOUDBROWSER-RUNTIME-STARTUP-V1",
                    )
                except Exception:
                    pass
            raise
        return session

    def get_session(self, session_id: str) -> BrowserSession:
        session = self._require_session(session_id)
        return self._expire_if_needed(session)

    def evaluate_action(
        self,
        session_id: str,
        request: BrowserActionRequest,
    ) -> BrowserAction:
        now = utcnow()
        session = self._require_active_session(session_id)
        existing = self.repository.get_action(request.action_id)
        if existing is not None:
            if existing.browser_session_id != session_id:
                raise StateConflictError("Action ID is already bound to another session")
            if existing.request is None or existing.request.model_dump(mode="json") != request.model_dump(mode="json"):
                raise StateConflictError("Action ID was reused with a different request")
            return existing
        policy = self._require_policy(session.policy_id)
        reasons: list[str] = []

        if not self.executor.supports(request.action_type):
            return self._deny_action(
                session, request, ["EXECUTOR_ACTION_UNSUPPORTED"], now
            )

        if request.action_type not in policy.allowed_actions:
            return self._deny_action(session, request, ["ACTION_NOT_ALLOWED"], now)
        reasons.append("ACTION_ALLOWED_BY_BROWSER_POLICY")

        target_url = str(request.target_url) if request.target_url else None
        if target_url and not self._domain_allowed(target_url, policy.allowed_domains):
            return self._deny_action(session, request, [*reasons, "DOMAIN_NOT_ALLOWED"], now)
        if target_url:
            reasons.append("DOMAIN_ALLOWED")

        control_denial = self._control_denial(policy, request)
        if control_denial:
            return self._deny_action(session, request, [*reasons, control_denial], now)
        self._reject_raw_secrets(request.payload)

        destination_zone = (
            "EXTERNAL_PROVIDER" if request.action_type in EGRESS_ACTIONS else "ORGANISATION"
        )
        warden_decision = self.warden.evaluate(
            {
                "request_id": f"WARDEN-{request.action_id}",
                "requested_at": now.isoformat(),
                "box_id": session.box_id,
                "runtime_id": session.runtime_id,
                "subject_id": session.digitalme_id,
                "agent_id": session.agent_id,
                "context_id": session.context_id,
                "resource_id": target_url or session.workspace_id,
                "requested_action": str(request.action_type),
                "purpose": request.purpose,
                "data_classes": request.data_classes,
                "source_zone": "ORGANISATION",
                "destination_zone": destination_zone,
                "requested_duration_seconds": min(300, int((session.expires_at - now).total_seconds())),
                "human_approval_present": False,
            }
        )
        if warden_decision["outcome"] not in {"ALLOW", "RESTRICT"}:
            return self._deny_action(
                session,
                request,
                [*reasons, *warden_decision.get("reason_codes", []), "WARDEN_DENIED"],
                now,
                warden_policy_decision_id=warden_decision["policy_decision_id"],
            )
        capability = self.warden.issue(
            warden_decision["policy_decision_id"],
            session.digitalme_id,
        )
        reasons.extend(warden_decision.get("reason_codes", []))

        if request.action_type in policy.high_impact_actions:
            event = self._build_event(
                session=session,
                event_type="HUMAN_APPROVAL_REQUESTED",
                actor_id=session.digitalme_id,
                action_reference=request.action_id,
                payload={
                    "action_type": request.action_type,
                    "target_url": target_url,
                },
            )
            action = BrowserAction(
                action_id=request.action_id,
                browser_session_id=session.browser_session_id,
                action_type=request.action_type,
                decision=ActionDecision.APPROVAL_REQUIRED,
                reason_codes=[*reasons, "HUMAN_APPROVAL_REQUIRED"],
                target_url=target_url,
                warden_policy_decision_id=warden_decision["policy_decision_id"],
                capability_id=capability["capability_id"],
                approval_id=None,
                requested_at=now,
                decided_at=now,
                evidence_event_id=event.event_id,
            ).bind_request(request)
            try:
                self.repository.record_action(action, event)
            except Exception:
                try:
                    self.warden.revoke(
                        capability["capability_id"],
                        reason="CloudBrowser approval request could not be persisted",
                        revoked_by=session.digitalme_id,
                        policy_reference="CLOUDBROWSER-PERSISTENCE-FAILURE-V1",
                    )
                except Exception:
                    pass
                raise
            return action

        authorization_event = self._build_event(
            session=session,
            event_type="BROWSER_ACTION_AUTHORIZED",
            actor_id=session.agent_id or session.digitalme_id,
            action_reference=request.action_id,
            payload={
                "action_type": request.action_type,
                "target_url": target_url,
                "capability_id": capability["capability_id"],
            },
        )
        authorized = BrowserAction(
            action_id=request.action_id,
            browser_session_id=session.browser_session_id,
            action_type=request.action_type,
            decision=ActionDecision.ALLOW,
            reason_codes=[*reasons, "EXECUTION_AUTHORIZED"],
            target_url=target_url,
            warden_policy_decision_id=warden_decision["policy_decision_id"],
            capability_id=capability["capability_id"],
            requested_at=now,
            decided_at=now,
            evidence_event_id=authorization_event.event_id,
        ).bind_request(request)
        try:
            self.repository.record_action(authorized, authorization_event)
        except Exception:
            try:
                self.warden.revoke(
                    capability["capability_id"],
                    reason="CloudBrowser action authorization could not be persisted",
                    revoked_by=session.digitalme_id,
                    policy_reference="CLOUDBROWSER-PERSISTENCE-FAILURE-V1",
                )
            except Exception:
                pass
            raise

        try:
            result = self.executor.execute(session, request, policy)
        except Exception:
            failure_event = self._build_event(
                session=session,
                event_type="BROWSER_ACTION_FAILED",
                actor_id=session.agent_id or session.digitalme_id,
                action_reference=request.action_id,
                payload={
                    "action_type": request.action_type,
                    "target_url": target_url,
                    "reason_codes": ["CHROMIUM_EXECUTION_FAILED"],
                },
            )
            failed = authorized.model_copy(
                update={
                    "decision": ActionDecision.DENY,
                    "reason_codes": [*authorized.reason_codes, "EXECUTOR_FAILED"],
                    "decided_at": utcnow(),
                    "evidence_event_id": failure_event.event_id,
                }
            ).bind_request(request)
            self.repository.record_action(failed, failure_event)
            try:
                self.warden.revoke(
                    capability["capability_id"],
                    reason="CloudBrowser executor failed before action completion",
                    revoked_by=session.digitalme_id,
                    policy_reference="CLOUDBROWSER-EXECUTION-FAILURE-V1",
                )
            except Exception:
                pass
            raise
        executed_at = utcnow()
        event = self._build_event(
            session=session,
            event_type="BROWSER_ACTION_EXECUTED",
            actor_id=session.agent_id or session.digitalme_id,
            action_reference=request.action_id,
            payload={
                "action_type": request.action_type,
                "target_url": target_url,
                "result": result,
            },
        )
        action = authorized.model_copy(
            update={
                "decision": ActionDecision.EXECUTED,
                "reason_codes": [*authorized.reason_codes, "EXECUTED_WITHIN_CAPABILITY"],
                "decided_at": executed_at,
                "executed_at": executed_at,
                "result": result,
                "evidence_event_id": event.event_id,
            }
        ).bind_request(request)
        usage = self._next_usage(session, request, approval=False)
        self.repository.record_action(action, event, usage)
        return action

    def approve_action(
        self,
        session_id: str,
        request: BrowserApprovalRequest,
    ) -> BrowserAction:
        now = utcnow()
        session = self._require_active_session(session_id)
        if request.approved_by != session.digitalme_id:
            raise ForbiddenError(
                "Only the bound DigitalMe principal may approve this action",
                reason_codes=["APPROVER_NOT_PRINCIPAL"],
            )
        action = self.repository.get_action(request.action_id)
        if action is None or action.browser_session_id != session_id:
            raise NotFoundError(f"Browser action {request.action_id} does not exist")
        if action.decision != ActionDecision.APPROVAL_REQUIRED:
            raise StateConflictError("Browser action is not awaiting approval")

        original_request = action.request
        if original_request is None:
            raise StateConflictError("Original browser action request is unavailable")
        policy = self._require_policy(session.policy_id)
        approval_id = new_id("BROWSER-APPROVAL")
        approval_event = self._build_event(
            session=session,
            event_type="HUMAN_APPROVAL_GRANTED",
            actor_id=request.approved_by,
            action_reference=request.action_id,
            payload={"approval_id": approval_id, "reason": request.approval_reason},
        )
        approval = BrowserApproval(
            approval_id=approval_id,
            browser_session_id=session_id,
            action_id=request.action_id,
            approved_by=request.approved_by,
            approval_reason=request.approval_reason,
            approved_at=now,
            expires_at=now + timedelta(seconds=self.settings.approval_ttl_seconds),
            evidence_event_id=approval_event.event_id,
        )
        approved = action.model_copy(
            update={
                "decision": ActionDecision.APPROVED,
                "reason_codes": [*action.reason_codes, "HUMAN_APPROVAL_GRANTED"],
                "approval_id": approval_id,
                "decided_at": now,
                "evidence_event_id": approval_event.event_id,
            }
        ).bind_request(original_request)
        approval_usage = self._next_approval_usage(session)
        self.repository.record_approval_grant(
            approval, approved, approval_event, approval_usage
        )

        try:
            result = self.executor.execute(session, original_request, policy)
        except Exception:
            failure_event = self._build_event(
                session=session,
                event_type="BROWSER_ACTION_FAILED",
                actor_id=request.approved_by,
                action_reference=request.action_id,
                payload={
                    "approval_id": approval_id,
                    "action_type": action.action_type,
                    "target_url": action.target_url,
                    "reason_codes": ["CHROMIUM_EXECUTION_FAILED"],
                },
            )
            failed = approved.model_copy(
                update={
                    "decision": ActionDecision.DENY,
                    "reason_codes": [*approved.reason_codes, "EXECUTOR_FAILED"],
                    "decided_at": utcnow(),
                    "evidence_event_id": failure_event.event_id,
                }
            ).bind_request(original_request)
            self.repository.record_action(failed, failure_event)
            if action.capability_id:
                try:
                    self.warden.revoke(
                        action.capability_id,
                        reason="Approved CloudBrowser action failed in the executor",
                        revoked_by=request.approved_by,
                        policy_reference="CLOUDBROWSER-EXECUTION-FAILURE-V1",
                    )
                except Exception:
                    pass
            raise

        executed_at = utcnow()
        execution_event = self._build_event(
            session=session,
            event_type="BROWSER_ACTION_EXECUTED",
            actor_id=request.approved_by,
            action_reference=request.action_id,
            payload={
                "approval_id": approval.approval_id,
                "action_type": action.action_type,
                "target_url": action.target_url,
                "result": result,
            },
        )
        updated = approved.model_copy(
            update={
                "decision": ActionDecision.EXECUTED,
                "reason_codes": [*approved.reason_codes, "EXECUTED_WITHIN_APPROVAL"],
                "decided_at": executed_at,
                "executed_at": executed_at,
                "result": result,
                "evidence_event_id": execution_event.event_id,
            }
        ).bind_request(original_request)
        usage = self._next_usage(session, original_request, approval=False)
        self.repository.record_action(updated, execution_event, usage)
        return updated

    def pause_session(self, session_id: str, request: SessionPauseRequest) -> BrowserSession:
        session = self._require_active_session(session_id)
        self.executor.pause_session(session)
        paused = session.model_copy(update={"session_status": SessionStatus.PAUSED})
        event = self._build_event(
            session=paused,
            event_type="BROWSER_SESSION_PAUSED",
            actor_id=request.paused_by,
            action_reference=session_id,
            payload={"reason": request.reason},
        )
        self.repository.transition_session(paused, event)
        return paused

    def terminate_session(
        self,
        session_id: str,
        request: SessionTerminateRequest,
    ) -> BrowserSession:
        now = utcnow()
        session = self._require_session(session_id)
        if session.session_status == SessionStatus.TERMINATED:
            raise StateConflictError("Browser session is already terminated")
        capability_ids = {session.capability_id}
        capability_ids.update(
            action.capability_id
            for action in self.repository.list_session_actions(session_id)
            if action.capability_id
        )
        for capability_id in capability_ids:
            try:
                self.warden.revoke(
                    capability_id,
                    reason=request.reason,
                    revoked_by=request.terminated_by,
                    policy_reference="CLOUDBROWSER-SESSION-TERMINATION-V1",
                )
            except Exception:
                pass
        self.executor.terminate_session(session)
        terminated = session.model_copy(
            update={
                "session_status": SessionStatus.TERMINATED,
                "terminated_at": now,
            }
        )
        event = self._build_event(
            session=terminated,
            event_type="BROWSER_SESSION_TERMINATED",
            actor_id=request.terminated_by,
            action_reference=session_id,
            payload={"reason": request.reason},
        )
        usage = self._next_runtime_usage(terminated, now)
        self.repository.transition_session(terminated, event, usage)
        return terminated

    def usage(self, session_id: str) -> UsageRecord:
        session = self._require_session(session_id)
        now = utcnow()
        self._refresh_runtime_usage(session, now)
        usage = self.repository.get_usage(session_id)
        if usage is None:
            raise StateConflictError("Session usage meter is missing")
        return usage

    def evidence(self, session_id: str):
        self._require_session(session_id)
        return self.repository.list_evidence(session_id)

    def _require_session(self, session_id: str) -> BrowserSession:
        session = self.repository.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Browser session {session_id} does not exist")
        return session

    def _require_active_session(self, session_id: str) -> BrowserSession:
        session = self._expire_if_needed(self._require_session(session_id))
        if session.session_status != SessionStatus.ACTIVE:
            raise StateConflictError(
                f"Browser session is not active: {session.session_status}"
            )
        return session

    def _expire_if_needed(self, session: BrowserSession) -> BrowserSession:
        now = utcnow()
        if session.session_status == SessionStatus.ACTIVE and now >= session.expires_at:
            self.executor.terminate_session(session)
            expired = session.model_copy(update={"session_status": SessionStatus.EXPIRED})
            event = self._build_event(
                session=expired,
                event_type="BROWSER_SESSION_EXPIRED",
                actor_id=session.digitalme_id,
                action_reference=session.browser_session_id,
                payload={},
            )
            usage = self._next_runtime_usage(expired, now)
            self.repository.transition_session(expired, event, usage)
            return expired
        return session

    def _require_policy(self, policy_id: str) -> BrowserPolicy:
        policy = self.repository.get_policy(policy_id)
        if policy is None:
            raise NotFoundError(f"Browser policy {policy_id} does not exist")
        return policy

    def _deny_action(
        self,
        session: BrowserSession,
        request: BrowserActionRequest,
        reasons: list[str],
        now,
        *,
        warden_policy_decision_id: str | None = None,
    ) -> BrowserAction:
        event = self._build_event(
            session=session,
            event_type="BROWSER_ACTION_DENIED",
            actor_id=session.agent_id or session.digitalme_id,
            action_reference=request.action_id,
            payload={
                "action_type": request.action_type,
                "target_url": str(request.target_url) if request.target_url else None,
                "reason_codes": reasons,
            },
        )
        action = BrowserAction(
            action_id=request.action_id,
            browser_session_id=session.browser_session_id,
            action_type=request.action_type,
            decision=ActionDecision.DENY,
            reason_codes=reasons,
            target_url=str(request.target_url) if request.target_url else None,
            warden_policy_decision_id=warden_policy_decision_id,
            requested_at=now,
            decided_at=now,
            evidence_event_id=event.event_id,
        ).bind_request(request)
        self.repository.record_action(action, event)
        return action

    def _control_denial(
        self,
        policy: BrowserPolicy,
        request: BrowserActionRequest,
    ) -> str | None:
        action = request.action_type
        if action == BrowserActionType.UPLOAD_FILE:
            if not policy.allow_uploads:
                return "UPLOAD_DISABLED"
            if request.estimated_file_bytes > policy.max_file_bytes:
                return "UPLOAD_SIZE_EXCEEDED"
        if action == BrowserActionType.DOWNLOAD_FILE:
            if not policy.allow_downloads:
                return "DOWNLOAD_DISABLED"
            if request.estimated_file_bytes > policy.max_file_bytes:
                return "DOWNLOAD_SIZE_EXCEEDED"
        if action == BrowserActionType.USE_CLIPBOARD and not policy.allow_clipboard:
            return "CLIPBOARD_DISABLED"
        if action == BrowserActionType.USE_CREDENTIAL:
            if not policy.allow_credentials:
                return "CREDENTIAL_USE_DISABLED"
            if "credential_reference" not in request.payload:
                return "CREDENTIAL_REFERENCE_REQUIRED"
        if action == BrowserActionType.CAPTURE_SCREEN and not policy.allow_screen_capture:
            return "SCREEN_CAPTURE_DISABLED"
        return None

    def _reject_raw_secrets(self, value) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key.lower() in RAW_SECRET_KEYS:
                    raise ForbiddenError(
                        "Raw credentials or secrets cannot enter CloudBrowser payloads",
                        reason_codes=["RAW_SECRET_REJECTED"],
                    )
                self._reject_raw_secrets(nested)
        elif isinstance(value, list):
            for nested in value:
                self._reject_raw_secrets(nested)

    def _domain_allowed(self, target_url: str, allowed_domains: list[str]) -> bool:
        hostname = (urlparse(target_url).hostname or "").lower()
        for rule in allowed_domains:
            normalized = rule.lower().strip()
            if normalized.startswith("*."):
                suffix = normalized[2:]
                if hostname.endswith(f".{suffix}") and hostname != suffix:
                    return True
            elif hostname == normalized:
                return True
        return False

    def _next_usage(
        self,
        session: BrowserSession,
        request: BrowserActionRequest,
        *,
        approval: bool,
    ) -> UsageRecord:
        usage = self.repository.get_usage(session.browser_session_id)
        if usage is None:
            raise StateConflictError("Session usage meter is missing")
        connector_calls = (
            1 if request.action_type == BrowserActionType.OPEN_CONNECTOR else 0
        )
        uploaded = (
            request.estimated_file_bytes
            if request.action_type == BrowserActionType.UPLOAD_FILE
            else 0
        )
        downloaded = (
            request.estimated_file_bytes
            if request.action_type == BrowserActionType.DOWNLOAD_FILE
            else 0
        )
        return usage.model_copy(
            update={
                "action_count": usage.action_count + 1,
                "approval_count": usage.approval_count + (1 if approval else 0),
                "connector_calls": usage.connector_calls + connector_calls,
                "uploaded_bytes": usage.uploaded_bytes + uploaded,
                "downloaded_bytes": usage.downloaded_bytes + downloaded,
                "network_bytes": (
                    usage.network_bytes + request.estimated_network_bytes
                ),
                "compute_units": round(
                    usage.compute_units
                    + 1.0
                    + request.estimated_network_bytes / 1_000_000,
                    6,
                ),
                "updated_at": utcnow(),
            }
        )

    def _next_approval_usage(self, session: BrowserSession) -> UsageRecord:
        usage = self.repository.get_usage(session.browser_session_id)
        if usage is None:
            raise StateConflictError("Session usage meter is missing")
        return usage.model_copy(
            update={
                "approval_count": usage.approval_count + 1,
                "compute_units": round(usage.compute_units + 0.25, 6),
                "updated_at": utcnow(),
            }
        )

    def _next_runtime_usage(self, session: BrowserSession, now) -> UsageRecord:
        usage = self.repository.get_usage(session.browser_session_id)
        if usage is None:
            raise StateConflictError("Session usage meter is missing")
        end = session.terminated_at or min(now, session.expires_at)
        runtime_seconds = max(0, int((end - session.started_at).total_seconds()))
        return usage.model_copy(
            update={
                "runtime_seconds": runtime_seconds,
                "compute_units": round(
                    max(usage.compute_units, runtime_seconds / 60), 6
                ),
                "updated_at": now,
            }
        )

    def _refresh_runtime_usage(self, session: BrowserSession, now) -> None:
        self.repository.save_usage(self._next_runtime_usage(session, now))

    def _build_event(
        self,
        *,
        session: BrowserSession,
        event_type: str,
        actor_id: str,
        action_reference: str,
        payload: dict,
        previous_event_hash: str | None = None,
    ):
        if previous_event_hash is None:
            latest = self.repository.latest_evidence(session.browser_session_id)
            previous_event_hash = latest.evidence_hash if latest else None
        return build_event(
            browser_session_id=session.browser_session_id,
            box_id=session.box_id,
            event_type=event_type,
            actor_id=actor_id,
            action_reference=action_reference,
            payload=payload,
            previous_event_hash=previous_event_hash,
        )

    def _emit(self, **kwargs):
        event = self._build_event(**kwargs)
        self.repository.append_evidence(event)
        return event

    @staticmethod
    def _parse_time(value: str):
        from datetime import datetime

        return datetime.fromisoformat(value.replace("Z", "+00:00"))
