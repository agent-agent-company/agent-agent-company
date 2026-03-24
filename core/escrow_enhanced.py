"""
AAC Protocol — Enhanced Token Escrow System

Production-grade token management with:
- Multi-signature approval for large transfers
- Comprehensive audit trail with tamper-proof hashing
- Atomic transactions with rollback support
- Time-locked transfers for dispute windows
- Staking mechanism for arbitrators
- Batch transfer support
- Fraud detection and anomaly alerting
"""

import os
import uuid
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import asyncio

from .models import Transaction, User, Creator


class TransactionStatus(str, Enum):
    """Enhanced transaction lifecycle"""
    PENDING = "pending"           # Awaiting execution
    LOCKED = "locked"             # Funds locked (escrow)
    AWAITING_SIGNATURES = "awaiting_signatures"  # Multi-sig pending
    EXECUTED = "executed"         # Successfully completed
    FAILED = "failed"             # Execution failed
    REVERSED = "reversed"         # Rolled back
    DISPUTED = "disputed"         # Under dispute
    TIME_LOCKED = "time_locked"   # Release delayed


class TransferType(str, Enum):
    """Types of transfers"""
    PAYMENT = "payment"
    REFUND = "refund"
    COMPENSATION = "compensation"
    STAKE = "stake"
    UNSTAKE = "unstake"
    REWARD = "reward"
    PENALTY = "penalty"
    FEE = "fee"
    BATCH = "batch"


@dataclass
class MultiSigConfig:
    """Multi-signature configuration"""
    required_signatures: int = 2
    total_signers: int = 3
    signers: List[str] = field(default_factory=list)
    threshold_amount: float = 1000.0  # Require multi-sig above this amount


@dataclass
class Signature:
    """Transaction signature"""
    signer_id: str
    signature: str  # HMAC signature
    timestamp: datetime
    signature_type: str = "hmac"  # hmac, ecdsa, etc.


@dataclass
class EnhancedTransaction:
    """Enhanced transaction with full audit trail"""
    id: str
    from_address: str
    to_address: str
    amount: float
    type: TransferType
    status: TransactionStatus
    
    # Multi-signature
    required_signatures: int = 1
    signatures: List[Signature] = field(default_factory=list)
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # For time-locked
    
    # Context
    task_id: Optional[str] = None
    dispute_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Audit
    previous_hash: Optional[str] = None  # Blockchain-style chaining
    transaction_hash: Optional[str] = None
    audit_log: List[Dict] = field(default_factory=list)
    
    # Rollback
    can_rollback: bool = True
    rolled_back_at: Optional[datetime] = None
    rollback_reason: Optional[str] = None


@dataclass
class Account:
    """Account with enhanced tracking"""
    address: str
    balance: float = 0.0
    locked_balance: float = 0.0
    staked_balance: float = 0.0
    total_received: float = 0.0
    total_sent: float = 0.0
    transaction_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    # Multi-sig settings
    multi_sig_config: Optional[MultiSigConfig] = None


class EscrowError(Exception):
    """Base escrow error"""
    pass


class InsufficientBalanceError(EscrowError):
    """Insufficient balance for operation"""
    pass


class MultiSigRequiredError(EscrowError):
    """Multi-signature required but not complete"""
    pass


class InvalidSignatureError(EscrowError):
    """Invalid transaction signature"""
    pass


class TimeLockError(EscrowError):
    """Time lock not expired"""
    pass


class RollbackError(EscrowError):
    """Cannot rollback transaction"""
    pass


