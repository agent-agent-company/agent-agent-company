"""
AAC Protocol — platform escrow ledger (centralized)

Balances and task holds live in the platform database. This module provides
transfers, per-task locks, release to creators, refunds, and dispute payouts.
No Merkle trees, multi-sig, or on-chain semantics — trust boundaries are the
same as any hosted marketplace (Stripe + internal ledger, etc.).
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


class FundsLockedError(Exception):
    """Raised when locked escrow does not cover a release"""
    pass


class EscrowLedger:
    """
    Platform-held balances and audit log of movements.

    Amounts are abstract units (e.g. USD, demo credits, or settled crypto);
    routing real fiat/crypto is outside this reference implementation.
    """

    INITIAL_DEMO_BALANCE = 1000.0
    DECIMAL_PLACES = 6

    def __init__(self, database: Database):
        self.db = database
        self._locks: Dict[str, float] = {}

    async def get_balance(self, account_id: str) -> float:
        user = await self.db.get_user(account_id)
        if user:
            return user.token_balance
        creator = await self.db.get_creator(account_id)
        if creator:
            return creator.token_balance
        return 0.0

    def _generate_transaction_id(
        self, from_addr: str, to_addr: str, amount: float, timestamp: datetime
    ) -> str:
        data = f"{from_addr}:{to_addr}:{amount}:{timestamp.isoformat()}:{uuid.uuid4().hex[:8]}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    async def transfer(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        transaction_type: str = "transfer",
        task_id: Optional[str] = None,
        dispute_id: Optional[str] = None,
    ) -> Transaction:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        amount = float(
            Decimal(str(amount)).quantize(
                Decimal("0." + "0" * self.DECIMAL_PLACES), rounding=ROUND_DOWN
            )
        )
        sender_balance = await self.get_balance(from_address)
        if sender_balance < amount:
            raise InsufficientBalanceError(
                f"Insufficient balance: {sender_balance} < {amount}"
            )
        timestamp = datetime.utcnow()
        transaction = Transaction(
            id=self._generate_transaction_id(
                from_address, to_address, amount, timestamp
            ),
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            type=transaction_type,
            task_id=task_id,
            dispute_id=dispute_id,
            timestamp=timestamp,
            signature=None,
        )
        await self._debit(from_address, amount)
        await self._credit(to_address, amount)
        await self.db.record_transaction(transaction)
        return transaction

    async def _debit(self, address: str, amount: float) -> None:
        user = await self.db.get_user(address)
        if user:
            await self.db.update_user_balance(address, user.token_balance - amount)
            return
        creator = await self.db.get_creator(address)
        if creator:
            creator.token_balance -= amount
            await self.db.update_creator(creator)
            return
        raise ValueError(f"Account not found: {address}")

    async def _credit(self, address: str, amount: float) -> None:
        user = await self.db.get_user(address)
        if user:
            await self.db.update_user_balance(address, user.token_balance + amount)
            return
        creator = await self.db.get_creator(address)
        if creator:
            creator.token_balance += amount
            await self.db.update_creator(creator)
            return
        raise ValueError(f"Account not found: {address}")

    async def lock_tokens(self, user_id: str, task_id: str, amount: float) -> bool:
        balance = await self.get_balance(user_id)
        locked_amount = self._locks.get(task_id, 0)
        available = balance - locked_amount
        if available < amount:
            raise InsufficientBalanceError(
                f"Insufficient available balance: {available} < {amount}"
            )
        self._locks[task_id] = locked_amount + amount
        return True

    async def unlock_tokens(self, task_id: str) -> float:
        return self._locks.pop(task_id, 0)

    async def release_payment(
        self,
        task_id: str,
        user_id: str,
        creator_id: str,
        agent_id: str,
        amount: float,
    ) -> Transaction:
        locked = self._locks.pop(task_id, 0)
        if locked < amount:
            raise FundsLockedError(f"Locked amount {locked} less than payment {amount}")
        return await self.transfer(
            from_address=user_id,
            to_address=creator_id,
            amount=amount,
            transaction_type="payment",
            task_id=task_id,
        )

    async def refund(
        self,
        task_id: str,
        from_creator_id: str,
        to_user_id: str,
        amount: float,
        reason: str = "refund",
    ) -> Transaction:
        self._locks.pop(task_id, None)
        return await self.transfer(
            from_address=from_creator_id,
            to_address=to_user_id,
            amount=amount,
            transaction_type=f"refund:{reason}",
            task_id=task_id,
        )

    async def compensate(
        self,
        dispute_id: str,
        from_address: str,
        to_address: str,
        amount: float,
        is_intentional: bool,
    ) -> Transaction:
        intent_str = "intentional" if is_intentional else "non_intentional"
        return await self.transfer(
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            transaction_type=f"compensation:{intent_str}",
            dispute_id=dispute_id,
        )

    async def get_transaction_history(
        self,
        address: str,
        limit: int = 100,
        transaction_type: Optional[str] = None,
    ) -> List[Transaction]:
        transactions = await self.db.get_transactions(address, limit)
        if transaction_type:
            transactions = [
                t for t in transactions if t.type.startswith(transaction_type)
            ]
        return transactions

    async def get_locked_amount(self, user_id: str) -> float:
        return sum(self._locks.values())

    async def get_available_balance(self, user_id: str) -> float:
        total = await self.get_balance(user_id)
        locked = await self.get_locked_amount(user_id)
        return total - locked

    @staticmethod
    def calculate_compensation(
        original_payment: float,
        is_intentional: bool,
        max_multiplier_non_intentional: float = 5.0,
        max_multiplier_intentional: float = 15.0,
    ) -> float:
        if is_intentional:
            return original_payment * max_multiplier_intentional
        return original_payment * max_multiplier_non_intentional


# Backward-compatible alias for older imports
TokenSystem = EscrowLedger
TokenLockedError = FundsLockedError
