"""
Unit tests for AAC Protocol arbitration system
"""

import pytest
import pytest_asyncio
from datetime import datetime

from aac_protocol.core.models import (
    User, Creator, AgentCard, AgentID, Task, TaskInput, Dispute,
    DisputeEvidence, DisputeStatus, ArbitrationResult,
    ArbitratorDecision, Intent
)
from aac_protocol.core.database import Database
from aac_protocol.core.escrow import EscrowLedger
from aac_protocol.core.arbitration import ArbitrationSystem, ArbitrationConfig, InvalidDisputeError


@pytest_asyncio.fixture
async def database():
    """Create test database"""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()
    yield db


@pytest_asyncio.fixture
async def arbitration_system(database):
    """Create arbitration system"""
    ledger = EscrowLedger(database)
    config = ArbitrationConfig(
        max_compensation_non_intentional=5.0,
        max_compensation_intentional=15.0,
    )
    return ArbitrationSystem(database, ledger, config)


@pytest_asyncio.fixture
async def test_user(database):
    """Create a test user with initial balance"""
    user = User(id="test-user-001", name="Test User", token_balance=1000.0)
    await database.create_user(user)
    return user


@pytest_asyncio.fixture
async def test_creator(database):
    """Create a test creator with initial balance"""
    creator = Creator(id="test-creator-001", name="Test Creator", token_balance=1000.0)
    await database.create_creator(creator)
    return creator


@pytest_asyncio.fixture
async def test_agent(database, test_creator):
    """Create a test agent"""
    agent_id = AgentID(name="test-agent", sequence_id=1)
    agent = AgentCard(
        id=agent_id,
        name="Test Agent",
        description="A test agent for unit testing with detailed description",
        creator_id=test_creator.id,
        price_per_task=10.0,
        endpoint_url="http://localhost:8001",
    )
    await database.create_agent(agent)
    return agent


@pytest_asyncio.fixture
async def test_task(database, test_user, test_agent):
    """Create a test task"""
    task = Task(
        id="test-task-001",
        user_id=test_user.id,
        agent_id=test_agent.id.full_id,
        input=TaskInput(content="Test task input"),
        price_locked=10.0,
    )
    await database.create_task(task)
    return task


@pytest_asyncio.fixture
async def dispute_setup(database, arbitration_system, test_user, test_creator, test_agent, test_task):
    """Complete setup for dispute-related tests"""
    return {
        "database": database,
        "arbitration_system": arbitration_system,
        "user": test_user,
        "creator": test_creator,
        "agent": test_agent,
        "task": test_task,
    }


class TestArbitrationSystem:
    """Tests for ArbitrationSystem"""

    @pytest.mark.asyncio
    async def test_file_dispute(self, arbitration_system, dispute_setup):
        """Test filing a dispute"""
        # File dispute using the pre-configured setup
        dispute = await arbitration_system.file_dispute(
            task_id=dispute_setup["task"].id,
            user_id=dispute_setup["user"].id,
            user_claim="Agent did not complete task",
            claimed_amount=20.0,
        )

        assert dispute.id.startswith("dispute-")
        assert dispute.task_id == dispute_setup["task"].id
        assert dispute.user_id == dispute_setup["user"].id
        assert dispute.creator_id == dispute_setup["creator"].id
        assert dispute.status == DisputeStatus.OPEN
    
    @pytest.mark.asyncio
    async def test_file_dispute_task_not_found(self, arbitration_system):
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
        """Test filing dispute with excessive claim amount (exceeds 15x max)"""
        # Create unique entities for this test to avoid conflicts
        user = User(id="user-excess", name="Test User")
        creator = Creator(id="creator-excess", name="Test Creator")
        agent_id = AgentID(name="test-excess", sequence_id=1)
        agent = AgentCard(
            id=agent_id,
            name="Test Agent",
            description="Test description long enough for validation",
            creator_id="creator-excess",
            price_per_task=10.0,
            endpoint_url="http://localhost:8001",
        )
        task = Task(
            id="task-excess",
            user_id="user-excess",
            agent_id=agent_id.full_id,
            input=TaskInput(content="Test content"),
            price_locked=10.0,
        )

        await database.create_user(user)
        await database.create_creator(creator)
        await database.create_agent(agent)
        await database.create_task(task)

        # Try to claim more than max (15x) - 200 is 20x, exceeds limit
        with pytest.raises(InvalidDisputeError) as exc_info:
            await arbitration_system.file_dispute(
                task_id="task-excess",
                user_id="user-excess",
                user_claim="Claim",
                claimed_amount=200.0,
            )

        assert "exceeds maximum" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_evidence(self, arbitration_system, dispute_setup):
        """Test submitting evidence"""
        # File dispute using shared fixture
        dispute = await arbitration_system.file_dispute(
            task_id=dispute_setup["task"].id,
            user_id=dispute_setup["user"].id,
            user_claim="Claim",
            claimed_amount=20.0,
        )

        # Submit evidence
        updated = await arbitration_system.submit_evidence(
            dispute_id=dispute.id,
            submitter_id=dispute_setup["user"].id,
            content="Screenshot of error",
            attachments=[{"type": "image", "url": "http://example.com/error.png"}],
        )

        assert len(updated.user_evidence) == 1
        assert updated.user_evidence[0].content == "Screenshot of error"

    @pytest.mark.asyncio
    async def test_submit_arbitration_decision(self, arbitration_system, dispute_setup):
        """Test submitting arbitrator decision"""
        # File dispute
        dispute = await arbitration_system.file_dispute(
            task_id=dispute_setup["task"].id,
            user_id=dispute_setup["user"].id,
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

        assert updated.platform_decision is not None
        assert updated.platform_decision.decision == ArbitrationResult.IN_FAVOR_OF_USER
        assert updated.platform_decision.compensation_amount == 15.0

    @pytest.mark.asyncio
    async def test_resolve_dispute(self, arbitration_system, dispute_setup):
        """Test resolving a dispute"""
        # Create and resolve dispute
        dispute = await arbitration_system.file_dispute(
            task_id=dispute_setup["task"].id,
            user_id=dispute_setup["user"].id,
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
    async def test_escalate_dispute(self, arbitration_system, dispute_setup):
        """Test escalating a dispute to community vote"""
        # Create dispute
        dispute = await arbitration_system.file_dispute(
            task_id=dispute_setup["task"].id,
            user_id=dispute_setup["user"].id,
            user_claim="Claim",
            claimed_amount=20.0,
        )

        await arbitration_system.assign_arbitrators(dispute.id)

        # Submit initial decision
        await arbitration_system.submit_arbitration_decision(
            dispute_id=dispute.id,
            arbitrator_id="arb-001",
            decision=ArbitrationResult.IN_FAVOR_OF_AGENT,
            intent=Intent.NON_INTENTIONAL,
            compensation_amount=0.0,
            reasoning="Evidence insufficient",
        )

        # Escalate to community vote
        escalated = await arbitration_system.escalate_dispute(
            dispute.id, dispute_setup["user"].id
        )

        assert escalated.status == DisputeStatus.COMMUNITY_VOTE


class TestArbitrationConfig:
    """Tests for ArbitrationConfig"""
    
    def test_default_config(self):
        """Test default configuration"""
        config = ArbitrationConfig()
        
        assert config.max_compensation_non_intentional == 5.0
        assert config.max_compensation_intentional == 15.0
        assert config.community_votes_required == 3
    
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
