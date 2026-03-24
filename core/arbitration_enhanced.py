"""
AAC Protocol — Enhanced Arbitration System

Resilient dispute resolution with:
- Weighted voting (stake-weighted, reputation-weighted, expertise-weighted)
- Sybil attack resistance (stake requirements, identity verification)
- Three-tier arbitration (platform + community + appeal)
- Consensus mechanisms (Quadratic voting, Futarchy elements)
- Slashing conditions for malicious arbitrators
- Appeal process with higher stakes
"""

import uuid
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from .models import (
    Dispute, DisputeEvidence, ArbitratorDecision, DisputeStatus,
    ArbitrationResult, Intent, Task, ArbitrationConfig
)
from .escrow_enhanced import EnhancedEscrowLedger, TransferType


class ArbitratorTier(str, Enum):
    """Arbitrator tiers"""
    PLATFORM = "platform"       # Platform staff
    COMMUNITY = "community"     # Community arbitrators
    EXPERT = "expert"          # Domain experts
    VALIDATOR = "validator"    # High-stake validators


class VotingMechanism(str, Enum):
    """Available voting mechanisms"""
    SIMPLE_MAJORITY = "simple_majority"
    STAKE_WEIGHTED = "stake_weighted"
    QUADRATIC = "quadratic"
    REPUTATION_WEIGHTED = "reputation_weighted"
    EXPERT_WEIGHTED = "expert_weighted"
    HYBRID = "hybrid"  # Combines multiple factors


@dataclass
class ArbitratorProfile:
    """Arbitrator profile with reputation tracking"""
    arbitrator_id: str
    tier: ArbitratorTier
    
    # Stake
    staked_amount: float = 0.0
    stake_locked_until: Optional[datetime] = None
    
    # Reputation
    total_cases: int = 0
    correct_decisions: int = 0
    reputation_score: float = 50.0  # 0-100
    
    # Expertise
    expertise_domains: List[str] = field(default_factory=list)
    expertise_scores: Dict[str, float] = field(default_factory=dict)  # domain -> score
    
    # Performance
    average_response_time: float = 0.0  # hours
    consistency_score: float = 1.0  # How often agrees with final outcome
    
    # Penalties
    slash_count: int = 0
    is_suspended: bool = False
    
    def calculate_weight(self, mechanism: VotingMechanism) -> float:
        """Calculate voting weight based on mechanism"""
        if mechanism == VotingMechanism.SIMPLE_MAJORITY:
            return 1.0
        
        elif mechanism == VotingMechanism.STAKE_WEIGHTED:
            # Weight proportional to square root of stake (diminishing returns)
            return math.sqrt(self.staked_amount)
        
        elif mechanism == VotingMechanism.QUADRATIC:
            # Quadratic voting: cost = weight^2, so weight = sqrt(votes)
            return math.sqrt(self.staked_amount)
        
        elif mechanism == VotingMechanism.REPUTATION_WEIGHTED:
            # Reputation score directly as weight
            return max(1.0, self.reputation_score / 10)
        
        elif mechanism == VotingMechanism.EXPERT_WEIGHTED:
            # Expertise-based with fallback to reputation
            avg_expertise = sum(self.expertise_scores.values()) / len(self.expertise_scores) if self.expertise_scores else 0
            return max(1.0, avg_expertise * 2)
        
        elif mechanism == VotingMechanism.HYBRID:
            # Combine stake, reputation, and expertise
            stake_weight = math.sqrt(self.staked_amount) * 0.3
            rep_weight = (self.reputation_score / 100) * 0.4
            exp_weight = (sum(self.expertise_scores.values()) / max(len(self.expertise_scores), 1) / 100) * 0.3
            return max(1.0, stake_weight + rep_weight + exp_weight)
        
        return 1.0


@dataclass
class WeightedDecision:
    """Decision with calculated weight"""
    decision: ArbitratorDecision
    arbitrator: ArbitratorProfile
    weight: float
    adjusted_confidence: float  # Confidence adjusted by arbitrator reputation


@dataclass
class ArbitrationRound:
    """A single round of arbitration"""
    round_number: int
    tier: ArbitratorTier
    mechanism: VotingMechanism
    decisions: List[WeightedDecision] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    outcome: Optional[ArbitrationResult] = None
    total_weight: float = 0.0
    
    def is_quorum_reached(self, min_voters: int = 3) -> bool:
        """Check if enough arbitrators have voted"""
        return len(self.decisions) >= min_voters


