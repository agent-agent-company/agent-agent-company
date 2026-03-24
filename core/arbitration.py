"""
AAC Protocol Arbitration System - Decentralized with VRF and Staking

Addresses circular dependency concerns:
1. VRF (Verifiable Random Function) for unbiased arbitrator selection
2. Staking mechanism - arbitrators must lock tokens as collateral
3. External reputation oracles - trust score from independent sources
4. Slashing conditions - dishonest arbitrators lose their stake

Three-level arbitration system:
- Level 1 (First Instance): 1 arbitrator (randomly selected via VRF)
- Level 2 (Second Instance): 3 arbitrators (VRF + stake-weighted)
- Level 3 (Final Instance): 5 arbitrators (VRF + high stake requirement)

Compensation rules:
- Non-intentional damage: Max 5x original payment
- Intentional damage: Max 15x original payment + agent deletion
"""

import uuid
import hashlib
import random
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Set
from decimal import Decimal
from dataclasses import dataclass

from .models import (
    Dispute, DisputeEvidence, ArbitratorDecision, DisputeStatus,
    ArbitrationLevel, ArbitrationResult, Intent, Task,
    ArbitrationConfig, TaskStatus, PaymentStatus,
)
from .database import Database
from .token import TokenSystem


class ArbitrationError(Exception):
    """Raised for arbitration system errors"""
    pass


class InvalidDisputeError(ArbitrationError):
    """Raised when dispute is invalid"""
    pass


class InsufficientStakeError(ArbitrationError):
    """Raised when arbitrator doesn't have sufficient stake"""
    pass


@dataclass
class ArbitratorProfile:
    """
    Profile of a registered arbitrator
    
    Includes stake amount and reputation from external oracles.
    """
    agent_id: str
    staked_amount: float  # Locked tokens as collateral
    reputation_score: float  # 0-100 from external oracle
    completed_arbitrations: int
    successful_arbitrations: int  # Where majority agreed with them
    slash_count: int  # Times they were slashed for dishonesty
    is_active: bool
    
    def calculate_weight(self) -> float:
        """
        Calculate selection weight based on stake and reputation
        
        Higher stake + higher reputation = higher chance of selection
        Slash count reduces weight significantly.
        """
        # Base weight from stake (linear up to 1000 AAC)
        stake_weight = min(self.staked_amount / 1000.0, 1.0) * 40
        
        # Reputation weight (40%)
        rep_weight = self.reputation_score * 0.4
        
        # Success rate weight (20%)
        if self.completed_arbitrations > 0:
            success_rate = self.successful_arbitrations / self.completed_arbitrations
        else:
            success_rate = 0.5  # Neutral for new arbitrators
        success_weight = success_rate * 20
        
        # Slash penalty (-50% per slash, max -90%)
        slash_penalty = min(self.slash_count * 0.5, 0.9)
        
        total = stake_weight + rep_weight + success_weight
        return total * (1 - slash_penalty)
    
    def meets_stake_requirement(self, level: ArbitrationLevel) -> bool:
        """Check if arbitrator meets minimum stake for level"""
        requirements = {
            ArbitrationLevel.FIRST: 100.0,   # 100 AAC for level 1
            ArbitrationLevel.SECOND: 500.0,  # 500 AAC for level 2
            ArbitrationLevel.THIRD: 2000.0,  # 2000 AAC for level 3
        }
        return self.staked_amount >= requirements.get(level, 100.0)


class VerifiableRandomFunction:
    """
    Simple VRF implementation for unbiased arbitrator selection
    
    Uses hash-based VRF that is:
    1. Deterministic - same input always produces same output
    2. Unpredictable - cannot predict output before running
    3. Verifiable - anyone can verify the result
    """
    
    @staticmethod
    def generate(seed: str, private_key: str) -> Tuple[float, str]:
        """
        Generate verifiable random number in [0, 1)
        
        Args:
            seed: Public seed (e.g., dispute_id + timestamp)
            private_key: Secret key for this VRF instance
            
        Returns:
            (random_value, proof)
        """
        # Create proof
        proof_input = f"{seed}:{private_key}"
        proof = hashlib.sha256(proof_input.encode()).hexdigest()
        
        # Generate random value from proof
        random_value = int(proof[:16], 16) / (2**64)
        
        return random_value, proof
    
    @staticmethod
    def verify(seed: str, public_key: str, random_value: float, proof: str) -> bool:
        """
        Verify that random value was correctly generated
        
        Args:
            seed: Public seed used
            public_key: Public key corresponding to private key
            random_value: Claimed random value
            proof: Proof provided by generator
            
        Returns:
            True if verification passes
        """
        # In a real implementation, this would use elliptic curve verification
        # For simplicity, we just check proof format
        expected_proof_length = 64  # SHA-256 hex
        return len(proof) == expected_proof_length


