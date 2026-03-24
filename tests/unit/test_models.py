"""
Unit tests for AAC Protocol data models
"""

import pytest
from datetime import datetime

from aac_protocol.core.models import (
    AgentCard, AgentID, Task, TaskInput, TaskOutput, TaskStatus,
    Payment, PaymentStatus, User, Creator, AgentStatus,
    Dispute, DisputeEvidence, DisputeStatus, ArbitrationLevel,
    ArbitratorDecision, ArbitrationResult, Intent, Transaction,
    DiscoveryQuery, AgentSelectorMode, AgentCapability
)


class TestAgentID:
    """Tests for AgentID model"""
    
    def test_agent_id_creation(self):
        """Test creating AgentID"""
        agent_id = AgentID(name="weather", sequence_id=1)
        
        assert agent_id.name == "weather"
        assert agent_id.sequence_id == 1
        assert agent_id.full_id == "weather-001"
    
    def test_agent_id_string_conversion(self):
        """Test AgentID string conversion"""
        agent_id = AgentID(name="translate", sequence_id=42)
        
        assert str(agent_id) == "translate-042"
    
    def test_agent_id_from_string(self):
        """Test parsing AgentID from string"""
        agent_id = AgentID.from_string("data-123")
        
        assert agent_id.name == "data"
        assert agent_id.sequence_id == 123
        assert agent_id.full_id == "data-123"
    
    def test_agent_id_from_string_invalid(self):
        """Test parsing invalid AgentID string"""
        with pytest.raises(ValueError):
            AgentID.from_string("invalid")


class TestAgentCard:
    """Tests for AgentCard model"""
    
    def test_agent_card_creation(self):
        """Test creating AgentCard"""
        agent_id = AgentID(name="weather", sequence_id=1)
        
        card = AgentCard(
            id=agent_id,
            name="Weather Agent",
            description="Provides weather forecasts",
            creator_id="creator-001",
            price_per_task=2.0,
            endpoint_url="http://localhost:8001",
        )
        
        assert card.id.full_id == "weather-001"
        assert card.name == "Weather Agent"
        assert card.price_per_task == 2.0
        assert card.status == AgentStatus.ACTIVE
        assert card.credibility_score == 3.0
    
    def test_trust_score_calculation(self):
        """Test trust score calculation"""
        agent_id = AgentID(name="test", sequence_id=1)
        
        card = AgentCard(
            id=agent_id,
            name="Test Agent",
            description="Test description that is long enough",
            creator_id="creator-001",
            price_per_task=1.0,
            completed_tasks=100,
            credibility_score=4.5,
            endpoint_url="http://localhost:8001",
        )
        
        score = card.calculate_trust_score()
        assert score > 50  # Should be reasonably high with good stats
        assert score <= 100
    
    def test_rating_update(self):
        """Test updating rating"""
        agent_id = AgentID(name="test", sequence_id=1)
        
        card = AgentCard(
            id=agent_id,
            name="Test Agent",
            description="Test description that is long enough",
            creator_id="creator-001",
            price_per_task=1.0,
            endpoint_url="http://localhost:8001",
        )
        
        # Initial rating
        card.update_rating(5.0)
        assert card.total_ratings == 1
        assert card.credibility_score == 5.0
        
        # Second rating
        card.update_rating(3.0)
        assert card.total_ratings == 2
        assert card.credibility_score == 4.0  # Average of 5 and 3


class TestTask:
    """Tests for Task model"""
    
    def test_task_creation(self):
        """Test creating Task"""
        task_input = TaskInput(content="What's the weather?")
        
        task = Task(
            id="task-001",
            user_id="user-001",
            agent_id="weather-001",
            input=task_input,
            price_locked=2.0,
        )
        
        assert task.id == "task-001"
        assert task.status == TaskStatus.PENDING
        assert task.input.content == "What's the weather?"
    
    def test_task_with_output(self):
        """Test task with output"""
        task_input = TaskInput(content="Query")
        task_output = TaskOutput(
            content="Result",
            metadata={"temp": 25}
        )
        
        task = Task(
            id="task-002",
            user_id="user-001",
            agent_id="agent-001",
            input=task_input,
            output=task_output,
            status=TaskStatus.COMPLETED,
            price_locked=1.0,
        )
        
        assert task.output.content == "Result"
        assert task.output.metadata["temp"] == 25


