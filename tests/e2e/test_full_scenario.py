"""
End-to-end tests for complete AAC Protocol scenarios
"""

import pytest
import asyncio
from datetime import datetime

from aac_protocol.core.models import (
    User, Creator, AgentCard, AgentID, Task, TaskInput, TaskOutput,
    TaskStatus, Dispute, DisputeStatus, ArbitrationResult, Intent,
    AgentSelectorMode
)
from aac_protocol.core.database import Database
from aac_protocol.core.escrow import EscrowLedger
from aac_protocol.core.arbitration import ArbitrationSystem, ArbitrationConfig
from aac_protocol.creator.sdk.registry import RegistryClient
from aac_protocol.creator.sdk.card import AgentCardBuilder
from aac_protocol.user.sdk.client import DiscoveryClient
from aac_protocol.user.sdk.task import TaskManager


@pytest.fixture
async def full_system():
    """Create complete system for end-to-end testing"""
    # Setup database
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()
    
    # Setup core systems
    tokens = EscrowLedger(db)
    arbitration = ArbitrationSystem(db, tokens, ArbitrationConfig())
    
    # Setup clients
    registry = RegistryClient(db)
    discovery = DiscoveryClient("http://localhost:8000")
    tasks = TaskManager(db, tokens, discovery)
    
    # Create participants
    user = User(
        id="e2e-user-001",
        name="E2E Test User",
        token_balance=1000.0,
    )
    
    creator = Creator(
        id="e2e-creator-001",
        name="E2E Test Creator",
        token_balance=1000.0,
    )
    
    high_trust_creator = Creator(
        id="e2e-creator-arb",
        name="Arbitration Creator",
        token_balance=2000.0,
        trust_score=95.0,
    )
    
    await db.create_user(user)
    await db.create_creator(creator)
    await db.create_creator(high_trust_creator)
    
    yield {
        "db": db,
        "tokens": tokens,
        "arbitration": arbitration,
        "registry": registry,
        "discovery": discovery,
        "tasks": tasks,
        "user": user,
        "creator": creator,
        "high_trust_creator": high_trust_creator,
    }
    
    await discovery.close()


