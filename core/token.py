"""
AAC Protocol Token System

A simplified ledger-based token system without blockchain PoW.
Features:
- Pre-allocated initial balance for new users/creators
- Immutable transaction records
- Transfer, lock, and release operations
- Balance queries
"""

import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal, ROUND_DOWN

from .models import Transaction, User, Creator
from .database import Database


class InsufficientBalanceError(Exception):
    """Raised when account has insufficient balance"""
    pass


class TokenLockedError(Exception):
    """Raised when trying to use locked tokens"""
    pass


class TokenSystem:
    """
    AAC Protocol Token System
    
    Manages token balances and transactions for users and creators.
    All transactions are recorded immutably in the database.
    
    Initial allocation: 1000 AAC tokens for new accounts
    """
    
    INITIAL_ALLOCATION = 1000.0
    DECIMAL_PLACES = 6
    
    def __init__(self, database: Database):
        self.db = database
        self._locks: Dict[str, float] = {}  # In-memory locks: {task_id: amount}
    
    def _generate_transaction_id(self, from_addr: str, to_addr: str, amount: float, timestamp: datetime) -> str:
        """Generate unique transaction ID"""
        data = f"{from_addr}:{to_addr}:{amount}:{timestamp.isoformat()}:{uuid.uuid4().hex[:8]}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    async def get_balance(self, address: str) -> float:
        """
        Get token balance for user or creator
        
        Args:
            address: User ID or Creator ID
            
        Returns:
            Current token balance
        """
        # Try user first
        user = await self.db.get_user(address)
        if user:
            return user.token_balance
        
        # Try creator
        creator = await self.db.get_creator(address)
        if creator:
            return creator.token_balance
        
        return 0.0
    
    async def transfer(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        transaction_type: str = "transfer",
        task_id: Optional[str] = None,
        dispute_id: Optional[str] = None
    ) -> Transaction:
        """
        Transfer tokens between accounts
        
        Args:
            from_address: Sender address
            to_address: Receiver address
            amount: Amount to transfer
            transaction_type: Type of transaction
            task_id: Associated task ID
            dispute_id: Associated dispute ID
            
        Returns:
            Transaction record
            
        Raises:
            InsufficientBalanceError: If sender has insufficient balance
            ValueError: If amount is invalid
        """
        # Validate amount
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Round to specified decimal places
        amount = float(Decimal(str(amount)).quantize(
            Decimal('0.' + '0' * self.DECIMAL_PLACES),
            rounding=ROUND_DOWN
        ))
        
        # Check sender balance
        sender_balance = await self.get_balance(from_address)
        if sender_balance < amount:
            raise InsufficientBalanceError(
                f"Insufficient balance: {sender_balance} < {amount}"
            )
        
        # Create transaction
        timestamp = datetime.utcnow()
        transaction = Transaction(
            id=self._generate_transaction_id(from_address, to_address, amount, timestamp),
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            type=transaction_type,
            task_id=task_id,
            dispute_id=dispute_id,
            timestamp=timestamp,
        )
        
        # Update balances
        await self._debit(from_address, amount)
        await self._credit(to_address, amount)
        
        # Record transaction
        await self.db.record_transaction(transaction)
        
        return transaction
    
    async def _debit(self, address: str, amount: float):
        """Debit (subtract) from account balance"""
        # Try user
        user = await self.db.get_user(address)
        if user:
            new_balance = user.token_balance - amount
            await self.db.update_user_balance(address, new_balance)
            return
        
        # Try creator
        creator = await self.db.get_creator(address)
        if creator:
            creator.token_balance -= amount
            await self.db.update_creator(creator)
            return
        
        raise ValueError(f"Account not found: {address}")
    
    async def _credit(self, address: str, amount: float):
        """Credit (add) to account balance"""
        # Try user
        user = await self.db.get_user(address)
        if user:
            new_balance = user.token_balance + amount
            await self.db.update_user_balance(address, new_balance)
            return
        
        # Try creator
        creator = await self.db.get_creator(address)
        if creator:
            creator.token_balance += amount
            await self.db.update_creator(creator)
            return
        
        raise ValueError(f"Account not found: {address}")
    
    async def lock_tokens(self, user_id: str, task_id: str, amount: float) -> bool:
        """
        Lock tokens for a task (payment reservation)
        
        Args:
            user_id: User locking tokens
            task_id: Task ID for lock
            amount: Amount to lock
            
        Returns:
            True if lock successful
            
        Raises:
            InsufficientBalanceError: If insufficient balance
        """
        # Check balance
        balance = await self.get_balance(user_id)
        locked_amount = self._locks.get(task_id, 0)
        available = balance - locked_amount
        
        if available < amount:
            raise InsufficientBalanceError(
                f"Insufficient available balance: {available} < {amount}"
            )
        
        # Add lock
        self._locks[task_id] = locked_amount + amount
        
        return True
    
    async def unlock_tokens(self, task_id: str) -> float:
        """
        Unlock tokens for a task
        
        Args:
            task_id: Task ID to unlock
            
        Returns:
            Amount unlocked
        """
        amount = self._locks.pop(task_id, 0)
        return amount
    
    async def release_payment(
        self,
        task_id: str,
        user_id: str,
        creator_id: str,
        agent_id: str,
        amount: float
    ) -> Transaction:
        """
        Release locked payment to creator after task completion
        
        Args:
            task_id: Task ID
            user_id: User who made payment
            creator_id: Creator receiving payment
            agent_id: Agent that completed task
            amount: Payment amount
            
        Returns:
            Payment transaction
        """
        # Remove lock
        locked = self._locks.pop(task_id, 0)
        if locked < amount:
            raise TokenLockedError(f"Locked amount {locked} less than payment {amount}")
        
        # Transfer from user to creator
        transaction = await self.transfer(
            from_address=user_id,
            to_address=creator_id,
            amount=amount,
            transaction_type="payment",
            task_id=task_id,
        )
        
        return transaction
    
    async def refund(
        self,
        task_id: str,
        from_creator_id: str,
        to_user_id: str,
        amount: float,
        reason: str = "refund"
    ) -> Transaction:
        """
        Refund tokens to user
        
        Args:
            task_id: Task ID
            from_creator_id: Creator issuing refund
            to_user_id: User receiving refund
            amount: Refund amount
            reason: Refund reason
            
        Returns:
            Refund transaction
        """
        # Remove any remaining lock
        self._locks.pop(task_id, None)
        
        # Transfer from creator to user
        transaction = await self.transfer(
            from_address=from_creator_id,
            to_address=to_user_id,
            amount=amount,
            transaction_type=f"refund:{reason}",
            task_id=task_id,
        )
        
        return transaction
    
    async def compensate(
        self,
        dispute_id: str,
        from_address: str,
        to_address: str,
        amount: float,
        is_intentional: bool
    ) -> Transaction:
        """
        Pay compensation as per arbitration decision
        
        Args:
            dispute_id: Dispute ID
            from_address: Party paying compensation
            to_address: Party receiving compensation
            amount: Compensation amount
            is_intentional: Whether damage was intentional
            
        Returns:
            Compensation transaction
        """
        intent_str = "intentional" if is_intentional else "non_intentional"
        
        transaction = await self.transfer(
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            transaction_type=f"compensation:{intent_str}",
            dispute_id=dispute_id,
        )
        
        return transaction
    
    async def get_transaction_history(
        self,
        address: str,
        limit: int = 100,
        transaction_type: Optional[str] = None
    ) -> List[Transaction]:
        """
        Get transaction history for an address
        
        Args:
            address: Account address
            limit: Maximum number of transactions
            transaction_type: Filter by type
            
        Returns:
            List of transactions
        """
        transactions = await self.db.get_transactions(address, limit)
        
        if transaction_type:
            transactions = [
                t for t in transactions
                if t.type.startswith(transaction_type)
            ]
        
        return transactions
    
    async def get_locked_amount(self, user_id: str) -> float:
        """
        Get total locked amount for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Total locked amount
        """
        # Sum all locks (simplified - in production, track per-user)
        return sum(self._locks.values())
    
    async def get_available_balance(self, user_id: str) -> float:
        """
        Get available (unlocked) balance for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Available balance
        """
        total = await self.get_balance(user_id)
        locked = await self.get_locked_amount(user_id)
        return total - locked
    
    @staticmethod
    def calculate_compensation(
        original_payment: float,
        is_intentional: bool,
        max_multiplier_non_intentional: float = 5.0,
        max_multiplier_intentional: float = 15.0
    ) -> float:
        """
        Calculate maximum compensation based on intent
        
        Args:
            original_payment: Original task payment
            is_intentional: Whether damage was intentional
            max_multiplier_non_intentional: Max multiplier for non-intentional
            max_multiplier_intentional: Max multiplier for intentional
            
        Returns:
            Maximum compensation amount
        """
        if is_intentional:
            return original_payment * max_multiplier_intentional
        else:
            return original_payment * max_multiplier_non_intentional


