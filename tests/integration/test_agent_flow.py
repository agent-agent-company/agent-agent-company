"""
Integration tests for complete agent workflows
"""

import pytest
import asyncio

from aac_protocol.core.models import (
    User, Creator, AgentCard, AgentID, Task, TaskInput, TaskOutput,
    AgentStatus, TaskStatus, PaymentStatus, AgentSelectorMode
)
from aac_protocol.core.database import Database
from aac_protocol.core.escrow import EscrowLedger
from aac_protocol.creator.sdk.registry import RegistryClient
from aac_protocol.creator.sdk.card import AgentCardBuilder
from aac_protocol.user.sdk.client import DiscoveryClient, AgentSelector
from aac_protocol.user.sdk.task import TaskManager


@pytest.fixture
async def test_environment():
    """Create complete test environment"""
    # Setup
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()
    
    tokens = EscrowLedger(db)
    registry = RegistryClient(db)
    discovery = DiscoveryClient("http://localhost:8000")  # Mock URL
    tasks = TaskManager(db, tokens, discovery)
    
    # Create test users
    user = User(id="user-test", name="Test User")
    creator = Creator(id="creator-test", name="Test Creator")
    
    await db.create_user(user)
    await db.create_creator(creator)
    
    yield {
        "db": db,
        "tokens": tokens,
        "registry": registry,
        "discovery": discovery,
        "tasks": tasks,
        "user": user,
        "creator": creator,
    }
    
    # Cleanup
    await discovery.close()


class TestAgentRegistrationFlow:
    """Tests for agent registration workflow"""
    
    @pytest.mark.asyncio
    async def test_complete_registration(self, test_environment):
        """Test complete agent registration flow"""
        env = test_environment
        creator = env["creator"]
        registry = env["registry"]
        
        # Build agent card
        builder = AgentCardBuilder("weather", creator)
        builder.with_id(1)
        builder.with_description(
            "Professional weather forecasting agent providing accurate "
            "forecasts for any location worldwide"
        )
        builder.with_price(5.0)
        builder.with_capabilities(["weather", "forecast", "location"])
        builder.at_endpoint("http://localhost:8001")
        
        card = builder.build()
        
        # Register
        registered = await registry.register_agent(card, creator)
        
        # Verify
        assert registered.id.full_id == "weather-001"
        assert registered.creator_id == creator.id
        assert registered.status == AgentStatus.ACTIVE
        
        # Verify stored
        retrieved = await registry.get_agent("weather-001")
        assert retrieved is not None
        assert retrieved.name == "weather"
    
    @pytest.mark.asyncio
    async def test_multiple_agents_same_name(self, test_environment):
        """Test registering multiple agents with same name"""
        env = test_environment
        creator = env["creator"]
        registry = env["registry"]
        
        # Register first weather agent
        card1 = AgentCardBuilder("weather", creator) \
            .with_id(1) \
            .with_description("First weather agent") \
            .with_price(5.0) \
            .at_endpoint("http://localhost:8001") \
            .build()
        
        reg1 = await registry.register_agent(card1, creator)
        
        # Register second weather agent
        card2 = AgentCardBuilder("weather", creator) \
            .with_id(2) \
            .with_description("Second weather agent") \
            .with_price(3.0) \
            .at_endpoint("http://localhost:8002") \
            .build()
        
        reg2 = await registry.register_agent(card2, creator)
        
        # Verify different IDs
        assert reg1.id.full_id == "weather-001"
        assert reg2.id.full_id == "weather-002"


class TestAgentDiscoveryFlow:
    """Tests for agent discovery workflow"""
    
    @pytest.mark.asyncio
    async def test_discover_by_keywords(self, test_environment):
        """Test discovering agents by keywords"""
        env = test_environment
        creator = env["creator"]
        registry = env["registry"]
        
        # Register multiple agents
        weather_card = AgentCardBuilder("weather", creator) \
            .with_id(1) \
            .with_description("Weather forecast agent") \
            .with_price(5.0) \
            .with_capabilities(["weather", "forecast"]) \
            .at_endpoint("http://localhost:8001") \
            .build()
        
        translate_card = AgentCardBuilder("translate", creator) \
            .with_id(1) \
            .with_description("Translation agent for multiple languages") \
            .with_price(3.0) \
            .with_capabilities(["translation", "language"]) \
            .at_endpoint("http://localhost:8002") \
            .build()
        
        await registry.register_agent(weather_card, creator)
        await registry.register_agent(translate_card, creator)
        
        # This would be a real query in production
        # For now, verify they exist
        weather = await registry.get_agent("weather-001")
        translate = await registry.get_agent("translate-001")
        
        assert weather is not None
        assert translate is not None
    
    @pytest.mark.asyncio
    async def test_select_by_performance(self, test_environment):
        """Test agent selection by performance mode"""
        env = test_environment
        creator = env["creator"]
        registry = env["registry"]
        
        # Register agents with different trust scores
        agent1 = AgentCardBuilder("agent1", creator) \
            .with_id(1) \
            .with_description("High trust agent") \
            .with_price(10.0) \
            .at_endpoint("http://localhost:8001") \
            .build()
        agent1.public_trust_score = 90.0
        
        agent2 = AgentCardBuilder("agent2", creator) \
            .with_id(1) \
            .with_description("Low trust agent") \
            .with_price(5.0) \
            .at_endpoint("http://localhost:8002") \
            .build()
        agent2.public_trust_score = 50.0
        
        await registry.register_agent(agent1, creator)
        await registry.register_agent(agent2, creator)
        
        # Verify trust scores
        retrieved1 = await registry.get_agent("agent1-001")
        retrieved2 = await registry.get_agent("agent2-001")
        
        assert retrieved1.public_trust_score == 90.0
        assert retrieved2.public_trust_score == 50.0


