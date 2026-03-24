"""
AAC Protocol — platform dispute mediation (centralized)

Disputes are triaged by platform staff (single binding decision). An optional
community advisory round collects multiple opinions and aggregates by majority;
randomness uses the standard library only (no VRF / on-chain claims).
"""

import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from .models import (
    Dispute,
    DisputeEvidence,
    ArbitratorDecision,
    DisputeStatus,
    ArbitrationResult,
    Intent,
    Task,
    ArbitrationConfig,
    TaskStatus,
    PaymentStatus,
)
from .database import Database
from .escrow import EscrowLedger


class ArbitrationError(Exception):
    """Dispute / mediation errors"""
    pass


class InvalidDisputeError(ArbitrationError):
    """Raised when dispute preconditions fail"""
    pass


class ArbitrationSystem:
    """
    Centralized dispute service: platform mediator + optional community votes.
    """

    def __init__(
        self,
        database: Database,
        ledger: EscrowLedger,
        config: Optional[ArbitrationConfig] = None,
    ):
        self.db = database
        self.ledger = ledger
        self.config = config or ArbitrationConfig()
        self._community_pool: List[str] = []

    async def add_community_voter(self, voter_id: str) -> None:
        """Register an account id eligible for optional community advisory votes."""
        if voter_id not in self._community_pool:
            self._community_pool.append(voter_id)

    async def file_dispute(
        self,
        task_id: str,
        user_id: str,
        user_claim: str,
        claimed_amount: float,
        initial_evidence: Optional[DisputeEvidence] = None,
    ) -> Dispute:
        task = await self.db.get_task(task_id)
        if not task:
            raise InvalidDisputeError(f"Task not found: {task_id}")
        if task.status == TaskStatus.DISPUTED:
            raise InvalidDisputeError("Task already has an active dispute")

        agent = await self.db.get_agent(task.agent_id)
        if not agent:
            raise InvalidDisputeError(f"Agent not found: {task.agent_id}")

        max_claim = task.price_locked * self.config.max_compensation_intentional
        if claimed_amount > max_claim:
            raise InvalidDisputeError(
                f"Claimed amount {claimed_amount} exceeds maximum {max_claim}"
            )

        dispute_id = f"dispute-{uuid.uuid4().hex[:12]}"
        user_evidence: List[DisputeEvidence] = []
        if initial_evidence:
            user_evidence.append(initial_evidence)

        dispute = Dispute(
            id=dispute_id,
            task_id=task_id,
            user_id=user_id,
            agent_id=task.agent_id,
            creator_id=agent.creator_id,
            user_claim=user_claim,
            claimed_amount=claimed_amount,
            user_evidence=user_evidence,
            status=DisputeStatus.OPEN,
        )
        await self.db.create_dispute(dispute)

        task.status = TaskStatus.DISPUTED
        await self.db.update_task(task)

        await self.db.update_payment_status(
            payment_id=f"payment-{task_id}",
            status=PaymentStatus.DISPUTED,
        )
        return dispute

    async def submit_evidence(
        self,
        dispute_id: str,
        submitter_id: str,
        content: str,
        attachments: Optional[List[dict]] = None,
    ) -> Dispute:
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        if dispute.status == DisputeStatus.RESOLVED:
            raise ArbitrationError("Dispute already resolved")

        evidence = DisputeEvidence(
            submitted_by=submitter_id,
            content=content,
            attachments=attachments or [],
            submitted_at=datetime.utcnow(),
        )
        if submitter_id == dispute.user_id:
            dispute.user_evidence.append(evidence)
        else:
            dispute.agent_evidence.append(evidence)
        await self.db.update_dispute(dispute)
        return dispute

    async def assign_platform_mediator(
        self, dispute_id: str, mediator_staff_id: str
    ) -> Dispute:
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        if dispute.status not in (DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW):
            raise ArbitrationError("Mediator can only be assigned while case is open")
        dispute.platform_mediator_id = mediator_staff_id
        dispute.status = DisputeStatus.UNDER_REVIEW
        await self.db.update_dispute(dispute)
        return dispute

    async def assign_arbitrators(self, dispute_id: str) -> Dispute:
        """
        Mark the case as under platform review. Mediator id is set when the
        first decision is submitted (legacy test / SDK flow).
        """
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        dispute.status = DisputeStatus.UNDER_REVIEW
        await self.db.update_dispute(dispute)
        return dispute

    async def submit_platform_decision(
        self,
        dispute_id: str,
        mediator_id: str,
        decision: ArbitrationResult,
        intent: Intent,
        compensation_amount: float,
        reasoning: str,
    ) -> Dispute:
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        if dispute.platform_mediator_id and dispute.platform_mediator_id != mediator_id:
            raise ArbitrationError("Mediator id does not match assigned mediator")
        if not dispute.platform_mediator_id:
            dispute.platform_mediator_id = mediator_id
        if dispute.status == DisputeStatus.OPEN:
            dispute.status = DisputeStatus.UNDER_REVIEW

        dispute.platform_decision = ArbitratorDecision(
            arbitrator_id=mediator_id,
            decision=decision,
            intent=intent,
            compensation_amount=compensation_amount,
            reasoning=reasoning,
            submitted_at=datetime.utcnow(),
        )
        await self.db.update_dispute(dispute)
        return dispute

    async def submit_arbitration_decision(
        self,
        dispute_id: str,
        arbitrator_id: str,
        decision: ArbitrationResult,
        intent: Intent,
        compensation_amount: float,
        reasoning: str,
    ) -> Dispute:
        """Alias for :meth:`submit_platform_decision` (tests / legacy SDK)."""
        return await self.submit_platform_decision(
            dispute_id,
            arbitrator_id,
            decision,
            intent,
            compensation_amount,
            reasoning,
        )

    async def request_community_review(
        self, dispute_id: str, requested_by: str
    ) -> Dispute:
        """Optional second phase: community advisory votes (non-binding until finalized)."""
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        if dispute.status not in (
            DisputeStatus.UNDER_REVIEW,
            DisputeStatus.OPEN,
        ):
            raise ArbitrationError("Community review not available for this status")
        dispute.status = DisputeStatus.COMMUNITY_VOTE
        dispute.community_review_requested_at = datetime.utcnow()
        dispute.community_review_requested_by = requested_by
        dispute.community_decisions = []
        await self.db.update_dispute(dispute)
        return dispute

    async def escalate_dispute(self, dispute_id: str, requested_by: str) -> Dispute:
        """Deprecated name: opens optional community advisory round."""
        return await self.request_community_review(dispute_id, requested_by)

    async def submit_community_decision(
        self,
        dispute_id: str,
        voter_id: str,
        decision: ArbitrationResult,
        intent: Intent,
        compensation_amount: float,
        reasoning: str,
    ) -> Dispute:
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        if dispute.status != DisputeStatus.COMMUNITY_VOTE:
            raise ArbitrationError("Case is not in community vote phase")

        dispute.community_decisions.append(
            ArbitratorDecision(
                arbitrator_id=voter_id,
                decision=decision,
                intent=intent,
                compensation_amount=compensation_amount,
                reasoning=reasoning,
                submitted_at=datetime.utcnow(),
            )
        )
        await self.db.update_dispute(dispute)
        return dispute

    def _aggregate_decisions(
        self, decisions: List[ArbitratorDecision], dispute: Dispute
    ) -> Tuple[ArbitrationResult, Intent, float]:
        if not decisions:
            raise ArbitrationError("No decisions to aggregate")

        user_votes = sum(
            1 for d in decisions if d.decision == ArbitrationResult.IN_FAVOR_OF_USER
        )
        agent_votes = sum(
            1 for d in decisions if d.decision == ArbitrationResult.IN_FAVOR_OF_AGENT
        )
        total = len(decisions)
        if user_votes > total / 2:
            final_decision = ArbitrationResult.IN_FAVOR_OF_USER
        elif agent_votes > total / 2:
            final_decision = ArbitrationResult.IN_FAVOR_OF_AGENT
        else:
            final_decision = ArbitrationResult.PARTIAL_COMPENSATION

        intentional_votes = sum(1 for d in decisions if d.intent == Intent.INTENTIONAL)
        final_intent = (
            Intent.INTENTIONAL if intentional_votes > 0 else Intent.NON_INTENTIONAL
        )

        if final_decision == ArbitrationResult.IN_FAVOR_OF_USER:
            final_compensation = min(
                dispute.claimed_amount,
                sum(d.compensation_amount for d in decisions) / len(decisions),
            )
        elif final_decision == ArbitrationResult.PARTIAL_COMPENSATION:
            final_compensation = sum(d.compensation_amount for d in decisions) / len(
                decisions
            )
        else:
            final_compensation = 0.0

        return final_decision, final_intent, final_compensation

    async def resolve_dispute(self, dispute_id: str) -> Dispute:
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")

        if (
            dispute.status == DisputeStatus.COMMUNITY_VOTE
            and len(dispute.community_decisions) >= self.config.community_votes_required
        ):
            final_decision, final_intent, final_compensation = self._aggregate_decisions(
                dispute.community_decisions, dispute
            )
        elif dispute.platform_decision:
            d = dispute.platform_decision
            final_decision, final_intent, final_compensation = (
                d.decision,
                d.intent,
                d.compensation_amount,
            )
        else:
            raise ArbitrationError("No platform or community decision to finalize")

        task = await self.db.get_task(dispute.task_id)
        if not task:
            raise ArbitrationError("Task missing for dispute")

        if final_intent == Intent.INTENTIONAL:
            max_comp = task.price_locked * self.config.max_compensation_intentional
            final_compensation = min(final_compensation, max_comp)
        else:
            max_comp = task.price_locked * self.config.max_compensation_non_intentional
            final_compensation = min(final_compensation, max_comp)

        dispute.final_decision = final_decision
        dispute.final_intent = final_intent
        dispute.final_compensation = final_compensation
        dispute.status = DisputeStatus.RESOLVED
        dispute.resolved_at = datetime.utcnow()
        await self.db.update_dispute(dispute)

        if final_compensation > 0 and final_decision in (
            ArbitrationResult.IN_FAVOR_OF_USER,
            ArbitrationResult.PARTIAL_COMPENSATION,
        ):
            await self.ledger.compensate(
                dispute_id=dispute.id,
                from_address=dispute.creator_id,
                to_address=dispute.user_id,
                amount=dispute.final_compensation,
                is_intentional=(dispute.final_intent == Intent.INTENTIONAL),
            )

        if final_intent == Intent.INTENTIONAL:
            from .models import AgentStatus

            agent = await self.db.get_agent(dispute.agent_id)
            if agent:
                agent.status = AgentStatus.DELETED
                await self.db.update_agent(agent)
            creator = await self.db.get_creator(dispute.creator_id)
            if creator:
                creator.trust_score = max(0, creator.trust_score - 50)
                await self.db.update_creator(creator)

        return dispute

    async def get_dispute_status(self, dispute_id: str) -> dict:
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")

        return {
            "dispute_id": dispute.id,
            "task_id": dispute.task_id,
            "status": dispute.status.value,
            "platform_mediator_id": dispute.platform_mediator_id,
            "user_claim": dispute.user_claim,
            "claimed_amount": dispute.claimed_amount,
            "evidence_count": {
                "user": len(dispute.user_evidence),
                "agent": len(dispute.agent_evidence),
            },
            "has_platform_decision": dispute.platform_decision is not None,
            "community_decisions_count": len(dispute.community_decisions),
            "final_decision": dispute.final_decision.value
            if dispute.final_decision
            else None,
            "final_intent": dispute.final_intent.value if dispute.final_intent else None,
            "final_compensation": dispute.final_compensation,
            "created_at": dispute.created_at.isoformat(),
            "resolved_at": dispute.resolved_at.isoformat()
            if dispute.resolved_at
            else None,
        }