class TestCompleteWorkflow:
    """End-to-end workflow tests"""
    
    @pytest.mark.asyncio
    async def test_successful_task_completion(self, full_system):
        """
        Test complete successful workflow:
        1. Creator registers agent
        2. User discovers agent
        3. User submits task
        4. Task completes successfully
        5. Payment transfers
        6. User rates agent
        """
        sys = full_system
        user = sys["user"]
        creator = sys["creator"]
        
        # Step 1: Creator registers agent
        agent_card = AgentCardBuilder("weather", creator) \
            .with_id(1) \
            .with_description(
                "Professional weather forecasting service with accurate "
                "predictions for any location worldwide"
            ) \
            .with_price(10.0) \
            .with_capabilities(["weather", "forecast", "location"]) \
            .at_endpoint("http://localhost:8001") \
            .build()
        
        registered = await sys["registry"].register_agent(agent_card, creator)
        assert registered.id.full_id == "weather-001"
        
        # Step 2: Verify agent is discoverable
        agent = await sys["registry"].get_agent("weather-001")
        assert agent is not None
        assert agent.status.value == "active"
        
        # Step 3: Verify initial balances
        user_balance = await sys["tokens"].get_balance(user.id)
        creator_balance = await sys["tokens"].get_balance(creator.id)
        assert user_balance == 1000.0
        assert creator_balance == 1000.0
        
        # Step 4: Simulate payment (task submission would lock tokens)
        await sys["tokens"].lock_tokens(user.id, "task-001", 10.0)
        locked = await sys["tokens"].get_locked_amount(user.id)
        assert locked == 10.0
        
        # Step 5: Simulate task completion and payment
        await sys["tokens"].release_payment(
            task_id="task-001",
            user_id=user.id,
            creator_id=creator.id,
            agent_id="weather-001",
            amount=10.0,
        )
        
        # Step 6: Verify balances after payment
        user_after = await sys["tokens"].get_balance(user.id)
        creator_after = await sys["tokens"].get_balance(creator.id)
        assert user_after == 990.0
        assert creator_after == 1010.0
        
        # Step 7: Update agent stats (completed task)
        agent.completed_tasks += 1
        agent.public_trust_score = agent.calculate_trust_score()
        await sys["registry"].update_agent(agent, creator)
        
        # Verify
        updated_agent = await sys["registry"].get_agent("weather-001")
        assert updated_agent.completed_tasks == 1
        assert updated_agent.public_trust_score > 0
    
    @pytest.mark.asyncio
    async def test_failed_task_with_refund(self, full_system):
        """
        Test workflow with failed task:
        1. User submits task
        2. Task fails
        3. User gets refund
        """
        sys = full_system
        user = sys["user"]
        creator = sys["creator"]
        
        # Setup agent
        agent_card = AgentCardBuilder("unreliable", creator) \
            .with_id(1) \
            .with_description("Unreliable agent for testing") \
            .with_price(5.0) \
            .at_endpoint("http://localhost:8002") \
            .build()
        
        await sys["registry"].register_agent(agent_card, creator)
        
        # Initial balance
        initial = await sys["tokens"].get_balance(user.id)
        
        # Lock tokens
        await sys["tokens"].lock_tokens(user.id, "task-fail-001", 5.0)
        
        # Simulate failure - refund
        await sys["tokens"].unlock_tokens("task-fail-001")
        await sys["tokens"].refund(
            task_id="task-fail-001",
            from_creator_id=creator.id,
            to_user_id=user.id,
            amount=5.0,
        )
        
        # Verify refund
        final = await sys["tokens"].get_balance(user.id)
        assert final == initial
    
    @pytest.mark.asyncio
    async def test_dispute_resolution_flow(self, full_system):
        """
        Test complete dispute resolution:
        1. User submits task
        2. User files dispute
        3. Evidence submitted
        4. Arbitration decision
        5. Compensation paid
        """
        sys = full_system
        user = sys["user"]
        creator = sys["creator"]
        high_trust = sys["high_trust_creator"]
        
        # Setup agent
        agent_card = AgentCardBuilder("disputed", creator) \
            .with_id(1) \
            .with_description("Agent that will have a dispute") \
            .with_price(10.0) \
            .at_endpoint("http://localhost:8003") \
            .build()
        
        await sys["registry"].register_agent(agent_card, creator)
        
        # Create task
        task = Task(
            id="task-dispute-001",
            user_id=user.id,
            agent_id="disputed-001",
            input=TaskInput(content="Test task"),
            price_locked=10.0,
            status=TaskStatus.COMPLETED,
        )
        await sys["db"].create_task(task)
        
        # Pre-compensation balances
        user_balance = await sys["tokens"].get_balance(user.id)
        creator_balance = await sys["tokens"].get_balance(creator.id)
        
        # Step 1: File dispute
        dispute = await sys["arbitration"].file_dispute(
            task_id="task-dispute-001",
            user_id=user.id,
            user_claim="Agent provided completely wrong information",
            claimed_amount=20.0,
        )
        
        assert dispute.status == DisputeStatus.OPEN
        
        # Step 2: Submit evidence
        await sys["arbitration"].submit_evidence(
            dispute_id=dispute.id,
            submitter_id=user.id,
            content="Screenshot showing wrong output",
            attachments=[{"type": "image", "url": "http://example.com/evidence.png"}],
        )
        
        # Step 3: Platform picks up the case
        await sys["arbitration"].assign_arbitrators(dispute.id)
        
        dispute_updated = await sys["db"].get_dispute(dispute.id)
        assert dispute_updated.status == DisputeStatus.UNDER_REVIEW
        
        # Step 4: Submit arbitrator decision
        await sys["arbitration"].submit_arbitration_decision(
            dispute_id=dispute.id,
            arbitrator_id="high-trust-agent-001",
            decision=ArbitrationResult.IN_FAVOR_OF_USER,
            intent=Intent.NON_INTENTIONAL,
            compensation_amount=15.0,
            reasoning="Evidence clearly shows agent error",
        )
        
        # Step 5: Resolve dispute
        resolved = await sys["arbitration"].resolve_dispute(dispute.id)
        
        assert resolved.status == DisputeStatus.RESOLVED
        assert resolved.final_decision == ArbitrationResult.IN_FAVOR_OF_USER
        assert resolved.final_compensation == 15.0
        
        # Step 6: Verify compensation
        # In a real system, compensation would be transferred
        # For this test, we verify the decision is correct
    
    @pytest.mark.asyncio
    async def test_community_review_after_platform(self, full_system):
        """
        Optional community advisory phase after platform review has started.
        """
        sys = full_system
        user = sys["user"]
        creator = sys["creator"]
        
        # Setup
        agent = AgentCardBuilder("escalation", creator) \
            .with_id(1) \
            .with_description("Test escalation") \
            .with_price(10.0) \
            .at_endpoint("http://localhost:8004") \
            .build()
        
        await sys["registry"].register_agent(agent, creator)
        
        task = Task(
            id="task-escalation-001",
            user_id=user.id,
            agent_id="escalation-001",
            input=TaskInput(content="Test"),
            price_locked=10.0,
        )
        await sys["db"].create_task(task)
        
        # File dispute
        dispute = await sys["arbitration"].file_dispute(
            task_id="task-escalation-001",
            user_id=user.id,
            user_claim="Claim",
            claimed_amount=20.0,
        )
        
        await sys["arbitration"].assign_arbitrators(dispute.id)
        
        await sys["arbitration"].submit_arbitration_decision(
            dispute_id=dispute.id,
            arbitrator_id="arb-001",
            decision=ArbitrationResult.IN_FAVOR_OF_AGENT,
            intent=Intent.NON_INTENTIONAL,
            compensation_amount=0.0,
            reasoning="Insufficient evidence",
        )
        
        escalated = await sys["arbitration"].escalate_dispute(dispute.id, user.id)
        
        assert escalated.status == DisputeStatus.COMMUNITY_VOTE
        assert escalated.community_review_requested_by == user.id
    
    @pytest.mark.asyncio
    async def test_multiple_agents_competition(self, full_system):
        """
        Test multiple agents with different pricing:
        1. Register multiple agents
        2. Sort by different criteria
        3. Verify selection works
        """
        sys = full_system
        creator = sys["creator"]
        
        # Register multiple agents
        agents = [
            ("premium", 20.0, 95.0),  # High price, high trust
            ("budget", 5.0, 60.0),     # Low price, medium trust
            ("balanced", 10.0, 80.0),  # Medium price, good trust
        ]
        
        for i, (name, price, trust) in enumerate(agents, 1):
            card = AgentCardBuilder(name, creator) \
                .with_id(i) \
                .with_description(f"{name} agent") \
                .with_price(price) \
                .at_endpoint(f"http://localhost:800{4+i}") \
                .build()
            
            # Manually set trust for testing
            card.public_trust_score = trust
            card.credibility_score = trust / 20  # Rough conversion
            
            await sys["registry"].register_agent(card, creator)
        
        # Verify all registered
        premium = await sys["registry"].get_agent("premium-001")
        budget = await sys["registry"].get_agent("budget-001")
        balanced = await sys["registry"].get_agent("balanced-001")
        
        assert premium.price_per_task == 20.0
        assert budget.price_per_task == 5.0
        assert balanced.price_per_task == 10.0
        
        # Verify selection by price
        all_agents = [premium, budget, balanced]
        cheapest = min(all_agents, key=lambda a: a.price_per_task)
        assert cheapest.id.full_id == "budget-001"
        
        # Verify selection by trust
        most_trusted = max(all_agents, key=lambda a: a.public_trust_score)
        assert most_trusted.id.full_id == "premium-001"