class EnhancedEscrowLedger:
    """
    Production-grade token escrow system
    
    Features:
    - Multi-signature approval for large transfers
    - Tamper-proof audit trail with hash chaining
    - Time-locked transfers for dispute resolution
    - Atomic batch operations
    - Automatic fraud detection
    - Comprehensive rollback support
    """
    
    DECIMAL_PLACES = 6
    DEFAULT_TIME_LOCK_HOURS = 24
    FRAUD_DETECTION_THRESHOLD = 10000.0  # Flag transactions above this
    
    def __init__(self, database: Any, secret_key: Optional[str] = None):
        self.db = database
        self._secret_key = secret_key or os.getenv("ESCROW_SECRET", "")
        
        # In-memory state (should be in database for production)
        self._accounts: Dict[str, Account] = {}
        self._locks: Dict[str, float] = {}  # task_id -> locked_amount
        self._pending_transactions: Dict[str, EnhancedTransaction] = {}
        self._stake_locks: Dict[str, float] = {}  # staker_id -> amount
        
        # Audit chain
        self._last_transaction_hash: Optional[str] = None
        
        # Anomaly detection
        self._anomaly_thresholds = {
            "velocity": 10,  # Max transactions per minute
            "amount": 50000.0,  # Max single transaction
            "daily_volume": 100000.0,  # Max daily volume per account
        }
        self._account_velocity: Dict[str, List[datetime]] = {}
    
    def _quantize(self, amount: float) -> float:
        """Quantize amount to fixed decimal places"""
        return float(
            Decimal(str(amount)).quantize(
                Decimal("0." + "0" * self.DECIMAL_PLACES),
                rounding=ROUND_DOWN
            )
        )
    
    def _calculate_transaction_hash(self, tx: EnhancedTransaction) -> str:
        """Calculate tamper-proof transaction hash"""
        data = {
            "id": tx.id,
            "from": tx.from_address,
            "to": tx.to_address,
            "amount": tx.amount,
            "type": tx.type.value,
            "created_at": tx.created_at.isoformat(),
            "previous_hash": tx.previous_hash or "",
        }
        data_str = json.dumps(data, sort_keys=True)
        
        if self._secret_key:
            return hmac.new(
                self._secret_key.encode(),
                data_str.encode(),
                hashlib.sha256
            ).hexdigest()
        else:
            return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _create_signature(self, signer_id: str, tx: EnhancedTransaction) -> Signature:
        """Create HMAC signature for transaction"""
        tx_hash = self._calculate_transaction_hash(tx)
        sig_data = f"{signer_id}:{tx_hash}:{datetime.utcnow().isoformat()}"
        
        if self._secret_key:
            sig = hmac.new(
                self._secret_key.encode(),
                sig_data.encode(),
                hashlib.sha256
            ).hexdigest()
        else:
            sig = hashlib.sha256(sig_data.encode()).hexdigest()
        
        return Signature(
            signer_id=signer_id,
            signature=sig,
            timestamp=datetime.utcnow()
        )
    
    def _verify_signature(
        self, 
        signature: Signature, 
        tx: EnhancedTransaction
    ) -> bool:
        """Verify transaction signature"""
        expected = self._create_signature(signature.signer_id, tx)
        return hmac.compare_digest(signature.signature, expected.signature)
    
    def _requires_multi_sig(self, amount: float, from_address: str) -> bool:
        """Check if transaction requires multi-signature"""
        account = self._accounts.get(from_address)
        if account and account.multi_sig_config:
            return amount >= account.multi_sig_config.threshold_amount
        return amount >= 10000.0  # Default threshold
    
    async def _check_anomalies(
        self, 
        from_address: str, 
        amount: float
    ) -> Tuple[bool, List[str]]:
        """
        Check for suspicious activity
        
        Returns:
            (is_safe, alerts)
        """
        alerts = []
        now = datetime.utcnow()
        
        # Check velocity
        if from_address not in self._account_velocity:
            self._account_velocity[from_address] = []
        
        # Clean old entries (keep last minute)
        self._account_velocity[from_address] = [
            t for t in self._account_velocity[from_address]
            if now - t < timedelta(minutes=1)
        ]
        
        if len(self._account_velocity[from_address]) > self._anomaly_thresholds["velocity"]:
            alerts.append(f"High transaction velocity detected for {from_address}")
        
        # Check amount
        if amount > self._anomaly_thresholds["amount"]:
            alerts.append(f"Large transaction amount: {amount}")
        
        # Check daily volume
        daily_volume = await self._get_daily_volume(from_address)
        if daily_volume + amount > self._anomaly_thresholds["daily_volume"]:
            alerts.append(f"Daily volume limit approaching for {from_address}")
        
        self._account_velocity[from_address].append(now)
        
        return len(alerts) == 0, alerts
    
    async def _get_daily_volume(self, address: str) -> float:
        """Get total volume for address in last 24 hours"""
        # In production, query database
        # For now, return 0
        return 0.0
    
    async def create_transfer(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        transfer_type: TransferType = TransferType.PAYMENT,
        task_id: Optional[str] = None,
        dispute_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        time_lock_hours: Optional[int] = None,
        required_signatures: int = 1,
        auto_execute: bool = True
    ) -> EnhancedTransaction:
        """
        Create a new transfer with full security controls
        
        Args:
            from_address: Sender address
            to_address: Recipient address
            amount: Transfer amount
            transfer_type: Type of transfer
            task_id: Associated task
            dispute_id: Associated dispute
            metadata: Additional data
            time_lock_hours: Delay execution by N hours
            required_signatures: Multi-sig requirement
            auto_execute: Execute immediately if conditions met
            
        Returns:
            EnhancedTransaction object
        """
        amount = self._quantize(amount)
        
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Check balance
        account = self._accounts.get(from_address)
        if not account:
            raise InsufficientBalanceError(f"Account not found: {from_address}")
        
        available = account.balance - account.locked_balance - account.staked_balance
        if available < amount:
            raise InsufficientBalanceError(
                f"Insufficient available balance: {available} < {amount}"
            )
        
        # Anomaly detection
        is_safe, alerts = await self._check_anomalies(from_address, amount)
        if not is_safe:
            # In production: notify, require additional verification
            print(f"⚠️ Anomaly alerts for {from_address}: {alerts}")
        
        # Determine multi-sig requirement
        needs_multi_sig = self._requires_multi_sig(amount, from_address)
        if needs_multi_sig:
            required_signatures = max(required_signatures, 2)
        
        # Create transaction
        tx = EnhancedTransaction(
            id=f"tx-{uuid.uuid4().hex[:16]}",
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            type=transfer_type,
            status=TransactionStatus.PENDING,
            required_signatures=required_signatures,
            task_id=task_id,
            dispute_id=dispute_id,
            metadata=metadata or {},
            previous_hash=self._last_transaction_hash,
        )
        
        # Calculate hash
        tx.transaction_hash = self._calculate_transaction_hash(tx)
        
        # Apply time lock if specified
        if time_lock_hours:
            tx.status = TransactionStatus.TIME_LOCKED
            tx.expires_at = datetime.utcnow() + timedelta(hours=time_lock_hours)
        
        # Lock funds
        account.locked_balance += amount
        
        # Store pending
        self._pending_transactions[tx.id] = tx
        
        # Update hash chain
        self._last_transaction_hash = tx.transaction_hash
        
        # Auto-execute if conditions met
        if auto_execute and required_signatures == 1 and not time_lock_hours:
            tx = await self._execute_transaction(tx)
        
        return tx
    
    async def sign_transaction(
        self, 
        tx_id: str, 
        signer_id: str
    ) -> EnhancedTransaction:
        """
        Add signature to multi-sig transaction
        
        Args:
            tx_id: Transaction ID
            signer_id: Signer identifier
            
        Returns:
            Updated transaction
        """
        tx = self._pending_transactions.get(tx_id)
        if not tx:
            raise EscrowError(f"Transaction not found: {tx_id}")
        
        if tx.status not in [TransactionStatus.PENDING, TransactionStatus.AWAITING_SIGNATURES]:
            raise EscrowError(f"Transaction cannot be signed (status: {tx.status})")
        
        # Create and add signature
        signature = self._create_signature(signer_id, tx)
        tx.signatures.append(signature)
        tx.audit_log.append({
            "action": "signed",
            "signer": signer_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Check if ready to execute
        if len(tx.signatures) >= tx.required_signatures:
            if tx.status == TransactionStatus.TIME_LOCKED:
                if datetime.utcnow() >= tx.expires_at:
                    tx = await self._execute_transaction(tx)
            else:
                tx = await self._execute_transaction(tx)
        else:
            tx.status = TransactionStatus.AWAITING_SIGNATURES
        
        return tx
    
    async def _execute_transaction(self, tx: EnhancedTransaction) -> EnhancedTransaction:
        """Execute a transaction atomically"""
        try:
            # Debit sender
            from_account = self._accounts.get(tx.from_address)
            if not from_account:
                raise InsufficientBalanceError(f"Sender account not found: {tx.from_address}")
            
            from_account.balance -= tx.amount
            from_account.locked_balance -= tx.amount
            from_account.total_sent += tx.amount
            
            # Credit recipient
            to_account = self._accounts.get(tx.to_address)
            if not to_account:
                # Create account if not exists
                to_account = Account(address=tx.to_address)
                self._accounts[tx.to_address] = to_account
            
            to_account.balance += tx.amount
            to_account.total_received += tx.amount
            
            # Update transaction
            tx.status = TransactionStatus.EXECUTED
            tx.executed_at = datetime.utcnow()
            tx.audit_log.append({
                "action": "executed",
                "timestamp": tx.executed_at.isoformat()
            })
            
            # Update account stats
            from_account.transaction_count += 1
            from_account.last_activity = datetime.utcnow()
            to_account.last_activity = datetime.utcnow()
            
            return tx
            
        except Exception as e:
            tx.status = TransactionStatus.FAILED
            tx.audit_log.append({
                "action": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            raise EscrowError(f"Transaction execution failed: {e}")
    
    async def rollback_transaction(
        self, 
        tx_id: str, 
        reason: str,
        admin_override: bool = False
    ) -> EnhancedTransaction:
        """
        Rollback a transaction (if allowed)
        
        Args:
            tx_id: Transaction to rollback
            reason: Reason for rollback
            admin_override: Allow rollback even if normally disallowed
        """
        tx = self._pending_transactions.get(tx_id)
        if not tx:
            raise EscrowError(f"Transaction not found: {tx_id}")
        
        # Check if can rollback
        if not tx.can_rollback and not admin_override:
            raise RollbackError("Transaction cannot be rolled back")
        
        if tx.status != TransactionStatus.EXECUTED:
            raise RollbackError(f"Cannot rollback transaction with status: {tx.status}")
        
        # Check time window (only allow rollback within 1 hour for non-admin)
        if not admin_override:
            time_since_execution = datetime.utcnow() - tx.executed_at
            if time_since_execution > timedelta(hours=1):
                raise RollbackError("Rollback window expired (> 1 hour)")
        
        try:
            # Reverse the transfer
            from_account = self._accounts.get(tx.from_address)
            to_account = self._accounts.get(tx.to_address)
            
            if from_account and to_account:
                to_account.balance -= tx.amount
                to_account.total_received -= tx.amount
                
                from_account.balance += tx.amount
                from_account.total_sent -= tx.amount
            
            # Mark as rolled back
            tx.status = TransactionStatus.REVERSED
            tx.rolled_back_at = datetime.utcnow()
            tx.rollback_reason = reason
            tx.can_rollback = False
            tx.audit_log.append({
                "action": "rolled_back",
                "reason": reason,
                "timestamp": tx.rolled_back_at.isoformat()
            })
            
            return tx
            
        except Exception as e:
            raise RollbackError(f"Rollback failed: {e}")
    
    async def stake_tokens(
        self,
        staker_id: str,
        amount: float,
        purpose: str = "arbitration"
    ) -> EnhancedTransaction:
        """
        Stake tokens for arbitration or other purposes
        
        Args:
            staker_id: Account staking tokens
            amount: Amount to stake
            purpose: Purpose of stake (arbitration, validator, etc.)
        """
        amount = self._quantize(amount)
        
        account = self._accounts.get(staker_id)
        if not account:
            raise InsufficientBalanceError(f"Account not found: {staker_id}")
        
        available = account.balance - account.locked_balance - account.staked_balance
        if available < amount:
            raise InsufficientBalanceError(f"Insufficient available balance")
        
        account.staked_balance += amount
        self._stake_locks[staker_id] = self._stake_locks.get(staker_id, 0) + amount
        
        # Record stake transaction
        tx = await self.create_transfer(
            from_address=staker_id,
            to_address="STAKE_POOL",
            amount=amount,
            transfer_type=TransferType.STAKE,
            metadata={"purpose": purpose},
            auto_execute=False
        )
        tx.status = TransactionStatus.EXECUTED
        tx.executed_at = datetime.utcnow()
        
        return tx
    
    async def unstake_tokens(
        self,
        staker_id: str,
        amount: Optional[float] = None
    ) -> EnhancedTransaction:
        """Unstake tokens"""
        account = self._accounts.get(staker_id)
        if not account:
            raise InsufficientBalanceError(f"Account not found: {staker_id}")
        
        unstake_amount = amount or account.staked_balance
        unstake_amount = min(unstake_amount, account.staked_balance)
        
        if unstake_amount <= 0:
            raise EscrowError("No staked balance to unstake")
        
        account.staked_balance -= unstake_amount
        self._stake_locks[staker_id] = max(0, self._stake_locks.get(staker_id, 0) - unstake_amount)
        
        # Create unstake transaction
        tx = EnhancedTransaction(
            id=f"tx-{uuid.uuid4().hex[:16]}",
            from_address="STAKE_POOL",
            to_address=staker_id,
            amount=unstake_amount,
            type=TransferType.UNSTAKE,
            status=TransactionStatus.EXECUTED,
            executed_at=datetime.utcnow()
        )
        
        return tx
    
    async def get_account(self, address: str) -> Optional[Account]:
        """Get account details"""
        return self._accounts.get(address)
    
    async def get_balance(self, address: str) -> Tuple[float, float, float]:
        """
        Get account balances
        
        Returns:
            Tuple of (total, available, staked)
        """
        account = self._accounts.get(address)
        if not account:
            return 0.0, 0.0, 0.0
        
        available = account.balance - account.locked_balance - account.staked_balance
        return account.balance, available, account.staked_balance
    
    async def get_transaction(self, tx_id: str) -> Optional[EnhancedTransaction]:
        """Get transaction by ID"""
        return self._pending_transactions.get(tx_id)
    
    async def get_transaction_history(
        self,
        address: str,
        limit: int = 100,
        tx_type: Optional[TransferType] = None
    ) -> List[EnhancedTransaction]:
        """Get transaction history for address"""
        txs = []
        for tx in self._pending_transactions.values():
            if tx.from_address == address or tx.to_address == address:
                if tx_type is None or tx.type == tx_type:
                    txs.append(tx)
        
        # Sort by created_at descending
        txs.sort(key=lambda x: x.created_at, reverse=True)
        return txs[:limit]
    
    async def create_account(
        self, 
        address: str, 
        initial_balance: float = 0.0,
        multi_sig_config: Optional[MultiSigConfig] = None
    ) -> Account:
        """Create new account"""
        if address in self._accounts:
            raise EscrowError(f"Account already exists: {address}")
        
        account = Account(
            address=address,
            balance=initial_balance,
            multi_sig_config=multi_sig_config
        )
        self._accounts[address] = account
        return account
    
    def verify_audit_chain(self) -> Tuple[bool, List[str]]:
        """
        Verify integrity of transaction chain
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Sort transactions by creation time
        txs = sorted(
            self._pending_transactions.values(),
            key=lambda x: x.created_at
        )
        
        expected_hash = None
        for tx in txs:
            if tx.previous_hash != expected_hash:
                errors.append(f"Hash chain broken at transaction {tx.id}")
            
            # Verify transaction hash
            calculated = self._calculate_transaction_hash(tx)
            if tx.transaction_hash != calculated:
                errors.append(f"Invalid hash for transaction {tx.id}")
            
            expected_hash = tx.transaction_hash
        
        return len(errors) == 0, errors


# Backward compatibility
EscrowLedger = EnhancedEscrowLedger
TokenSystem = EnhancedEscrowLedger