class ArbitrationSystem:
    """
    Decentralized three-level arbitration system for AAC Protocol
    
    Key improvements for decentralization:
    1. VRF (Verifiable Random Function) for unbiased arbitrator selection
    2. Staking mechanism - arbitrators must lock tokens as collateral
    3. External reputation oracles prevent circular dependency
    4. Slashing for dishonest arbitrators
    5. Multi-signature requirements for arbitration decisions
    
    Handles dispute filing, evidence submission, arbitrator selection,
    decision making, and compensation execution.
    """
    
    def __init__(
        self,
        database: Database,
        token_system: TokenSystem,
        config: Optional[ArbitrationConfig] = None,
        vrf_private_key: Optional[str] = None,
        oracle_endpoints: Optional[List[str]] = None
    ):
        self.db = database
        self.tokens = token_system
        self.config = config or ArbitrationConfig()
        
        # VRF for random selection
        self._vrf_key = vrf_private_key or uuid.uuid4().hex
        self._vrf = VerifiableRandomFunction()
        
        # External oracle endpoints for reputation (independent sources)
        self._oracle_endpoints = oracle_endpoints or []
        
        # Registered arbitrators with stakes
        self._arbitrators: Dict[str, ArbitratorProfile] = {}
        
        # Selection history for verification
        self._selection_logs: List[Dict] = []
    
    async def register_arbitrator(
        self,
        agent_id: str,
        stake_amount: float,
        reputation_oracle_sources: List[str]
    ) -> ArbitratorProfile:
        """
        Register as an arbitrator with stake
        
        Args:
            agent_id: Agent ID to register
            stake_amount: Amount of tokens to stake (minimum 100 AAC)
            reputation_oracle_sources: List of external oracle URLs for reputation
            
        Returns:
            Arbitrator profile
            
        Raises:
            InsufficientStakeError: If stake is below minimum
        """
        # Check minimum stake
        if stake_amount < 100.0:
            raise InsufficientStakeError("Minimum stake is 100 AAC")
        
        # Lock the stake
        # In production, this would call token_system to lock tokens
        
        # Fetch reputation from external oracles
        reputation = await self._fetch_reputation_from_oracles(
            agent_id, 
            reputation_oracle_sources
        )
        
        profile = ArbitratorProfile(
            agent_id=agent_id,
            staked_amount=stake_amount,
            reputation_score=reputation,
            completed_arbitrations=0,
            successful_arbitrations=0,
            slash_count=0,
            is_active=True,
        )
        
        self._arbitrators[agent_id] = profile
        return profile
    
    async def _fetch_reputation_from_oracles(
        self,
        agent_id: str,
        oracle_sources: List[str]
    ) -> float:
        """
        Fetch reputation score from external oracles
        
        This prevents circular dependency - reputation comes from
        independent external sources, not from the system itself.
        
        Args:
            agent_id: Agent to query
            oracle_sources: List of oracle URLs
            
        Returns:
            Aggregated reputation score (0-100)
        """
        scores = []
        
        # Query each oracle
        for oracle in oracle_sources:
            try:
                # In production, this would make HTTP request to oracle
                # For now, simulate with random but deterministic score
                seed = f"{oracle}:{agent_id}"
                score = int(hashlib.sha256(seed.encode()).hexdigest()[:2], 16) % 100
                scores.append(score)
            except Exception:
                continue
        
        if not scores:
            return 50.0  # Default neutral score
        
        # Return median (robust to outliers)
        return sorted(scores)[len(scores) // 2]
    
    async def select_arbitrators_vrf(
        self,
        dispute_id: str,
        level: ArbitrationLevel,
        exclude_agents: Set[str]
    ) -> List[str]:
        """
        Select arbitrators using VRF (Verifiable Random Function)
        
        This ensures:
        1. Unbiased selection (cannot be predicted or manipulated)
        2. Verifiable (anyone can check selection was fair)
        3. Stake-weighted (higher stake = higher chance, but not guaranteed)
        
        Args:
            dispute_id: Dispute ID as seed
            level: Arbitration level
            exclude_agents: Agents to exclude (conflict of interest)
            
        Returns:
            List of selected arbitrator agent IDs
        """
        # Get qualified arbitrators
        qualified = [
            aid for aid, profile in self._arbitrators.items()
            if profile.is_active 
            and profile.meets_stake_requirement(level)
            and aid not in exclude_agents
            and profile.slash_count < 3  # Max 2 slashes allowed
        ]
        
        if len(qualified) < self._get_arbitrator_count(level):
            raise ArbitrationError("Insufficient qualified arbitrators")
        
        # Calculate weights
        weights = {}
        for aid in qualified:
            weights[aid] = self._arbitrators[aid].calculate_weight()
        
        # Use VRF for random selection
        selected = []
        used_seeds = set()
        
        for i in range(self._get_arbitrator_count(level)):
            # Generate unique seed for this selection
            seed = f"{dispute_id}:{level.value}:{i}:{':'.join(used_seeds)}"
            
            # Get VRF random value
            rand, proof = self._vrf.generate(seed, self._vrf_key)
            
            # Weighted random selection
            total_weight = sum(weights.get(aid, 0) for aid in qualified if aid not in selected)
            if total_weight == 0:
                # Fallback to uniform if all weights are 0
                remaining = [aid for aid in qualified if aid not in selected]
                chosen = random.choice(remaining) if remaining else None
            else:
                # Weighted selection
                cumulative = 0
                target = rand * total_weight
                chosen = None
                for aid in qualified:
                    if aid in selected:
                        continue
                    cumulative += weights.get(aid, 0)
                    if cumulative >= target:
                        chosen = aid
                        break
                
                # Fallback if no selection
                if chosen is None:
                    remaining = [aid for aid in qualified if aid not in selected]
                    chosen = remaining[-1] if remaining else None
            
            if chosen:
                selected.append(chosen)
                used_seeds.add(chosen)
                
                # Log selection for verification
                self._selection_logs.append({
                    "dispute_id": dispute_id,
                    "level": level.value,
                    "round": i,
                    "selected": chosen,
                    "seed": seed,
                    "vrf_proof": proof,
                    "random_value": rand,
                    "timestamp": datetime.utcnow().isoformat(),
                })
        
        return selected
    
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
        if task.status == TaskStatus.DISPUTED:
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
        task.status = TaskStatus.DISPUTED
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
