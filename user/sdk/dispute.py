"""
AAC Protocol User SDK - Dispute Manager

Client for filing and managing disputes.
"""

from typing import List, Optional, Dict, Any
import httpx

from ...core.models import (
    Dispute, DisputeEvidence, DisputeStatus, ArbitrationResult, Intent,
    Task, User, AgentCard
)
from ...core.database import Database
from ...core.arbitration import ArbitrationSystem
from ...core.token import TokenSystem


class DisputeError(Exception):
    """Dispute operation error"""
    pass


class DisputeManager:
    """
    Manager for dispute lifecycle
    
    Handles filing disputes, submitting evidence, and tracking status.
    """
    
    def __init__(
        self,
        database: Database,
        arbitration_system: ArbitrationSystem,
        token_system: TokenSystem
    ):
        self.db = database
        self.arbitration = arbitration_system
        self.tokens = token_system
    
    async def file_dispute(
        self,
        task: Task,
        user: User,
        claim: str,
        claimed_amount: float,
        evidence: Optional[DisputeEvidence] = None
    ) -> Dispute:
        """
        File a new dispute
        
        Args:
            task: Related task
            user: Filing user
            claim: Dispute description
            claimed_amount: Amount being claimed
            evidence: Optional initial evidence
            
        Returns:
            Created dispute
        """
        return await self.arbitration.file_dispute(
            task_id=task.id,
            user_id=user.id,
            user_claim=claim,
            claimed_amount=claimed_amount,
            initial_evidence=evidence,
        )
    
    async def submit_user_evidence(
        self,
        dispute_id: str,
        user: User,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dispute:
        """
        Submit evidence as user
        
        Args:
            dispute_id: Dispute ID
            user: Submitting user
            content: Evidence description
            attachments: Supporting files
            
        Returns:
            Updated dispute
        """
        evidence = DisputeEvidence(
            submitted_by=user.id,
            content=content,
            attachments=attachments or [],
        )
        
        return await self.arbitration.submit_evidence(
            dispute_id=dispute_id,
            submitter_id=user.id,
            content=content,
            attachments=attachments,
        )
    
    async def get_dispute(self, dispute_id: str) -> Optional[Dispute]:
        """Get dispute by ID"""
        return await self.db.get_dispute(dispute_id)
    
    async def get_user_disputes(
        self,
        user_id: str,
        status: Optional[DisputeStatus] = None,
        limit: int = 50
    ) -> List[Dispute]:
        """
        Get disputes for a user
        
        Args:
            user_id: User ID
            status: Filter by status
            limit: Maximum results
            
        Returns:
            List of disputes
        """
        # In production, query database
        return []
    
    async def escalate(
        self,
        dispute_id: str,
        user: User
    ) -> Dispute:
        """
        Escalate dispute to next level
        
        Args:
            dispute_id: Dispute ID
            user: Requesting user
            
        Returns:
            Escalated dispute
        """
        return await self.arbitration.escalate_dispute(
            dispute_id=dispute_id,
            requested_by=user.id
        )
    
    async def get_status(self, dispute_id: str) -> Dict[str, Any]:
        """
        Get detailed dispute status
        
        Args:
            dispute_id: Dispute ID
            
        Returns:
            Status dictionary
        """
        return await self.arbitration.get_dispute_status(dispute_id)
    
    def calculate_max_claim(self, original_payment: float) -> Dict[str, float]:
        """
        Calculate maximum claimable amounts
        
        Args:
            original_payment: Original task payment
            
        Returns:
            Dictionary with max amounts
        """
        return {
            "non_intentional_max": original_payment * 5,
            "intentional_max": original_payment * 15,
            "recommended": original_payment * 2,
        }


class DisputeBuilder:
    """
    Builder for constructing disputes
    
    Provides fluent interface for dispute creation.
    """
    
    def __init__(self, task: Task, user: User):
        self._task = task
        self._user = user
        self._claim: Optional[str] = None
        self._claimed_amount: Optional[float] = None
        self._evidence: List[DisputeEvidence] = []
    
    def with_claim(self, claim: str) -> "DisputeBuilder":
        """Set dispute claim description"""
        self._claim = claim
        return self
    
    def claiming(self, amount: float) -> "DisputeBuilder":
        """Set claimed amount"""
        self._claimed_amount = amount
        return self
    
    def add_evidence(
        self,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> "DisputeBuilder":
        """Add evidence"""
        evidence = DisputeEvidence(
            submitted_by=self._user.id,
            content=content,
            attachments=attachments or [],
        )
        self._evidence.append(evidence)
        return self
    
    async def file(self, manager: DisputeManager) -> Dispute:
        """File dispute using manager"""
        if not self._claim:
            raise ValueError("Claim description is required")
        
        if self._claimed_amount is None:
            raise ValueError("Claimed amount is required")
        
        # Use first evidence as initial, rest as additional
        initial_evidence = self._evidence[0] if self._evidence else None
        
        dispute = await manager.file_dispute(
            task=self._task,
            user=self._user,
            claim=self._claim,
            claimed_amount=self._claimed_amount,
            evidence=initial_evidence,
        )
        
        # Submit additional evidence
        for evidence in self._evidence[1:]:
            await manager.submit_user_evidence(
                dispute_id=dispute.id,
                user=self._user,
                content=evidence.content,
                attachments=evidence.attachments,
            )
        
        return dispute