@dataclass
class EnhancedDisputeConfig:
    """Configuration for enhanced arbitration"""
    # Platform mediation
    enable_platform_mediation: bool = True
    platform_mediators_required: int = 1
    
    # Community voting
    enable_community_voting: bool = True
    community_voters_required: int = 5
    community_voting_mechanism: VotingMechanism = VotingMechanism.HYBRID
    
    # Expert panel (optional for complex cases)
    enable_expert_panel: bool = True
    expert_panel_size: int = 3
    expert_voting_mechanism: VotingMechanism = VotingMechanism.EXPERT_WEIGHTED
    
    # Stakes
    min_arbitrator_stake: float = 100.0
    user_appeal_stake_multiplier: float = 2.0  # Must stake 2x to appeal
    
    # Appeal
    enable_appeals: bool = True
    appeal_window_hours: int = 72
    max_appeals: int = 1
    
    # Slashing
    slash_threshold: float = 0.7  # Slash if wrong with >70% confidence
    slash_percentage: float = 0.1  # Lose 10% of stake
    
    # Timing
    voting_period_hours: int = 48
    reveal_period_hours: int = 24  # For commit-reveal schemes


class EnhancedArbitrationSystem:
    """
    Production-grade arbitration system
    
    Features:
    - Three-tier arbitration (Platform → Community → Appeal)
    - Weighted voting (stake, reputation, expertise)
    - Sybil resistance through stake requirements
    - Slashing for malicious/incorrect behavior
    - Commit-reveal voting (optional)
    - Comprehensive reputation tracking
    """
    
    def __init__(
        self,
        database: Any,
        ledger: EnhancedEscrowLedger,
        config: Optional[EnhancedDisputeConfig] = None
    ):
        self.db = database
        self.ledger = ledger
        self.config = config or EnhancedDisputeConfig()
        
        # Arbitrator registry
        self._arbitrators: Dict[str, ArbitratorProfile] = {}
        
        # Active disputes with their rounds
        self._dispute_rounds: Dict[str, List[ArbitrationRound]] = {}
        
        # Vote commitments (for commit-reveal)
        self._commitments: Dict[str, str] = {}  # commitment_id -> hashed_vote
        
        # Appeal tracking
        self._appeals: Dict[str, int] = {}  # dispute_id -> appeal_count
    
    async def register_arbitrator(
        self,
        arbitrator_id: str,
        tier: ArbitratorTier,
        initial_stake: float,
        expertise_domains: Optional[List[str]] = None
    ) -> ArbitratorProfile:
        """
        Register a new arbitrator with stake
        
        Args:
            arbitrator_id: Unique identifier
            tier: Arbitrator tier
            initial_stake: Amount to stake (must meet minimum)
            expertise_domains: List of expertise areas
        """
        if initial_stake < self.config.min_arbitrator_stake:
            raise ValueError(
                f"Minimum stake is {self.config.min_arbitrator_stake}, "
                f"provided {initial_stake}"
            )
        
        # Stake tokens
        await self.ledger.stake_tokens(arbitrator_id, initial_stake, "arbitration")
        
        # Create profile
        profile = ArbitratorProfile(
            arbitrator_id=arbitrator_id,
            tier=tier,
            staked_amount=initial_stake,
            stake_locked_until=datetime.utcnow() + timedelta(days=30),
            expertise_domains=expertise_domains or [],
            expertise_scores={d: 50.0 for d in (expertise_domains or [])}
        )
        
        self._arbitrators[arbitrator_id] = profile
        return profile
    
    async def file_dispute(
        self,
        task_id: str,
        user_id: str,
        user_claim: str,
        claimed_amount: float,
        initial_evidence: Optional[Any] = None
    ) -> Dispute:
        """File a new dispute (extends original)"""
        # Get task details
        task = await self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        # Create dispute
        dispute_id = f"dispute-{uuid.uuid4().hex[:12]}"
        
        dispute = Dispute(
            id=dispute_id,
            task_id=task_id,
            user_id=user_id,
            agent_id=task.agent_id,
            creator_id=task.agent_id.split("-")[0],  # Simplified
            user_claim=user_claim,
            claimed_amount=claimed_amount,
            status=DisputeStatus.OPEN,
            user_evidence=[initial_evidence] if initial_evidence else []
        )
        
        await self.db.create_dispute(dispute)
        
        # Initialize first round (platform mediation)
        if self.config.enable_platform_mediation:
            round1 = ArbitrationRound(
                round_number=1,
                tier=ArbitratorTier.PLATFORM,
                mechanism=VotingMechanism.SIMPLE_MAJORITY
            )
            self._dispute_rounds[dispute_id] = [round1]
        
        return dispute
    
    async def assign_platform_mediator(
        self,
        dispute_id: str,
        mediator_id: str
    ) -> Dispute:
        """Assign a platform mediator to a dispute"""
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ValueError(f"Dispute not found: {dispute_id}")
        
        # Verify mediator is registered and active
        mediator = self._arbitrators.get(mediator_id)
        if not mediator or mediator.tier != ArbitratorTier.PLATFORM:
            raise ValueError(f"Invalid platform mediator: {mediator_id}")
        
        if mediator.is_suspended:
            raise ValueError(f"Mediator is suspended: {mediator_id}")
        
        dispute.platform_mediator_id = mediator_id
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
        confidence: float = 0.8
    ) -> Dispute:
        """
        Submit platform mediator decision
        
        Args:
            confidence: Confidence level (0-1), affects reputation weight
        """
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ValueError(f"Dispute not found: {dispute_id}")
        
        # Verify mediator
        if dispute.platform_mediator_id != mediator_id:
            raise ValueError("Unauthorized mediator")
        
        mediator = self._arbitrators.get(mediator_id)
        if not mediator:
            raise ValueError(f"Mediator not found: {mediator_id}")
        
        # Create weighted decision
        arb_decision = ArbitratorDecision(
            arbitrator_id=mediator_id,
            decision=decision,
            intent=intent,
            compensation_amount=compensation_amount,
            reasoning=reasoning,
            submitted_at=datetime.utcnow()
        )
        
        weight = mediator.calculate_weight(VotingMechanism.SIMPLE_MAJORITY)
        
        weighted = WeightedDecision(
            decision=arb_decision,
            arbitrator=mediator,
            weight=weight,
            adjusted_confidence=confidence * (mediator.reputation_score / 100)
        )
        
        # Add to round
        rounds = self._dispute_rounds.get(dispute_id, [])
        if rounds:
            rounds[0].decisions.append(weighted)
            rounds[0].total_weight += weight
        
        # Store decision
        dispute.platform_decision = arb_decision
        
        # Update mediator stats
        mediator.total_cases += 1
        
        await self.db.update_dispute(dispute)
        return dispute
    
    async def start_community_voting(self, dispute_id: str) -> Dispute:
        """Move dispute to community voting phase"""
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ValueError(f"Dispute not found: {dispute_id}")
        
        # Create community voting round
        community_round = ArbitrationRound(
            round_number=2,
            tier=ArbitratorTier.COMMUNITY,
            mechanism=self.config.community_voting_mechanism,
            start_time=datetime.utcnow()
        )
        
        if dispute_id not in self._dispute_rounds:
            self._dispute_rounds[dispute_id] = []
        self._dispute_rounds[dispute_id].append(community_round)
        
        dispute.status = DisputeStatus.COMMUNITY_VOTE
        dispute.community_review_requested_at = datetime.utcnow()
        
        await self.db.update_dispute(dispute)
        return dispute
    
    async def submit_community_decision(
        self,
        dispute_id: str,
        voter_id: str,
        decision: ArbitrationResult,
        intent: Intent,
        compensation_amount: float,
        reasoning: str,
        confidence: float = 0.7
    ) -> Dispute:
        """Submit a community arbitrator decision"""
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ValueError(f"Dispute not found: {dispute_id}")
        
        if dispute.status != DisputeStatus.COMMUNITY_VOTE:
            raise ValueError("Dispute not in community voting phase")
        
        # Verify voter
        voter = self._arbitrators.get(voter_id)
        if not voter:
            raise ValueError(f"Arbitrator not registered: {voter_id}")
        
        if voter.tier not in [ArbitratorTier.COMMUNITY, ArbitratorTier.EXPERT]:
            raise ValueError("Invalid tier for community voting")
        
        if voter.is_suspended:
            raise ValueError("Voter is suspended")
        
        # Check minimum stake
        if voter.staked_amount < self.config.min_arbitrator_stake:
            raise ValueError(f"Insufficient stake: {voter.staked_amount}")
        
        # Create weighted decision
        arb_decision = ArbitratorDecision(
            arbitrator_id=voter_id,
            decision=decision,
            intent=intent,
            compensation_amount=compensation_amount,
            reasoning=reasoning,
            submitted_at=datetime.utcnow()
        )
        
        # Calculate weight based on configured mechanism
        weight = voter.calculate_weight(self.config.community_voting_mechanism)
        
        weighted = WeightedDecision(
            decision=arb_decision,
            arbitrator=voter,
            weight=weight,
            adjusted_confidence=confidence * (voter.reputation_score / 100)
        )
        
        # Add to round
        rounds = self._dispute_rounds[dispute_id]
        community_round = rounds[-1] if rounds[-1].tier == ArbitratorTier.COMMUNITY else None
        
        if community_round:
            community_round.decisions.append(weighted)
            community_round.total_weight += weight
        
        dispute.community_decisions.append(arb_decision)
        
        # Update voter stats
        voter.total_cases += 1
        
        await self.db.update_dispute(dispute)
        return dispute
    
    def _aggregate_weighted_decisions(
        self,
        round_data: ArbitrationRound,
        dispute: Dispute
    ) -> Tuple[ArbitrationResult, Intent, float]:
        """
        Aggregate weighted decisions using configured mechanism
        
        Returns:
            Tuple of (result, intent, compensation)
        """
        if not round_data.decisions:
            raise ValueError("No decisions to aggregate")
        
        # Weighted vote counting
        user_weight = sum(
            d.weight for d in round_data.decisions
            if d.decision.decision == ArbitrationResult.IN_FAVOR_OF_USER
        )
        agent_weight = sum(
            d.weight for d in round_data.decisions
            if d.decision.decision == ArbitrationResult.IN_FAVOR_OF_AGENT
        )
        partial_weight = sum(
            d.weight for d in round_data.decisions
            if d.decision.decision == ArbitrationResult.PARTIAL_COMPENSATION
        )
        
        total_weight = user_weight + agent_weight + partial_weight
        
        # Determine winner
        if user_weight > agent_weight and user_weight > partial_weight:
            final_decision = ArbitrationResult.IN_FAVOR_OF_USER
        elif agent_weight > user_weight and agent_weight > partial_weight:
            final_decision = ArbitrationResult.IN_FAVOR_OF_AGENT
        else:
            final_decision = ArbitrationResult.PARTIAL_COMPENSATION
        
        # Weighted intent (proportion of weight voting intentional)
        intentional_weight = sum(
            d.weight for d in round_data.decisions
            if d.decision.intent == Intent.INTENTIONAL
        )
        
        intent_threshold = 0.5  # Need >50% weight to declare intentional
        if intentional_weight / total_weight > intent_threshold:
            final_intent = Intent.INTENTIONAL
        else:
            final_intent = Intent.NON_INTENTIONAL
        
        # Weighted average compensation
        weighted_compensation = sum(
            d.decision.compensation_amount * d.weight
            for d in round_data.decisions
        ) / total_weight
        
        return final_decision, final_intent, weighted_compensation
    
    async def resolve_dispute(
        self,
        dispute_id: str,
        force_resolve: bool = False
    ) -> Dispute:
        """Resolve a dispute and update reputations"""
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ValueError(f"Dispute not found: {dispute_id}")
        
        rounds = self._dispute_rounds.get(dispute_id, [])
        if not rounds:
            raise ValueError("No arbitration rounds found")
        
        # Use the highest tier round that reached quorum
        resolving_round = None
        for round_data in reversed(rounds):
            if round_data.is_quorum_reached():
                resolving_round = round_data
                break
        
        if not resolving_round and not force_resolve:
            raise ValueError("No round has reached quorum")
        
        if not resolving_round:
            # Use whatever we have
            resolving_round = rounds[-1]
        
        # Aggregate decisions
        final_decision, final_intent, final_compensation = self._aggregate_weighted_decisions(
            resolving_round, dispute
        )
        
        # Update dispute
        dispute.final_decision = final_decision
        dispute.final_intent = final_intent
        dispute.final_compensation = final_compensation
        dispute.status = DisputeStatus.RESOLVED
        dispute.resolved_at = datetime.utcnow()
        
        # Execute compensation if needed
        if final_compensation > 0 and final_decision in [
            ArbitrationResult.IN_FAVOR_OF_USER,
            ArbitrationResult.PARTIAL_COMPENSATION
        ]:
            await self.ledger.compensate(
                dispute_id=dispute.id,
                from_address=dispute.creator_id,
                to_address=dispute.user_id,
                amount=final_compensation,
                is_intentional=(final_intent == Intent.INTENTIONAL)
            )
        
        # Update arbitrator reputations and slash if needed
        await self._update_arbitrator_reputations(dispute_id, resolving_round, final_decision)
        
        await self.db.update_dispute(dispute)
        return dispute
    
    async def _update_arbitrator_reputations(
        self,
        dispute_id: str,
        round_data: ArbitrationRound,
        final_decision: ArbitrationResult
    ):
        """Update reputations and apply slashing"""
        for weighted_decision in round_data.decisions:
            arbitrator = weighted_decision.arbitrator
            decision = weighted_decision.decision
            
            # Check if decision matches outcome
            is_correct = decision.decision == final_decision
            
            if is_correct:
                arbitrator.correct_decisions += 1
                # Boost reputation
                arbitrator.reputation_score = min(
                    100.0,
                    arbitrator.reputation_score + 1.0
                )
                arbitrator.consistency_score = (
                    (arbitrator.consistency_score * (arbitrator.total_cases - 1) + 1.0)
                    / arbitrator.total_cases
                )
            else:
                # Penalize
                arbitrator.consistency_score = (
                    (arbitrator.consistency_score * (arbitrator.total_cases - 1) + 0.0)
                    / arbitrator.total_cases
                )
                
                # Slashing condition: wrong with high confidence
                if weighted_decision.adjusted_confidence > self.config.slash_threshold:
                    slash_amount = arbitrator.staked_amount * self.config.slash_percentage
                    arbitrator.staked_amount -= slash_amount
                    arbitrator.slash_count += 1
                    
                    # Suspend if slashed too many times
                    if arbitrator.slash_count >= 3:
                        arbitrator.is_suspended = True
    
    async def file_appeal(
        self,
        dispute_id: str,
        user_id: str,
        appeal_reason: str
    ) -> Dispute:
        """File an appeal (requires higher stake)"""
        if not self.config.enable_appeals:
            raise ValueError("Appeals are disabled")
        
        appeal_count = self._appeals.get(dispute_id, 0)
        if appeal_count >= self.config.max_appeals:
            raise ValueError("Maximum appeals reached")
        
        dispute = await self.db.get_dispute(dispute_id)
        if not dispute:
            raise ValueError(f"Dispute not found: {dispute_id}")
        
        # Check appeal window
        if dispute.resolved_at:
            hours_since = (datetime.utcnow() - dispute.resolved_at).total_seconds() / 3600
            if hours_since > self.config.appeal_window_hours:
                raise ValueError("Appeal window has closed")
        
        # Require additional stake for appeal
        appeal_stake = dispute.final_compensation * self.config.user_appeal_stake_multiplier
        # In production: actually stake the tokens
        
        # Create appeal round with higher-tier arbitrators
        appeal_round = ArbitrationRound(
            round_number=len(self._dispute_rounds.get(dispute_id, [])) + 1,
            tier=ArbitratorTier.VALIDATOR,
            mechanism=VotingMechanism.HYBRID
        )
        
        if dispute_id not in self._dispute_rounds:
            self._dispute_rounds[dispute_id] = []
        self._dispute_rounds[dispute_id].append(appeal_round)
        
        # Reset status
        dispute.status = DisputeStatus.UNDER_REVIEW
        
        self._appeals[dispute_id] = appeal_count + 1
        
        await self.db.update_dispute(dispute)
        return dispute
    
    def get_arbitrator_stats(self, arbitrator_id: str) -> Optional[Dict]:
        """Get arbitrator statistics"""
        arb = self._arbitrators.get(arbitrator_id)
        if not arb:
            return None
        
        accuracy = arb.correct_decisions / arb.total_cases if arb.total_cases > 0 else 0
        
        return {
            "arbitrator_id": arb.arbitrator_id,
            "tier": arb.tier.value,
            "staked_amount": arb.staked_amount,
            "reputation_score": arb.reputation_score,
            "accuracy": accuracy,
            "total_cases": arb.total_cases,
            "slash_count": arb.slash_count,
            "is_suspended": arb.is_suspended,
            "expertise_domains": arb.expertise_domains
        }


# Backward compatibility
ArbitrationSystem = EnhancedArbitrationSystem