class TestUser:
    """Tests for User model"""
    
    def test_user_creation(self):
        """Test creating User"""
        user = User(
            id="user-001",
            name="Test User",
            email="test@example.com",
        )
        
        assert user.id == "user-001"
        assert user.name == "Test User"
        assert user.token_balance == 1000.0  # Initial allocation
    
    def test_user_default_allocation(self):
        """Test default token allocation"""
        user = User(id="user-new")
        
        assert user.token_balance == 1000.0


class TestCreator:
    """Tests for Creator model"""
    
    def test_creator_creation(self):
        """Test creating Creator"""
        creator = Creator(
            id="creator-001",
            name="Test Creator",
            email="creator@example.com",
        )
        
        assert creator.id == "creator-001"
        assert creator.name == "Test Creator"
        assert creator.token_balance == 1000.0
        assert creator.trust_score == 50.0


class TestDispute:
    """Tests for Dispute model"""
    
    def test_dispute_creation(self):
        """Test creating Dispute"""
        dispute = Dispute(
            id="dispute-001",
            task_id="task-001",
            user_id="user-001",
            agent_id="agent-001",
            creator_id="creator-001",
            user_claim="Agent provided wrong information",
            claimed_amount=10.0,
        )
        
        assert dispute.id == "dispute-001"
        assert dispute.status == DisputeStatus.OPEN
        assert dispute.current_level == ArbitrationLevel.FIRST
    
    def test_dispute_evidence(self):
        """Test dispute evidence"""
        evidence = DisputeEvidence(
            submitted_by="user-001",
            content="Screenshot of wrong output",
            attachments=[{"type": "image", "url": "http://example.com/img.png"}],
        )
        
        assert evidence.submitted_by == "user-001"
        assert evidence.content == "Screenshot of wrong output"
        assert len(evidence.attachments) == 1


class TestTransaction:
    """Tests for Transaction model"""
    
    def test_transaction_creation(self):
        """Test creating Transaction"""
        transaction = Transaction(
            id="tx-001",
            from_address="user-001",
            to_address="creator-001",
            amount=2.5,
            type="payment",
            task_id="task-001",
        )
        
        assert transaction.id == "tx-001"
        assert transaction.amount == 2.5
        assert transaction.type == "payment"


class TestDiscoveryQuery:
    """Tests for DiscoveryQuery model"""
    
    def test_discovery_query_defaults(self):
        """Test DiscoveryQuery defaults"""
        query = DiscoveryQuery()
        
        assert query.sort_by == "trust_score"
        assert query.limit == 20
    
    def test_discovery_query_with_filters(self):
        """Test DiscoveryQuery with filters"""
        query = DiscoveryQuery(
            keywords=["weather", "forecast"],
            min_credibility=4.0,
            max_price=5.0,
            capabilities=["api"],
            limit=10,
        )
        
        assert "weather" in query.keywords
        assert query.min_credibility == 4.0
        assert query.max_price == 5.0
        assert query.limit == 10


class TestArbitratorDecision:
    """Tests for ArbitratorDecision model"""
    
    def test_decision_creation(self):
        """Test creating ArbitratorDecision"""
        decision = ArbitratorDecision(
            arbitrator_id="arbitrator-001",
            decision=ArbitrationResult.IN_FAVOR_OF_USER,
            intent=Intent.NON_INTENTIONAL,
            compensation_amount=5.0,
            reasoning="Evidence supports user's claim",
        )
        
        assert decision.arbitrator_id == "arbitrator-001"
        assert decision.decision == ArbitrationResult.IN_FAVOR_OF_USER
        assert decision.intent == Intent.NON_INTENTIONAL
        assert decision.compensation_amount == 5.0
