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
    """Payment transaction status"""
    PENDING = "pending"
    LOCKED = "locked"  # Tokens locked during task execution
    RELEASED = "released"  # Released to agent
    REFUNDED = "refunded"  # Refunded to user
    DISPUTED = "disputed"  # Under arbitration


class DisputeStatus(str, Enum):
    """Dispute resolution status"""
    OPEN = "open"
    FIRST_INSTANCE = "first_instance"  # Level 1: 1 arbitrator
    SECOND_INSTANCE = "second_instance"  # Level 2: 3 arbitrators
    FINAL_INSTANCE = "final_instance"  # Level 3: 5 arbitrators
    RESOLVED = "resolved"
    CLOSED = "closed"


class ArbitrationLevel(int, Enum):
    """Arbitration level enum"""
    FIRST = 1  # 1 arbitrator
    SECOND = 2  # 3 arbitrators
    THIRD = 3  # 5 arbitrators


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
    price_per_task: float = Field(..., ge=0, description="Price in AAC tokens per task")
    
    # Reputation metrics
    credibility_score: float = Field(default=3.0, ge=1.0, le=5.0,
                                     description="Average user rating (1-5)")
    total_ratings: int = Field(default=0, ge=0, description="Total number of ratings")
    public_trust_score: float = Field(default=0.0, ge=0.0, le=100.0,
                                      description="Public trust based on volume and ratings")
    completed_tasks: int = Field(default=0, ge=0, description="Total completed tasks")
    
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
    
    def calculate_trust_score(self) -> float:
        """
        Calculate public trust score based on:
        - Total completed tasks (volume)
        - Average rating (quality)
        - Age of agent (longevity)
        """
        volume_factor = min(self.completed_tasks / 100, 1.0) * 40  # Max 40 points
        quality_factor = (self.credibility_score / 5.0) * 40  # Max 40 points
        longevity_factor = 20  # Base trust for registered agents
        
        return volume_factor + quality_factor + longevity_factor
    
    def update_rating(self, new_rating: float) -> None:
        """Update credibility score with new rating"""
        total_score = self.credibility_score * self.total_ratings + new_rating
        self.total_ratings += 1
        self.credibility_score = total_score / self.total_ratings
        self.public_trust_score = self.calculate_trust_score()


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
    price_locked: float = Field(..., ge=0, description="Locked token amount")
    
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
    Payment transaction record
    
    Tracks token transfers between users and agents.
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
    """
    Generic token transaction for ledger
    """
    id: str
    from_address: str
    to_address: str
    amount: float = Field(..., gt=0)
    type: str = Field(..., description="Transaction type: payment, refund, compensation, etc.")
    task_id: Optional[str] = None
    dispute_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    signature: Optional[str] = None  # For verification


class DisputeEvidence(BaseModel):
    """Evidence submitted for dispute"""
    submitted_by: str  # user_id or agent_id
    content: str
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


class ArbitratorDecision(BaseModel):
    """Individual arbitrator decision"""
    arbitrator_id: str
    decision: ArbitrationResult
    intent: Intent
    compensation_amount: float
    reasoning: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


class Dispute(BaseModel):
    """
    Dispute case for arbitration
    
    Three-level arbitration system:
    - Level 1 (First): 1 high-trust arbitrator
    - Level 2 (Second): 3 high-trust arbitrators  
    - Level 3 (Final): 5 high-trust arbitrators
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
    current_level: ArbitrationLevel = Field(default=ArbitrationLevel.FIRST)
    
    # Arbitrators assigned at each level
    level_1_arbitrator: Optional[str] = None
    level_2_arbitrators: List[str] = Field(default_factory=list)
    level_3_arbitrators: List[str] = Field(default_factory=list)
    
    # Decisions
    level_1_decision: Optional[ArbitratorDecision] = None
    level_2_decisions: List[ArbitratorDecision] = Field(default_factory=list)
    level_3_decisions: List[ArbitratorDecision] = Field(default_factory=list)
    
    # Final result
    final_decision: Optional[ArbitrationResult] = None
    final_intent: Optional[Intent] = None
    final_compensation: float = Field(default=0, ge=0)
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    escalated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Escalation trigger
    escalation_requested_by: Optional[str] = None  # user_id or agent_id


class ArbitrationConfig(BaseModel):
    """Configuration for arbitration system"""
    # Compensation limits (multiplier of original payment)
    max_compensation_non_intentional: float = Field(default=5.0, ge=1.0, le=10.0)
    max_compensation_intentional: float = Field(default=15.0, ge=1.0, le=20.0)
    
    # Arbitrator requirements
    min_trust_score_level_1: float = Field(default=70.0, ge=0, le=100)
    min_trust_score_level_2: float = Field(default=80.0, ge=0, le=100)
    min_trust_score_level_3: float = Field(default=90.0, ge=0, le=100)


class User(BaseModel):
    """User account model"""
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    
    # Token balance
    token_balance: float = Field(default=1000.0, ge=0,
                                  description="Initial allocation: 1000 AAC tokens")
    
    # Stats
    total_tasks_submitted: int = Field(default=0)
    total_spent: float = Field(default=0.0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)


class Creator(BaseModel):
    """Creator account model"""
    id: str
    name: str
    email: Optional[str] = None
    
    # Token balance (earnings)
    token_balance: float = Field(default=1000.0, ge=0,
                                  description="Initial allocation: 1000 AAC tokens")
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