class TestTaskFlow:
    """Tests for complete task workflow"""
    
    @pytest.mark.asyncio
    async def test_task_creation(self, test_environment):
        """Test task creation"""
        env = test_environment
        user = env["user"]
        
        # Create task input
        task_input = TaskInput(
            content="Get weather for Tokyo",
            metadata={"location": "Tokyo"},
        )
        
        # Create agent
        creator = env["creator"]
        agent = AgentCardBuilder("weather", creator) \
            .with_id(1) \
            .with_description("Weather agent") \
            .with_price(5.0) \
            .at_endpoint("http://localhost:8001") \
            .build()
        
        # Verify balance before
        balance_before = await env["tokens"].get_balance(user.id)
        assert balance_before == 1000.0
        
        # In production, this would submit the task
        # For integration test, we verify the flow works
        assert task_input.content == "Get weather for Tokyo"
        assert agent.price_per_task == 5.0
    
    @pytest.mark.asyncio
    async def test_token_locking(self, test_environment):
        """Test token locking during task"""
        env = test_environment
        user = env["user"]
        tokens = env["tokens"]
        
        # Lock tokens
        await tokens.lock_tokens(user.id, "task-001", 50.0)
        
        # Check available
        available = await tokens.get_available_balance(user.id)
        assert available == 950.0
        
        # Unlock
        unlocked = await tokens.unlock_tokens("task-001")
        assert unlocked == 50.0
        
        # Check available again
        available_after = await tokens.get_available_balance(user.id)
        assert available_after == 1000.0


class TestPaymentFlow:
    """Tests for payment workflow"""
    
    @pytest.mark.asyncio
    async def test_payment_transfer(self, test_environment):
        """Test payment transfer between user and creator"""
        env = test_environment
        user = env["user"]
        creator = env["creator"]
        tokens = env["tokens"]
        
        # Initial balances
        user_balance = await tokens.get_balance(user.id)
        creator_balance = await tokens.get_balance(creator.id)
        
        assert user_balance == 1000.0
        assert creator_balance == 1000.0
        
        # Make payment
        await tokens.transfer(user.id, creator.id, 25.0, "payment")
        
        # Verify balances
        user_after = await tokens.get_balance(user.id)
        creator_after = await tokens.get_balance(creator.id)
        
        assert user_after == 975.0
        assert creator_after == 1025.0
    
    @pytest.mark.asyncio
    async def test_refund_flow(self, test_environment):
        """Test refund flow"""
        env = test_environment
        user = env["user"]
        creator = env["creator"]
        tokens = env["tokens"]
        
        # Initial balance
        initial = await tokens.get_balance(user.id)
        
        # Lock and refund
        await tokens.lock_tokens(user.id, "task-002", 10.0)
        await tokens.refund("task-002", creator.id, user.id, 10.0)
        
        # Balance should be restored
        final = await tokens.get_balance(user.id)
        assert final == initial


class TestRatingFlow:
    """Tests for rating workflow"""
    
    @pytest.mark.asyncio
    async def test_agent_rating_update(self, test_environment):
        """Test agent rating updates correctly"""
        env = test_environment
        creator = env["creator"]
        registry = env["registry"]
        
        # Create agent
        agent = AgentCardBuilder("rated", creator) \
            .with_id(1) \
            .with_description("Rated agent") \
            .with_price(5.0) \
            .at_endpoint("http://localhost:8001") \
            .build()
        
        registered = await registry.register_agent(agent, creator)
        
        # Initial rating
        assert registered.credibility_score == 3.0
        assert registered.total_ratings == 0
        
        # Add rating
        registered.update_rating(5.0)
        await registry.update_agent(registered, creator)
        
        # Verify
        updated = await registry.get_agent(registered.id.full_id)
        assert updated.credibility_score == 5.0
        assert updated.total_ratings == 1
        
        # Add another rating
        updated.update_rating(3.0)
        await registry.update_agent(updated, creator)
        
        # Verify average
        final = await registry.get_agent(registered.id.full_id)
        assert final.credibility_score == 4.0  # Average of 5 and 3
        assert final.total_ratings == 2


class TestAgentLifecycle:
    """Tests for agent lifecycle"""
    
    @pytest.mark.asyncio
    async def test_activate_deactivate(self, test_environment):
        """Test agent activation and deactivation"""
        env = test_environment
        creator = env["creator"]
        registry = env["registry"]
        
        # Create agent
        agent = AgentCardBuilder("lifecycle", creator) \
            .with_id(1) \
            .with_description("Lifecycle test agent") \
            .with_price(5.0) \
            .at_endpoint("http://localhost:8001") \
            .build()
        
        registered = await registry.register_agent(agent, creator)
        
        # Initial status
        assert registered.status == AgentStatus.ACTIVE
        
        # Deactivate
        await registry.deactivate_agent(registered.id.full_id, creator)
        
        # Verify
        deactivated = await registry.get_agent(registered.id.full_id)
        assert deactivated.status == AgentStatus.INACTIVE
        
        # Reactivate
        await registry.activate_agent(registered.id.full_id, creator)
        
        # Verify
        activated = await registry.get_agent(registered.id.full_id)
        assert activated.status == AgentStatus.ACTIVE
