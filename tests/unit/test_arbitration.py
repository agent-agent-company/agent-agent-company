"""
Unit tests for AAC Protocol arbitration system
"""

import pytest
from datetime import datetime

from aac_protocol.core.models import (
    User, Creator, AgentCard, AgentID, Task, TaskInput, Dispute,
    DisputeEvidence, DisputeStatus, ArbitrationLevel, ArbitrationResult,
    ArbitratorDecision, Intent
)
from aac_protocol.core.database import Database
from aac_protocol.core.token import TokenSystem
from aac_protocol.core.arbitration import ArbitrationSystem, ArbitrationConfig, InvalidDisputeError


@pytest.fixture
async def database():
    """Create test database"""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()
    yield db


@pytest.fixture
async def arbitration_system(database):
    """Create arbitration system"""
    tokens = TokenSystem(database)
    config = ArbitrationConfig(
        max_compensation_non_intentional=5.0,
        max_compensation_intentional=15.0,
    )
    return ArbitrationSystem(database, tokens, config)


class TestArbitrationSystem:
    """Tests for ArbitrationSystem"""
    
    @pytest.mark.asyncio
    async def test_file_dispute(self, database, arbitration_system):
        """Test filing a dispute"""
        # Setup
        user = User(id="user-001", name="Test User", token_balance=1000.0)
        creator = Creator(id="creator-001", name="Test Creator", token_balance=1000.0)
        agent_id = AgentID(name="test", sequence_id=1)
        agent = AgentCard(
            id=agent_id,
            name="Test Agent",
            description="Test description long enough",
            creator_id="creator-001",
            price_per_task=10.0,
            endpoint_url="http://localhost:8001",
        )
        task = Task(
            id="task-001",
            user_id="user-001",
            agent_id=agent_id.full_id,
            input=TaskInput(content="Test"),
            price_locked=10.0,
        )
        
        await database.create_user(user)
        await database.create_creator(creator)
        await database.create_agent(agent)
        await database.create_task(task)
        
        # File dispute
        dispute = await arbitration_system.file_dispute(
            task_id="task-001",
            user_id="user-001",
            user_claim="Agent did not complete task",
            claimed_amount=20.0,
        )
        
        assert dispute.id.startswith("dispute-")
        assert dispute.task_id == "task-001"
        assert dispute.user_id == "user-001"
        assert dispute.creator_id == "creator-001"
        assert dispute.status == DisputeStatus.OPEN
        assert dispute.current_level == ArbitrationLevel.FIRST
    
    @pytest.mark.asyncio
    async def test_file_dispute_task_not_found(self, database, arbitration_system):
        """Test filing dispute for non-existent task"""
        with pytest.raises(InvalidDisputeError) as exc_info:
            await arbitration_system.file_dispute(
                task_id="nonexistent",
                user_id="user-001",
                user_claim="Claim",
                claimed_amount=10.0,
            )
        
        assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_file_dispute_excessive_claim(self, database, arbitration_system):
        """Test filing dispute with excessive claim amount"""
        # Setup
        user = User(id="user-002", name="Test User")
        creator = Creator(id="creator-002", name="Test Creator")
        agent_id = AgentID(name="test", sequence_id=1)
        agent = AgentCard(
            id=agent_id,
            name="Test Agent",
            description="Test description long enough",
            creator_id="creator-002",
            price_per_task=10.0,
            endpoint_url="http://localhost:8001",
        )
        task = Task(
            id="task-002",
            user_id="user-002",
            agent_id=agent_id.full_id,
            input=TaskInput(content="Test"),
            price_locked=10.0,
        )
        
        await database.create_user(user)
        await database.create_creator(creator)
        await database.create_agent(agent)
        await database.create_task(task)
        
        # Try to claim more than max (15x)
        with pytest.raises(InvalidDisputeError) as exc_info:
            await arbitration_system.file_dispute(
                task_id="task-002",
                user_id="user-002",
                user_claim="Claim",
                claimed_amount=200.0,  # 20x, exceeds 15x max
            )
        
        assert "exceeds maximum" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_submit_evidence(self, database, arbitration_system):
        """Test submitting evidence"""
        # Setup
        user = User(id="user-003", name="Test User")
        creator = Creator(id="creator-003", name="Test Creator")
        agent_id = AgentID(name="test", sequence_id=1)
        agent = AgentCard(
            id=agent_id,
            name="Test Agent",
            description="Test description long enough",
            creator_id="creator-003",
            price_per_task=10.0,
            endpoint_url="http://localhost:8001",
        )
        task = Task(
            id="task-003",
            user_id="user-003",
            agent_id=agent_id.full_id,
            input=TaskInput(content="Test"),
            price_locked=10.0,
        )
        
        await database.create_user(user)
        await database.create_creator(creator)
        await database.create_agent(agent)
        await database.create_task(task)
        
        dispute = await arbitration_system.file_dispute(
            task_id="task-003",
            user_id="user-003",
            user_claim="Claim",
            claimed_amount=20.0,
        )
        
        # Submit evidence
        updated = await arbitration_system.submit_evidence(
            dispute_id=dispute.id,
            submitter_id="user-003",
            content="Screenshot of error",
            attachments=[{"type": "image", "url": "http://example.com/error.png"}],
        )
        
        assert len(updated.user_evidence) == 1
        assert updated.user_evidence[0].content == "Screenshot of error"
    
    @pytest.mark.asyncio
    async def test_submit_arbitration_decision(self, database, arbitration_system):
        """Test submitting arbitrator decision"""
        # Setup
        user = User(id="user-004", name="Test User")
        creator = Creator(id="creator-004", name="Test Creator")
        agent_id = AgentID(name="test", sequence_id=1)
        agent = AgentCard(
            id=agent_id,
            name="Test Agent",
            description="Test description long enough",
            creator_id="creator-004",
            price_per_task=10.0,
            endpoint_url="http://localhost:8001",
        )
        task = Task(
            id="task-004",
            user_id="user-004",
            agent_id=agent_id.full_id,
            input=TaskInput(content="Test"),
            price_locked=10.0,
        )
        
        await database.create_user(user)
        await database.create_creator(creator)
        await database.create_agent(agent)
        await database.create_task(task)
        
        dispute = await arbitration_system.file_dispute(
            task_id="task-004",
            user_id="user-004",
            user_claim="Claim",
            claimed_amount=20.0,
        )
        
        # Assign arbitrator
        await arbitration_system.assign_arbitrators(dispute.id)
        
        # Submit decision
        updated = await arbitration_system.submit_arbitration_decision(
            dispute_id=dispute.id,
            arbitrator_id="arbitrator-001",
            decision=ArbitrationResult.IN_FAVOR_OF_USER,
            intent=Intent.NON_INTENTIONAL,
            compensation_amount=15.0,
            reasoning="Evidence supports user claim",
        )
        
        assert updated.level_1_decision is not None
        assert updated.level_1_decision.decision == ArbitrationResult.IN_FAVOR_OF_USER
        assert updated.level_1_decision.compensation_amount == 15.0
    
    @pytest.mark.asyncio
    async def test_resolve_dispute(self, database, arbitration_system):
        """Test resolving a dispute"""
        # Setup
        user = User(id="user-005", name="Test User", token_balance=500.0)
        creator = Creator(id="creator-005", name="Test Creator", token_balance=1000.0)
        agent_id = AgentID(name="test", sequence_id=1)
        agent = AgentCard(
            id=agent_id,
            name="Test Agent",
            description="Test description long enough",
            creator_id="creator-005",
            price_per_task=10.0,
            endpoint_url="http://localhost:8001",
        )
        task = Task(
            id="task-005",
            user_id="user-005",
            agent_id=agent_id.full_id,
            input=TaskInput(content="Test"),
            price_locked=10.0,
        )
        
        await database.create_user(user)
        await database.create_creator(creator)
        await database.create_agent(agent)
        await database.create_task(task)
        
        # Create and resolve dispute
        dispute = await arbitration_system.file_dispute(
            task_id="task-005",
            user_id="user-005",
            user_claim="Claim",
            claimed_amount=15.0,
        )
        
        await arbitration_system.assign_arbitrators(dispute.id)
        
        await arbitration_system.submit_arbitration_decision(
            dispute_id=dispute.id,
            arbitrator_id="arb-001",
            decision=ArbitrationResult.IN_FAVOR_OF_USER,
            intent=Intent.NON_INTENTIONAL,
            compensation_amount=15.0,
            reasoning="User is right",
        )
        
        resolved = await arbitration_system.resolve_dispute(dispute.id)
        
        assert resolved.status == DisputeStatus.RESOLVED
        assert resolved.final_decision == ArbitrationResult.IN_FAVOR_OF_USER
        assert resolved.final_compensation == 15.0
    
    @pytest.mark.asyncio
    async def test_escalate_dispute(self, database, arbitration_system):
        """Test escalating a dispute"""
        # Setup
        user = User(id="user-006", name="Test User")
        creator = Creator(id="creator-006", name="Test Creator")
        agent_id = AgentID(name="test", sequence_id=1)
        agent = AgentCard(
            id=agent_id,
            name="Test Agent",
            description="Test description long enough",
            creator_id="creator-006",
            price_per_task=10.0,
            endpoint_url="http://localhost:8001",
        )
        task = Task(
            id="task-006",
            user_id="user-006",
            agent_id=agent_id.full_id,
            input=TaskInput(content="Test"),
            price_locked=10.0,
        )
        
        await database.create_user(user)
        await database.create_creator(creator)
        await database.create_agent(agent)
        await database.create_task(task)
        
        dispute = await arbitration_system.file_dispute(
            task_id="task-006",
            user_id="user-006",
            user_claim="Claim",
            claimed_amount=20.0,
        )
        
        await arbitration_system.assign_arbitrators(dispute.id)
        
        # Submit level 1 decision
        await arbitration_system.submit_arbitration_decision(
            dispute_id=dispute.id,
            arbitrator_id="arb-001",
            decision=ArbitrationResult.IN_FAVOR_OF_AGENT,
            intent=Intent.NON_INTENTIONAL,
            compensation_amount=0.0,
            reasoning="Evidence insufficient",
        )
        
        # Escalate
        escalated = await arbitration_system.escalate_dispute(dispute.id, "user-006")
        
        assert escalated.current_level == ArbitrationLevel.SECOND
        assert escalated.status == DisputeStatus.SECOND_INSTANCE