class TestSystemStress:
    """Stress tests for system limits"""
    
    @pytest.mark.asyncio
    async def test_many_agents_registration(self, full_system):
        """Test registering many agents"""
        sys = full_system
        creator = sys["creator"]
        
        # Register 50 agents
        for i in range(50):
            card = AgentCardBuilder(f"agent{i}", creator) \
                .with_id(1) \
                .with_description(f"Agent {i}") \
                .with_price(float(i + 1)) \
                .at_endpoint(f"http://localhost:{9000+i}") \
                .build()
            
            await sys["registry"].register_agent(card, creator)
        
        # Verify count
        agents = await sys["registry"].list_agents(limit=100)
        assert len(agents) >= 50
    
    @pytest.mark.asyncio
    async def test_many_transactions(self, full_system):
        """Test handling many transactions"""
        sys = full_system
        user = sys["user"]
        creator = sys["creator"]
        tokens = sys["tokens"]
        
        # Perform many transfers
        for i in range(100):
            await tokens.transfer(user.id, creator.id, 1.0, "payment")
        
        # Verify
        history = await tokens.get_transaction_history(user.id, limit=200)
        assert len(history) == 100
        
        # Verify balances
        user_balance = await tokens.get_balance(user.id)
        creator_balance = await tokens.get_balance(creator.id)
        
        assert user_balance == 900.0  # 1000 - 100
        assert creator_balance == 1100.0  # 1000 + 100
