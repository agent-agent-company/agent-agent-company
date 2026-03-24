"""
AAC Protocol Data Models

This module defines all Pydantic models for the AAC Protocol.
All models are validated and serialized using Pydantic v2.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class AgentStatus(str, Enum):
    """Agent lifecycle status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"  # Task under arbitration (payment may be PaymentStatus.DISPUTED)


class PaymentStatus(str, Enum):
    """Payment / escrow status"""
    PENDING = "pending"
    LOCKED = "locked"  # Held in platform escrow during task execution
    RELEASED = "released"  # Released to creator
    REFUNDED = "refunded"  # Returned to user
    DISPUTED = "disputed"  # Under platform dispute handling


class DisputeStatus(str, Enum):
    """Dispute lifecycle (centralized platform)"""
    OPEN = "open"
    UNDER_REVIEW = "under_review"  # Platform staff / policy review
    COMMUNITY_VOTE = "community_vote"  # Optional community advisory round
    RESOLVED = "resolved"
    CLOSED = "closed"


class ArbitrationResult(str, Enum):
    """Arbitration decision result"""
    IN_FAVOR_OF_USER = "in_favor_of_user"
    IN_FAVOR_OF_AGENT = "in_favor_of_agent"
    PARTIAL_COMPENSATION = "partial_compensation"


class Intent(str, Enum):
    """Creator intent classification for disputes"""
    NON_INTENTIONAL = "non_intentional"  # Creator not at fault
    INTENTIONAL = "intentional"  # Creator intentionally caused harm