class TestArbitrationConfig:
    """Tests for ArbitrationConfig"""
    
    def test_default_config(self):
        """Test default configuration"""
        config = ArbitrationConfig()
        
        assert config.max_compensation_non_intentional == 5.0
        assert config.max_compensation_intentional == 15.0
        assert config.min_trust_score_level_1 == 70.0
        assert config.min_trust_score_level_2 == 80.0
        assert config.min_trust_score_level_3 == 90.0
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = ArbitrationConfig(
            max_compensation_non_intentional=3.0,
            max_compensation_intentional=10.0,
        )
        
        assert config.max_compensation_non_intentional == 3.0
        assert config.max_compensation_intentional == 10.0


class TestDisputeEvidence:
    """Tests for DisputeEvidence"""
    
    def test_evidence_creation(self):
        """Test creating evidence"""
        evidence = DisputeEvidence(
            submitted_by="user-001",
            content="Test evidence",
            attachments=[{"type": "text", "content": "data"}],
        )
        
        assert evidence.submitted_by == "user-001"
        assert evidence.content == "Test evidence"
        assert len(evidence.attachments) == 1
        assert evidence.submitted_at is not None


class TestArbitratorDecision:
    """Tests for ArbitratorDecision"""
    
    def test_decision_creation(self):
        """Test creating decision"""
        decision = ArbitratorDecision(
            arbitrator_id="arb-001",
            decision=ArbitrationResult.PARTIAL_COMPENSATION,
            intent=Intent.NON_INTENTIONAL,
            compensation_amount=25.0,
            reasoning="Partial fault on both sides",
        )
        
        assert decision.arbitrator_id == "arb-001"
        assert decision.decision == ArbitrationResult.PARTIAL_COMPENSATION
        assert decision.compensation_amount == 25.0