class TokenLedger:
    """
    Immutable token ledger for audit purposes
    
    Provides read-only access to all transactions for transparency.
    """
    
    def __init__(self, database: Database):
        self.db = database
    
    async def get_all_transactions(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[Transaction]:
        """
        Query all transactions (audit function)
        
        Args:
            start_time: Filter from timestamp
            end_time: Filter to timestamp
            transaction_type: Filter by type
            limit: Maximum results
            
        Returns:
            List of transactions
        """
        # This would query all transactions in a real implementation
        # For now, returns empty list (placeholder)
        return []
    
    async def verify_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """
        Verify and retrieve a specific transaction
        
        Args:
            transaction_id: Transaction ID to verify
            
        Returns:
            Transaction if found, None otherwise
        """
        # This would query by transaction ID
        # For now, returns None (placeholder)
        return None
    
    async def get_total_supply(self) -> float:
        """
        Get total token supply in circulation
        
        Returns:
            Total supply amount
        """
        # Sum all user and creator balances
        # This is a placeholder - real implementation would aggregate
        return 0.0
    
    async def get_circulating_supply(self) -> float:
        """
        Get circulating supply (not locked)
        
        Returns:
            Circulating supply amount
        """
        # Total minus locked
        # This is a placeholder
        return 0.0