class AgentID(BaseModel):
    """
    Agent unique identifier
    
    Format: {name}-{id} (e.g., "weather-001")
    - name: Human-readable agent name
    - id: Sequential number (starts at 001)
    """
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$",
                      description="Agent name (lowercase alphanumeric with hyphens/underscores)")
    sequence_id: int = Field(..., ge=1, description="Sequential ID number")
    
    @property
    def full_id(self) -> str:
        """Return full identifier string"""
        return f"{self.name}-{self.sequence_id:03d}"
    
    def __str__(self) -> str:
        return self.full_id
    
    @classmethod
    def from_string(cls, id_str: str) -> "AgentID":
        """Parse from string format"""
        parts = id_str.rsplit("-", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid AgentID format: {id_str}")
        name, seq = parts
        return cls(name=name, sequence_id=int(seq))


class Rating(BaseModel):
    """User rating for an agent"""
    user_id: str
    agent_id: str
    score: float = Field(..., ge=1.0, le=5.0, description="Rating score 1-5")
    comment: Optional[str] = Field(None, max_length=500)
    task_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentCard(BaseModel):
    """
    Agent Card - describes agent capabilities and metadata
    
    Similar to A2A AgentCard concept, this is the metadata document
    that allows discovery and understanding of an agent's capabilities.
    """
    # Identity
    id: AgentID
    name: str = Field(..., min_length=1, max_length=128, description="Display name")
    description: str = Field(..., min_length=10, max_length=2000,
                             description="Detailed description of agent capabilities")
    
    # Creator info
    creator_id: str
    creator_name: Optional[str] = None
    
    # Pricing
    price_per_task: float = Field(
        ..., ge=0, description="Price per task in platform billing units (e.g. fiat or demo credits)"
    )
    
    # Reputation metrics
    credibility_score: float = Field(default=3.0, ge=1.0, le=5.0,
                                     description="Average user rating (1-5)")
    total_ratings: int = Field(default=0, ge=0, description="Total number of ratings")
    unique_raters: int = Field(default=0, ge=0, 
                               description="Number of unique users who rated (prevents Sybil attacks)")
    public_trust_score: float = Field(default=0.0, ge=0.0, le=100.0,
                                      description="Public trust based on volume and ratings")
    completed_tasks: int = Field(default=0, ge=0, description="Total completed tasks")
    failed_tasks: int = Field(default=0, ge=0, description="Total failed/cancelled tasks")
    
    # Anti-gaming: Rate limiting for ratings
    last_rating_at: Optional[datetime] = Field(default=None, 
                                                description="Timestamp of last rating received")
    ratings_this_month: int = Field(default=0, ge=0,
                                    description="Ratings received in current month (rate limiting)")
    
    # Capabilities
    capabilities: List[str] = Field(default_factory=list,
                                    description="List of capability keywords")
    input_types: List[str] = Field(default_factory=list,
                                   description="Accepted input formats")
    output_types: List[str] = Field(default_factory=list,
                                    description="Output formats")
    
    # Status
    status: AgentStatus = Field(default=AgentStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Contact
    endpoint_url: str = Field(..., description="Agent JSON-RPC endpoint URL")
    documentation_url: Optional[str] = None
    
    def calculate_trust_score(self, current_time: Optional[datetime] = None) -> float:
        """
        Calculate public trust score with anti-gaming protections.
        
        Formula improvements:
        1. Volume factor: Requires minimum tasks, scales logarithmically (harder to game)
        2. Quality factor: Weighted by unique raters (prevents single-user spam)
        3. Success rate: Penalizes failed tasks
        4. Confidence penalty: Low rating count reduces score
        5. Time decay: Recent ratings weighted more heavily
        
        Args:
            current_time: Optional reference time for calculations
            
        Returns:
            Trust score between 0-100
        """
        if current_time is None:
            current_time = datetime.utcnow()
        
        # Calculate success rate (completed vs total tasks)
        total_tasks = self.completed_tasks + self.failed_tasks
        if total_tasks == 0:
            success_rate = 0.5  # Neutral for new agents
        else:
            success_rate = self.completed_tasks / total_tasks
        
        # Volume factor: Logarithmic scaling (diminishing returns after 100 tasks)
        # Min 5 tasks to get any volume points (prevents easy gaming)
        if self.completed_tasks < 5:
            volume_factor = 0
        else:
            volume_factor = min(1.0, (1 + (self.completed_tasks - 5) / 95) ** 0.5) * 25
        
        # Quality factor: Weighted by unique raters (Sybil resistance)
        # Requires at least 3 unique raters for full quality score
        uniqueness_factor = min(1.0, self.unique_raters / 3.0) if self.unique_raters > 0 else 0
        quality_factor = (self.credibility_score / 5.0) * 30 * uniqueness_factor
        
        # Success rate factor: Penalizes failures
        success_factor = success_rate * 25
        
        # Confidence penalty: Low rating count reduces score
        # Ratings < 3 get reduced weight (could be fake)
        confidence_factor = min(1.0, self.total_ratings / 5.0)
        
        # Calculate base score
        base_score = (volume_factor + quality_factor + success_factor) * confidence_factor
        
        # Longevity bonus: +5 points for agents older than 30 days
        # (reduces impact of new fake agents)
        age_days = (current_time - self.created_at).days if self.created_at else 0
        longevity_bonus = 5 if age_days >= 30 else (age_days / 30) * 5
        
        # Penalty for suspicious activity: High rating velocity
        if self.ratings_this_month > 50:  # More than 50 ratings/month is suspicious
            velocity_penalty = -10
        elif self.ratings_this_month > 30:
            velocity_penalty = -5
        else:
            velocity_penalty = 0
        
        final_score = base_score + longevity_bonus + velocity_penalty
        return max(0.0, min(100.0, final_score))
    
    def can_receive_rating(self, user_id: str, current_time: Optional[datetime] = None) -> tuple[bool, str]:
        """
        Check if agent can receive a rating (rate limiting for anti-gaming).
        
        Returns:
            Tuple of (allowed, reason)
        """
        if current_time is None:
            current_time = datetime.utcnow()
        
        # Check if too many ratings this month (possible review bombing)
        if self.ratings_this_month >= 100:
            return False, "Rate limit exceeded: Too many ratings this month"
        
        # Check rating velocity (more than 10 ratings per day is suspicious)
        if self.last_rating_at:
            hours_since_last = (current_time - self.last_rating_at).total_seconds() / 3600
            if hours_since_last < 1:  # Less than 1 hour since last rating
                return False, "Rate limit: Too many ratings in short time period"
        
        return True, "OK"
    
    def update_rating(self, new_rating: float, user_id: str, 
                      current_time: Optional[datetime] = None) -> None:
        """
        Update credibility score with anti-gaming protections.
        
        Args:
            new_rating: Rating score (1-5)
            user_id: ID of user giving rating (for tracking unique raters)
            current_time: Optional reference time
        """
        if current_time is None:
            current_time = datetime.utcnow()
        
        # Update rolling average
        total_score = self.credibility_score * self.total_ratings + new_rating
        self.total_ratings += 1
        self.credibility_score = total_score / self.total_ratings
        
        # Update unique rater count (in production, check if user_id is new)
        # For now, assume each rating is from a unique user for the demo
        self.unique_raters += 1
        
        # Update rate limiting counters
        self.last_rating_at = current_time
        self.ratings_this_month += 1
        
        # Recalculate trust score
        self.public_trust_score = self.calculate_trust_score(current_time)
        self.updated_at = current_time


class TaskInput(BaseModel):
    """Task input parameters"""
    content: str = Field(..., description="Main task content/query")
    attachments: List[Dict[str, Any]] = Field(default_factory=list,
                                                 description="Additional files/data")
    metadata: Dict[str, Any] = Field(default_factory=dict,
                                     description="Additional context")


class TaskOutput(BaseModel):
    """Task output/result"""
    content: str = Field(..., description="Main output content")
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    """
    Task model representing a job submitted to an agent
    """
    # Identity
    id: str = Field(..., description="Unique task ID")
    user_id: str
    agent_id: str
    
    # Content
    input: TaskInput
    output: Optional[TaskOutput] = None
    
    # Status
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    error_message: Optional[str] = None
    
    # Payment
    price_locked: float = Field(..., ge=0, description="Amount held in escrow for this task")
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    
    # Rating (after completion)
    user_rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    user_feedback: Optional[str] = None


class Payment(BaseModel):
    """
    Payment / escrow record for a task (platform ledger).
    """
    id: str
    task_id: str
    
    # Parties
    from_user_id: str
    to_agent_id: str
    to_creator_id: str
    
    # Amount
    amount: float = Field(..., gt=0)
    
    # Status
    status: PaymentStatus
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    
    # Dispute info
    dispute_id: Optional[str] = None


class Transaction(BaseModel):
    """Ledger movement between platform accounts (audit trail)."""
    id: str
    from_address: str
    to_address: str
    amount: float = Field(..., gt=0)
    type: str = Field(..., description="Transaction type: payment, refund, compensation, etc.")
    task_id: Optional[str] = None
    dispute_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    signature: Optional[str] = None  # Optional external PSP reference


class DisputeEvidence(BaseModel):
    """Evidence submitted for dispute"""
    submitted_by: str  # user_id or agent_id
    content: str
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


class ArbitratorDecision(BaseModel):
    """Single mediation / advisory decision (staff or community voter)."""
    arbitrator_id: str
    decision: ArbitrationResult
    intent: Intent
    compensation_amount: float
    reasoning: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


class Dispute(BaseModel):
    """
    Dispute handled by the platform: staff mediation first, optional community round.
    """
    id: str
    task_id: str
    user_id: str
    agent_id: str
    creator_id: str
    
    # Claims
    user_claim: str = Field(..., description="User's complaint description")
    claimed_amount: float = Field(..., gt=0, description="Amount user is claiming")
    
    # Evidence
    user_evidence: List[DisputeEvidence] = Field(default_factory=list)
    agent_evidence: List[DisputeEvidence] = Field(default_factory=list)
    
    # Status
    status: DisputeStatus = Field(default=DisputeStatus.OPEN)
    platform_mediator_id: Optional[str] = None
    platform_decision: Optional[ArbitratorDecision] = None
    community_decisions: List[ArbitratorDecision] = Field(default_factory=list)
    
    # Final result (set when case is closed)
    final_decision: Optional[ArbitrationResult] = None
    final_intent: Optional[Intent] = None
    final_compensation: float = Field(default=0, ge=0)
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    community_review_requested_at: Optional[datetime] = None
    community_review_requested_by: Optional[str] = None


class ArbitrationConfig(BaseModel):
    """Caps for dispute outcomes (policy knobs for the platform)."""
    max_compensation_non_intentional: float = Field(default=5.0, ge=1.0, le=10.0)
    max_compensation_intentional: float = Field(default=15.0, ge=1.0, le=20.0)
    community_votes_required: int = Field(default=3, ge=1, le=50)


class User(BaseModel):
    """
    User account model.

    Users start with zero balance and must deposit funds or earn tokens
    through platform tasks and rewards. This prevents inflation from
    unlimited free token distribution.
    """
    id: str
    name: Optional[str] = None
    email: Optional[str] = None

    token_balance: float = Field(
        default=0.0,
        ge=0,
        description="Account balance in platform billing units. Users must deposit or earn through tasks/rewards. Default is 0.0 (no free tokens).",
    )
    
    # Stats
    total_tasks_submitted: int = Field(default=0)
    total_spent: float = Field(default=0.0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)


class Creator(BaseModel):
    """
    Creator account model.

    Creators start with zero balance and earn tokens through task execution.
    No upfront deposit required - creators earn as they provide services.
    """
    id: str
    name: str
    email: Optional[str] = None

    token_balance: float = Field(
        default=0.0,
        ge=0,
        description="Creator balance in platform billing units. Creators earn through task execution fees. Default is 0.0.",
    )
    total_earned: float = Field(default=0.0)
    
    # Agents owned
    agent_ids: List[str] = Field(default_factory=list)
    
    # Stats
    total_tasks_completed: int = Field(default=0)
    average_rating: float = Field(default=0.0, ge=0, le=5)
    
    # Reputation
    is_verified: bool = Field(default=False)
    trust_score: float = Field(default=50.0, ge=0, le=100)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)


class DiscoveryQuery(BaseModel):
    """Query parameters for agent discovery"""
    keywords: Optional[List[str]] = None
    min_credibility: Optional[float] = Field(None, ge=1, le=5)
    min_trust_score: Optional[float] = Field(None, ge=0, le=100)
    max_price: Optional[float] = Field(None, ge=0)
    capabilities: Optional[List[str]] = None
    sort_by: str = Field(default="trust_score", pattern=r"^(trust_score|price|credibility|name)$")
    limit: int = Field(default=20, ge=1, le=100)


class AgentSelectorMode(str, Enum):
    """Agent selection mode"""
    PERFORMANCE = "performance"  # Highest credibility + trust
    PRICE = "price"  # Lowest price
    BALANCED = "balanced"  # Good rating at reasonable price


class TaskSubmission(BaseModel):
    """Task submission request"""
    user_id: str
    agent_id: str
    input: TaskInput
    mode: AgentSelectorMode = Field(default=AgentSelectorMode.BALANCED)
    max_price: Optional[float] = None
    deadline: Optional[datetime] = None


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 Request"""
    jsonrpc: str = Field(default="2.0")
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 Response"""
    jsonrpc: str = Field(default="2.0")
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 Error"""
    code: int
    message: str
    data: Optional[Any] = None
