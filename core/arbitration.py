"""
AAC Protocol Arbitration System

Three-level arbitration system for dispute resolution:
- Level 1 (First Instance): 1 high-trust arbitrator
- Level 2 (Second Instance): 3 high-trust arbitrators
- Level 3 (Final Instance): 5 high-trust arbitrators

Compensation rules:
- Non-intentional damage: Max 5x original payment
- Intentional damage: Max 15x original payment + agent deletion
"""

import uuid
from datetime import datetime
from typing import List, Optional, Tuple
from decimal import Decimal

from .models import (
    Dispute, DisputeEvidence, ArbitratorDecision, DisputeStatus,
    ArbitrationLevel, ArbitrationResult, Intent, Task,
    ArbitrationConfig
)
from .database import Database
from .token import TokenSystem


class ArbitrationError(Exception):
    """Raised for arbitration system errors"""
    pass


class InvalidDisputeError(ArbitrationError):
    """Raised when dispute is invalid"""
    pass


class ArbitrationSystem:
    """
    Three-level arbitration system for AAC Protocol
    
    Handles dispute filing, evidence submission, arbitrator selection,
    decision making, and compensation execution.
    """
    
    def __init__(
        self,
        database: Database,
        token_system: TokenSystem,
        config: Optional[ArbitrationConfig] = None
    ):
        self.db = database
        self.tokens = token_system
        self.config = config or ArbitrationConfig()
        
        # Track high-trust agents eligible for arbitration
        self._arbitrator_pool: List[str] = []
    
    async def file_dispute(
        self,
        task_id: str,
        user_id: str,
        user_claim: str,
        claimed_amount: float,
        initial_evidence: Optional[DisputeEvidence] = None
    ) -> Dispute:
        """
        File a new dispute
        
        Args:
            task_id: Related task ID
            user_id: User filing the dispute
            user_claim: Description of the complaint
            claimed_amount: Amount being claimed
            initial_evidence: Optional initial evidence
            
        Returns:
            Created dispute object
            
        Raises:
            InvalidDisputeError: If task not found or already disputed
        """
        # Get task
        task = await self.db.get_task(task_id)
        if not task:
            raise InvalidDisputeError(f"Task not found: {task_id}")
        
        # Check if already disputed
        if task.status.value == "disputed":
            raise InvalidDisputeError("Task already has an active dispute")
        
        # Get agent and creator
        agent = await self.db.get_agent(task.agent_id)
        if not agent:
            raise InvalidDisputeError(f"Agent not found: {task.agent_id}")
        
        # Validate claim amount (max 15x original payment)
        max_claim = task.price_locked * self.config.max_compensation_intentional
        if claimed_amount > max_claim:
            raise InvalidDisputeError(
                f"Claimed amount {claimed_amount} exceeds maximum {max_claim}"
            )
        
        # Create dispute
        dispute_id = f"dispute-{uuid.uuid4().hex[:12]}"
        
        user_evidence = []
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
            current_level=ArbitrationLevel.FIRST,
            final_compensation=0.0,
        )
        
        # Save dispute
        await self.db.create_dispute(dispute)
        
        # Update task status
        task.status = TaskStatus(DisputeStatus.DISPUTED.value)
        await self.db.update_task(task)
        
        # Lock payment
        await self.db.update_payment_status(
            payment_id=f"payment-{task_id}",  # Assuming this format
            status=PaymentStatus.DISPUTED
        )
        
        return dispute
    
    async def submit_evidence(
        self,
        dispute_id: str,
        submitter_id: str,
        content: str,
        attachments: Optional[List[dict]] = None
    ) -> Dispute:
        """
        Submit evidence for a dispute
        
        Args:
            dispute_id: Dispute ID
            submitter_id: User or Creator/Agent ID
            content: Evidence description
            attachments: Supporting files/data
            
        Returns:
            Updated dispute
        """
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
        
        # Add to appropriate list
        if submitter_id == dispute.user_id:
            dispute.user_evidence.append(evidence)
        else:
            dispute.agent_evidence.append(evidence)
        
        await self.db.update_dispute(dispute)
        return dispute
    
    async def assign_arbitrators(self, dispute_id: str) -> Dispute:
        """
        Assign arbitrators for current level
        
        Args:
            dispute_id: Dispute ID
            
        Returns:
            Updated dispute with assigned arbitrators
        """
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        
        # Get pool of qualified arbitrators
        arbitrators = await self._get_qualified_arbitrators(dispute.current_level)
        
        if len(arbitrators) < self._get_arbitrator_count(dispute.current_level):
            raise ArbitrationError("Insufficient qualified arbitrators available")
        
        # Assign based on level
        if dispute.current_level == ArbitrationLevel.FIRST:
            dispute.level_1_arbitrator = arbitrators[0]
            dispute.status = DisputeStatus.FIRST_INSTANCE
            
        elif dispute.current_level == ArbitrationLevel.SECOND:
            dispute.level_2_arbitrators = arbitrators[:3]
            dispute.status = DisputeStatus.SECOND_INSTANCE
            
        elif dispute.current_level == ArbitrationLevel.THIRD:
            dispute.level_3_arbitrators = arbitrators[:5]
            dispute.status = DisputeStatus.FINAL_INSTANCE
        
        await self.db.update_dispute(dispute)
        return dispute
    
    async def submit_arbitration_decision(
        self,
        dispute_id: str,
        arbitrator_id: str,
        decision: ArbitrationResult,
        intent: Intent,
        compensation_amount: float,
        reasoning: str
    ) -> Dispute:
        """
        Submit arbitrator decision
        
        Args:
            dispute_id: Dispute ID
            arbitrator_id: Arbitrator agent ID
            decision: Decision result
            intent: Intent classification
            compensation_amount: Recommended compensation
            reasoning: Decision explanation
            
        Returns:
            Updated dispute
        """
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        
        # Create decision
        arb_decision = ArbitratorDecision(
            arbitrator_id=arbitrator_id,
            decision=decision,
            intent=intent,
            compensation_amount=compensation_amount,
            reasoning=reasoning,
            submitted_at=datetime.utcnow(),
        )
        
        # Add to appropriate level
        if dispute.current_level == ArbitrationLevel.FIRST:
            if dispute.level_1_decision:
                raise ArbitrationError("Level 1 decision already submitted")
            dispute.level_1_decision = arb_decision
            
        elif dispute.current_level == ArbitrationLevel.SECOND:
            if len(dispute.level_2_decisions) >= 3:
                raise ArbitrationError("All Level 2 decisions submitted")
            dispute.level_2_decisions.append(arb_decision)
            
        elif dispute.current_level == ArbitrationLevel.THIRD:
            if len(dispute.level_3_decisions) >= 5:
                raise ArbitrationError("All Level 3 decisions submitted")
            dispute.level_3_decisions.append(arb_decision)
        
        await self.db.update_dispute(dispute)
        
        # Check if all decisions received for current level
        await self._check_level_complete(dispute)
        
        return dispute
    
    async def escalate_dispute(
        self,
        dispute_id: str,
        requested_by: str
    ) -> Dispute:
        """
        Escalate dispute to next arbitration level
        
        Args:
            dispute_id: Dispute ID
            requested_by: User or Creator requesting escalation
            
        Returns:
            Escalated dispute
        """
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        
        # Check current level
        if dispute.current_level == ArbitrationLevel.THIRD:
            raise ArbitrationError("Dispute already at final level")
        
        # Verify current level has decision
        if dispute.current_level == ArbitrationLevel.FIRST and not dispute.level_1_decision:
            raise ArbitrationError("Level 1 must have a decision before escalation")
        
        if dispute.current_level == ArbitrationLevel.SECOND and len(dispute.level_2_decisions) < 3:
            raise ArbitrationError("Level 2 must have all decisions before escalation")
        
        # Escalate
        dispute.current_level = ArbitrationLevel(dispute.current_level.value + 1)
        dispute.escalated_at = datetime.utcnow()
        dispute.escalation_requested_by = requested_by
        
        await self.db.update_dispute(dispute)
        
        # Assign new arbitrators
        await self.assign_arbitrators(dispute_id)
        
        return dispute
    
    async def resolve_dispute(self, dispute_id: str) -> Dispute:
        """
        Resolve dispute with final decision
        
        Args:
            dispute_id: Dispute ID
            
        Returns:
            Resolved dispute
        """
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        
        # Aggregate decisions
        final_decision, final_intent, final_compensation = await self._aggregate_decisions(dispute)
        
        # Apply limits
        task = await self.db.get_task(dispute.task_id)
        if final_intent == Intent.INTENTIONAL:
            max_comp = task.price_locked * self.config.max_compensation_intentional
            final_compensation = min(final_compensation, max_comp)
        else:
            max_comp = task.price_locked * self.config.max_compensation_non_intentional
            final_compensation = min(final_compensation, max_comp)
        
        # Update dispute
        dispute.final_decision = final_decision
        dispute.final_intent = final_intent
        dispute.final_compensation = final_compensation
        dispute.status = DisputeStatus.RESOLVED
        dispute.resolved_at = datetime.utcnow()
        
        await self.db.update_dispute(dispute)
        
        # Execute compensation if needed
        if final_compensation > 0 and final_decision in [
            ArbitrationResult.IN_FAVOR_OF_USER,
            ArbitrationResult.PARTIAL_COMPENSATION
        ]:
            await self._execute_compensation(dispute)
        
        # Handle intentional damage consequences
        if final_intent == Intent.INTENTIONAL:
            await self._handle_intentional_damage(dispute)
        
        return dispute
    
    async def _aggregate_decisions(
        self,
        dispute: Dispute
    ) -> Tuple[ArbitrationResult, Intent, float]:
        """
        Aggregate decisions from current level
        
        Returns:
            Tuple of (decision, intent, compensation)
        """
        decisions = []
        
        if dispute.current_level == ArbitrationLevel.FIRST and dispute.level_1_decision:
            decisions = [dispute.level_1_decision]
        elif dispute.current_level == ArbitrationLevel.SECOND:
            decisions = dispute.level_2_decisions
        elif dispute.current_level == ArbitrationLevel.THIRD:
            decisions = dispute.level_3_decisions
        
        if not decisions:
            raise ArbitrationError("No decisions to aggregate")
        
        # Count votes
        user_votes = sum(1 for d in decisions if d.decision == ArbitrationResult.IN_FAVOR_OF_USER)
        agent_votes = sum(1 for d in decisions if d.decision == ArbitrationResult.IN_FAVOR_OF_AGENT)
        partial_votes = sum(1 for d in decisions if d.decision == ArbitrationResult.PARTIAL_COMPENSATION)
        
        # Determine result (majority)
        total = len(decisions)
        
        if user_votes > total / 2:
            final_decision = ArbitrationResult.IN_FAVOR_OF_USER
        elif agent_votes > total / 2:
            final_decision = ArbitrationResult.IN_FAVOR_OF_AGENT
        else:
            final_decision = ArbitrationResult.PARTIAL_COMPENSATION
        
        # Check intent (any intentional is enough for intentional classification)
        intentional_votes = sum(1 for d in decisions if d.intent == Intent.INTENTIONAL)
        final_intent = Intent.INTENTIONAL if intentional_votes > 0 else Intent.NON_INTENTIONAL
        
        # Average compensation
        if final_decision == ArbitrationResult.IN_FAVOR_OF_USER:
            # User gets claimed amount or average recommended
            final_compensation = min(
                dispute.claimed_amount,
                sum(d.compensation_amount for d in decisions) / len(decisions)
            )
        elif final_decision == ArbitrationResult.PARTIAL_COMPENSATION:
            final_compensation = sum(d.compensation_amount for d in decisions) / len(decisions)
        else:
            final_compensation = 0.0
        
        return final_decision, final_intent, final_compensation
    
    async def _execute_compensation(self, dispute: Dispute):
        """Execute compensation payment"""
        await self.tokens.compensate(
            dispute_id=dispute.id,
            from_address=dispute.creator_id,
            to_address=dispute.user_id,
            amount=dispute.final_compensation,
            is_intentional=(dispute.final_intent == Intent.INTENTIONAL)
        )
    
    async def _handle_intentional_damage(self, dispute: Dispute):
        """Handle consequences of intentional damage"""
        # Delete/suspend the agent
        from .models import AgentStatus
        
        agent = await self.db.get_agent(dispute.agent_id)
        if agent:
            agent.status = AgentStatus.DELETED
            await self.db.update_agent(agent)
        
        # Update creator trust score
        creator = await self.db.get_creator(dispute.creator_id)
        if creator:
            creator.trust_score = max(0, creator.trust_score - 50)
            await self.db.update_creator(creator)
    
    async def _check_level_complete(self, dispute: Dispute):
        """Check if all decisions received for current level"""
        required = self._get_arbitrator_count(dispute.current_level)
        
        current_count = 0
        if dispute.current_level == ArbitrationLevel.FIRST:
            current_count = 1 if dispute.level_1_decision else 0
        elif dispute.current_level == ArbitrationLevel.SECOND:
            current_count = len(dispute.level_2_decisions)
        elif dispute.current_level == ArbitrationLevel.THIRD:
            current_count = len(dispute.level_3_decisions)
        
        if current_count >= required:
            # Level complete - can resolve or escalate
            pass  # Arbitration proceeds based on party satisfaction
    
    def _get_arbitrator_count(self, level: ArbitrationLevel) -> int:
        """Get number of arbitrators for a level"""
        counts = {
            ArbitrationLevel.FIRST: 1,
            ArbitrationLevel.SECOND: 3,
            ArbitrationLevel.THIRD: 5,
        }
        return counts[level]
    
    async def _get_qualified_arbitrators(self, level: ArbitrationLevel) -> List[str]:
        """
        Get list of agents qualified to arbitrate at this level
        
        Returns:
            List of agent IDs ordered by trust score
        """
        # Get threshold
        thresholds = {
            ArbitrationLevel.FIRST: self.config.min_trust_score_level_1,
            ArbitrationLevel.SECOND: self.config.min_trust_score_level_2,
            ArbitrationLevel.THIRD: self.config.min_trust_score_level_3,
        }
        min_trust = thresholds[level]
        
        # Query high-trust agents
        # In production, this would query database for agents with trust score >= min_trust
        # and exclude agents owned by involved parties
        
        # Return mock list for now
        return self._arbitrator_pool
    
    async def add_to_arbitrator_pool(self, agent_id: str):
        """Add agent to arbitrator pool"""
        if agent_id not in self._arbitrator_pool:
            self._arbitrator_pool.append(agent_id)
    
    async def get_dispute_status(self, dispute_id: str) -> dict:
        """
        Get detailed dispute status
        
        Args:
            dispute_id: Dispute ID
            
        Returns:
            Status dictionary
        """
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ArbitrationError(f"Dispute not found: {dispute_id}")
        
        return {
            "dispute_id": dispute.id,
            "task_id": dispute.task_id,
            "status": dispute.status.value,
            "current_level": dispute.current_level.value,
            "user_claim": dispute.user_claim,
            "claimed_amount": dispute.claimed_amount,
            "evidence_count": {
                "user": len(dispute.user_evidence),
                "agent": len(dispute.agent_evidence),
            },
            "decisions_received": {
                "level_1": 1 if dispute.level_1_decision else 0,
                "level_2": len(dispute.level_2_decisions),
                "level_3": len(dispute.level_3_decisions),
            },
            "final_decision": dispute.final_decision.value if dispute.final_decision else None,
            "final_intent": dispute.final_intent.value if dispute.final_intent else None,
            "final_compensation": dispute.final_compensation,
            "created_at": dispute.created_at.isoformat(),
            "resolved_at": dispute.resolved_at.isoformat() if dispute.resolved_at else None,
        }
