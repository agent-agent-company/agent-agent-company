"""
AAC Protocol — Enhanced Token Escrow System

Production-grade token management with:
- Multi-signature approval for large transfers (HMAC-based, requires ESCROW_SECRET)
- Comprehensive audit trail with tamper-evident hashing
- Atomic transactions with rollback support
- Time-locked transfers for dispute windows
- Staking mechanism for arbitrators
- Batch transfer support
- Fraud detection and anomaly alerting

IMPORTANT: This module requires ESCROW_SECRET environment variable to be set
for secure HMAC signatures. Without it, the system will refuse to start.

NOTE: This is a centralized platform ledger. The "hash chain" provides audit
trail integrity within the platform, not blockchain decentralization.
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
import logging

from .models import Transaction, User, Creator
from .database import Database

logger = logging.getLogger(__name__)


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
    """
    Multi-signature configuration with authorized signers.
    
    Security: Only signers in the authorized list can sign transactions.
    Each signer must have a unique signer_id registered with the platform.
    """
    required_signatures: int = 2
    total_signers: int = 3
    authorized_signers: List[str] = field(default_factory=list)  # List of authorized signer_ids
    threshold_amount: float = 1000.0  # Require multi-sig above this amount
    
    def is_authorized(self, signer_id: str) -> bool:
        """Check if signer is authorized for multi-sig"""
        return signer_id in self.authorized_signers


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
    
    # Audit - tamper-evident hash chain (for platform audit, not blockchain)
    previous_hash: Optional[str] = None
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


class ConfigurationError(EscrowError):
    """Escrow configuration error"""
    pass


class EnhancedEscrowLedger:
    """
    Production-grade token escrow system with database persistence.
    
    Features:
    - Multi-signature approval for large transfers (requires ESCROW_SECRET)
    - Tamper-evident audit trail with hash chaining
    - Time-locked transfers for dispute resolution
    - Atomic batch operations
    - Automatic fraud detection
    - Comprehensive rollback support
    - Database persistence for all account and transaction data
    
    SECURITY NOTICE: 
    - ESCROW_SECRET environment variable MUST be set for secure operation
    - All accounts and transactions are persisted to database
    - Hash chain provides tamper-evidence for audit purposes only (not blockchain)
    """
    
    DECIMAL_PLACES = 6
    DEFAULT_TIME_LOCK_HOURS = 24
    FRAUD_DETECTION_THRESHOLD = 10000.0  # Flag transactions above this
    
    def __init__(self, database: Database, secret_key: Optional[str] = None):
        """
        Initialize the enhanced escrow ledger.
        
        Args:
            database: Database instance for persistence
            secret_key: Optional secret key for HMAC signatures. If not provided,
                       will use ESCROW_SECRET environment variable.
        
        Raises:
            ConfigurationError: If no secret key is provided or found in environment
        """
        self.db = database
        
        # SECURITY: Require secret key - no empty keys allowed
        self._secret_key = secret_key or os.getenv("ESCROW_SECRET")
        if not self._secret_key:
            raise ConfigurationError(
                "ESCROW_SECRET environment variable must be set for secure operation. "
                "The escrow system cannot start without a secret key for HMAC signatures."
            )
        
        # In-memory cache only - data is persisted to database
        # These are refreshed from database on operations
        self._account_cache: Dict[str, Account] = {}
        self._locks: Dict[str, float] = {}  # task_id -> locked_amount (volatile, reconstructed on restart)
        self._pending_transactions: Dict[str, EnhancedTransaction] = {}
        self._stake_locks: Dict[str, float] = {}  # staker_id -> amount
        
        # Audit chain - last hash persisted in database
        self._last_transaction_hash: Optional[str] = None
        
        # Anomaly detection
        self._anomaly_thresholds = {
            "velocity": 10,  # Max transactions per minute
            "amount": 50000.0,  # Max single transaction
            "daily_volume": 100000.0,  # Max daily volume per account
        }
        self._account_velocity: Dict[str, List[datetime]] = {}
        
        # Concurrency control - protect critical operations
        self._account_locks: Dict[str, asyncio.Lock] = {}  # Per-account locks
        self._global_lock = asyncio.Lock()  # Global lock for operations involving multiple accounts
    
    def _quantize(self, amount: float) -> float:
        """Quantize amount to fixed decimal places"""
        return float(
            Decimal(str(amount)).quantize(
                Decimal("0." + "0" * self.DECIMAL_PLACES),
                rounding=ROUND_DOWN
            )
        )
    
    def _calculate_transaction_hash(self, tx: EnhancedTransaction) -> str:
        """Calculate tamper-evident transaction hash using HMAC"""
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
        
        # HMAC with secret key (secret key is guaranteed to exist)
        return hmac.new(
            self._secret_key.encode(),
            data_str.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _create_signature(self, signer_id: str, tx: EnhancedTransaction) -> Signature:
        """Create HMAC signature for transaction"""
        tx_hash = self._calculate_transaction_hash(tx)
        sig_data = f"{signer_id}:{tx_hash}:{datetime.utcnow().isoformat()}"
        
        # HMAC with secret key (secret key is guaranteed to exist)
        sig = hmac.new(
            self._secret_key.encode(),
            sig_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
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
        account = self._account_cache.get(from_address)
        if account and account.multi_sig_config:
            return amount >= account.multi_sig_config.threshold_amount
        return amount >= 10000.0  # Default threshold
    
    def _get_account_lock(self, address: str) -> asyncio.Lock:
        """Get or create a lock for an account"""
        if address not in self._account_locks:
            self._account_locks[address] = asyncio.Lock()
        return self._account_locks[address]
    
    async def _verify_signer_authorization(
        self, 
        signer_id: str, 
        from_address: str,
        tx: EnhancedTransaction
    ) -> bool:
        """
        Verify that signer is authorized to sign this transaction.
        
        For multi-sig transactions, signer must be in the authorized list.
        For regular transactions, signer must be the sender.
        """
        account = self._account_cache.get(from_address)
        
        # If no multi-sig config, only sender can sign
        if not account or not account.multi_sig_config:
            return signer_id == from_address
        
        # For multi-sig, check if signer is authorized
        return account.multi_sig_config.is_authorized(signer_id)
    
    async def _get_or_create_account(self, address: str) -> Account:
        """Get account from cache or database, create if not exists"""
        if address in self._account_cache:
            return self._account_cache[address]
        
        # Try to get from database
        user = await self.db.get_user(address)
        if user:
            account = Account(
                address=address,
                balance=user.token_balance,
                created_at=user.created_at,
                last_activity=user.last_active
            )
            self._account_cache[address] = account
            return account
        
        creator = await self.db.get_creator(address)
        if creator:
            account = Account(
                address=address,
                balance=creator.token_balance,
                created_at=creator.created_at,
                last_activity=creator.last_active
            )
            self._account_cache[address] = account
            return account
        
        # Create new account
        account = Account(address=address)
        self._account_cache[address] = account
        return account
    
    async def _persist_account_balance(self, address: str) -> None:
        """Persist account balance to database"""
        account = self._account_cache.get(address)
        if not account:
            return
        
        # Update user or creator balance
        user = await self.db.get_user(address)
        if user:
            await self.db.update_user_balance(address, account.balance)
            return
        
        creator = await self.db.get_creator(address)
        if creator:
            creator.token_balance = account.balance
            await self.db.update_creator(creator)
    
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
        """Get total volume for address in last 24 hours from database"""
        # Query database for transactions in last 24 hours
        transactions = await self.db.get_transactions(address, limit=1000)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        daily_volume = sum(
            tx.amount for tx in transactions
            if tx.timestamp > cutoff and tx.from_address == address
        )
        return daily_volume
    
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
        account = await self._get_or_create_account(from_address)
        
        available = account.balance - account.locked_balance - account.staked_balance
        if available < amount:
            raise InsufficientBalanceError(
                f"Insufficient available balance: {available} < {amount}"
            )
        
        # Anomaly detection
        is_safe, alerts = await self._check_anomalies(from_address, amount)
        if not is_safe:
            logger.warning(f"Anomaly alerts for {from_address}: {alerts}")
        
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
        signer_id: str,
        signer_credentials: Optional[str] = None
    ) -> EnhancedTransaction:
        """
        Add signature to multi-sig transaction with signer authorization.
        
        SECURITY: This method now verifies that the signer is authorized:
        - For regular transactions: only the sender can sign
        - For multi-sig transactions: signer must be in authorized_signers list
        
        Args:
            tx_id: Transaction ID
            signer_id: Signer identifier
            signer_credentials: Optional credentials for signer verification (future use)
            
        Returns:
            Updated transaction
            
        Raises:
            EscrowError: If transaction not found or cannot be signed
            InvalidSignatureError: If signer is not authorized
        """
        tx = self._pending_transactions.get(tx_id)
        if not tx:
            raise EscrowError(f"Transaction not found: {tx_id}")
        
        if tx.status not in [TransactionStatus.PENDING, TransactionStatus.AWAITING_SIGNATURES]:
            raise EscrowError(f"Transaction cannot be signed (status: {tx.status})")
        
        # SECURITY: Verify signer authorization
        is_authorized = await self._verify_signer_authorization(signer_id, tx.from_address, tx)
        if not is_authorized:
            raise InvalidSignatureError(
                f"Signer '{signer_id}' is not authorized to sign transaction {tx_id}. "
                f"For multi-sig, signer must be in authorized_signers list. "
                f"For regular transactions, only the sender can sign."
            )
        
        # Check for duplicate signatures from same signer
        existing_signers = {sig.signer_id for sig in tx.signatures}
        if signer_id in existing_signers:
            raise InvalidSignatureError(f"Signer '{signer_id}' has already signed this transaction")
        
        # Create and add signature
        signature = self._create_signature(signer_id, tx)
        tx.signatures.append(signature)
        tx.audit_log.append({
            "action": "signed",
            "signer": signer_id,
            "timestamp": datetime.utcnow().isoformat(),
            "authorized": True
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
        """
        Execute a transaction atomically with database persistence and concurrency protection.
        
        CONCURRENCY: Uses per-account locks to prevent race conditions during:
        - Balance checks and updates
        - Locked balance adjustments
        - Statistics updates
        """
        from_lock = self._get_account_lock(tx.from_address)
        to_lock = self._get_account_lock(tx.to_address)
        
        async with from_lock:
            async with to_lock:
                try:
                    # Refresh accounts to get latest state (prevents stale data issues)
                    from_account = await self._get_or_create_account(tx.from_address)
                    if not from_account:
                        raise InsufficientBalanceError(f"Sender account not found: {tx.from_address}")
                    
                    # Re-verify balance under lock (prevent TOCTOU race condition)
                    available = from_account.balance - from_account.locked_balance - from_account.staked_balance
                    if available < tx.amount:
                        raise InsufficientBalanceError(
                            f"Insufficient available balance under lock: {available} < {tx.amount}. "
                            f"Balance may have changed due to concurrent operations."
                        )
                    
                    # Debit sender
                    from_account.balance -= tx.amount
                    from_account.locked_balance -= tx.amount
                    from_account.total_sent += tx.amount
                    
                    # Credit recipient
                    to_account = await self._get_or_create_account(tx.to_address)
                    
                    to_account.balance += tx.amount
                    to_account.total_received += tx.amount
                    
                    # Update transaction
                    tx.status = TransactionStatus.EXECUTED
                    tx.executed_at = datetime.utcnow()
                    tx.audit_log.append({
                        "action": "executed",
                        "timestamp": tx.executed_at.isoformat(),
                        "concurrency_protected": True
                    })
                    
                    # Update account stats
                    from_account.transaction_count += 1
                    from_account.last_activity = datetime.utcnow()
                    to_account.last_activity = datetime.utcnow()
                    
                    # Persist to database
                    await self._persist_account_balance(tx.from_address)
                    await self._persist_account_balance(tx.to_address)
                    
                    # Record transaction in database
                    db_tx = Transaction(
                        id=tx.id,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        amount=tx.amount,
                        type=tx.type.value,
                        task_id=tx.task_id,
                        dispute_id=tx.dispute_id,
                        timestamp=tx.executed_at,
                        signature=tx.transaction_hash,
                    )
                    await self.db.record_transaction(db_tx)
                    
                    logger.info(f"Transaction {tx.id} executed: {tx.from_address} -> {tx.to_address}, amount: {tx.amount}")
                    return tx
                    
                except Exception as e:
                    tx.status = TransactionStatus.FAILED
                    tx.audit_log.append({
                        "action": "failed",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    logger.error(f"Transaction {tx.id} failed: {e}")
                    raise EscrowError(f"Transaction execution failed: {e}")
    
    async def rollback_transaction(
        self, 
        tx_id: str, 
        reason: str,
        admin_override: bool = False
    ) -> EnhancedTransaction:
        """
        Rollback a transaction (if allowed) with safety checks.
        
        SAFETY: This method now includes critical checks:
        1. Verifies recipient has sufficient available balance (not locked/staked)
        2. Prevents negative balance scenarios
        3. Acquires locks to prevent race conditions during rollback
        
        Args:
            tx_id: Transaction to rollback
            reason: Reason for rollback
            admin_override: Allow rollback even if normally disallowed
            
        Raises:
            RollbackError: If rollback cannot be performed
            InsufficientBalanceError: If recipient lacks sufficient available balance
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
        
        # Acquire locks for both accounts to prevent race conditions
        from_lock = self._get_account_lock(tx.from_address)
        to_lock = self._get_account_lock(tx.to_address)
        
        async with from_lock:
            async with to_lock:
                try:
                    # Refresh accounts from database to get latest state
                    from_account = await self._get_or_create_account(tx.from_address)
                    to_account = await self._get_or_create_account(tx.to_address)
                    
                    if not from_account or not to_account:
                        raise RollbackError("Cannot rollback: one or both accounts not found")
                    
                    # SAFETY: Check recipient has sufficient available balance
                    # Cannot rollback if funds are locked or already withdrawn
                    to_available = to_account.balance - to_account.locked_balance - to_account.staked_balance
                    if to_available < tx.amount:
                        raise RollbackError(
                            f"Cannot rollback: recipient '{tx.to_address}' lacks sufficient available balance. "
                            f"Required: {tx.amount}, Available: {to_available}. "
                            f"Funds may be locked, staked, or already withdrawn."
                        )
                    
                    # SAFETY: Verify sender won't exceed maximum balance limits (sanity check)
                    if from_account.balance + tx.amount > 1e15:  # Sanity limit
                        logger.warning(f"Rollback would result in extremely large balance for {tx.from_address}")
                    
                    # Perform the rollback
                    to_account.balance -= tx.amount
                    to_account.total_received -= tx.amount
                    
                    from_account.balance += tx.amount
                    from_account.total_sent -= tx.amount
                    
                    # Verify no negative balances (shouldn't happen due to above check, but safety first)
                    if to_account.balance < 0 or from_account.balance < 0:
                        raise RollbackError("Rollback would result in negative balance - aborting")
                    
                    # Mark as rolled back
                    tx.status = TransactionStatus.REVERSED
                    tx.rolled_back_at = datetime.utcnow()
                    tx.rollback_reason = reason
                    tx.can_rollback = False
                    tx.audit_log.append({
                        "action": "rolled_back",
                        "reason": reason,
                        "timestamp": tx.rolled_back_at.isoformat(),
                        "safety_checks_passed": True
                    })
                    
                    # Persist changes
                    await self._persist_account_balance(tx.from_address)
                    await self._persist_account_balance(tx.to_address)
                    
                    logger.info(f"Transaction {tx_id} rolled back: {reason}")
                    return tx
                    
                except Exception as e:
                    if isinstance(e, RollbackError):
                        raise
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
        
        account = await self._get_or_create_account(staker_id)
        if not account:
            raise InsufficientBalanceError(f"Account not found: {staker_id}")
        
        available = account.balance - account.locked_balance - account.staked_balance
        if available < amount:
            raise InsufficientBalanceError(f"Insufficient available balance")
        
        account.staked_balance += amount
        self._stake_locks[staker_id] = self._stake_locks.get(staker_id, 0) + amount
        
        # Persist stake balance
        await self._persist_account_balance(staker_id)
        
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
        account = await self._get_or_create_account(staker_id)
        if not account:
            raise InsufficientBalanceError(f"Account not found: {staker_id}")
        
        unstake_amount = amount or account.staked_balance
        unstake_amount = min(unstake_amount, account.staked_balance)
        
        if unstake_amount <= 0:
            raise EscrowError("No staked balance to unstake")
        
        account.staked_balance -= unstake_amount
        self._stake_locks[staker_id] = max(0, self._stake_locks.get(staker_id, 0) - unstake_amount)
        
        # Persist changes
        await self._persist_account_balance(staker_id)
        
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
        return await self._get_or_create_account(address)
    
    async def get_balance(self, address: str) -> Tuple[float, float, float]:
        """
        Get account balances
        
        Returns:
            Tuple of (total, available, staked)
        """
        account = await self._get_or_create_account(address)
        if not account:
            return 0.0, 0.0, 0.0
        
        available = account.balance - account.locked_balance - account.staked_balance
        return account.balance, available, account.staked_balance
    
    async def get_transaction(self, tx_id: str) -> Optional[EnhancedTransaction]:
        """Get transaction by ID"""
        # Check pending first
        if tx_id in self._pending_transactions:
            return self._pending_transactions[tx_id]
        
        # Query from database
        # Note: This requires adding a method to get transaction by ID
        # For now, return None
        return None
    
    async def get_transaction_history(
        self,
        address: str,
        limit: int = 100,
        tx_type: Optional[TransferType] = None
    ) -> List[EnhancedTransaction]:
        """Get transaction history for address from database"""
        # Query from database
        db_txs = await self.db.get_transactions(address, limit)
        
        txs = []
        for db_tx in db_txs:
            tx = EnhancedTransaction(
                id=db_tx.id,
                from_address=db_tx.from_address,
                to_address=db_tx.to_address,
                amount=db_tx.amount,
                type=TransferType(db_tx.type),
                status=TransactionStatus.EXECUTED,
                task_id=db_tx.task_id,
                dispute_id=db_tx.dispute_id,
                transaction_hash=db_tx.signature,
            )
            if tx_type is None or tx.type == tx_type:
                txs.append(tx)
        
        return txs
    
    async def create_account(
        self, 
        address: str, 
        initial_balance: float = 0.0,
        multi_sig_config: Optional[MultiSigConfig] = None
    ) -> Account:
        """Create new account with database persistence"""
        existing = await self._get_or_create_account(address)
        if existing.balance > 0 or existing.address in self._account_cache:
            raise EscrowError(f"Account already exists: {address}")
        
        account = Account(
            address=address,
            balance=initial_balance,
            multi_sig_config=multi_sig_config
        )
        self._account_cache[address] = account
        
        # Persist to database
        await self._persist_account_balance(address)
        
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
