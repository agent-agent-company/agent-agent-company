"""
Unit tests for AAC Protocol token system
"""

import pytest
from datetime import datetime

from aac_protocol.core.models import User, Creator, Transaction
from aac_protocol.core.database import Database
from aac_protocol.core.escrow import EscrowLedger, TokenSystem, InsufficientBalanceError


@pytest.fixture
async def database():
    """Create test database"""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()
    yield db


@pytest.fixture
async def token_system(database):
    """Create token system with test database"""
    return TokenSystem(database)


class TestTokenSystem:
    """Tests for TokenSystem"""
    
    @pytest.mark.asyncio
    async def test_initial_allocation(self, database):
        """Test initial token allocation"""
        # Create user
        user = User(id="user-001", name="Test User")
        await database.create_user(user)
        
        # Check balance
        tokens = TokenSystem(database)
        balance = await tokens.get_balance("user-001")
        
        assert balance == 1000.0  # Initial allocation
    
    @pytest.mark.asyncio
    async def test_transfer_success(self, database):
        """Test successful transfer"""
        # Create accounts
        user = User(id="user-001", name="Test User", token_balance=1000.0)
        creator = Creator(id="creator-001", name="Test Creator", token_balance=1000.0)
        await database.create_user(user)
        await database.create_creator(creator)
        
        # Transfer
        tokens = TokenSystem(database)
        tx = await tokens.transfer("user-001", "creator-001", 100.0, "payment")
        
        # Check balances
        user_balance = await tokens.get_balance("user-001")
        creator_balance = await tokens.get_balance("creator-001")
        
        assert user_balance == 900.0
        assert creator_balance == 1100.0
        assert tx.amount == 100.0
        assert tx.type == "payment"
    
    @pytest.mark.asyncio
    async def test_transfer_insufficient_balance(self, database):
        """Test transfer with insufficient balance"""
        # Create user with low balance
        user = User(id="user-002", name="Poor User", token_balance=50.0)
        creator = Creator(id="creator-002", name="Rich Creator", token_balance=1000.0)
        await database.create_user(user)
        await database.create_creator(creator)
        
        # Attempt transfer
        tokens = TokenSystem(database)
        
        with pytest.raises(InsufficientBalanceError):
            await tokens.transfer("user-002", "creator-002", 100.0)
    
    @pytest.mark.asyncio
    async def test_lock_tokens(self, database):
        """Test token locking"""
        # Create user
        user = User(id="user-003", name="Test User", token_balance=1000.0)
        await database.create_user(user)
        
        # Lock tokens
        tokens = TokenSystem(database)
        result = await tokens.lock_tokens("user-003", "task-001", 50.0)
        
        assert result is True
        
        # Check available balance
        available = await tokens.get_available_balance("user-003")
        assert available == 950.0
    
    @pytest.mark.asyncio
    async def test_lock_insufficient(self, database):
        """Test locking more than available"""
        # Create user
        user = User(id="user-004", name="Test User", token_balance=100.0)
        await database.create_user(user)
        
        # Attempt to lock too much
        tokens = TokenSystem(database)
        
        with pytest.raises(InsufficientBalanceError):
            await tokens.lock_tokens("user-004", "task-001", 150.0)
    
    @pytest.mark.asyncio
    async def test_release_payment(self, database):
        """Test payment release"""
        # Setup
        user = User(id="user-005", name="Test User", token_balance=1000.0)
        creator = Creator(id="creator-005", name="Test Creator", token_balance=1000.0)
        await database.create_user(user)
        await database.create_creator(creator)
        
        tokens = TokenSystem(database)
        await tokens.lock_tokens("user-005", "task-002", 25.0)
        
        # Release
        tx = await tokens.release_payment(
            task_id="task-002",
            user_id="user-005",
            creator_id="creator-005",
            agent_id="agent-001",
            amount=25.0
        )
        
        # Check
        user_balance = await tokens.get_balance("user-005")
        creator_balance = await tokens.get_balance("creator-005")
        
        assert user_balance == 975.0
        assert creator_balance == 1025.0
    
    @pytest.mark.asyncio
    async def test_refund(self, database):
        """Test refund"""
        # Setup
        user = User(id="user-006", name="Test User", token_balance=1000.0)
        creator = Creator(id="creator-006", name="Test Creator", token_balance=1000.0)
        await database.create_user(user)
        await database.create_creator(creator)
        
        # Lock and refund
        tokens = TokenSystem(database)
        await tokens.lock_tokens("user-006", "task-003", 10.0)
        
        tx = await tokens.refund(
            task_id="task-003",
            from_creator_id="creator-006",
            to_user_id="user-006",
            amount=10.0,
        )
        
        # Refund leg: creator sends amount back to user (demo ledger semantics)
        user_balance = await tokens.get_balance("user-006")
        creator_balance = await tokens.get_balance("creator-006")
        assert user_balance == 1010.0
        assert creator_balance == 990.0
    
    @pytest.mark.asyncio
    async def test_compensation(self, database):
        """Test compensation payment"""
        # Setup
        user = User(id="user-007", name="Test User", token_balance=500.0)
        creator = Creator(id="creator-007", name="Test Creator", token_balance=1000.0)
        await database.create_user(user)
        await database.create_creator(creator)
        
        # Pay compensation
        tokens = TokenSystem(database)
        tx = await tokens.compensate(
            dispute_id="dispute-001",
            from_address="creator-007",
            to_address="user-007",
            amount=50.0,
            is_intentional=False,
        )
        
        # Check
        user_balance = await tokens.get_balance("user-007")
        creator_balance = await tokens.get_balance("creator-007")
        
        assert user_balance == 550.0
        assert creator_balance == 950.0
        assert tx.type == "compensation:non_intentional"
    
    @pytest.mark.asyncio
    async def test_transaction_history(self, database):
        """Test transaction history"""
        # Setup
        user = User(id="user-008", name="Test User", token_balance=1000.0)
        creator = Creator(id="creator-008", name="Test Creator", token_balance=1000.0)
        await database.create_user(user)
        await database.create_creator(creator)
        
        # Make some transfers
        tokens = TokenSystem(database)
        await tokens.transfer("user-008", "creator-008", 10.0, "payment")
        await tokens.transfer("user-008", "creator-008", 20.0, "payment")
        await tokens.transfer("user-008", "creator-008", 30.0, "payment")
        
        # Get history
        history = await tokens.get_transaction_history("user-008")
        
        assert len(history) == 3
        assert history[0].amount == 30.0  # Most recent first
        assert history[1].amount == 20.0
        assert history[2].amount == 10.0


class TestCompensationCalculation:
    """Tests for compensation calculation"""
    
    def test_non_intentional_max(self):
        """Test max compensation for non-intentional"""
        max_comp = TokenSystem.calculate_compensation(
            original_payment=10.0,
            is_intentional=False,
        )
        
        assert max_comp == 50.0  # 5x
    
    def test_intentional_max(self):
        """Test max compensation for intentional"""
        max_comp = TokenSystem.calculate_compensation(
            original_payment=10.0,
            is_intentional=True,
        )
        
        assert max_comp == 150.0  # 15x
    
    def test_custom_multipliers(self):
        """Test custom compensation multipliers"""
        max_comp = TokenSystem.calculate_compensation(
            original_payment=100.0,
            is_intentional=False,
            max_multiplier_non_intentional=3.0,
            max_multiplier_intentional=10.0,
        )
        
        assert max_comp == 300.0
