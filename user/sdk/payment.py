"""
AAC Protocol User SDK - Payment Client

Client for balances, escrow, and ledger history.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import httpx

from ...core.models import Transaction, User, Creator, PaymentStatus
from ...core.database import Database
from ...core.escrow import EscrowLedger


class PaymentError(Exception):
    """Payment operation error"""
    pass


class PaymentClient:
    """
    User-facing payments and balance helpers (platform ledger).
    """
    
    def __init__(
        self,
        database: Database,
        ledger: EscrowLedger,
        server_url: str = "http://localhost:8000"
    ):
        self.db = database
        self.ledger = ledger
        self._client = httpx.AsyncClient(base_url=server_url, timeout=30.0)
    
    async def get_balance(self, address: str) -> float:
        """
        Get account balance (platform billing units).
        """
        return await self.ledger.get_balance(address)
    
    async def get_available_balance(self, user_id: str) -> float:
        """
        Get available (non-locked) balance
        
        Args:
            user_id: User ID
            
        Returns:
            Available balance
        """
        return await self.ledger.get_available_balance(user_id)
    
    async def get_transaction_history(
        self,
        address: str,
        limit: int = 50,
        transaction_type: Optional[str] = None
    ) -> List[Transaction]:
        """
        Get transaction history
        
        Args:
            address: User or Creator ID
            limit: Maximum transactions
            transaction_type: Filter by type
            
        Returns:
            List of transactions
        """
        return await self.ledger.get_transaction_history(
            address, limit, transaction_type
        )
    
    async def get_spending_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get spending summary for user
        
        Args:
            user_id: User ID
            
        Returns:
            Summary dictionary
        """
        user = await self.db.get_user(user_id)
        if not user:
            raise PaymentError(f"User not found: {user_id}")
        
        transactions = await self.get_transaction_history(user_id, limit=1000)
        
        # Calculate statistics
        total_spent = sum(
            t.amount for t in transactions
            if t.from_address == user_id and t.type == "payment"
        )
        total_received = sum(
            t.amount for t in transactions
            if t.to_address == user_id
        )
        
        payment_count = len([t for t in transactions if t.type == "payment"])
        refund_count = len([t for t in transactions if t.type.startswith("refund")])
        
        return {
            "current_balance": user.token_balance,
            "available_balance": await self.get_available_balance(user_id),
            "total_spent": total_spent,
            "total_received": total_received,
            "net_flow": total_received - total_spent,
            "payment_count": payment_count,
            "refund_count": refund_count,
            "transaction_count": len(transactions),
        }
    
    async def get_earnings_summary(self, creator_id: str) -> Dict[str, Any]:
        """
        Get earnings summary for creator
        
        Args:
            creator_id: Creator ID
            
        Returns:
            Summary dictionary
        """
        creator = await self.db.get_creator(creator_id)
        if not creator:
            raise PaymentError(f"Creator not found: {creator_id}")
        
        transactions = await self.get_transaction_history(creator_id, limit=1000)
        
        # Calculate earnings
        total_earnings = sum(
            t.amount for t in transactions
            if t.to_address == creator_id and t.type == "payment"
        )
        total_compensation_paid = sum(
            t.amount for t in transactions
            if t.from_address == creator_id and t.type.startswith("compensation")
        )
        
        return {
            "current_balance": creator.token_balance,
            "total_earned": total_earnings,
            "total_compensation_paid": total_compensation_paid,
            "net_earnings": total_earnings - total_compensation_paid,
            "task_count": len([t for t in transactions if t.type == "payment"]),
            "dispute_count": len([t for t in transactions if t.dispute_id]),
        }
    
    async def transfer(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        memo: Optional[str] = None
    ) -> Transaction:
        """
        Transfer between platform accounts (admin / settlement use cases).
        """
        return await self.ledger.transfer(
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            transaction_type="transfer",
        )
    
    async def close(self):
        """Close client connection"""
        await self._client.aclose()


class PaymentMonitor:
    """
    Monitor for payment events and notifications
    
    Tracks payment status changes and provides callbacks.
    """
    
    def __init__(self, database: Database):
        self.db = database
        self._callbacks: Dict[str, list] = {
            "payment_completed": [],
            "refund_issued": [],
            "compensation_paid": [],
        }
    
    def on_payment_completed(self, callback: callable):
        """Register callback for completed payments"""
        self._callbacks["payment_completed"].append(callback)
    
    def on_refund_issued(self, callback: callable):
        """Register callback for refunds"""
        self._callbacks["refund_issued"].append(callback)
    
    def on_compensation_paid(self, callback: callable):
        """Register callback for compensation payments"""
        self._callbacks["compensation_paid"].append(callback)
    
    async def _trigger(self, event: str, data: Dict[str, Any]):
        """Trigger event callbacks"""
        for callback in self._callbacks.get(event, []):
            try:
                await callback(data)
            except Exception:
                pass  # Log error but don't stop other callbacks
